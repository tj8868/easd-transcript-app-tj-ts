"""
transcript_translator.py - convert a verbatim (mixed Bangla/English) transcript into
English-only or Bangla-only text (v8.9).

Design rules:
  * The "[MM:SS] Speaker N:" prefix of every line is never sent to the model and is
    re-attached unchanged, so timestamps and speaker labels survive translation exactly.
  * Lines are sent in numbered batches and the model must return a JSON array with the
    same number of items. A batch whose answer does not line up is retried line by line;
    a line that still fails keeps its original text and is reported in "warnings".
  * Lines already entirely in the target language (and gap markers) are skipped.
  * Providers: Gemini, any OpenAI-compatible endpoint, or the on-device local model.
"""
import json
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from diag_logging import get_logger, describe_exception, redact_key

log = get_logger("translate")

TARGETS = {
    "en": "English",
    "bn": "Bangla (Bengali script, বাংলা)",
}
BATCH_MAX_LINES = 40
BATCH_MAX_CHARS = 6000

_PREFIX_RE = re.compile(r"^(\s*\[[\d:]+\](?:\s*-\s*\[?[\d:]+\]?)?\s*(?:Speaker\s*\w+\s*:)?\s*)(.*)$")
_BENGALI_RE = re.compile(r"[ঀ-৿]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def _split_prefix(line: str) -> Tuple[str, str]:
    m = _PREFIX_RE.match(line)
    if m:
        return m.group(1), m.group(2)
    return "", line


def _already_in_target(text: str, target: str) -> bool:
    bn = len(_BENGALI_RE.findall(text))
    la = len(_LATIN_RE.findall(text))
    if target == "en":
        return bn == 0
    # Bangla target: English acronyms/names (EASD, Q4, budget codes) may stay, so allow a
    # few Latin letters as long as the line is clearly Bangla.
    return la == 0 or (bn > 0 and la <= 6)


def _system_prompt(target: str) -> str:
    lang = TARGETS[target]
    return (
        f"You translate meeting transcript utterances into {lang}.\n"
        "Rules:\n"
        f"1. Translate every item fully into {lang}. Code-switched (mixed Bangla/English) speech must "
        f"come out entirely in {lang}.\n"
        "2. Keep the meaning, tone and every fact (names, numbers, dates, amounts, decisions) exactly. "
        "Do not summarise, shorten, explain or add anything.\n"
        "3. Keep organisation names, acronyms (EASD, NGO, Q4 ...) and people's names as they are"
        + (" (written in Bengali script only if that is how the speaker said them)." if target == "bn" else ".") + "\n"
        "4. Input is a JSON object {\"items\": [\"...\", ...]}. Reply with ONLY a JSON object "
        "{\"items\": [\"...\", ...]} with exactly the same number of items, in the same order."
    )


def _parse_items(raw: str, expected: int) -> Optional[List[str]]:
    if not raw:
        return None
    txt = raw.strip()
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt)
    # Decode only the items array and ignore anything after it: small local models often append
    # stray tokens after an otherwise valid answer (e.g. '{"items": ["..."][]}').
    key = txt.find('"items"')
    start = txt.find("[", key if key >= 0 else 0)
    if start < 0:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(txt[start:])
    except Exception:
        return None
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list) or len(items) != expected:
        return None
    return [str(x).strip() for x in items]


# ---------------------------------------------------------------------------
# Provider callers: (system_prompt, user_json) -> raw model text
# ---------------------------------------------------------------------------
def _gemini_caller(api_key: str, model: str) -> Callable[[str, str], str]:
    import stt_pipeline
    from google.genai import types
    client = stt_pipeline._gemini_client(api_key)

    def call(system: str, user: str) -> str:
        last: Optional[Exception] = None
        for attempt in range(1, 4):
            try:
                cfg = types.GenerateContentConfig(system_instruction=system, temperature=0.1,
                                                  max_output_tokens=32768, response_mime_type="application/json")
                resp = client.models.generate_content(model=model, contents=user, config=cfg)
                return (getattr(resp, "text", None) or "").strip()
            except Exception as e:
                last = e
                if not stt_pipeline._is_retryable(e) or attempt == 3:
                    break
                time.sleep(stt_pipeline._retry_delay_hint(e) or 3 * attempt)
        raise RuntimeError(stt_pipeline._friendly(stt_pipeline._short_reason(last)) if last else "Gemini failed")
    return call


