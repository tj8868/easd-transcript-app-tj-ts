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
        if avail_gb < 2.0:
            return 1
        cores = os.cpu_count() or 4
        return max(1, min(cores - 1, 4))
    except Exception:
        return 1

_DYNAMIC_THREADS = str(get_optimal_cpu_threads())
os.environ.setdefault("OMP_NUM_THREADS", _DYNAMIC_THREADS)
os.environ.setdefault("MKL_NUM_THREADS", _DYNAMIC_THREADS)

logger = logging.getLogger("local_whisper_engine")
logger.setLevel(logging.INFO)
if not logger.handlers:
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
    "বাংলা এবং English আলোচনা ও কার্যবিবরণী। "
    "Verbatim meeting transcript: agenda, budget, review, decisions, action items, participants. "
    "হুবহু বাংলা ও ইংরেজি প্রতিলিপি।"
)


def detect_audio_language(
    model: Any,
    audio_input: Union[str, Any]
) -> Tuple[str, float]:
    """
    Accurately detects any spoken language across all supported Whisper languages.
    Preserves Bengali / Indic acoustic bias when detected, but reliably supports English,
    Hindi, Arabic, Spanish, French, Urdu, Chinese, and all 99+ languages.
    Returns: (resolved_language, confidence)
    """
    try:
        import faster_whisper
        if isinstance(audio_input, str) and os.path.isfile(audio_input):
            audio = faster_whisper.decode_audio(audio_input)
        else:
            audio = audio_input

        if audio is None or len(audio) == 0:
            return "bn", 0.5

        # Take strictly the first 30 seconds (30s * 16000 = 480,000 samples)
        # Slicing avoids allocating hundreds of megabytes in STFT complex128 for long files
        if len(audio) > 30 * 16000:
            audio = audio[:30 * 16000]

        _, _, all_probs = model.detect_language(audio)
        probs = dict(all_probs)

        if not probs:
            return "bn", 0.5

        prob_bn = probs.get("bn", 0.0) + probs.get("as", 0.0)
        prob_en = probs.get("en", 0.0)
        top_lang = max(probs, key=probs.get)
        top_prob = probs.get(top_lang, 0.0)

        # 1. Prominent Bengali / Assamese
        if prob_bn >= 0.18 and (top_lang in ["bn", "as"] or (top_prob - prob_bn) < 0.15):
            return "bn", min(1.0, max(0.5, prob_bn))

        # 2. Prominent English (especially when top_prob is low or top_lang is an Indic accent mismatch like 'hi'/'ne'/'ja')
        if prob_en >= 0.12 and (top_lang == "en" or top_prob < 0.35 or (top_prob - prob_en) < 0.12):
            return "en", min(1.0, max(0.5, prob_en))

        # 3. High confidence for any other language (Spanish, Arabic, French, Hindi, Chinese, etc.)
        if top_prob >= 0.35:
            return top_lang, top_prob

        # 4. Fallback for diffuse probabilities: use top_lang if plausible, otherwise English
        return (top_lang if top_prob >= 0.28 else "en"), top_prob
    except Exception as e:
        logger.warning(f"Audio language detection notice: {e}")
        return "en", 0.5

# Alias for backwards compatibility
detect_bilingual_audio_language = detect_audio_language


