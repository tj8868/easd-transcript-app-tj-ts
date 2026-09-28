"""
EASD STT pipeline (v8.3)
========================

Robust multi-chunk speech-to-text for long recordings.

Guarantees
----------
* Every chunk is attempted with:  Gemini (retry + backoff)  ->  Gemini prompt-mode
  fallback model  ->  Local Whisper (only if usable).
* Nothing is ever silently dropped or fabricated. Each chunk ends as
  ``ok`` or ``failed`` with a concrete, human-readable reason.
* The combined transcript keeps every successful chunk. Failed ranges are marked
  inline with a ``TRANSCRIPT GAP`` line so the UI and the summariser both see them.
* Overall status: ``success`` (all chunks ok), ``partial`` (some failed),
  ``error`` (nothing transcribed).
* Timestamps are shifted by the REAL cumulative chunk durations (not index*600).

Public API
----------
    transcribe_chunks(chunks, chunk_durations=None, provider="gemini", api_key="",
                      model_name="", language="auto", mime_type="audio/mp3") -> dict
    gemini_transcribe_bytes(audio_bytes, api_key, model_name, mime_type, ctx) -> dict
    whisper_transcribe_bytes(audio_bytes, language, mime_type, ctx) -> dict
"""

from __future__ import annotations

import contextvars
import os
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from diag_logging import describe_exception, fmt_ts, get_logger, redact_key

log = get_logger("stt")

# ---------------------------------------------------------------------------
# Tunables (env-overridable)
# ---------------------------------------------------------------------------
GEMINI_TRANSCRIBE_MODEL = os.environ.get("EASD_GEMINI_STT_MODEL", "gemini-3.5-transcribe")
GEMINI_PROMPT_FALLBACK_MODELS = [
    m.strip() for m in os.environ.get("EASD_GEMINI_STT_FALLBACK_MODELS", "gemini-2.5-flash").split(",") if m.strip()
]
GEMINI_MAX_PARALLEL = max(1, int(os.environ.get("EASD_GEMINI_MAX_PARALLEL", "2")))
GEMINI_STAGGER_SEC = float(os.environ.get("EASD_GEMINI_STAGGER_SEC", "1.5"))
GEMINI_MAX_ATTEMPTS = max(1, int(os.environ.get("EASD_GEMINI_MAX_ATTEMPTS", "4")))
GEMINI_BACKOFF_BASE_SEC = float(os.environ.get("EASD_GEMINI_BACKOFF_BASE_SEC", "4"))
GEMINI_BACKOFF_MAX_SEC = float(os.environ.get("EASD_GEMINI_BACKOFF_MAX_SEC", "60"))
GEMINI_HTTP_TIMEOUT_MS = int(os.environ.get("EASD_GEMINI_HTTP_TIMEOUT_MS", str(10 * 60 * 1000)))
# Gemini inline request limit is 20 MB total; base64 inflates by 4/3.
GEMINI_INLINE_MAX_BYTES = int(os.environ.get("EASD_GEMINI_INLINE_MAX_BYTES", str(14 * 1024 * 1024)))

GAP_MARKER = "TRANSCRIPT GAP"

_RETRYABLE_HTTP = {408, 429, 500, 502, 503, 504}
_gemini_semaphore = threading.BoundedSemaphore(GEMINI_MAX_PARALLEL)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _http_code(e: BaseException) -> Optional[int]:
    for attr in ("code", "status_code"):
        v = getattr(e, attr, None)
        if isinstance(v, int):
            return v
    resp = getattr(e, "response", None)
    v = getattr(resp, "status_code", None) if resp is not None else None
    return v if isinstance(v, int) else None


def _is_retryable(e: BaseException) -> bool:
    code = _http_code(e)
    if code is not None:
        return code in _RETRYABLE_HTTP
    name = type(e).__name__.lower()
    text = str(e).lower()
    transient_words = ("timeout", "timed out", "connection", "temporarily", "unavailable",
                       "reset by peer", "remote end closed", "eof occurred", "resource_exhausted")
    return any(w in name or w in text for w in transient_words)


