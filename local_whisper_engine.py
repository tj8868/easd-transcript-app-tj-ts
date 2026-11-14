"""
Local Whisper Engine (Offline, Zero-Cost, Embedded STT)
Powered by faster-whisper (CTranslate2) with INT8 quantization on CPU.
Optimized for EASD Meeting Minutes (Bangla and English bilingual speech).
"""

import functools
import os
import re
import sys
import io
import time
import logging
import tempfile
import threading
import subprocess
from typing import Optional, Dict, Any, Union, List, Tuple

def get_optimal_cpu_threads() -> int:
    """CPU threads for faster-whisper: all cores but one, at most 3 (more thrashes small CPUs).
    psutil is optional; without it the old code silently fell back to 1 thread (~3x slower)."""
    cores = os.cpu_count() or 4
    avail_gb = None
    try:
        import psutil
        avail_gb = psutil.virtual_memory().available / (1024 ** 3)
    except Exception:
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        avail_gb = int(line.split()[1]) / (1024 ** 2)
                        break
        except Exception:
            pass
    if avail_gb is not None and avail_gb < 0.5:
        return 1
    return max(1, min(cores - 1, 3))


# Progress hook for long transcriptions. stt_pipeline sets it per chunk; transcribe_local_audio calls
# it before and after every slice so the UI keeps moving instead of sitting on one percentage.
# Signature: callback(slices_done: int, slices_total: int, note: str).
import contextvars
progress_callback: "contextvars.ContextVar" = contextvars.ContextVar("whisper_progress_callback", default=None)


def _report_progress(done: int, total: int, note: str = "") -> None:
    cb = progress_callback.get()
    if cb is not None:
        try:
            cb(done, total, note)
        except Exception:
            pass

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
_TURBO_MODEL_DIR = os.path.join(_BASE_DIR, "models", "whisper-large-v3-turbo")
# Default local model: BengaliAI's Whisper-medium fine-tuned on Bangla speech (regional dialects),
# CTranslate2 format. Writes Bengali script. Best open Bangla result in arXiv 2602.21741.
_BENGALIAI_MODEL_DIR = os.path.join(_BASE_DIR, "models", "whisper-bengaliai")
_BENGALIAI_REPO = "IamSanjid/tugstugi_bengaliai-regional-asr_whisper-medium-ct2"
_TURBO_REPO = "deepdml/faster-whisper-large-v3-turbo"

_DEFAULT_MODEL_DIR = _BENGALIAI_MODEL_DIR

# v9.0 Bangla/English switching (docs/designs/bilingual_local_transcription.md). whisper-bengaliai
# only writes Bangla, so English speech stretches go to small.en, and a detector model tags each
# stretch Bangla or English. Each model is downloaded once into models/ (never a per-user cache).
#   kind -> (folder, Hugging Face repo)
_AUX_MODELS: Dict[str, Tuple[str, str]] = {
    "en": (os.path.join(_BASE_DIR, "models", "whisper-small.en"), "Systran/faster-whisper-small.en"),
    "tiny": (os.path.join(_BASE_DIR, "models", "whisper-tiny"), "Systran/faster-whisper-tiny"),
    "base": (os.path.join(_BASE_DIR, "models", "whisper-base"), "Systran/faster-whisper-base"),
}
_CS_DETECTORS = ("bengaliai", "tiny", "base")
_AUX_DOWNLOAD_FAILED: Dict[str, str] = {}  # kind -> reason; not retried until the app restarts
_AUX_DOWNLOAD_LOCK = threading.Lock()
_EN_PROMPT = "Meeting discussion and proceedings in English verbatim. Agenda, budget, review, action items."

_LOCAL_MODELS: Dict[str, Any] = {}
_LOCAL_MODEL = None
_MODEL_LOCK = threading.Lock()
_TRANSCRIBE_LOCK = threading.Lock()
_IS_WARMING_UP = False
_MODEL_STATUS = "unloaded"  # unloaded | loading | ready | error
_MODEL_LOAD_ERROR = None
_MODEL_LOAD_TIME = 0.0

# Bilingual initial_prompt for Whisper's decoder to steer code-switched
# Bangla-English output.  Contains real Bengali script mixed with English
# terminology so Whisper learns to keep each language in its native script.
# This text is NEVER shown in the transcript — it only conditions the
# decoder's first 224 tokens via faster-whisper's `initial_prompt` arg.
DEFAULT_BILINGUAL_PROMPT = (
    "আজকের meeting এর agenda এবং আলোচনা। "
    "Budget review তে participants সবাই present ছিলেন। "
    "Action items ঠিক করা হয়েছে, decisions finalize হয়েছে। "
    "Proceedings verbatim transcription with speaker tags."
)