def sanitize_whisper_text(text: Optional[str], language: Optional[str] = None) -> str:
    """
    Cleans raw Whisper transcription output to eliminate hallucinations and decoder loops:
    1. Removes Unicode replacement characters (\uFFFD) and zero-width spaces (\u200B, \uFEFF).
    2. Strips hallucinated Tibetan / delimiter Unicode blocks (\u0F00-\u0FFF, e.g. ༼, ༽).
    3. Strips hallucinated CJK / East Asian characters (\u4E00-\u9FFF, \u3400-\u4DBF, \u3000-\u303F, \u3040-\u30FF, \uAC00-\uD7AF)
       unless the explicit/detected language is Chinese, Japanese, or Korean.
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


def select_optimal_model_name() -> str:
    """
    Dynamically select between whisper-base, whisper-small, and whisper-tiny
    based on host system specifications and available model weights.
    Base model (75MB) is the stable default standard, avoiding tiny-model hallucinations.
    """
    specs = get_system_ram_specs()
    total_gb = specs.get("total_ram_gb", 8.0)
    avail_gb = specs.get("available_ram_gb", 2.0)

    # High-spec machines (>= 16GB RAM) select medium if downloaded
    if (total_gb >= 16.0 or avail_gb >= 5.0) and os.path.isdir(_MEDIUM_MODEL_DIR):
        if os.path.isfile(os.path.join(_MEDIUM_MODEL_DIR, "model.bin")) or os.path.isfile(os.path.join(_MEDIUM_MODEL_DIR, "model.safetensors")):
            return "medium"

    # Severely constrained RAM (< 3.0GB total or < 0.4GB available)
    if total_gb < 3.0 or avail_gb < 0.4:
        if os.path.isdir(_TINY_MODEL_DIR) and (os.path.isfile(os.path.join(_TINY_MODEL_DIR, "model.bin")) or os.path.isfile(os.path.join(_TINY_MODEL_DIR, "model.safetensors"))):
            return "tiny"
        if os.path.isdir(_BASE_MODEL_DIR) and os.path.isfile(os.path.join(_BASE_MODEL_DIR, "model.bin")):
            return "base"

    # Base model is the optimal balance: 75MB weights, uses ~150MB RAM, fast, and does not hallucinate like tiny
    if os.path.isdir(_BASE_MODEL_DIR) and os.path.isfile(os.path.join(_BASE_MODEL_DIR, "model.bin")):
        return "base"
    if os.path.isdir(_SMALL_MODEL_DIR) and os.path.isfile(os.path.join(_SMALL_MODEL_DIR, "model.bin")):
        return "small"
    if os.path.isdir(_TINY_MODEL_DIR):
        return "tiny"
    return "base"


def get_model_path(preferred_name: Optional[str] = None) -> str:
    """Resolve the local model path on disk."""
    if preferred_name:
        pref_clean = preferred_name.strip().lower()
        if "medium" in pref_clean:
            if os.path.isdir(_MEDIUM_MODEL_DIR) and (os.path.isfile(os.path.join(_MEDIUM_MODEL_DIR, "model.bin")) or os.path.isfile(os.path.join(_MEDIUM_MODEL_DIR, "model.safetensors"))):
                return _MEDIUM_MODEL_DIR
            return _SMALL_MODEL_DIR
        elif "tiny" in pref_clean:
            if os.path.isdir(_TINY_MODEL_DIR) and (os.path.isfile(os.path.join(_TINY_MODEL_DIR, "model.bin")) or os.path.isfile(os.path.join(_TINY_MODEL_DIR, "model.safetensors"))):
                return _TINY_MODEL_DIR
            if os.path.isdir(_BASE_MODEL_DIR) and os.path.isfile(os.path.join(_BASE_MODEL_DIR, "model.bin")):
                return _BASE_MODEL_DIR
        elif "base" in pref_clean:
            if os.path.isdir(_BASE_MODEL_DIR) and os.path.isfile(os.path.join(_BASE_MODEL_DIR, "model.bin")):
                return _BASE_MODEL_DIR
        elif "small" in pref_clean:
            if os.path.isdir(_SMALL_MODEL_DIR) and os.path.isfile(os.path.join(_SMALL_MODEL_DIR, "model.bin")):
                return _SMALL_MODEL_DIR

    # Automatic spec-based resolution
    optimal = select_optimal_model_name()
    if optimal == "medium" and os.path.isdir(_MEDIUM_MODEL_DIR):
        return _MEDIUM_MODEL_DIR
    if optimal == "tiny" and os.path.isdir(_TINY_MODEL_DIR):
        return _TINY_MODEL_DIR
    if optimal == "base" and os.path.isdir(_BASE_MODEL_DIR):
        return _BASE_MODEL_DIR
    if os.path.isdir(_SMALL_MODEL_DIR) and os.path.isfile(os.path.join(_SMALL_MODEL_DIR, "model.bin")):
        return _SMALL_MODEL_DIR
    if os.path.isdir(_BASE_MODEL_DIR) and os.path.isfile(os.path.join(_BASE_MODEL_DIR, "model.bin")):
        return _BASE_MODEL_DIR
    if os.path.isdir(_TINY_MODEL_DIR):
        return _TINY_MODEL_DIR
    return _SMALL_MODEL_DIR


def get_local_whisper_model(model_name_or_path: Optional[str] = None):
    """
    Get or initialize the singleton WhisperModel instance for the target model.
    Runs with device='cpu', compute_type='int8', dynamic cpu_threads, local_files_only=True.
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

        if not os.path.exists(resolved_path):
            _MODEL_STATUS = "error"
            _MODEL_LOAD_ERROR = f"Model directory not found at {resolved_path}"
            logger.error(_MODEL_LOAD_ERROR)
            raise FileNotFoundError(_MODEL_LOAD_ERROR)

        model_bin = os.path.join(resolved_path, "model.bin")
        model_safe = os.path.join(resolved_path, "model.safetensors")
        if not os.path.exists(model_bin) and not os.path.exists(model_safe):
            _MODEL_STATUS = "error"
            _MODEL_LOAD_ERROR = f"model weights missing in {resolved_path}"
            logger.error(_MODEL_LOAD_ERROR)
            raise FileNotFoundError(_MODEL_LOAD_ERROR)

        _MODEL_STATUS = "loading"
        t0 = time.time()
        n_threads = get_optimal_cpu_threads()
        logger.info(f"Loading local Whisper model from '{resolved_path}' (INT8 CPU, {n_threads} threads)...")

        try:
            from faster_whisper import WhisperModel
            # INT8 is the most compact (39MB-75MB) and fastest format for CPU inference without memory allocation errors.
            compute_types = ["int8", "int8_float32", "float32"]
            model = None
            last_err = None

            paths_to_try = [resolved_path]
            if resolved_path != _BASE_MODEL_DIR and os.path.exists(_BASE_MODEL_DIR):
                paths_to_try.append(_BASE_MODEL_DIR)
            if resolved_path != _TINY_MODEL_DIR and os.path.exists(_TINY_MODEL_DIR):
                paths_to_try.append(_TINY_MODEL_DIR)

            for target_path in paths_to_try:
                for c_type in compute_types:
                    try:
                        logger.info(f"Loading WhisperModel from '{os.path.basename(target_path)}' (compute_type={c_type}, threads={n_threads})...")
                        model = WhisperModel(
                            target_path,
                            device="cpu",
                            compute_type=c_type,
                            cpu_threads=n_threads,
                            local_files_only=True
                        )
                        resolved_path = target_path
                        break
                    except Exception as try_err:
                        last_err = try_err
                        logger.warning(f"WhisperModel init notice ({os.path.basename(target_path)}, {c_type}): {try_err}")
                        import gc
                        gc.collect()
                        continue
                if model is not None:
                    break

            if model is None:
                raise last_err or RuntimeError("Failed to load local Whisper model with any compute type")

            _LOCAL_MODELS[resolved_path] = model
            _LOCAL_MODEL = model
            _MODEL_LOAD_TIME = round(time.time() - t0, 2)
            _MODEL_STATUS = "ready"
            _MODEL_LOAD_ERROR = None
            logger.info(f"Local Whisper model loaded successfully from '{os.path.basename(resolved_path)}' in {_MODEL_LOAD_TIME}s")
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
        "device": "cpu",
        "compute_type": "int8",
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
    """
    temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_wav.close()

    temp_in = None
    try:
        if isinstance(media_input, str) and os.path.isfile(media_input):
            input_path = media_input
        else:
            ext = f".{input_hint.lstrip('.')}" if input_hint else ".webm"
            temp_in_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            if isinstance(media_input, io.BytesIO):
                temp_in_file.write(media_input.getvalue())
            elif isinstance(media_input, (bytes, bytearray)):
                temp_in_file.write(media_input)
            temp_in_file.close()
            temp_in = temp_in_file.name
            input_path = temp_in

        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", input_path,
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            temp_wav.name
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
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
    effective_model = model_name or select_optimal_model_name()
    model = get_local_whisper_model(effective_model)

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
    temp_audio_file = convert_to_wav_pcm16k(media_input, input_hint=hint)

    # Check if a specific language was explicitly requested
    explicit_lang = normalize_language_code(language)
    # CRITICAL: If language is "auto", "detect", "", or None, do NOT force any specific language!
    # Passing language=None lets faster-whisper decode naturally without forced bias.
    target_language = explicit_lang

    if prompt:
        init_prompt = prompt
    elif explicit_lang == "en":
        init_prompt = "Meeting discussion and proceedings in English verbatim. Agenda, budget, review, action items."
    elif explicit_lang == "bn":
        init_prompt = "বাংলা এবং English আলোচনা ও কার্যবিবরণী। এজেন্ডা, বাজেট, সিদ্ধান্ত, কর্মপরিকল্পনা।"
    else:
        # Neutral unforced prompt: do not bias towards any single language
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

    try:
        formatted_lines = []
        raw_text_parts = []
        segments_data = []
        current_spk = 1
        last_end = 0.0
        last_clean_text = ""
        detected_whisper_lang = None
        detected_whisper_prob = 1.0

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

            try:
                with _TRANSCRIBE_LOCK:
                    segments, info = model.transcribe(
                        input_to_transcribe,
                        task="transcribe",
                        beam_size=beam_size or 1,
                        best_of=1,
                        temperature=0.0,
                        initial_prompt=init_prompt,
                        language=target_language,
                        condition_on_previous_text=False,
                        vad_filter=True,
                        vad_parameters=dict(min_silence_duration_ms=500),
                        no_speech_threshold=0.6,
                        log_prob_threshold=None,
                        compression_ratio_threshold=None
                    )

                if detected_whisper_lang is None and hasattr(info, "language"):
                    detected_whisper_lang = info.language
                    detected_whisper_prob = getattr(info, "language_probability", 1.0)

                for segment in segments:
                    raw_text = (segment.text or "").strip()
                    if not raw_text:
                        continue

                    # Skip pure silence segments where no_speech_prob is extreme (> 0.95)
                    no_speech = getattr(segment, "no_speech_prob", 0.0)
                    if no_speech > 0.95:
                        continue

                    # Sanitize text: collapse repetition loops, strip Tibetan/alien tokens, strip CJK hallucinations
                    text = sanitize_whisper_text(raw_text, language=target_language or detected_whisper_lang)
                    if not text:
                        continue

                    # Deduplicate consecutive identical segments
                    if text == last_clean_text:
                        continue

                    abs_start = chunk_start_sec + segment.start
                    abs_end = chunk_start_sec + segment.end

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
                        "timestamp": f"[{timestamp_str}]"
                    })
            finally:
                if chunk_temp_wav and os.path.exists(chunk_temp_wav):
                    try:
                        os.remove(chunk_temp_wav)
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

        detected_lang = explicit_lang or detected_whisper_lang or "auto"
        if clean_text:
            import re
            bengali_chars = len(re.findall(r'[\u0980-\u09FF]', clean_text))
            latin_chars = len(re.findall(r'[a-zA-Z]', clean_text))
            if bengali_chars > 0 and bengali_chars >= latin_chars * 0.2:
                detected_lang = "bn"
            elif latin_chars > 0:
                detected_lang = "en"
        duration_sec = total_duration_sec or 0.0

        return {
            "status": "success",
            "provider": "local_whisper",
            "model": os.path.basename(get_model_path(model_name)),
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
        logger.error(f"Error during local whisper transcription: {e}")
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

