"""
Local Whisper Engine (Offline, Zero-Cost, Embedded STT)
Powered by faster-whisper (CTranslate2) with INT8 quantization on CPU.
Optimized for EASD Meeting Minutes (Bangla and English bilingual speech).
"""

import os
import sys
import io
import time
import logging
import tempfile
import threading
import subprocess
from typing import Optional, Dict, Any, Union, List, Tuple

def get_optimal_cpu_threads() -> int:
    """Calculates optimal CPU threads for faster-whisper on Windows without thrashing."""
    try:
        import psutil
        avail_gb = psutil.virtual_memory().available / (1024 ** 3)
        if avail_gb < 0.5:
            return 1
        cores = os.cpu_count() or 4
        return max(1, min(cores - 1, 3))
    except Exception:
        return 1

_DYNAMIC_THREADS = str(get_optimal_cpu_threads())
os.environ.setdefault("OMP_NUM_THREADS", _DYNAMIC_THREADS)
os.environ.setdefault("MKL_NUM_THREADS", _DYNAMIC_THREADS)

try:
    from diag_logging import get_logger as _easd_get_logger
    logger = _easd_get_logger("whisper")  # -> app_service.log (+ console when present)
except Exception:
    logger = logging.getLogger("local_whisper_engine")
logger.setLevel(logging.INFO)
if not logger.handlers and not logger.name.startswith("easd."):
    # Use utf-8 safe handler
    try:
        stream = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    except Exception:
        stream = sys.stdout
    ch = logging.StreamHandler(stream)
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(asctime)s] [%(name)s] %(message)s", datefmt="%H:%M:%S")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_MEDIUM_MODEL_DIR = os.path.join(_BASE_DIR, "models", "whisper-medium")
_SMALL_MODEL_DIR = os.path.join(_BASE_DIR, "models", "whisper-small")
_BASE_MODEL_DIR = os.path.join(_BASE_DIR, "models", "whisper-base")
_TINY_MODEL_DIR = os.path.join(_BASE_DIR, "models", "whisper-tiny")

_DEFAULT_MODEL_DIR = _SMALL_MODEL_DIR
_FALLBACK_MODEL_DIR = _BASE_MODEL_DIR

_LOCAL_MODELS: Dict[str, Any] = {}
_LOCAL_MODEL = None
_MODEL_LOCK = threading.Lock()
_TRANSCRIBE_LOCK = threading.Lock()
_IS_WARMING_UP = False
_MODEL_STATUS = "unloaded"  # unloaded | loading | ready | error
_MODEL_LOAD_ERROR = None
_MODEL_LOAD_TIME = 0.0

DEFAULT_BILINGUAL_PROMPT = (
    "Ajker meeting er alochna ebong karjobiboroni. "
    "Verbatim meeting transcript: agenda, budget, review, decisions, action items, participants."
)


# Languages Whisper's detector routinely confuses with Bengali on South-Asian speech.
# Bengali is only preferred over one of these when the two are genuinely close.
_BN_CONFUSABLE_LANGS = ("hi", "ne", "ur", "as")
# Bengali must reach at least this share of the top candidate's probability to win.
_BN_AMBIGUITY_RATIO = 0.6
# A chunk is treated as code-switched (let Whisper decide per 30s window) when the
# runner-up language has at least this share of the top candidate's probability.
_CODE_SWITCH_RATIO = 0.5
# Silero VAD settings used for both language detection and transcription.
# Validated in test_whisper_language_and_vad.py against real recordings with long silences.
WHISPER_VAD_PARAMETERS = {
    "threshold": 0.5,
    "min_speech_duration_ms": 250,
    "min_silence_duration_ms": 1000,
    "speech_pad_ms": 400,
}


def _get_vad_options():
    try:
        from faster_whisper.vad import VadOptions
        return VadOptions(**WHISPER_VAD_PARAMETERS)
    except Exception:
        return WHISPER_VAD_PARAMETERS


def detect_audio_language_detail(
    model: Any,
    audio_input: Union[str, Any],
    _ctx: str = ""
) -> Dict[str, Any]:
    """
    Detects the spoken language of an audio file/array and explains the decision.

    Only the speech portions are scored (Silero VAD strips silence/noise first), and the
    top-ranked language wins unless a confusable language (hi/ne/ur/as) narrowly beats
    Bengali. Every call logs the full probability distribution to app_service.log.

    Returns:
        {"language": str | None, "confidence": float, "ambiguous": bool,
         "reason": str, "ranked": [(lang, prob), ...]}
        language is None when detection failed (caller should let Whisper auto-detect).
    """
    ctx = _ctx or "[lang]"
    t0 = time.time()
    result: Dict[str, Any] = {"language": None, "confidence": 0.0, "ambiguous": False,
                              "reason": "", "ranked": [], "candidates": []}
    try:
        import faster_whisper
        if isinstance(audio_input, str) and os.path.isfile(audio_input):
            audio = faster_whisper.decode_audio(audio_input)
        else:
            audio = audio_input

        if audio is None or len(audio) == 0:
            result["reason"] = "empty audio"
            logger.warning(f"{ctx} language detection skipped: empty audio")
            return result

        try:
            _, _, all_probs = model.detect_language(
                audio, vad_filter=True, vad_parameters=_get_vad_options()
            )
        except (TypeError, AttributeError):
            # Older faster-whisper without VAD support in detect_language: score the first 30s.
            _, _, all_probs = model.detect_language(audio[:30 * 16000])
        probs = dict(all_probs or [])
        if not probs:
            result["reason"] = "detector returned no probabilities"
            logger.warning(f"{ctx} language detection returned no probabilities")
            return result

        ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
        top_lang, top_prob = ranked[0]
        second_lang, second_prob = ranked[1] if len(ranked) > 1 else ("", 0.0)
        language, confidence, reason = top_lang, top_prob, "top-ranked language"

        # Bengali / Hindi / Nepali / Urdu / Assamese confusion: only switch to Bengali
        # when Bengali is genuinely close to the winner, never off a fixed low floor.
        prob_bn = probs.get("bn", 0.0)
        if top_lang in _BN_CONFUSABLE_LANGS and prob_bn >= _BN_AMBIGUITY_RATIO * top_prob:
            language, confidence = "bn", prob_bn
            reason = f"bn within {_BN_AMBIGUITY_RATIO:.0%} of confusable top '{top_lang}'"

        # Runner-up = best language other than the chosen one, ignoring Bengali's confusables
        # when Bengali was chosen (a bn/hi split is misdetection, not code-switching).
        bn_family = ("bn",) + _BN_CONFUSABLE_LANGS
        runner_up, runner_up_prob = "", 0.0
        for k, v in ranked:
            if k == language or (language == "bn" and k in bn_family):
                continue
            runner_up, runner_up_prob = k, v
            break
        ambiguous = bool(runner_up and runner_up_prob >= 0.15 and runner_up_prob >= _CODE_SWITCH_RATIO * confidence)
        result.update(language=language, confidence=float(confidence), ambiguous=ambiguous,
                      reason=reason, ranked=[(k, round(float(v), 4)) for k, v in ranked],
                      candidates=[language, runner_up] if ambiguous else [language])

        dist = ", ".join(f"{k}={v:.3f}" for k, v in ranked if v >= 0.001)
        logger.info(f"{ctx} language -> {language} (p={confidence:.3f}, ambiguous={ambiguous}, reason={reason}) "
                    f"in {time.time() - t0:.1f}s | distribution: {dist}")
        return result
    except Exception as e:
        result["reason"] = f"detection error: {type(e).__name__}"
        logger.error(f"{ctx} language detection FAILED after {time.time() - t0:.1f}s: "
                     f"{type(e).__name__}: {e}", exc_info=True)
        return result