# Languages Whisper's detector routinely confuses with Bengali on South-Asian speech.
# Bengali is only preferred over one of these when the two are genuinely close.
_BN_CONFUSABLE_LANGS = ("hi", "ne", "ur", "as")
def _max_compression(lang: Optional[str]) -> float:
    """Repetition-loop cut-off. Normal Bengali text already compresses to ~2.4 (3-byte UTF-8
    characters sharing lead bytes), so 2.4 dropped real Bangla speech; loops score far higher."""
    return 3.0 if lang == "bn" else 2.4


# A slice is decoded as English only when the detector gives "en" at least this probability;
# otherwise it is Bangla (env EASD_WHISPER_EN_CONFIDENCE).
_EN_CONFIDENT = float(os.environ.get("EASD_WHISPER_EN_CONFIDENCE", "0.5"))
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
        # EASD meetings are only ever Bangla or English. On Bangla speech Whisper's detector
        # often ranks ko/ja/jw/pt/... first, and decoding as those writes Bangla in Latin
        # letters. So the choice is bn vs en: English only when the detector is confident.
        prob_en = probs.get("en", 0.0)
        if prob_en >= _EN_CONFIDENT:
            language, confidence, reason = "en", prob_en, f"en p>={_EN_CONFIDENT}"
        else:
            language, confidence = "bn", probs.get("bn", 0.0) + sum(probs.get(c, 0.0) for c in _BN_CONFUSABLE_LANGS)
            reason = f"bn (meeting languages are bn/en; en p={prob_en:.2f} < {_EN_CONFIDENT})"
        ambiguous = 0.15 <= prob_en < _EN_CONFIDENT  # mixed slice: decode per window as bn or en
        result.update(language=language, confidence=float(confidence), ambiguous=ambiguous,
                      reason=reason, ranked=[(k, round(float(v), 4)) for k, v in ranked],
                      candidates=["bn", "en"] if ambiguous else [language])

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