def _retry_delay_hint(e: BaseException) -> Optional[float]:
    """Honour a server-provided RetryInfo delay like 'retryDelay': '27s'."""
    m = re.search(r"retry[_ ]?delay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", str(getattr(e, "details", "")) + str(e), re.I)
    return float(m.group(1)) if m else None


def _short_reason(e: BaseException) -> str:
    code = _http_code(e)
    status = getattr(e, "status", None)
    msg = getattr(e, "message", None) or str(e)
    msg = re.sub(r"\s+", " ", str(msg)).strip()
    if len(msg) > 220:
        msg = msg[:217] + "..."
    head = f"HTTP {code}" if code else type(e).__name__
    if status and str(status) not in msg:
        head += f" {status}"
    return f"{head}: {msg}"


def _friendly(reason: str) -> str:
    """
    Translate a raw error into a short message a user can act on.
    Only the HTTP status is kept for recognised categories; exception class names,
    file paths and response bodies stay in app_service.log (logged by the caller).
    """
    r = reason.lower()
    head = reason.split(":", 1)[0].strip() if reason.startswith("HTTP ") else ""
    tag = f" ({head})" if head else ""
    if any(w in r for w in ("proxyerror", "connecterror", "connecttimeout", "name resolution", "getaddrinfo",
                            "ssl", "network is unreachable", "connection refused", "remoteprotocolerror")):
        return "Cannot reach the Gemini service - check the internet connection, proxy or firewall"
    if "429" in r or "resource_exhausted" in r or "quota" in r:
        return f"Gemini rate limit / quota exceeded{tag}"
    if "401" in r or "403" in r or "api key" in r or "permission" in r:
        return f"Gemini API key rejected - check the key in Settings{tag}"
    if "404" in r or "not found" in r:
        return f"Gemini model not available for this key{tag}"
    if "payload" in r and "size" in r:
        return f"Audio chunk too large for Gemini{tag}"
    if "timeout" in r or "timed out" in r:
        return "Gemini did not answer in time"
    if r.startswith("empty response"):
        fr = re.search(r"finish_reason=([A-Za-z_.]+)", reason)
        return f"Gemini returned no transcript (finish_reason={fr.group(1) if fr else 'unknown'})"
    if reason.startswith("HTTP "):
        return reason if len(reason) <= 160 else reason[:157] + "..."
    return "Gemini request failed unexpectedly (details in app_service.log)"


def _parse_offset_seconds(v: Any) -> Optional[float]:
    if v is None:
        return None
    if hasattr(v, "total_seconds"):
        try:
            return float(v.total_seconds())
        except Exception:
            return None
    s = str(v).strip()
    try:
        return float(s.rstrip("s"))
    except ValueError:
        pass
    m = re.match(r"^(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)$", s)
    if m:
        h = int(m.group(1) or 0)
        return h * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return None