def detect_audio_language(
    model: Any,
    audio_input: Union[str, Any]
) -> Tuple[str, float]:
    """
    Backwards-compatible wrapper around detect_audio_language_detail().
    Returns: (resolved_language, confidence); ("auto", 0.0) when detection failed,
    so callers let Whisper auto-detect instead of forcing a guessed language.
    """
    d = detect_audio_language_detail(model, audio_input)
    return (d["language"] or "auto"), float(d["confidence"])

def _resolve_window_language(model: Any, audio_window: Any, candidates: List[str], ctx: str = "") -> str:
    """
    Picks which of the chunk's candidate languages dominates one ~30s window.
    Restricting the choice to the chunk's own top candidates stops a noisy window
    from being decoded as an unrelated script (Telugu, Kannada, ...).
    """
    try:
        _, _, all_probs = model.detect_language(audio_window, vad_filter=True,
                                                vad_parameters=_get_vad_options())
    except (TypeError, AttributeError):
        _, _, all_probs = model.detect_language(audio_window)
    except Exception as e:
        logger.warning(f"{ctx} window language detection failed ({type(e).__name__}: {e}); using {candidates[0]}")
        return candidates[0]
    probs = dict(all_probs or [])
    # Bengali absorbs its confusables so a Bangla window is never decoded as Hindi.
    scores = {}
    for cand in candidates:
        scores[cand] = probs.get(cand, 0.0) + (sum(probs.get(c, 0.0) for c in _BN_CONFUSABLE_LANGS)
                                               if cand == "bn" else 0.0)
    chosen = max(scores, key=scores.get)
    logger.info(f"{ctx} window language -> {chosen} scores={ {k: round(v, 3) for k, v in scores.items()} }")
    return chosen


# Alias for backwards compatibility
detect_bilingual_audio_language = detect_audio_language


# (unicode range, languages that legitimately use it) for scripts Whisper hallucinates
# on Bangla/English audio. Extend this table when a new hallucinated script shows up,
# and add a sample to whisper_hallucination_fixtures.py.
_HALLUCINATION_SCRIPTS: List[Tuple[str, Tuple[str, ...]]] = [
    ("\u0900-\u0963\u0966-\u097F", ("hi", "mr", "ne", "sa", "mai", "hindi", "marathi", "nepali")),  # Devanagari
    ("\u0A00-\u0A7F", ("pa", "punjabi")),                        # Gurmukhi
    ("\u0A80-\u0AFF", ("gu", "gujarati")),                       # Gujarati
    ("\u0B00-\u0B7F", ("or", "odia", "oriya")),                  # Odia
    ("\u0B80-\u0BFF", ("ta", "tamil")),                          # Tamil
    ("\u0C00-\u0C7F", ("te", "telugu")),                         # Telugu
    ("\u0C80-\u0CFF", ("kn", "kannada")),                        # Kannada
    ("\u0D00-\u0D7F", ("ml", "malayalam")),                      # Malayalam
]