def _bn_en_scores(probs: Dict[str, float], candidates: Any) -> Dict[str, float]:
    """Scores for the candidate languages. Bengali absorbs its confusables (hi/ne/ur/as) so a
    Bangla window or stretch is never decoded as Hindi."""
    return {cand: probs.get(cand, 0.0) + (sum(probs.get(c, 0.0) for c in _BN_CONFUSABLE_LANGS)
                                          if cand == "bn" else 0.0)
            for cand in candidates}


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
    scores = _bn_en_scores(dict(all_probs or []), candidates)
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
    'large-v3-turbo' on an NVIDIA GPU (disable with EASD_WHISPER_GPU_TURBO=0), else 'bengaliai'.
    The small multilingual models (tiny/base/small) were removed in v8.9: on Bangla meeting audio
    they produced only repetition loops or Latin-script text.
    """
    if os.environ.get("EASD_WHISPER_GPU_TURBO", "1") != "0" and _select_compute_device()[0] == "cuda":
        name, why = "large-v3-turbo", "CUDA GPU detected"
    else:
        name, why = "bengaliai", "default Bangla model"
    if _LAST_AUTO_CHOICE.get("name") != name:
        logger.info(f"select_optimal_model_name -> '{name}' ({why})")
        _LAST_AUTO_CHOICE["name"] = name
    return name


_KNOWN_MODEL_SIZES = ("bengaliai", "large-v3-turbo")


def resolve_whisper_model_choice(requested: Optional[str] = None) -> Tuple[str, str]:
    """
    'turbo' in the request -> large-v3-turbo; anything else (including the removed tiny/base/small/
    medium/banglish choices saved in old settings) -> automatic selection.
    Returns: (model_name, source) where source is 'explicit' or 'auto'.
    """
    req = (requested or "").strip().lower()
    if "turbo" in req:
        return "large-v3-turbo", "explicit"
    if "bengaliai" in req:
        return "bengaliai", "explicit"
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
    """Directory of the model to load (weights are downloaded on first use)."""
    name = resolve_whisper_model_choice(preferred_name)[0]
    return _TURBO_MODEL_DIR if name == "large-v3-turbo" else _BENGALIAI_MODEL_DIR


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
    n_gpu = _cuda_device_count()
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

        if not _model_has_weights(resolved_path):
            repo = _TURBO_REPO if resolved_path == _TURBO_MODEL_DIR else _BENGALIAI_REPO
            logger.info(f"Downloading local Whisper model {repo} (one time) to '{resolved_path}'...")
            try:
                from huggingface_hub import snapshot_download
                snapshot_download(repo, local_dir=resolved_path)
            except Exception as dl_err:
                _MODEL_STATUS = "error"
                _MODEL_LOAD_ERROR = f"Model download failed: {dl_err}"
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
        # One-time download of the Bangla/English switching models (no-op when already in models/).
        if code_switch_enabled():
            try:
                ensure_code_switch_models()
            except Exception as err:
                logger.warning(f"Bangla/English switching models not prepared: {err}")

    t = threading.Thread(target=_worker, daemon=True, name="whisper-warmup-thread")
    t.start()
    logger.info("Initiated background pre-warming of local Whisper model.")


@functools.lru_cache(maxsize=1)
def _cuda_device_count() -> int:
    """Number of CUDA devices CTranslate2 can see (0 when none or when the probe fails). Probed once."""
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
        "threads": get_optimal_cpu_threads(),
        "code_switch": code_switch_status(),
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


def _mime_to_hint(mime_type: Optional[str]) -> str:
    """Container hint for FFmpeg from a MIME type (webm when unknown)."""
    mime = (mime_type or "").replace("mpeg", "mp3")
    return next((h for h in ("mp3", "wav", "mp4", "ogg") if h in mime), "webm")


def _finalize_result(segments_data: List[Dict[str, Any]], raw_text_parts: List[str], wav_path: str,
                     lang_hint: Optional[str], model_label: str, slice_languages: List[str],
                     duration_sec: float, elapsed: float) -> Dict[str, Any]:
    """Shared tail of every local Whisper backend: voice-based speaker labels, the
    "[MM:SS] Speaker N: text" transcript, language detection and the result dict."""
    import speaker_diarization
    if segments_data:
        labels = speaker_diarization.diarize_wav_segments(wav_path, segments_data) or [1] * len(segments_data)
        for seg, spk in zip(segments_data, labels):
            seg["speaker"] = f"Speaker {spk}"
    transcript = "\n".join(f"{seg['timestamp']} {seg['speaker']}: {seg['text']}" for seg in segments_data)
    clean_text = " ".join(raw_text_parts)

    # Debug copy only on request (EASD_DEBUG_SAVE_TRANSCRIPT=1), per job, in the temp folder -
    # never a shared file in the app folder.
    if transcript and os.environ.get("EASD_DEBUG_SAVE_TRANSCRIPT") == "1":
        try:
            dbg = os.path.join(tempfile.gettempdir(), f"easd_transcript_{int(time.time() * 1000)}.txt")
            with open(dbg, "w", encoding="utf-8") as f:
                f.write(transcript)
            logger.info(f"Debug transcript copy saved to {dbg}")
        except Exception as io_err:
            logger.warning(f"Could not save debug transcript copy: {io_err}")

    detected_lang = lang_hint or "auto"
    bengali_chars = len(re.findall(r'[\u0980-\u09FF]', clean_text))
    latin_chars = len(re.findall(r'[a-zA-Z]', clean_text))
    if bengali_chars > 0 and bengali_chars >= latin_chars * 0.15:
        detected_lang = "bn"
    elif detected_lang != "bn" and latin_chars > 0 and bengali_chars == 0:
        detected_lang = "en"
    return {
        "status": "success", "provider": "local_whisper", "model": model_label,
        "slice_languages": slice_languages, "text": transcript, "raw_transcript": transcript,
        "transcript": transcript, "soak_transcript": transcript, "speaker_transcript": transcript,
        "clean_text": clean_text, "language": detected_lang, "detected_language": detected_lang,
        "duration": round(float(duration_sec or 0.0), 2), "segments": segments_data,
        "segments_count": len(segments_data), "processing_time_sec": elapsed,
    }


# ---------------------------------------------------------------------------
# v9.0 Bangla/English switching for whisper-bengaliai
# (docs/designs/bilingual_local_transcription.md)
#
# Each 3-minute slice is split at pauses into speech stretches, a detector tags each stretch
# Bangla or English, and the resulting language runs go to whisper-bengaliai (Bangla) or
# small.en (English). Every failure falls back to today's Bangla-only decoding.
# Settings are read at call time so tests and scripts/measure_language_id.py can change them.
# ---------------------------------------------------------------------------

def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def code_switch_enabled() -> bool:
    """EASD_CODE_SWITCH: master switch (default off until measured on real meetings)."""
    return os.environ.get("EASD_CODE_SWITCH", "0").strip().lower() in ("1", "true", "on", "yes")


def code_switch_detector() -> str:
    """EASD_CS_DETECTOR: 'bengaliai' (the loaded Bangla model), 'tiny' or 'base' (default 'tiny')."""
    det = os.environ.get("EASD_CS_DETECTOR", "tiny").strip().lower()
    return det if det in _CS_DETECTORS else "tiny"


def ensure_aux_model(kind: str) -> bool:
    """Makes sure a switching model ('en', 'tiny', 'base') is in models/. Downloads it once if it
    is missing: into '<folder>.partial', renamed only when complete, so a broken download never
    counts as installed (the next attempt resumes it). No network call when already installed.
    A failed download is not retried until the app restarts. Never raises."""
    if kind not in _AUX_MODELS:
        return False
    final_dir, repo = _AUX_MODELS[kind]
    if _model_has_weights(final_dir):
        return True
    if kind in _AUX_DOWNLOAD_FAILED:
        return False
    with _AUX_DOWNLOAD_LOCK:
        if _model_has_weights(final_dir):
            return True
        if kind in _AUX_DOWNLOAD_FAILED:
            return False
        partial_dir = final_dir + ".partial"
        t0 = time.time()
        try:
            logger.info(f"Downloading {repo} (one time) to '{partial_dir}'...")
            from huggingface_hub import snapshot_download
            snapshot_download(repo, local_dir=partial_dir)
            if not _model_has_weights(partial_dir):
                raise RuntimeError("download finished without model weights")
            if os.path.isdir(final_dir):
                import shutil
                shutil.rmtree(final_dir)
            os.replace(partial_dir, final_dir)
            logger.info(f"Installed {repo} in '{final_dir}' ({time.time() - t0:.0f}s)")
            return True
        except Exception as e:
            _AUX_DOWNLOAD_FAILED[kind] = f"{type(e).__name__}: {e}"[:300]
            logger.warning(f"Download of {repo} failed ({_AUX_DOWNLOAD_FAILED[kind]}); "
                           f"Bangla/English switching stays off until the next app start")
            return False


def ensure_code_switch_models() -> Dict[str, bool]:
    """One-time download of the English model and the configured detector."""
    result = {"en": ensure_aux_model("en")}
    det = code_switch_detector()
    if det != "bengaliai":
        result[det] = ensure_aux_model(det)
    return result


def _load_aux_model(kind: str):
    """Loaded WhisperModel for a switching model, or None (missing weights / load error).
    Never downloads. Cached in _LOCAL_MODELS like the main model."""
    final_dir = _AUX_MODELS[kind][0]
    if final_dir in _LOCAL_MODELS:
        return _LOCAL_MODELS[final_dir]
    if not _model_has_weights(final_dir):
        return None
    with _MODEL_LOCK:
        if final_dir in _LOCAL_MODELS:
            return _LOCAL_MODELS[final_dir]
        t0 = time.time()
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel(final_dir, device="cpu", compute_type="int8",
                                 cpu_threads=get_optimal_cpu_threads(), local_files_only=True)
        except Exception as e:
            logger.warning(f"Could not load {os.path.basename(final_dir)} ({type(e).__name__}: {e})")
            return None
        _LOCAL_MODELS[final_dir] = model
        _MODEL_DEVICE[final_dir] = "cpu"
        logger.info(f"Loaded {os.path.basename(final_dir)} (cpu, int8) in {time.time() - t0:.1f}s")
        return model


def _code_switch_ready() -> Tuple[bool, str]:
    """(True, '') when switching can run now; otherwise (False, reason for the log)."""
    if not code_switch_enabled():
        return False, "EASD_CODE_SWITCH is off"
    det = code_switch_detector()
    needed = ["en"] + ([det] if det != "bengaliai" else [])
    for kind in needed:
        folder = _AUX_MODELS[kind][0]
        if not _model_has_weights(folder):
            why = f"{os.path.basename(folder)} is not installed"
            if kind in _AUX_DOWNLOAD_FAILED:
                why += f" (download failed: {_AUX_DOWNLOAD_FAILED[kind]})"
            return False, why
    if all(_AUX_MODELS[k][0] in _LOCAL_MODELS for k in needed):
        return True, ""
    min_free_mb = _env_float("EASD_CS_MIN_FREE_MB", 1200.0)
    free_mb = float(get_system_ram_specs().get("available_ram_gb", 0.0)) * 1024
    if free_mb < min_free_mb:
        return False, f"only {free_mb:.0f} MB RAM free (< {min_free_mb:.0f} MB) to load the extra models"
    return True, ""


def code_switch_status() -> Dict[str, Any]:
    """Switching readiness for get_engine_status() / /api/system_audit."""
    def _info(kind: str) -> Dict[str, Any]:
        folder = _AUX_MODELS[kind][0]
        return {"folder": os.path.basename(folder), "installed": _model_has_weights(folder),
                "loaded": folder in _LOCAL_MODELS, "download_error": _AUX_DOWNLOAD_FAILED.get(kind)}
    det = code_switch_detector()
    return {"enabled": code_switch_enabled(), "detector": det, "english_model": _info("en"),
            "detector_model": _info(det) if det != "bengaliai" else {"folder": "whisper-bengaliai", "shared": True}}


def _split_speech_stretches(audio: Any, sr: int = 16000) -> List[Tuple[float, float]]:
    """Speech stretches (start_sec, end_sec): a new stretch at every pause of at least
    EASD_CS_MIN_PAUSE_SEC; stretches longer than EASD_CS_MAX_STRETCH_SEC are cut at their
    quietest 100 ms. Silero runs on 30 s blocks (its state saturates on long noise, see
    _vad_is_reliable_for); spans split only by a block edge are joined again."""
    import numpy as np
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    min_pause = max(0.1, _env_float("EASD_CS_MIN_PAUSE_SEC", 0.6))
    max_len = max(5.0, _env_float("EASD_CS_MAX_STRETCH_SEC", 30.0))
    opts = VadOptions(threshold=WHISPER_VAD_PARAMETERS["threshold"], min_speech_duration_ms=250,
                      min_silence_duration_ms=int(min_pause * 1000), speech_pad_ms=150)
    block = 30 * sr
    spans: List[List[float]] = []
    for off in range(0, len(audio), block):
        edge = off / sr
        for ts in get_speech_timestamps(audio[off:off + block], vad_options=opts, sampling_rate=sr):
            s, e = (off + int(ts["start"])) / sr, (off + int(ts["end"])) / sr
            # Silero restarts at each block and needs ~0.5-1 s to pick speech up again, so a span
            # that reaches the block edge and one starting within 1 s after it are one stretch.
            split_by_edge = bool(spans) and edge > 0 and spans[-1][1] >= edge - 0.05 and edge <= s <= edge + 1.0
            if spans and (s - spans[-1][1] < min_pause or split_by_edge):
                spans[-1][1] = max(spans[-1][1], e)
            else:
                spans.append([s, e])

    frame = int(0.1 * sr)
    out: List[Tuple[float, float]] = []
    for s, e in spans:
        while e - s > max_len:
            # quietest 100 ms frame in the second half of the allowed length
            lo, hi = int((s + max_len / 2) * sr), int((s + max_len) * sr)
            seg = audio[lo:hi]
            n = len(seg) // frame
            if n < 1:
                break
            energy = np.square(seg[:n * frame].astype("float32")).reshape(n, frame).mean(axis=1)
            cut = (lo + int(np.argmin(energy)) * frame + frame // 2) / sr
            out.append((s, cut))
            s = cut
        out.append((s, e))
    return out


def _stretch_language(detector: Any, samples: Any) -> Tuple[str, float]:
    """('en' | 'bn', p_en). English only when the normalised English score reaches
    EASD_CS_EN_THRESHOLD (default 0.6): a Bangla stretch sent to small.en would be a new error,
    an English stretch kept in Bangla is today's behaviour."""
    _, _, all_probs = detector.detect_language(samples)
    scores = _bn_en_scores(dict(all_probs or []), ("bn", "en"))
    total = scores["bn"] + scores["en"]
    p_en = scores["en"] / total if total > 0 else 0.0
    return ("en" if p_en >= _env_float("EASD_CS_EN_THRESHOLD", 0.6) else "bn"), p_en