def _openai_caller(api_key: str, base_url: str, model: str) -> Callable[[str, str], str]:
    import httpx
    root = (base_url or "").strip().rstrip("/")
    if not root or not model:
        raise RuntimeError("Custom API base URL and model must be set in Settings")

    def call(system: str, user: str) -> str:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        body = {"model": model, "temperature": 0.1,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        with httpx.Client(timeout=180.0) as c:
            r = c.post(f"{root}/chat/completions", headers=headers, json=body)
        if r.status_code >= 400:
            raise RuntimeError(f"Custom API returned HTTP {r.status_code}")
        from ai_providers import _oac_extract_content
        return _oac_extract_content(r.json())
    return call


def _local_caller(model_key: Optional[str]) -> Callable[[str, str], str]:
    import local_llm_engine
    return lambda system, user: local_llm_engine.chat(system, user, model_key, temperature=0.1)[0]


def _make_caller(provider: str, api_key: str, model: str, base_url: str) -> Tuple[Callable[[str, str], str], str]:
    prov = (provider or "gemini").lower()
    if prov in ("openai_compatible", "custom", "openai", "openrouter"):
        return _openai_caller(api_key, base_url, model), f"custom:{model}"
    if prov in ("local", "local_whisper", "offline"):
        import local_llm_engine
        key = model if model in getattr(local_llm_engine, "SUPPORTED_MODELS", {}) else None
        return _local_caller(key), f"local:{key or local_llm_engine.DEFAULT_MODEL_KEY}"
    if not api_key:
        raise RuntimeError("No Gemini API key configured (add it in Settings)")
    m = model if (model and model.startswith("gemini") and "transcribe" not in model) else "gemini-3.8-flash"
    return _gemini_caller(api_key, m), m


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def translate_transcript(transcript: str, target: str, provider: str = "gemini", api_key: str = "",
                         model_name: str = "", base_url: str = "") -> Dict[str, Any]:
    """Cloud first; whatever the cloud could not convert is finished by the on-device model."""
    res = _translate(transcript, target, provider, api_key, model_name, base_url)
    if res["status"] == "success" or (provider or "").lower() in ("local", "local_whisper", "offline") \
            or target not in TARGETS or not (transcript or "").strip():
        return res
    reason = res.get("error") or "; ".join(res.get("warnings", []))
    log.warning("translate: cloud incomplete (%s) - finishing with the on-device model", reason)
    local = _translate(res.get("text") or transcript, target, "local")  # converted lines are skipped
    if local["status"] == "error":
        return res
    local["warnings"] = [f"Cloud AI was unavailable ({reason}); the on-device model converted the rest."] \
        + local.get("warnings", [])
    return local


def _translate(transcript: str, target: str, provider: str = "gemini", api_key: str = "",
               model_name: str = "", base_url: str = "") -> Dict[str, Any]:
    """
    Returns {"status": "success"|"partial"|"error", "text", "target", "model",
             "lines_total", "lines_translated", "warnings": [...], "error"?}
    """
    target = (target or "").lower()
    if target not in TARGETS:
        return {"status": "error", "error": f"Unknown target language {target!r} (use 'en' or 'bn')."}
    lines = (transcript or "").splitlines()
    if not any(l.strip() for l in lines):
        return {"status": "error", "error": "The transcript is empty."}

    try:
        call, model_label = _make_caller(provider, api_key, model_name, base_url)
    except Exception as e:
        log.error("translate: provider setup failed: %s", describe_exception(e))
        return {"status": "error", "error": f"Could not start the translation model: {e}"}

    log.info("translate START target=%s provider=%s model=%s key=%s lines=%d", target, provider, model_label,
             redact_key(api_key), len(lines))
    t0 = time.time()
    prefixes: List[str] = []
    bodies: List[str] = []
    todo: List[int] = []
    for i, line in enumerate(lines):
        pre, body = _split_prefix(line)
        prefixes.append(pre)
        bodies.append(body)
        if body.strip() and "TRANSCRIPT GAP" not in line and not _already_in_target(body, target):
            todo.append(i)

    batches: List[List[int]] = []
    cur: List[int] = []
    cur_chars = 0
    for i in todo:
        if cur and (len(cur) >= BATCH_MAX_LINES or cur_chars + len(bodies[i]) > BATCH_MAX_CHARS):
            batches.append(cur)
            cur, cur_chars = [], 0
        cur.append(i)
        cur_chars += len(bodies[i])
    if cur:
        batches.append(cur)

    system = _system_prompt(target)
    out = list(bodies)
    failed: List[int] = []
    fatal: Optional[str] = None

    def run(idx: List[int]) -> Optional[List[str]]:
        user = json.dumps({"items": [bodies[i] for i in idx]}, ensure_ascii=False)
        return _parse_items(call(system, user), len(idx))

    for b_no, batch in enumerate(batches, start=1):
        try:
            items = run(batch)
            if items is None:
                log.warning("translate batch %d/%d misaligned - retrying line by line", b_no, len(batches))
                items = []
                for i in batch:
                    single = run([i])
                    items.append(single[0] if single else None)
            for i, txt in zip(batch, items):
                if txt:
                    out[i] = txt
                else:
                    failed.append(i)
        except Exception as e:
            fatal = str(e)
            log.error("translate batch %d/%d FAILED: %s", b_no, len(batches), describe_exception(e))
            failed.extend(batch)
            # A dead key / unreachable endpoint will not recover for the next batch.
            failed.extend(i for later in batches[b_no:] for i in later)
            break

    text = "\n".join(p + b for p, b in zip(prefixes, out))
    warnings = []
    if failed:
        shown = ", ".join(str(i + 1) for i in sorted(set(failed))[:10])
        warnings.append(f"{len(set(failed))} line(s) could not be converted and were left as spoken "
                        f"(line {shown}{'...' if len(set(failed)) > 10 else ''}).")
    translated = len(todo) - len(set(failed))
    status = "success" if not failed else ("error" if translated == 0 else "partial")
    log.info("translate END status=%s translated=%d/%d in %.1fs", status, translated, len(todo), time.time() - t0)
    res = {"status": status, "text": text, "target": target, "model": model_label,
           "lines_total": len(lines), "lines_translated": translated, "warnings": warnings}
    if status == "error":
        res["error"] = fatal or "The model did not return a usable translation."
    return res