def format_ts(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"[{h:02d}:{m:02d}:{s:02d}]" if h else f"[{m:02d}:{s:02d}]"


_TS_RE = re.compile(r"^\[(\d{1,3}):(\d{2})(?::(\d{2}))?\]")


def shift_line_timestamp(line: str, offset_sec: float) -> str:
    """Shift ONLY the leading [MM:SS]/[HH:MM:SS] of a line (never text inside speech)."""
    m = _TS_RE.match(line)
    if not m or offset_sec <= 0:
        return line
    if m.group(3) is not None:
        total = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    else:
        total = int(m.group(1)) * 60 + int(m.group(2))
    return format_ts(total + offset_sec) + line[m.end():]


def clamp_line_timestamp(line: str, max_sec: float) -> str:
    """Guard against model timestamps that run past the end of the chunk (would misalign the next chunk)."""
    m = _TS_RE.match(line)
    if not m:
        return line
    if m.group(3) is not None:
        total = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    else:
        total = int(m.group(1)) * 60 + int(m.group(2))
    if total <= max_sec:
        return line
    return format_ts(max(0, int(max_sec) - 1)) + line[m.end():]


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
_PROMPT_TRANSCRIBE = (
    "You are a verbatim meeting transcriptionist. Transcribe the ENTIRE audio from start to end.\n"
    "Rules:\n"
    "1. Output one line per utterance in exactly this format: [MM:SS] Speaker N: <text>\n"
    "   where [MM:SS] is the start time from the beginning of THIS audio and N is 1, 2, 3...\n"
    "2. Keep Bengali speech in Bengali script (বাংলা) and English speech in English. Preserve code-switching.\n"
    "3. Never translate, summarise, or invent words. Skip silence. Output ONLY transcript lines."
)


def _gemini_client(api_key: str):
    from google import genai
    from google.genai import types
    try:
        return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=GEMINI_HTTP_TIMEOUT_MS))
    except Exception:
        return genai.Client(api_key=api_key)


def _response_diag(resp: Any) -> str:
    try:
        cands = getattr(resp, "candidates", None) or []
        c0 = cands[0] if cands else None
        return (f"candidates={len(cands)} finish_reason={getattr(c0, 'finish_reason', None)} "
                f"prompt_feedback={getattr(resp, 'prompt_feedback', None)}")
    except Exception:
        return "unreadable response"


def _lines_from_transcribe_response(resp: Any) -> List[str]:
    lines: List[str] = []
    speaker_map: Dict[str, int] = {}
    cands = getattr(resp, "candidates", None) or []
    if not cands or not getattr(cands[0], "content", None):
        return lines
    for p in (cands[0].content.parts or []):
        at = getattr(p, "audio_transcription", None)
        if at:
            txt = (getattr(at, "text", "") or "").strip()
            if not txt:
                continue
            label = str(getattr(at, "speaker_label", "") or "spk_1")
            if label not in speaker_map:
                speaker_map[label] = len(speaker_map) + 1  # stable per-chunk numbering
            sec = None
            words = getattr(at, "words", None) or []
            if words:
                sec = _parse_offset_seconds(getattr(words[0], "start_offset", None))
            lines.append(f"{format_ts(sec or 0)} Speaker {speaker_map[label]}: {txt}")
        elif getattr(p, "text", None) and not getattr(p, "thought", False):
            lines.extend(_normalise_prompt_lines(p.text))
    return lines


def _normalise_prompt_lines(text: str) -> List[str]:
    out = []
    for raw in (text or "").splitlines():
        s = raw.strip().strip("`").strip()
        if not s:
            continue
        s = re.sub(r"^\*+|\*+$", "", s).strip()
        if _TS_RE.match(s):
            out.append(s)
        elif out:
            out[-1] = f"{out[-1]} {s}"  # continuation of previous utterance
        else:
            out.append(f"[00:00] Speaker 1: {s}")
    return out


def _gemini_call_once(client, model: str, audio: bytes, mime: str, prompt_mode: bool):
    from google.genai import types
    part = types.Part.from_bytes(data=audio, mime_type=mime)
    if prompt_mode:
        cfg = types.GenerateContentConfig(temperature=0.0, max_output_tokens=65536)
        return client.models.generate_content(model=model, contents=[_PROMPT_TRANSCRIBE, part], config=cfg)
    cfg = types.GenerateContentConfig(
        audio_transcription_config=types.AudioTranscriptionConfig(mode="VERBATIM", diarization=True, word_timestamp=True)
    )
    return client.models.generate_content(model=model, contents=[part], config=cfg)