def _plan_bilingual_runs(detector: Any, slice_wav_path: str, slice_duration_sec: float,
                         ctx: str = "") -> List[Tuple[float, float, Optional[str]]]:
    """Language runs [(offset_sec, duration_sec, 'bn'|'en')] covering the whole slice, in the
    shape the decode loop already uses. Raises on VAD/detector errors (caller falls back)."""
    import faster_whisper
    sr = 16000
    t0 = time.time()
    audio = faster_whisper.decode_audio(slice_wav_path)
    stretches = _split_speech_stretches(audio, sr)
    if not stretches:
        return [(0.0, slice_duration_sec, "bn")]

    min_lid = _env_float("EASD_CS_MIN_LID_SEC", 2.0)
    tags: List[List[Any]] = []  # [start, end, lang or None]
    for s, e in stretches:
        lang = None
        if e - s >= min_lid:
            lang, _ = _stretch_language(detector, audio[int(s * sr):int(e * sr)])
        tags.append([s, e, lang])
    # Short stretches take the previous stretch's language, else the next tagged one, else Bangla.
    for i, t in enumerate(tags):
        if t[2] is None:
            nxt = next((u[2] for u in tags[i + 1:] if u[2] is not None), None)
            t[2] = tags[i - 1][2] if i > 0 else (nxt or "bn")

    runs: List[List[Any]] = []
    for s, e, lang in tags:
        if runs and runs[-1][2] == lang:
            runs[-1][1] = e
        else:
            runs.append([s, e, lang])
    for a, b in zip(runs, runs[1:]):  # boundary in the middle of the pause between languages
        a[1] = b[0] = (a[1] + b[0]) / 2
    runs[0][0], runs[-1][1] = 0.0, slice_duration_sec

    n_en = sum(1 for t in tags if t[2] == "en")
    logger.info(f"{ctx} Bangla/English: {len(tags)} stretch(es), {n_en} English -> {len(runs)} run(s): "
                + ", ".join(f"{s:.0f}s+{e - s:.0f}s={lang}" for s, e, lang in runs)
                + f" (planned in {time.time() - t0:.1f}s)")
    return [(s, e - s, lang) for s, e, lang in runs]