def sanitize_whisper_text(text: Optional[str], language: Optional[str] = None) -> str:
    """
    Cleans raw Whisper transcription output to eliminate hallucinations and decoder loops:
    1. Removes Unicode replacement characters (\uFFFD) and zero-width spaces (\u200B, \uFEFF).
    2. Strips hallucinated Tibetan / delimiter Unicode blocks (\u0F00-\u0FFF, e.g. ༼, ༽).
    3. Strips hallucinated CJK / East Asian characters (\u4E00-\u9FFF, \u3400-\u4DBF, \u3000-\u303F, \u3040-\u30FF, \uAC00-\uD7AF)
       unless the explicit/detected language is Chinese, Japanese, or Korean.
    3b. Strips hallucinated Indic scripts (Devanagari, Gurmukhi, Gujarati, Odia, Tamil, Telugu,
       Kannada, Malayalam) unless the language uses that script; drops the whole segment when
       most of its letters were foreign-script garbage.
    4. Collapses repetitive character/syllable/phrase loops (e.g. 'বিবিবিবিবিবি...' -> 'বি').
    5. Eliminates phantom punctuation repetitions (e.g. '..........', '।।।।।।').
    6. Discards segments lacking authentic alphanumeric speech tokens in ANY language (Unicode letters/digits).
    """
    if not text:
        return ""

    import re

    # Strip replacement char and zero-width artifacts
    cleaned = text.replace("\ufffd", "").replace("\u200b", "").replace("\ufeff", "")

    # Strip Tibetan / alien symbol Unicode block (\u0F00-\u0FFF, including ༼, ༽, etc.)
    cleaned = re.sub(r"[\u0F00-\u0FFF༼༽ༀ༁༂༃]+", " ", cleaned)

    # Strip CJK ideographs & East Asian syllabaries (e.g. 詞, 词, 谢谢, etc.) unless language is explicitly zh/ja/ko
    norm_lang = (language or "").lower().strip()
    if norm_lang not in ["zh", "ja", "ko", "chinese", "japanese", "korean", "yue"]:
        cleaned = re.sub(r"[\u4E00-\u9FFF\u3400-\u4DBF\u2E80-\u2EFF\u3000-\u303F\u3040-\u30FF\uAC00-\uD7AF]+", " ", cleaned)

    # Strip hallucinated Indic scripts (Devanagari, Telugu, Kannada, ...) unless the target
    # language is written in that script. Bengali (\u0980-\u09FF) is never stripped, and the
    # danda marks (\u0964-\u0965) are kept because Bengali shares them with Devanagari.
    letters_before = sum(1 for ch in cleaned if ch.isalpha())
    for script_range, script_langs in _HALLUCINATION_SCRIPTS:
        if norm_lang not in script_langs:
            cleaned = re.sub(f"[{script_range}]+", " ", cleaned)
    letters_after = sum(1 for ch in cleaned if ch.isalpha())
    # A segment that was mostly foreign-script garbage is a hallucination as a whole;
    # the few Latin/Bengali letters left over are not trustworthy speech either.
    if letters_before and letters_after < 0.5 * letters_before:
        return ""

    # Collapse repetitive character / syllable / phrase loops (e.g. 'বি' repeated 4+ times)
    # Run multiple passes to catch nested loops
    for _ in range(3):
        prev = cleaned
        cleaned = re.sub(r"(.{1,8}?)\1{3,}", r"\1", cleaned)
        cleaned = re.sub(r"(\b\w+\s+)\1{3,}", r"\1", cleaned)
        if cleaned == prev:
            break

    # Clean excessive punctuation repeats
    cleaned = re.sub(r"([।\.\?\!\,\-\_])\1{2,}", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # If the text has no meaningful alphanumeric characters in any language script, discard it
    has_meaningful_speech = any(ch.isalnum() for ch in cleaned)
    if not has_meaningful_speech:
        return ""

    return cleaned


def format_seconds_to_min_sec(seconds: float) -> str:
    """
    Formats a duration in seconds into 'MM:SS' (or 'HH:MM:SS' if duration >= 1 hour).
    Examples:
        0.0     -> '00:00'
        180.0   -> '03:00'
        204.94  -> '03:25'
        690.0   -> '11:30'
        1020.0  -> '17:00'
        1223.0  -> '20:23'
        3665.0  -> '01:01:05'
    """
    try:
        total_sec = round(max(0.0, float(seconds)))
    except (ValueError, TypeError):
        return "00:00"

    hrs = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60

    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def get_system_ram_specs() -> Dict[str, Any]:
    """Detect system RAM specs to decide between small, base, and tiny models."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        total_gb = round(mem.total / (1024 ** 3), 2)
        avail_gb = round(mem.available / (1024 ** 3), 2)
        # Low RAM only when total RAM < 5.0GB or available RAM < 0.8GB
        is_low = total_gb < 5.0 or avail_gb < 0.8
        return {
            "total_ram_gb": total_gb,
            "available_ram_gb": avail_gb,
            "is_low_ram": is_low
        }
    except Exception:
        return {
            "total_ram_gb": 8.0,
            "available_ram_gb": 2.0,
            "is_low_ram": False
        }


def is_low_ram_system() -> bool:
    """Returns True if the host machine has low total or available RAM."""
    specs = get_system_ram_specs()
    return bool(specs.get("is_low_ram", False))


_LAST_AUTO_CHOICE: Dict[str, str] = {}


def select_optimal_model_name() -> str:
    """
    Dynamically select between whisper-medium, whisper-small, whisper-base and whisper-tiny
    based on host RAM and which model weights are present on disk.
    whisper-medium int8 needs ~1.5-2GB of RAM, so an 8GB machine with >=2.5GB free
    can run it; the decision and its reason are logged every time.
    """
    specs = get_system_ram_specs()
    total_gb = specs.get("total_ram_gb", 8.0)
    avail_gb = specs.get("available_ram_gb", 2.0)

    def _pick(name: str, why: str) -> str:
        msg = (f"select_optimal_model_name -> '{name}' ({why}; total_ram={total_gb}GB "
               f"available_ram={avail_gb}GB)")
        # INFO when the decision changes, DEBUG on repeats (this runs several times per request)
        if _LAST_AUTO_CHOICE.get("name") != name:
            logger.info(msg)
            _LAST_AUTO_CHOICE["name"] = name
        else:
            logger.debug(msg)
        return name

    # Medium: needs weights on disk, >= ~8GB total (7.5 allows for OS-reported rounding) and 2.5GB free
    if _model_has_weights(_MEDIUM_MODEL_DIR):
        if total_gb >= 7.5 and avail_gb >= 2.5:
            return _pick("medium", "weights present and enough RAM")
        logger.warning(f"select_optimal_model_name: whisper-medium weights present but skipped - "
                       f"needs total>=7.5GB and available>=2.5GB (have total={total_gb}GB, available={avail_gb}GB)")

    # Severely constrained RAM (< 3.0GB total or < 0.4GB available)
    if total_gb < 3.0 or avail_gb < 0.4:
        if _model_has_weights(_TINY_MODEL_DIR):
            return _pick("tiny", "severely constrained RAM")
        if _model_has_weights(_BASE_MODEL_DIR):
            return _pick("base", "severely constrained RAM")

    # Standard systems (>= 6GB RAM) prefer whisper-small if present for accurate bilingual speech
    if total_gb >= 6.0 and _model_has_weights(_SMALL_MODEL_DIR):
        return _pick("small", "standard RAM, small weights present")

    # Base model is the fast lightweight fallback (145MB)
    if _model_has_weights(_BASE_MODEL_DIR):
        return _pick("base", "fallback to base weights")
    if _model_has_weights(_SMALL_MODEL_DIR):
        return _pick("small", "fallback to small weights")
    if _model_has_weights(_TINY_MODEL_DIR):
        return _pick("tiny", "fallback to tiny weights")
    return _pick("base", "no weights on disk - base will be downloaded on first use")


_KNOWN_MODEL_SIZES = ("tiny", "base", "small", "medium")


def resolve_whisper_model_choice(requested: Optional[str] = None) -> Tuple[str, str]:
    """
    Resolves which Whisper model a request should use.
    An explicit size ('tiny'/'base'/'small'/'medium') is always respected; only
    None/''/'auto' (or an unknown value) falls through to select_optimal_model_name().
    Returns: (model_name, source) where source is 'explicit' or 'auto'.
    """
    req = (requested or "").strip().lower()
    for size in _KNOWN_MODEL_SIZES:
        if req == size or req == f"whisper-{size}" or req.endswith(f"/{size}"):
            logger.info(f"resolve_whisper_model_choice: using explicitly requested model '{size}' (requested={requested!r})")
            return size, "explicit"
    if req and req not in ("auto", "default", "local", "local_whisper"):
        logger.warning(f"resolve_whisper_model_choice: unknown model {requested!r} - using automatic selection")
    return select_optimal_model_name(), "auto"


def _model_has_weights(directory: str) -> bool:
    """Returns True if the directory exists and contains valid model weights."""
    if not os.path.isdir(directory):
        return False
    return (
        os.path.isfile(os.path.join(directory, "model.bin")) or
        os.path.isfile(os.path.join(directory, "model.safetensors"))
    )


def get_model_path(preferred_name: Optional[str] = None) -> str:
    """Resolve the local model path on disk, gracefully falling back to available weights."""
    if preferred_name:
        pref_clean = preferred_name.strip().lower()
        if "medium" in pref_clean:
            if _model_has_weights(_MEDIUM_MODEL_DIR):
                return _MEDIUM_MODEL_DIR
            if _model_has_weights(_SMALL_MODEL_DIR):
                return _SMALL_MODEL_DIR
            if _model_has_weights(_BASE_MODEL_DIR):
                return _BASE_MODEL_DIR
            return _MEDIUM_MODEL_DIR
        elif "tiny" in pref_clean:
            if _model_has_weights(_TINY_MODEL_DIR):
                return _TINY_MODEL_DIR
            if _model_has_weights(_BASE_MODEL_DIR):
                return _BASE_MODEL_DIR
            if _model_has_weights(_SMALL_MODEL_DIR):
                return _SMALL_MODEL_DIR
            return _TINY_MODEL_DIR
        elif "base" in pref_clean:
            if _model_has_weights(_BASE_MODEL_DIR):
                return _BASE_MODEL_DIR
            if _model_has_weights(_SMALL_MODEL_DIR):
                return _SMALL_MODEL_DIR
            return _BASE_MODEL_DIR
        elif "small" in pref_clean:
            if _model_has_weights(_SMALL_MODEL_DIR):
                return _SMALL_MODEL_DIR
            if _model_has_weights(_BASE_MODEL_DIR):
                return _BASE_MODEL_DIR
            return _SMALL_MODEL_DIR

    # Automatic spec-based resolution
    optimal = select_optimal_model_name()
    if optimal == "medium" and _model_has_weights(_MEDIUM_MODEL_DIR):
        return _MEDIUM_MODEL_DIR
    if optimal == "small" and _model_has_weights(_SMALL_MODEL_DIR):
        return _SMALL_MODEL_DIR
    if optimal == "base" and _model_has_weights(_BASE_MODEL_DIR):
        return _BASE_MODEL_DIR
    if optimal == "tiny" and _model_has_weights(_TINY_MODEL_DIR):
        return _TINY_MODEL_DIR

    # Fallback to any model that has weights
    if _model_has_weights(_SMALL_MODEL_DIR):
        return _SMALL_MODEL_DIR
    if _model_has_weights(_BASE_MODEL_DIR):
        return _BASE_MODEL_DIR
    if _model_has_weights(_TINY_MODEL_DIR):
        return _TINY_MODEL_DIR

    return _SMALL_MODEL_DIR


def _select_compute_device() -> Tuple[str, List[str]]:
    """
    Picks the inference device: CUDA when CTranslate2 sees a GPU, otherwise CPU.
    GPU use is optional and auto-detected; CPU-only machines are unaffected.
    Override with EASD_WHISPER_DEVICE=cpu|cuda|auto.
    Returns: (device, compute_types_to_try_in_order)
    """
    forced = (os.environ.get("EASD_WHISPER_DEVICE") or "auto").strip().lower()
    cpu_types = ["int8", "int8_float32", "float32"]
    if forced == "cpu":
        return "cpu", cpu_types
    try:
        import ctranslate2
        n_gpu = ctranslate2.get_cuda_device_count()
    except Exception as e:
        logger.info(f"CUDA probe unavailable ({type(e).__name__}: {e}) - using CPU")
        n_gpu = 0
    if n_gpu > 0 or forced == "cuda":
        logger.info(f"CUDA devices detected: {n_gpu} (EASD_WHISPER_DEVICE={forced}) - trying GPU first")
        return "cuda", ["float16", "int8_float16", "int8"]
    return "cpu", cpu_types


_MODEL_DEVICE: Dict[str, str] = {}


def get_loaded_model_name(model: Any) -> str:
    """Name of the model directory actually loaded for this model object (e.g. 'whisper-small')."""
    for path, m in _LOCAL_MODELS.items():
        if m is model:
            return os.path.basename(path)
    return "unknown"


def get_local_whisper_model(model_name_or_path: Optional[str] = None):
    """
    Get or initialize the singleton WhisperModel instance for the target model.
    Runs with device='cpu', compute_type='int8', dynamic cpu_threads.
    Auto-downloads weights if missing from disk.
    """
    global _LOCAL_MODEL, _LOCAL_MODELS, _MODEL_STATUS, _MODEL_LOAD_ERROR, _MODEL_LOAD_TIME

    resolved_path = get_model_path(model_name_or_path)

    if resolved_path in _LOCAL_MODELS:
        _LOCAL_MODEL = _LOCAL_MODELS[resolved_path]
        return _LOCAL_MODEL

    with _MODEL_LOCK:
        if resolved_path in _LOCAL_MODELS:
            _LOCAL_MODEL = _LOCAL_MODELS[resolved_path]
            return _LOCAL_MODEL

        # If resolved path does not have weights, fallback to another local model or auto-download
        if not _model_has_weights(resolved_path):
            fallback_found = False
            for cand in [_SMALL_MODEL_DIR, _BASE_MODEL_DIR, _TINY_MODEL_DIR, _MEDIUM_MODEL_DIR]:
                if _model_has_weights(cand):
                    logger.info(f"Target '{resolved_path}' missing weights, using local '{os.path.basename(cand)}'")
                    resolved_path = cand
                    fallback_found = True
                    break

            if not fallback_found:
                base_name = os.path.basename(resolved_path)
                target_size = next((sz for sz in _KNOWN_MODEL_SIZES if sz in base_name), "base")
                logger.info(f"Downloading local Whisper model '{target_size}' to '{resolved_path}'...")
                try:
                    from faster_whisper import download_model
                    os.makedirs(resolved_path, exist_ok=True)
                    download_model(target_size, output_dir=resolved_path)
                except Exception as dl_err:
                    _MODEL_STATUS = "error"
                    _MODEL_LOAD_ERROR = f"Model directory missing and download failed: {dl_err}"
                    logger.error(_MODEL_LOAD_ERROR)
                    raise FileNotFoundError(_MODEL_LOAD_ERROR)

        _MODEL_STATUS = "loading"
        t0 = time.time()
        n_threads = get_optimal_cpu_threads()
        device, device_compute_types = _select_compute_device()
        logger.info(f"Loading local Whisper model from '{resolved_path}' (device={device}, {n_threads} CPU threads)...")

        try:
            from faster_whisper import WhisperModel
            # INT8 is the most compact (39MB-75MB) and fastest format for CPU inference without memory allocation errors.
            model = None
            last_err = None

            paths_to_try = [resolved_path]
            for cand_dir in [_SMALL_MODEL_DIR, _BASE_MODEL_DIR, _TINY_MODEL_DIR]:
                if cand_dir != resolved_path and _model_has_weights(cand_dir):
                    paths_to_try.append(cand_dir)

            attempts = [(device, c) for c in device_compute_types]
            if device != "cpu":
                attempts += [("cpu", c) for c in ["int8", "int8_float32", "float32"]]
            loaded_device = "cpu"
            for target_path in paths_to_try:
                for dev_name, c_type in attempts:
                    try:
                        logger.info(f"Loading WhisperModel from '{os.path.basename(target_path)}' "
                                    f"(device={dev_name}, compute_type={c_type}, threads={n_threads})...")
                        model = WhisperModel(
                            target_path,
                            device=dev_name,
                            compute_type=c_type,
                            cpu_threads=n_threads,
                            local_files_only=True
                        )
                        resolved_path = target_path
                        loaded_device = dev_name
                        break
                    except Exception as try_err:
                        last_err = try_err
                        logger.warning(f"WhisperModel init notice ({os.path.basename(target_path)}, {dev_name}, {c_type}): {try_err}")
                        import gc
                        gc.collect()
                        continue
                if model is not None:
                    break

            if model is None:
                raise last_err or RuntimeError("Failed to load local Whisper model with any compute type")

            if os.path.normcase(resolved_path) != os.path.normcase(get_model_path(model_name_or_path)):
                logger.warning(f"Requested Whisper model {model_name_or_path!r} not loadable - "
                               f"actually loaded '{os.path.basename(resolved_path)}'")
            _LOCAL_MODELS[resolved_path] = model
            _MODEL_DEVICE[resolved_path] = loaded_device
            _LOCAL_MODEL = model
            _MODEL_LOAD_TIME = round(time.time() - t0, 2)
            _MODEL_STATUS = "ready"
            _MODEL_LOAD_ERROR = None
            logger.info(f"Local Whisper model loaded successfully from '{os.path.basename(resolved_path)}' "
                        f"on {loaded_device} in {_MODEL_LOAD_TIME}s")
            return _LOCAL_MODEL
        except Exception as e:
            _MODEL_STATUS = "error"
            _MODEL_LOAD_ERROR = str(e)
            logger.error(f"Failed to load local Whisper model: {e}")
            raise


def warm_up_local_whisper_in_background():
    """Trigger background loading of the local Whisper model on startup."""
    global _IS_WARMING_UP
    if _LOCAL_MODEL is not None or _IS_WARMING_UP:
        return

    _IS_WARMING_UP = True

    def _worker():
        global _IS_WARMING_UP
        try:
            get_local_whisper_model()
        except Exception as err:
            logger.warning(f"Background warm-up encountered: {err}")
        finally:
            _IS_WARMING_UP = False

    t = threading.Thread(target=_worker, daemon=True, name="whisper-warmup-thread")
    t.start()
    logger.info("Initiated background pre-warming of local Whisper model.")


def _cuda_device_count() -> int:
    """Number of CUDA devices CTranslate2 can see (0 when none or when the probe fails)."""
    try:
        import ctranslate2
        return int(ctranslate2.get_cuda_device_count())
    except Exception:
        return 0


def get_engine_status() -> Dict[str, Any]:
    """Return status and diagnostics for the local whisper engine."""
    model_dir = get_model_path()
    has_weights = os.path.isfile(os.path.join(model_dir, "model.bin"))
    weight_size_mb = 0.0
    if has_weights:
        weight_size_mb = round(os.path.getsize(os.path.join(model_dir, "model.bin")) / (1024 * 1024), 2)

    return {
        "status": _MODEL_STATUS,
        "is_loaded": _LOCAL_MODEL is not None,
        "model_dir": model_dir,
        "model_name": os.path.basename(model_dir),
        "weights_present": has_weights,
        "weights_size_mb": weight_size_mb,
        "load_time_sec": _MODEL_LOAD_TIME,
        "error": _MODEL_LOAD_ERROR,
        "device": _MODEL_DEVICE.get(model_dir, "not loaded"),
        "cuda_devices": _cuda_device_count(),
        "compute_type": "int8" if _MODEL_DEVICE.get(model_dir, "cpu") == "cpu" else "float16",
        "threads": get_optimal_cpu_threads()
    }


def normalize_language_code(lang: Optional[str]) -> Optional[str]:
    """Normalize user input language to faster-whisper language codes."""
    if not lang:
        return None
    l_str = str(lang).strip().lower()
    if l_str in ["auto", "detect", "auto-detect", "all", "none", ""]:
        return None
    if l_str in ["bn", "bangla", "bengali", "bn-bd", "bn-in", "বাংলা"]:
        return "bn"
    if l_str in ["en", "english", "en-us", "en-gb"]:
        return "en"
    return l_str[:2]


def convert_to_wav_pcm16k(media_input: Union[bytes, bytearray, io.BytesIO, str], input_hint: str = "webm") -> str:
    """
    Converts audio input to a temporary 16kHz mono 16-bit PCM WAV file via FFmpeg.
    Returns the file path. Caller must remove the file after use.
    If the audio input is already a 16kHz mono 16-bit PCM WAV, FFmpeg conversion is bypassed.
    """
    # 1. Fast check if media_input is already a 16kHz mono PCM WAV file on disk
    if isinstance(media_input, str) and os.path.isfile(media_input):
        _, ext = os.path.splitext(media_input.lower())
        if ext == ".wav":
            try:
                import wave
                with wave.open(media_input, "rb") as wf:
                    if wf.getnchannels() == 1 and wf.getframerate() == 16000 and wf.getsampwidth() == 2:
                        return media_input
            except Exception:
                pass

    temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_wav.close()

    # 2. Fast check if in-memory bytes are already a 16kHz mono PCM WAV
    raw_bytes = None
    if isinstance(media_input, io.BytesIO):
        raw_bytes = media_input.getvalue()
    elif isinstance(media_input, (bytes, bytearray)):
        raw_bytes = bytes(media_input)

    if raw_bytes and len(raw_bytes) >= 44 and raw_bytes[:4] == b"RIFF" and raw_bytes[8:12] == b"WAVE":
        try:
            import wave
            with wave.open(io.BytesIO(raw_bytes), "rb") as wf:
                if wf.getnchannels() == 1 and wf.getframerate() == 16000 and wf.getsampwidth() == 2:
                    with open(temp_wav.name, "wb") as f:
                        f.write(raw_bytes)
                    return temp_wav.name
        except Exception:
            pass

    temp_in = None
    try:
        if isinstance(media_input, str) and os.path.isfile(media_input):
            input_path = media_input
        else:
            ext = f".{input_hint.lstrip('.')}" if input_hint else ".webm"
            temp_in_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            if raw_bytes is not None:
                temp_in_file.write(raw_bytes)
            elif isinstance(media_input, io.BytesIO):
                temp_in_file.write(media_input.getvalue())
            elif isinstance(media_input, (bytes, bytearray)):
                temp_in_file.write(media_input)
            temp_in_file.close()
            temp_in = temp_in_file.name
            input_path = temp_in

        try:
            import media_processor
            ffmpeg_bin = media_processor.find_ffmpeg_binary() or "ffmpeg"
        except Exception:
            ffmpeg_bin = "ffmpeg"

        cmd = [
            ffmpeg_bin, "-y", "-nostdin", "-loglevel", "error",
            "-i", input_path,
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            temp_wav.name
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
        if res.returncode == 0 and os.path.exists(temp_wav.name) and os.path.getsize(temp_wav.name) > 0:
            return temp_wav.name
    except Exception as e:
        logger.warning(f"FFmpeg conversion notice: {e}")
    finally:
        if temp_in and os.path.exists(temp_in):
            try:
                os.remove(temp_in)
            except Exception:
                pass

    # If conversion failed, fallback to direct temp file
    if isinstance(media_input, (bytes, bytearray, io.BytesIO)):
        data = media_input.getvalue() if isinstance(media_input, io.BytesIO) else media_input
        with open(temp_wav.name, "wb") as f:
            f.write(data)
    elif isinstance(media_input, str) and os.path.isfile(media_input):
        return media_input

    return temp_wav.name


def slice_wav_pcm16k(source_wav: str, start_sec: float, duration_sec: float, target_wav: str) -> bool:
    """Extracts a slice from a 16kHz mono 16-bit PCM WAV file without re-encoding."""
    try:
        import wave
        with wave.open(source_wav, "rb") as r:
            framerate = r.getframerate() or 16000
            total_frames = r.getnframes()
            start_frame = min(total_frames, int(start_sec * framerate))
            dur_frames = min(total_frames - start_frame, int(duration_sec * framerate))
            if dur_frames <= 0:
                return False
            r.setpos(start_frame)
            frames = r.readframes(dur_frames)
            with wave.open(target_wav, "wb") as w:
                w.setnchannels(r.getnchannels())
                w.setsampwidth(r.getsampwidth())
                w.setframerate(framerate)
                w.writeframes(frames)
        return True
    except Exception as e:
        logger.warning(f"Error slicing WAV file: {e}")
        return False


# Segments whose average token log-probability is below this are almost always
# hallucinations (off-script gibberish) rather than real speech.
_MIN_SEGMENT_AVG_LOGPROB = -1.5
# Window size used to split a code-switched slice into per-language runs.
_CODE_SWITCH_WINDOW_SEC = 30.0


def _plan_code_switched_runs(
    model: Any,
    slice_wav_path: str,
    slice_duration_sec: float,
    candidates: List[str],
    ctx: str = ""
) -> List[Tuple[float, float, Optional[str]]]:
    """
    Splits a code-switched slice into consecutive ~30s windows, resolves each window to one
    of the slice's candidate languages, and merges neighbouring windows with the same language.
    Returns: [(offset_sec, duration_sec, language), ...] relative to the slice start.
    """
    try:
        import faster_whisper
        audio = faster_whisper.decode_audio(slice_wav_path)
    except Exception as e:
        logger.warning(f"{ctx} could not decode slice for window detection ({type(e).__name__}: {e}); "
                       f"using '{candidates[0]}' for the whole slice")
        return [(0.0, slice_duration_sec, candidates[0])]

    sr = 16000
    win = int(_CODE_SWITCH_WINDOW_SEC * sr)
    runs: List[Tuple[float, float, Optional[str]]] = []
    for w_start in range(0, len(audio), win):
        window = audio[w_start:w_start + win]
        if len(window) < sr:  # under 1s: attach to the previous run
            break
        lang = _resolve_window_language(model, window, candidates, f"{ctx}[{w_start / sr:.0f}s]")
        off, dur = w_start / sr, len(window) / sr
        if runs and runs[-1][2] == lang:
            p_off, p_dur, _ = runs[-1]
            runs[-1] = (p_off, p_dur + dur, lang)
        else:
            runs.append((off, dur, lang))
    if runs:
        last_off, _, last_lang = runs[-1]
        runs[-1] = (last_off, max(0.0, slice_duration_sec - last_off), last_lang)
    else:
        runs = [(0.0, slice_duration_sec, candidates[0])]
    logger.info(f"{ctx} code-switched slice split into {len(runs)} run(s): "
                + ", ".join(f"{o:.0f}s+{d:.0f}s={l}" for o, d, l in runs))
    return runs


# If 30s-block VAD finds this many more seconds (or >5%) of speech than whole-slice VAD, the
# Silero LSTM state was saturated by a long noise/silence stretch and would silently
# drop real speech after it - transcribe that slice without VAD instead.
_VAD_MISS_TOLERANCE_SEC = 3.0


def _vad_is_reliable_for(audio_path: str, ctx: str = "") -> bool:
    """
    Cross-checks Silero VAD on one slice: whole-slice pass vs. independent 30s blocks.
    Validated on a real recording with 150s of silence + noise before speech, where the
    whole-slice pass returned 0s of the following speech (see test_whisper_language_and_vad.py).
    Returns False (-> disable VAD for this slice) when the whole-slice pass misses speech.
    """
    try:
        import faster_whisper
        from faster_whisper.vad import get_speech_timestamps, VadOptions
        audio = faster_whisper.decode_audio(audio_path)
        opts = VadOptions(**WHISPER_VAD_PARAMETERS)
        sr = 16000
        whole = sum((t["end"] - t["start"]) / sr for t in get_speech_timestamps(audio, opts))
        blocks = 0.0
        step = 30 * sr
        for b in range(0, len(audio), step):
            block = audio[b:b + step]
            if len(block) >= sr // 2:
                blocks += sum((t["end"] - t["start"]) / sr for t in get_speech_timestamps(block, opts))
        # block edges add a little padding, so allow 3s or 5% of the detected speech, whichever is larger
        reliable = (blocks - whole) <= max(_VAD_MISS_TOLERANCE_SEC, 0.05 * whole)
        (logger.info if reliable else logger.warning)(
            f"{ctx} VAD cross-check: whole-slice speech={whole:.1f}s, 30s-block speech={blocks:.1f}s -> "
            f"{'VAD on' if reliable else 'VAD OFF for this slice (whole-slice pass would drop speech)'}")
        return reliable
    except Exception as e:
        logger.warning(f"{ctx} VAD cross-check failed ({type(e).__name__}: {e}) - VAD off for this slice")
        return False


def transcribe_local_audio(
    media_input: Union[bytes, bytearray, io.BytesIO, str],
    language: Optional[str] = None,
    prompt: Optional[str] = None,
    beam_size: int = 5,
    temperature: float = 0.0,
    mime_type: str = "audio/webm",
    model_name: Optional[str] = None,
    _is_fallback_retry: bool = False
) -> Dict[str, Any]:
    """
    Transcribe audio using the embedded local faster-whisper model.
    
    Args:
        media_input: Raw audio bytes, BytesIO buffer, or path to audio file.
        language: Language code ('bn', 'en') or None/'auto' for unforced auto-detection.
        prompt: Optional initial prompt to steer bilingual context.
        beam_size: 1 for fastest live streaming, 2 for multi-take batch accuracy.
        temperature: Sampling temperature (default 0.0 for greedy decoding).
        mime_type: MIME type hint for audio container.
        model_name: 'small' or 'base'
        
    Returns:
        Dict with 'status', 'text', 'raw_transcript', 'clean_text', 'language', 'duration', etc.
    """
    if not media_input:
        return {
            "status": "success",
            "text": "",
            "raw_transcript": "",
            "clean_text": "",
            "language": "auto",
            "segments": []
        }

    if isinstance(media_input, (bytes, bytearray)) and len(media_input) < 32:
        return {
            "status": "success",
            "text": "",
            "raw_transcript": "",
            "clean_text": "",
            "language": "auto",
            "segments": []
        }

    t_start = time.time()
    effective_model, _model_source = resolve_whisper_model_choice(model_name)
    _in_desc = (f"file={os.path.basename(media_input)}" if isinstance(media_input, str)
                else f"bytes={len(media_input.getvalue() if isinstance(media_input, io.BytesIO) else media_input) / 1048576:.2f}MB")
    logger.info(f"transcribe_local_audio START {_in_desc} mime={mime_type} lang={language!r} model={effective_model} ({_model_source}) "
                f"path={get_model_path(effective_model)} weights={_model_has_weights(get_model_path(effective_model))} "
                f"ram={get_system_ram_specs()} status={_MODEL_STATUS}")
    try:
        model = get_local_whisper_model(effective_model)
    except Exception as _load_err:
        logger.error(f"transcribe_local_audio MODEL LOAD FAILED after {time.time() - t_start:.1f}s: "
                     f"{type(_load_err).__name__}: {_load_err}")
        raise

    # Determine input extension hint
    hint = "webm"
    if "mp3" in (mime_type or ""):
        hint = "mp3"
    elif "wav" in (mime_type or ""):
        hint = "wav"
    elif "mp4" in (mime_type or ""):
        hint = "mp4"
    elif "ogg" in (mime_type or ""):
        hint = "ogg"

    # Convert audio to clean 16kHz mono WAV file
    _cv0 = time.time()
    temp_audio_file = convert_to_wav_pcm16k(media_input, input_hint=hint)
    try:
        _wav_sz = os.path.getsize(temp_audio_file)
    except Exception:
        _wav_sz = -1
    logger.info(f"  WAV conversion {time.time() - _cv0:.1f}s -> {os.path.basename(str(temp_audio_file))} ({_wav_sz / 1048576:.2f} MB)")

    # Check if a specific language was explicitly requested
    explicit_lang = normalize_language_code(language)

    # Whole-file detection is only a PRIOR (it picks the initial_prompt). Each slice below
    # gets its own detection so one early guess can't force the whole file into one language.
    prior: Dict[str, Any] = {}
    if explicit_lang is None:
        prior = detect_audio_language_detail(model, temp_audio_file, _ctx="[whisper file-prior]")
        target_language = prior.get("language")
    else:
        target_language = explicit_lang
        logger.info(f"Language forced by caller: '{explicit_lang}' (per-slice detection disabled)")

    if prompt:
        init_prompt = prompt
    elif prior.get("ambiguous") and set(prior.get("candidates", [])) >= {"bn", "en"}:
        init_prompt = DEFAULT_BILINGUAL_PROMPT
    elif target_language == "bn":
        init_prompt = "Ajker meeting er alochna ebong karjobiboroni. Agenda, budget, review, decisions."
    elif target_language == "en":
        init_prompt = "Meeting discussion and proceedings in English verbatim. Agenda, budget, review, action items."
    else:
        init_prompt = "Verbatim speech transcription with timestamps and speaker tags."

    import wave, math, gc

    total_duration_sec = 0.0
    try:
        with wave.open(temp_audio_file, "rb") as wf:
            framerate = wf.getframerate() or 16000
            total_duration_sec = wf.getnframes() / float(framerate)
    except Exception:
        total_duration_sec = 0.0

    # For long audio (> 240 seconds / 4 minutes), slice into 180s chunks to prevent
    # 'Unable to allocate 370. MiB' STFT contiguous memory errors on Windows.
    chunk_size = 180.0
    if total_duration_sec > 240.0:
        chunk_slices = []
        n_chunks = math.ceil(total_duration_sec / chunk_size)
        for c_idx in range(n_chunks):
            c_start = c_idx * chunk_size
            c_dur = min(chunk_size, total_duration_sec - c_start)
            chunk_slices.append((c_start, c_dur))
        logger.info(f"Long audio detected ({total_duration_sec:.1f}s). Processing in {len(chunk_slices)} chunks of {chunk_size}s.")
    else:
        chunk_slices = [(0.0, total_duration_sec)]

    loaded_model_name = get_loaded_model_name(model)
    logger.info(f"transcribe_local_audio using model={loaded_model_name} (requested={effective_model!r}) "
                f"vad=on(cross-checked per slice) params={WHISPER_VAD_PARAMETERS} beam={beam_size or 1}")

    try:
        formatted_lines = []
        raw_text_parts = []
        segments_data = []
        current_spk = 1
        last_end = 0.0
        last_clean_text = ""
        detected_whisper_lang = target_language
        detected_whisper_prob = 1.0
        slice_languages: List[str] = []

        for slice_idx, (chunk_start_sec, chunk_dur_sec) in enumerate(chunk_slices):
            chunk_temp_wav = None
            if len(chunk_slices) > 1:
                chunk_temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                chunk_temp_file.close()
                chunk_temp_wav = chunk_temp_file.name
                sliced = slice_wav_pcm16k(temp_audio_file, chunk_start_sec, chunk_dur_sec, chunk_temp_wav)
                input_to_transcribe = chunk_temp_wav if sliced else temp_audio_file
            else:
                input_to_transcribe = temp_audio_file

            slice_ctx = f"[whisper slice {slice_idx + 1}/{len(chunk_slices)} @{chunk_start_sec:.0f}s]"
            _sl0 = time.time()
            _seen = _drop_nospeech = _drop_lowconf = _drop_loop = _drop_sanitize = _drop_dup = _kept = 0
            run_temp_files: List[str] = []
            try:
                # 1. Decide the language(s) for this slice
                if explicit_lang is not None:
                    runs = [(0.0, chunk_dur_sec, explicit_lang)]
                else:
                    det = prior if len(chunk_slices) == 1 else detect_audio_language_detail(
                        model, input_to_transcribe, _ctx=slice_ctx)
                    if not det.get("language"):
                        runs = [(0.0, chunk_dur_sec, None)]  # let Whisper auto-detect
                    elif det.get("ambiguous"):
                        runs = _plan_code_switched_runs(model, input_to_transcribe, chunk_dur_sec,
                                                        det["candidates"], slice_ctx)
                    else:
                        runs = [(0.0, chunk_dur_sec, det["language"])]
                slice_languages.append("+".join(sorted({r[2] or "auto" for r in runs})))
                use_vad = _vad_is_reliable_for(input_to_transcribe, slice_ctx)

                # 2. Transcribe each language run of this slice
                for run_off, run_dur, run_lang in runs:
                    if len(runs) == 1:
                        run_input = input_to_transcribe
                    else:
                        run_tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                        run_tmp.close()
                        run_temp_files.append(run_tmp.name)
                        run_input = run_tmp.name if slice_wav_pcm16k(input_to_transcribe, run_off, run_dur, run_tmp.name) \
                            else input_to_transcribe
                    with _TRANSCRIBE_LOCK:
                        segments, info = model.transcribe(
                            run_input,
                            task="transcribe",
                            beam_size=beam_size or 1,
                            best_of=1,
                            temperature=0.0,
                            initial_prompt=init_prompt,
                            language=run_lang,
                            condition_on_previous_text=False,
                            vad_filter=use_vad,
                            vad_parameters=WHISPER_VAD_PARAMETERS if use_vad else None,
                            no_speech_threshold=0.6,
                            compression_ratio_threshold=2.4
                        )

                    if detected_whisper_lang is None and hasattr(info, "language"):
                        detected_whisper_lang = info.language
                        detected_whisper_prob = getattr(info, "language_probability", 1.0)
                    seg_lang = run_lang or getattr(info, "language", None) or target_language

                    for segment in segments:
                        _seen += 1
                        raw_text = (segment.text or "").strip()
                        if not raw_text:
                            _drop_sanitize += 1
                            continue

                        # Confidence gating BEFORE the regex sanitizer (Whisper's own signals)
                        no_speech = getattr(segment, "no_speech_prob", 0.0) or 0.0
                        avg_logprob = getattr(segment, "avg_logprob", 0.0) or 0.0
                        comp_ratio = getattr(segment, "compression_ratio", 0.0) or 0.0
                        if no_speech > 0.95 or (no_speech > 0.6 and avg_logprob < -1.0):
                            _drop_nospeech += 1
                            logger.debug(f"{slice_ctx} drop no_speech={no_speech:.2f} logprob={avg_logprob:.2f}: {raw_text[:60]!r}")
                            continue
                        if avg_logprob < _MIN_SEGMENT_AVG_LOGPROB:
                            _drop_lowconf += 1
                            logger.debug(f"{slice_ctx} drop low-confidence logprob={avg_logprob:.2f}: {raw_text[:60]!r}")
                            continue
                        if comp_ratio > 2.4:
                            _drop_loop += 1
                            logger.debug(f"{slice_ctx} drop repetition loop compression={comp_ratio:.2f}: {raw_text[:60]!r}")
                            continue

                        # Sanitize text: collapse repetition loops, strip foreign-script hallucinations
                        text = sanitize_whisper_text(raw_text, language=seg_lang)
                        if not text:
                            _drop_sanitize += 1
                            logger.debug(f"{slice_ctx} drop sanitized-empty lang={seg_lang}: {raw_text[:60]!r}")
                            continue

                        # Deduplicate consecutive identical segments
                        if text == last_clean_text:
                            _drop_dup += 1
                            continue
                        _kept += 1

                        abs_start = chunk_start_sec + run_off + segment.start
                        abs_end = chunk_start_sec + run_off + segment.end

                        # Detect conversational turn shifts when speech pause > 1.6s
                        if last_end > 0 and (abs_start - last_end) > 1.6:
                            current_spk = 2 if current_spk == 1 else 1

                        timestamp_str = format_seconds_to_min_sec(abs_start)
                        line = f"[{timestamp_str}] Speaker {current_spk}: {text}"
                        formatted_lines.append(line)
                        raw_text_parts.append(text)
                        last_end = abs_end
                        last_clean_text = text
                        segments_data.append({
                            "start": round(abs_start, 2),
                            "end": round(abs_end, 2),
                            "text": text,
                            "speaker": f"Speaker {current_spk}",
                            "timestamp": f"[{timestamp_str}]",
                            "language": seg_lang
                        })
            finally:
                logger.info(f"  slice {slice_idx + 1}/{len(chunk_slices)} @{chunk_start_sec:.0f}s+{chunk_dur_sec:.0f}s "
                            f"lang={slice_languages[-1] if slice_languages else '?'} took {time.time() - _sl0:.1f}s: "
                            f"segments={_seen} kept={_kept} dropped(no_speech={_drop_nospeech}, "
                            f"low_logprob={_drop_lowconf}, loop={_drop_loop}, sanitized_empty={_drop_sanitize}, "
                            f"dup={_drop_dup})")
                for tmp_path in run_temp_files + ([chunk_temp_wav] if chunk_temp_wav else []):
                    if tmp_path and os.path.exists(tmp_path):
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
                gc.collect()

        # Dual-pass resilience: If a specific language was requested (e.g. 'bn') but produced
        # zero valid speech segments, automatically fall back to unforced auto-detection
        # so spoken dialogue in another language (English, bilingual code-switching) is never lost.
        if not formatted_lines and not _is_fallback_retry and explicit_lang is not None:
            logger.info(f"Forced language '{language}' yielded no speech output. Retrying with unforced automatic language detection...")
            return transcribe_local_audio(
                media_input=media_input,
                language=None,
                prompt=prompt,
                beam_size=beam_size,
                temperature=temperature,
                mime_type=mime_type,
                model_name=model_name,
                _is_fallback_retry=True
            )

        elapsed = round(time.time() - t_start, 2)
        logger.info(f"transcribe_local_audio END in {elapsed}s: audio={total_duration_sec:.1f}s lines={len(formatted_lines)} "
                    f"(RTF={elapsed / total_duration_sec if total_duration_sec else 0:.2f})")
        speaker_transcript = "\n".join(formatted_lines)
        clean_text = " ".join(raw_text_parts)

        # Primary verbatim output in user's requested format: [MM:SS] Speaker X: <text>
        raw_transcript_final = speaker_transcript.strip()
        if not raw_transcript_final and clean_text:
            raw_transcript_final = f"[00:00] Speaker 1: {clean_text}"

        try:
            if raw_transcript_final:
                with open("raw_transcript.txt", "w", encoding="utf-8") as f:
                    f.write(raw_transcript_final)
        except Exception as io_err:
            logger.warning(f"Could not save raw_transcript.txt: {io_err}")

        detected_lang = target_language or explicit_lang or detected_whisper_lang or "auto"
        if clean_text:
            import re
            bengali_chars = len(re.findall(r'[\u0980-\u09FF]', clean_text))
            latin_chars = len(re.findall(r'[a-zA-Z]', clean_text))
            if bengali_chars > 0 and bengali_chars >= latin_chars * 0.15:
                detected_lang = "bn"
            elif detected_lang != "bn" and latin_chars > 0 and bengali_chars == 0:
                detected_lang = "en"
        duration_sec = total_duration_sec or 0.0

        return {
            "status": "success",
            "provider": "local_whisper",
            "model": loaded_model_name,
            "slice_languages": slice_languages,
            "text": raw_transcript_final,
            "raw_transcript": raw_transcript_final,
            "transcript": raw_transcript_final,
            "soak_transcript": raw_transcript_final,
            "speaker_transcript": speaker_transcript,
            "clean_text": clean_text,
            "language": detected_lang,
            "detected_language": detected_lang,
            "duration": round(float(duration_sec), 2),
            "segments": segments_data,
            "segments_count": len(segments_data),
            "processing_time_sec": elapsed
        }

    except Exception as e:
        logger.error(f"Error during local whisper transcription after {time.time() - t_start:.1f}s: "
                     f"{type(e).__name__}: {e}", exc_info=True)
        return {
            "status": "error",
            "provider": "local_whisper",
            "detail": f"Local Whisper error: {str(e)}",
            "text": "",
            "raw_transcript": "",
            "transcript": "",
            "clean_text": "",
            "language": "auto",
            "segments": []
        }
    finally:
        if temp_audio_file and os.path.exists(temp_audio_file) and temp_audio_file != media_input:
            try:
                os.remove(temp_audio_file)
            except Exception:
                pass


def test_local_engine() -> Dict[str, Any]:
    """Test local whisper engine diagnostics."""
    status = get_engine_status()
    if not status["weights_present"]:
        return {
            "status": "error",
            "message": f"Whisper weights not found in {status['model_dir']}.",
            "diagnostics": status
        }

    try:
        model = get_local_whisper_model()
        updated_status = get_engine_status()
        return {
            "status": "success",
            "message": f"Local Whisper Engine ({updated_status['model_name']} INT8) is READY. Loaded in {updated_status['load_time_sec']}s",
            "diagnostics": updated_status
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to initialize local Whisper: {str(e)}",
            "diagnostics": status
        }


def transcribe_default_whisper(
    audio_path: str = "interview_input.mp3",
    model_size: Optional[str] = None,
    beam_size: int = 5,
    output_path: str = "raw_transcript.txt"
) -> str:
    """
    Standard default Whisper execution code with system-capacity adaptation:
    from faster_whisper import WhisperModel
    # Dynamically select model size based on system RAM / hardware capacity:
    # >= 16GB RAM -> 'medium'
    # 8-16GB RAM  -> 'small'
    # 4-8GB RAM   -> 'base'
    # < 4GB RAM   -> 'tiny'
    effective_model = model_size or select_optimal_model_name()
    model = WhisperModel(effective_model, device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, beam_size=5)
    Combine segments with context anchor point timestamps: [start.2fs - end.2fs] text
    Save raw transcript to raw_transcript.txt
    """
    from faster_whisper import WhisperModel

    chosen_model = model_size if model_size and model_size != "auto" else select_optimal_model_name()
    resolved = get_model_path(chosen_model)
    target = resolved if (isinstance(resolved, str) and os.path.exists(resolved)) else chosen_model

    try:
        model = WhisperModel(target, device="cpu", compute_type="int8")
    except Exception as err:
        logger.warning(f"Could not initialize '{target}' with int8 ({err}), using optimal local model.")
        fallback = get_model_path()
        model = WhisperModel(fallback, device="cpu", compute_type="int8")

    print(f"Transcribing audio file ({audio_path})...")
    segments, info = model.transcribe(audio_path, beam_size=beam_size)

    # Combine segments into a structured layout ready for your SOAK template
    transcript_text = ""
    current_spk = 1
    last_end = 0.0
    for segment in segments:
        clean_seg_text = sanitize_whisper_text(segment.text or "")
        if not clean_seg_text:
            continue
        # Autodetect conversational turn shifts based on speech pause (> 1.8s)
        if last_end > 0 and (segment.start - last_end) > 1.8:
            current_spk = 2 if current_spk == 1 else 1
        # Captures timestamps to maintain context anchor points in min and sec
        start_ts = format_seconds_to_min_sec(segment.start)
        end_ts = format_seconds_to_min_sec(segment.end)
        transcript_text += f"[{start_ts} - {end_ts}] Speaker {current_spk}: {clean_seg_text}\n"
        last_end = segment.end

    # Save the raw transcript if non-empty
    if transcript_text.strip():
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(transcript_text)

    print(f"Transcription complete! Saved to {output_path}.")
    return transcript_text