def gemini_transcribe_bytes(audio: bytes, api_key: str, model_name: str = "", mime_type: str = "audio/mp3",
                            ctx: str = "[gemini]") -> Dict[str, Any]:
    """Returns {ok, text, provider, model, attempts, error}. Never raises."""
    attempts: List[str] = []
    if not api_key:
        return {"ok": False, "text": "", "provider": "gemini", "attempts": attempts,
                "error": "No Gemini API key configured (add it in Settings)"}
    if len(audio) > GEMINI_INLINE_MAX_BYTES:
        return {"ok": False, "text": "", "provider": "gemini", "attempts": attempts,
                "error": f"Audio chunk is {len(audio)/1048576:.1f} MB, above Gemini's inline limit"}

    primary = model_name if (model_name and "transcribe" in model_name) else GEMINI_TRANSCRIBE_MODEL
    plan = [(primary, False)] + [(m, True) for m in GEMINI_PROMPT_FALLBACK_MODELS if m != primary]
    client = _gemini_client(api_key)
    last_err = ""
    last_exc: Optional[BaseException] = None
    retryable = False

    for model, prompt_mode in plan:
        for attempt in range(1, GEMINI_MAX_ATTEMPTS + 1):
            t0 = time.time()
            with _gemini_semaphore:
                try:
                    resp = _gemini_call_once(client, model, audio, mime_type, prompt_mode)
                    lines = _lines_from_transcribe_response(resp) if not prompt_mode else \
                        _normalise_prompt_lines(getattr(resp, "text", "") or "")
                    if lines:
                        log.info("%s Gemini OK model=%s mode=%s attempt=%d in %.1fs: %d lines",
                                 ctx, model, "prompt" if prompt_mode else "transcribe", attempt, time.time() - t0, len(lines))
                        attempts.append(f"{model}#{attempt}: ok")
                        return {"ok": True, "text": "\n".join(lines), "provider": "gemini", "model": model,
                                "attempts": attempts, "error": ""}
                    last_err = f"empty response from {model} ({_response_diag(resp)})"
                    log.error("%s Gemini %s", ctx, last_err)
                    attempts.append(f"{model}#{attempt}: empty")
                    break  # an empty answer will not change on retry -> next model
                except Exception as e:
                    last_exc = e
                    last_err = _short_reason(e)
                    attempts.append(f"{model}#{attempt}: {last_err}")
                    log.error("%s Gemini FAILED model=%s attempt=%d/%d after %.1fs: %s",
                              ctx, model, attempt, GEMINI_MAX_ATTEMPTS, time.time() - t0, describe_exception(e))
                    retryable = _is_retryable(e)
            if not retryable or attempt == GEMINI_MAX_ATTEMPTS:
                break
            delay = _retry_delay_hint(last_exc) or min(GEMINI_BACKOFF_MAX_SEC, GEMINI_BACKOFF_BASE_SEC * (2 ** (attempt - 1)))
            delay += random.uniform(0, 1.5)
            log.warning("%s retrying %s in %.1fs (retryable error)", ctx, model, delay)
            time.sleep(delay)
        code = None
        m = re.match(r"HTTP (\d+)", last_err)
        if m:
            code = int(m.group(1))
        if code in (401, 403):
            break  # bad key: other models won't help
    return {"ok": False, "text": "", "provider": "gemini", "attempts": attempts, "error": _friendly(last_err)}


# ---------------------------------------------------------------------------
# Local Whisper
# ---------------------------------------------------------------------------
def whisper_status(model_name: str = "") -> Dict[str, Any]:
    """Local Whisper readiness for the requested model ('' / 'auto' = automatic selection)."""
    try:
        import local_whisper_engine as lwe
        name, source = lwe.resolve_whisper_model_choice(model_name)
        path = lwe.get_model_path(name)
        has = any(lwe._model_has_weights(p) for p in (path, lwe._SMALL_MODEL_DIR, lwe._BASE_MODEL_DIR,
                                                      lwe._TINY_MODEL_DIR, lwe._MEDIUM_MODEL_DIR))
        return {"available": True, "weights_present": has, "model": name, "model_source": source, "path": path,
                "load_error": lwe._MODEL_LOAD_ERROR}
    except Exception as e:
        log.error("Local Whisper engine unavailable: %s", describe_exception(e))
        return {"available": False, "weights_present": False,
                "error": "Local Whisper engine (faster-whisper) is not installed"}