def _transcribe_local_audio_openvino(media_input, language: Optional[str], prompt: Optional[str],
                                     mime_type: str) -> Optional[Dict[str, Any]]:
    """
    Intel-GPU path (Iris Xe / Arc / Core Ultra) via OpenVINO GenAI. Produces the same result
    shape as the faster-whisper path, including sanitising and voice-based speaker labels.
    Returns None if nothing usable came out, so the caller falls back to faster-whisper.
    """
    import math
    import openvino_whisper_engine
    import speaker_diarization

    t0 = time.time()
    wav_path = convert_to_wav_pcm16k(media_input, input_hint=_mime_to_hint(mime_type))
    try:
        audio = speaker_diarization.read_wav_pcm16k(wav_path)
        total = len(audio) / 16000.0
        # OpenVINO exposes no language probabilities, and free auto-detection writes Bangla
        # speech in Latin letters (ko/jw/pt guesses), so unspecified means Bangla.
        lang = normalize_language_code(language) or "bn"
        segments_data: List[Dict[str, Any]] = []
        raw_parts: List[str] = []
        last_text = ""
        model_used = device_used = None
        slice_sec = 180.0
        n_pieces = max(1, math.ceil(total / slice_sec))
        for k in range(n_pieces):
            _report_progress(k, n_pieces, f"section {k + 1} of {n_pieces}")
            off = k * slice_sec
            piece = audio[int(off * 16000):int(min(total, off + slice_sec) * 16000)]
            if len(piece) < 16000 * 0.5:
                continue
            out = openvino_whisper_engine.transcribe_samples(piece, language=lang, prompt=prompt or "")
            model_used, device_used = out["model"], out["device"]
            for seg in out["segments"]:
                text = sanitize_whisper_text(seg["text"], language=lang)
                if not text or text == last_text:
                    continue
                last_text = text
                start, end = off + seg["start"], off + seg["end"]
                segments_data.append({"start": round(start, 2), "end": round(end, 2), "text": text,
                                      "speaker": "Speaker 1", "timestamp": f"[{format_seconds_to_min_sec(start)}]",
                                      "language": lang})
                raw_parts.append(text)
        if not segments_data:
            logger.info("OpenVINO Whisper produced no speech - falling back to faster-whisper")
            return None

        elapsed = round(time.time() - t0, 2)
        logger.info(f"OpenVINO Whisper END model={model_used} device={device_used} audio={total:.1f}s "
                    f"segments={len(segments_data)} in {elapsed}s (RTF={elapsed / total if total else 0:.2f})")
        return _finalize_result(segments_data, raw_parts, wav_path, lang, f"openvino:{model_used}@{device_used}",
                                [lang or "auto"], total, elapsed)
    finally:
        if wav_path and os.path.exists(wav_path) and wav_path != media_input:
            try:
                os.remove(wav_path)
            except Exception:
                pass


def transcribe_local_audio(
    media_input: Union[bytes, bytearray, io.BytesIO, str],
    language: Optional[str] = None,
    prompt: Optional[str] = None,
    beam_size: int = 5,
    temperature: float = 0.0,
    mime_type: str = "audio/webm",
    model_name: Optional[str] = None,
    _is_fallback_retry: bool = False,
    code_switch: bool = True
) -> Dict[str, Any]:
    """
    Transcribe audio using the embedded local faster-whisper model.

    code_switch: allow Bangla/English switching for whisper-bengaliai (v9.0). It runs only when
    this is True, EASD_CODE_SWITCH is on, no language was forced by the caller, and the switching
    models are installed. The live preview passes False.

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
    # Free RAM for Whisper: stop an idle preloaded llama-server when memory is low (restarts on demand).
    try:
        import local_llm_engine
        local_llm_engine.release_for_transcription()
    except Exception:
        pass

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
    try:
        import openvino_whisper_engine
        # The Bangla model only exists for faster-whisper; OpenVINO (Intel GPU) is used for large-v3-turbo only.
        if openvino_whisper_engine.should_use() and resolve_whisper_model_choice(model_name)[0] == "large-v3-turbo":
            ov_res = _transcribe_local_audio_openvino(media_input, language, prompt, mime_type)
            if ov_res is not None:
                return ov_res
    except Exception as _ov_err:
        logger.warning(f"OpenVINO Whisper unavailable ({type(_ov_err).__name__}: {_ov_err}) - using faster-whisper")
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

    # Convert audio to clean 16kHz mono WAV file
    _cv0 = time.time()
    temp_audio_file = convert_to_wav_pcm16k(media_input, input_hint=_mime_to_hint(mime_type))
    try:
        _wav_sz = os.path.getsize(temp_audio_file)
    except Exception:
        _wav_sz = -1
    logger.info(f"  WAV conversion {time.time() - _cv0:.1f}s -> {os.path.basename(str(temp_audio_file))} ({_wav_sz / 1048576:.2f} MB)")

    # Check if a specific language was explicitly requested
    explicit_lang = normalize_language_code(language)
    caller_forced_lang = explicit_lang is not None
    is_banglish = effective_model == "bengaliai"
    if is_banglish:
        # Fine-tuned on Bangla only: decode with the Bangla token and no prompt (tested v8.9 on a
        # real EASD meeting; it writes Bengali script).
        explicit_lang, prompt = "bn", None

    # v9.0 Bangla/English switching: English stretches go to small.en (see _plan_bilingual_runs).
    cs_active, en_model, cs_detector = False, None, None
    if is_banglish and code_switch and not caller_forced_lang and code_switch_enabled():
        ready, why = _code_switch_ready()
        if ready:
            det_name = code_switch_detector()
            en_model = _load_aux_model("en")
            cs_detector = model if det_name == "bengaliai" else _load_aux_model(det_name)
            cs_active = en_model is not None and cs_detector is not None
            why = "" if cs_active else "could not load the switching models"
        if cs_active:
            logger.info(f"Bangla/English switching ON (detector={code_switch_detector()}, English=small.en)")
        else:
            logger.info(f"Bangla/English switching skipped: {why} - decoding as Bangla only")

    # Whole-file detection is only a PRIOR (it picks the initial_prompt). Each slice below
    # gets its own detection so one early guess can't force the whole file into one language.
    prior: Dict[str, Any] = {}
    if explicit_lang is None:
        prior = detect_audio_language_detail(model, temp_audio_file, _ctx="[whisper file-prior]")
        target_language = prior.get("language")
    else:
        target_language = explicit_lang
        if cs_active:
            logger.info("Bangla model with per-stretch Bangla/English switching (English stretches -> small.en)")
        else:
            logger.info(f"Language forced by caller: '{explicit_lang}' (per-slice detection disabled)")

    if is_banglish:
        init_prompt = None
    elif prompt:
        init_prompt = prompt
    elif prior.get("ambiguous") and set(prior.get("candidates", [])) >= {"bn", "en"}:
        init_prompt = DEFAULT_BILINGUAL_PROMPT
    elif target_language == "bn":
        # Bengali script: a romanized prompt makes Whisper write Bangla in Latin letters.
        init_prompt = "আজকের মিটিংয়ের আলোচনা এবং কার্যবিবরণী। এজেন্ডা, বাজেট, পর্যালোচনা, সিদ্ধান্ত।"
    elif target_language == "en":
        init_prompt = _EN_PROMPT
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
        raw_text_parts = []
        segments_data = []
        last_clean_text = ""
        detected_whisper_lang = target_language
        detected_whisper_prob = 1.0
        slice_languages: List[str] = []
        used_en_model = False  # any run decoded by small.en (v9.0 switching)

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
            _report_progress(slice_idx, len(chunk_slices), f"section {slice_idx + 1} of {len(chunk_slices)}")
            _sl0 = time.time()
            _seen = _drop_nospeech = _drop_lowconf = _drop_loop = _drop_sanitize = _drop_dup = _kept = 0
            run_temp_files: List[str] = []
            try:
                # 1. Decide the language(s) for this slice
                if cs_active:
                    try:
                        with _TRANSCRIBE_LOCK:  # the detector may be the shared Bangla model
                            runs = _plan_bilingual_runs(cs_detector, input_to_transcribe, chunk_dur_sec, slice_ctx)
                    except Exception as cs_err:
                        logger.warning(f"{slice_ctx} Bangla/English split failed ({type(cs_err).__name__}: "
                                       f"{cs_err}) - decoding this slice as Bangla")
                        runs = [(0.0, chunk_dur_sec, "bn")]
                elif explicit_lang is not None:
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
                    # Hold the lock while decoding: model.transcribe() returns a lazy generator, so the
                    # real work happens while iterating. Without list() two chunks decoded at once
                    # (double RAM on 8 GB PCs) even though this lock looked like it serialised them.
                    def _decode(dec_model, dec_lang, dec_prompt):
                        with _TRANSCRIBE_LOCK:
                            segs, inf = dec_model.transcribe(
                                run_input,
                                task="transcribe",
                                beam_size=beam_size or 1,
                                best_of=1,
                                temperature=0.0,
                                initial_prompt=dec_prompt,
                                language=dec_lang,
                                condition_on_previous_text=False,
                                vad_filter=use_vad,
                                vad_parameters=WHISPER_VAD_PARAMETERS if use_vad else None,
                                no_speech_threshold=0.6,
                                compression_ratio_threshold=_max_compression(dec_lang)
                            )
                            return list(segs), inf

                    if cs_active and run_lang == "en":
                        # English run -> small.en; on any error re-decode the run the old way (Bangla).
                        try:
                            segments, info = _decode(en_model, "en", _EN_PROMPT)
                            used_en_model = True
                        except Exception as en_err:
                            logger.warning(f"{slice_ctx} small.en failed on run @{run_off:.0f}s "
                                           f"({type(en_err).__name__}: {en_err}) - decoding it as Bangla")
                            run_lang = "bn"
                            segments, info = _decode(model, "bn", init_prompt)
                    else:
                        segments, info = _decode(model, run_lang, init_prompt)

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
                        if comp_ratio > _max_compression(seg_lang):
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

                        # Provisional label only - real voice-based labels are assigned after all
                        # slices are done (speaker_diarization.diarize_wav_segments).
                        timestamp_str = format_seconds_to_min_sec(abs_start)
                        raw_text_parts.append(text)
                        last_clean_text = text
                        segments_data.append({
                            "start": round(abs_start, 2),
                            "end": round(abs_end, 2),
                            "text": text,
                            "speaker": "Speaker 1",
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
                _report_progress(slice_idx + 1, len(chunk_slices))

        # Dual-pass resilience: If a specific language was requested (e.g. 'bn') but produced
        # zero valid speech segments, automatically fall back to unforced auto-detection
        # so spoken dialogue in another language (English, bilingual code-switching) is never lost.
        if not segments_data and not _is_fallback_retry and explicit_lang is not None:
            logger.info(f"Forced language '{language}' yielded no speech output. Retrying with unforced automatic language detection...")
            return transcribe_local_audio(
                media_input=media_input,
                language=None,
                prompt=prompt,
                beam_size=beam_size,
                temperature=temperature,
                mime_type=mime_type,
                model_name=model_name,
                _is_fallback_retry=True,
                code_switch=code_switch
            )

        elapsed = round(time.time() - t_start, 2)
        logger.info(f"transcribe_local_audio END in {elapsed}s: audio={total_duration_sec:.1f}s lines={len(segments_data)} "
                    f"(RTF={elapsed / total_duration_sec if total_duration_sec else 0:.2f})")
        return _finalize_result(segments_data, raw_text_parts, temp_audio_file,
                                target_language or explicit_lang or detected_whisper_lang,
                                loaded_model_name + ("+small.en" if used_en_model else ""),
                                slice_languages, total_duration_sec, elapsed)

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