_whisper_download_failed: Dict[str, str] = {}


def whisper_transcribe_bytes(audio: bytes, language: str = "auto", mime_type: str = "audio/mp3",
                             ctx: str = "[whisper]", model_name: str = "") -> Dict[str, Any]:
    """
    Returns {ok, text, provider, model, error, language}. Never raises.
    model_name: explicit Whisper size ('small', 'medium', ...) or ''/'auto' for automatic selection.
    """
    st = whisper_status(model_name)
    if not st.get("available"):
        return {"ok": False, "text": "", "provider": "local_whisper", "error": st.get("error")}
    if not st.get("weights_present") and _whisper_download_failed.get("reason"):
        # don't hammer the network once per chunk after a failed download
        return {"ok": False, "text": "", "provider": "local_whisper",
                "error": "Local Whisper model is not installed and could not be downloaded"}
    t0 = time.time()
    try:
        import local_whisper_engine as lwe
        lang = None if language in ("auto", "detect", "", None) else language
        res = lwe.transcribe_local_audio(media_input=audio, language=lang, model_name=st.get("model"),
                                         mime_type=mime_type, beam_size=1, temperature=0.0)
        text = (res.get("raw_transcript") or "").strip()
        if res.get("status") == "error":
            log.error("%s Local Whisper returned error status: %s", ctx, res.get("detail"))
            return {"ok": False, "text": "", "provider": "local_whisper",
                    "error": "Local Whisper failed while transcribing this audio"}
        if not text:
            return {"ok": False, "text": "", "provider": "local_whisper",
                    "error": f"Local Whisper found no speech ({res.get('segments_count', 0)} segments kept)"}
        log.info("%s Local Whisper OK in %.1fs (%d chars) model=%s (%s) lang=%s slices=%s", ctx, time.time() - t0,
                 len(text), res.get("model"), st.get("model_source"), res.get("detected_language"),
                 res.get("slice_languages"))
        return {"ok": True, "text": text, "provider": "local_whisper", "model": res.get("model") or st.get("model"), "error": "",
                "language": res.get("detected_language")}
    except Exception as e:
        reason = _short_reason(e)
        log.error("%s Local Whisper FAILED after %.1fs: %s", ctx, time.time() - t0, describe_exception(e))
        if "download failed" in str(e).lower() or "missing" in str(e).lower():
            _whisper_download_failed["reason"] = reason
            return {"ok": False, "text": "", "provider": "local_whisper",
                    "error": "Local Whisper model is not installed and could not be downloaded"}
        return {"ok": False, "text": "", "provider": "local_whisper",
                "error": "Local Whisper failed unexpectedly (details in app_service.log)"}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def _sanitize_lines(text: str, lang: str) -> List[str]:
    try:
        import local_whisper_engine as lwe
        sanitize = lwe.sanitize_whisper_text
    except Exception:
        sanitize = lambda t, language=None: (t or "").strip()  # noqa: E731
    out = []
    for line in (text or "").splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("[") and ": " in s:
            prefix, content = s.split(": ", 1)
            c = sanitize(content, language=lang)
            if c:
                out.append(f"{prefix}: {c}")
        else:
            c = sanitize(s, language=lang)
            if c:
                out.append(c)
    return out


def _detect_lang(text: str) -> str:
    bn = len(re.findall(r"[ঀ-৿]", text or ""))
    la = len(re.findall(r"[A-Za-z]", text or ""))
    if bn and bn >= la * 0.15:
        return "bn"
    return "en" if la else "auto"


def transcribe_chunks(
    chunks: List[bytes],
    chunk_durations: Optional[List[float]] = None,
    provider: str = "gemini",
    api_key: str = "",
    model_name: str = "",
    language: str = "auto",
    mime_type: str = "audio/mp3",
    segment_time_sec: float = 600.0,
    base_offset_sec: float = 0.0,
    label: str = "",
    on_progress: Optional[Any] = None,
    whisper_model: str = "",
) -> Dict[str, Any]:
    t_all = time.time()
    prov = (provider or "gemini").lower()
    use_local_only = prov in ("local_whisper", "local", "whisper_local", "whisper")
    n = len(chunks or [])
    if n == 0:
        return {"status": "error", "transcript": "", "language": "auto", "chunks": [], "missing_ranges": [],
                "errors": ["No audio was extracted from the file"], "message": "No audio was extracted from the file"}

    durs = list(chunk_durations or [])
    if len(durs) != n or any((d or 0) <= 0 for d in durs):
        durs = [float(segment_time_sec)] * n
    starts = [base_offset_sec]
    for d in durs[:-1]:
        starts.append(starts[-1] + d)

    log.info("transcribe_chunks START %s chunks=%d provider=%s model=%s whisper_model=%s lang=%s mime=%s key=%s durations=%s",
             label, n, prov, model_name or GEMINI_TRANSCRIBE_MODEL, whisper_model or "auto", language, mime_type,
             redact_key(api_key), [round(d, 1) for d in durs])

    results: List[Dict[str, Any]] = [None] * n  # type: ignore

    def _notify_progress(chunk_idx: int):
        if callable(on_progress):
            try:
                finished_count = sum(1 for r in results if r is not None)
                ok_count = sum(1 for r in results if r is not None and r.get("status") == "ok")
                on_progress({
                    "chunks_total": n,
                    "chunks_done": finished_count,
                    "chunks_ok": ok_count,
                    "last_chunk_index": chunk_idx,
                    "last_chunk_range": f"{fmt_ts(starts[chunk_idx-1])}-{fmt_ts(starts[chunk_idx-1]+durs[chunk_idx-1])}"
                })
            except Exception as pe:
                log.debug("on_progress callback error: %s", pe)

    def run(i: int) -> Dict[str, Any]:
        s, e = starts[i], starts[i] + durs[i]
        ctx = f"[chunk {i+1}/{n} {fmt_ts(s)}-{fmt_ts(e)}]"
        t0 = time.time()
        audio = chunks[i] or b""
        info: Dict[str, Any] = {"index": i + 1, "start_sec": round(s, 1), "end_sec": round(e, 1),
                                "range": f"{fmt_ts(s)}-{fmt_ts(e)}", "status": "failed", "provider": None,
                                "errors": [], "chars": 0, "text": ""}
        if len(audio) < 1024:
            info["errors"].append(f"chunk is empty ({len(audio)} bytes)")
        else:
            if not use_local_only:
                g = gemini_transcribe_bytes(audio, api_key, model_name, mime_type, ctx)
                if g["ok"]:
                    info.update(status="ok", provider="gemini", text=g["text"], model=g.get("model"))
                else:
                    info["errors"].append(f"Gemini: {g['error']}")
            if info["status"] != "ok":
                w = whisper_transcribe_bytes(audio, language, mime_type, ctx, model_name=whisper_model)
                if w["ok"]:
                    info.update(status="ok", provider="local_whisper", text=w["text"], model=w.get("model"),
                                language=w.get("language"))
                else:
                    info["errors"].append(w["error"] if w["error"].startswith("Local Whisper") else f"Local Whisper: {w['error']}")
        info["elapsed_sec"] = round(time.time() - t0, 1)
        info["chars"] = len(info["text"])
        lvl = 20 if info["status"] == "ok" else 40
        log.log(lvl, "%s %s via %s in %.1fs chars=%d%s", ctx, info["status"].upper(), info["provider"] or "-",
                info["elapsed_sec"], info["chars"], "" if info["status"] == "ok" else f" reasons={info['errors']}")
        return info

    if n == 1 or use_local_only:
        # Whisper is CPU-bound and serialised internally; run sequentially.
        for i in range(n):
            results[i] = run(i)
            _notify_progress(i + 1)
    else:
        with ThreadPoolExecutor(max_workers=min(GEMINI_MAX_PARALLEL, n), thread_name_prefix="stt") as ex:
            futs = {}
            for i in range(n):
                # copy_context keeps the request's correlation id (job=...) on worker-thread log lines
                futs[ex.submit(contextvars.copy_context().run, run, i)] = i
                if i < n - 1:
                    time.sleep(GEMINI_STAGGER_SEC)
            for f in as_completed(futs):
                i = futs[f]
                try:
                    results[i] = f.result()
                except Exception as e:  # defensive: run() should never raise
                    results[i] = {"index": i + 1, "status": "failed", "errors": [describe_exception(e)], "text": "",
                                  "range": f"{fmt_ts(starts[i])}-{fmt_ts(starts[i]+durs[i])}",
                                  "start_sec": starts[i], "end_sec": starts[i] + durs[i], "chars": 0}
                _notify_progress(i + 1)

    ok_text = "\n".join(r["text"] for r in results if r["status"] == "ok")
    if language not in ("auto", "detect", "", None):
        lang = language
    else:
        audio_langs = [r.get("language") for r in results if r and r.get("status") == "ok" and r.get("language")]
        if audio_langs:
            lang = max(set(audio_langs), key=audio_langs.count)
        else:
            lang = _detect_lang(ok_text)

    out_lines: List[str] = []
    missing, errors = [], []
    for r in results:
        if r["status"] == "ok":
            chunk_len = max(1.0, r["end_sec"] - r["start_sec"])
            for line in _sanitize_lines(r["text"], lang):
                out_lines.append(shift_line_timestamp(clamp_line_timestamp(line, chunk_len), r["start_sec"]))
        else:
            reason = "; ".join(r["errors"]) or "unknown error"
            missing.append({"index": r["index"], "range": r["range"], "start_sec": r["start_sec"],
                            "end_sec": r["end_sec"], "reason": reason})
            errors.append(f"Chunk {r['index']} of {n} ({r['range']}) failed: {reason}")
            short = r["errors"][0] if r["errors"] else "unknown error"
            short = short if len(short) <= 140 else short[:137] + "..."
            out_lines.append(f"{format_ts(r['start_sec'])} ⚠ {GAP_MARKER} {r['range']}: "
                             f"audio not transcribed ({short})")

    n_ok = sum(1 for r in results if r["status"] == "ok")
    if n_ok == n:
        status, message = "success", f"Transcribed all {n} chunk(s)."
    elif n_ok == 0:
        status = "error"
        reasons = {"; ".join(r["errors"]) for r in results}
        message = f"Transcription failed for all {n} chunk(s)."
        if len(reasons) == 1:
            message += f" Reason: {reasons.pop()}"
    else:
        status = "partial"
        message = f"Transcribed {n_ok} of {n} chunk(s); {n - n_ok} time range(s) are missing and marked in the transcript."

    transcript = "\n".join(out_lines) if n_ok else ""
    log.log(20 if status == "success" else 40,
            "transcribe_chunks END %s status=%s ok=%d/%d chars=%d in %.1fs missing=%s",
            label, status, n_ok, n, len(transcript), time.time() - t_all, [m["range"] for m in missing])
    public_chunks = [{k: v for k, v in r.items() if k != "text"} for r in results]
    return {"status": status, "transcript": transcript, "language": lang, "chunks": public_chunks,
            "missing_ranges": missing, "errors": errors, "message": message,
            "providers_used": sorted({r["provider"] for r in results if r.get("provider")})}
