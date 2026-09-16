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
from typing import Optional, Dict, Any, Union, List

# Constrain thread count to avoid MKL/OMP thrashing and memory spike
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"

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
_SMALL_MODEL_DIR = os.path.join(_BASE_DIR, "models", "whisper-small")
_BASE_MODEL_DIR = os.path.join(_BASE_DIR, "models", "whisper-base")
_TINY_MODEL_DIR = os.path.join(_BASE_DIR, "models", "whisper-tiny")

_DEFAULT_MODEL_DIR = _SMALL_MODEL_DIR
_FALLBACK_MODEL_DIR = _BASE_MODEL_DIR

_LOCAL_MODELS: Dict[str, Any] = {}
_LOCAL_MODEL = None
_MODEL_LOCK = threading.Lock()
_IS_WARMING_UP = False
_MODEL_STATUS = "unloaded"  # unloaded | loading | ready | error
_MODEL_LOAD_ERROR = None
_MODEL_LOAD_TIME = 0.0

DEFAULT_BILINGUAL_PROMPT = (
    "EASD Eminence Associates for Social Development. "
    "বাংলা এবং English আলোচনা ও কার্যবিবরণী। "
    "Agenda, follow-up, decisions, action items, participants, Dr. Shamim Talukder."
)


def sanitize_whisper_text(text: Optional[str]) -> str:
    """
    Cleans raw Whisper transcription output to eliminate hallucinations and decoder loops:
    1. Removes Unicode replacement characters (\uFFFD) and zero-width spaces (\u200B).
    2. Strips hallucinated Tibetan / delimiter Unicode blocks (\u0F00-\u0FFF, e.g. ༼, ༽).
    3. Collapses repetitive character/syllable/phrase loops (e.g. 'বিবিবিবিবিবি...' -> 'বি').
    4. Eliminates phantom punctuation repetitions (e.g. '..........', '।।।।।।').
    5. Discards segments lacking authentic alphanumeric speech tokens (Bangla or English).
    """
    if not text:
        return ""

    import re

    # Strip replacement char and zero-width artifacts
    cleaned = text.replace("\ufffd", "").replace("\u200b", "").replace("\ufeff", "")

    # Strip Tibetan / alien symbol Unicode block (\u0F00-\u0FFF, including ༼, ༽, etc.)
    cleaned = re.sub(r"[\u0F00-\u0FFF༼༽ༀ༁༂༃]+", " ", cleaned)

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

    # If the text has no meaningful alphanumeric characters (Bangla or Latin script), discard it
    has_meaningful_speech = bool(re.search(r"[\u0980-\u09FFa-zA-Z0-9]", cleaned))
    if not has_meaningful_speech:
        return ""

    return cleaned


def get_system_ram_specs() -> Dict[str, Any]:
    """Detect system RAM specs to decide between small and nano (tiny/base) models."""
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
    Dynamically select between whisper-small and whisper-nano (tiny/base)
    based on host system specifications.
    Standard systems (>= 6GB RAM) will reliably select 'small' for superior
    Bangla/English bilingual accuracy and resistance to hallucinations.
    Low-spec machines (< 4GB total or < 0.6GB available) select 'tiny' (nano).
    """
    specs = get_system_ram_specs()
    total_gb = specs.get("total_ram_gb", 8.0)
    avail_gb = specs.get("available_ram_gb", 2.0)

    # Severely constrained RAM
    if total_gb < 4.0 or avail_gb < 0.6:
        if os.path.isdir(_TINY_MODEL_DIR) and (os.path.isfile(os.path.join(_TINY_MODEL_DIR, "model.bin")) or os.path.isfile(os.path.join(_TINY_MODEL_DIR, "model.safetensors"))):
            return "tiny"
        if os.path.isdir(_BASE_MODEL_DIR) and os.path.isfile(os.path.join(_BASE_MODEL_DIR, "model.bin")):
            return "base"
    elif total_gb < 6.0 or avail_gb < 1.0:
        if os.path.isdir(_BASE_MODEL_DIR) and os.path.isfile(os.path.join(_BASE_MODEL_DIR, "model.bin")):
            return "base"
        if os.path.isdir(_SMALL_MODEL_DIR) and os.path.isfile(os.path.join(_SMALL_MODEL_DIR, "model.bin")):
            return "small"

    # Standard system: small model is optimal
    if os.path.isdir(_SMALL_MODEL_DIR) and os.path.isfile(os.path.join(_SMALL_MODEL_DIR, "model.bin")):
        return "small"
    if os.path.isdir(_BASE_MODEL_DIR) and os.path.isfile(os.path.join(_BASE_MODEL_DIR, "model.bin")):
        return "base"
    if os.path.isdir(_TINY_MODEL_DIR):
        return "tiny"
    return "small"


def get_model_path(preferred_name: Optional[str] = None) -> str:
    """Resolve the local model path on disk."""
    if preferred_name:
        pref_clean = preferred_name.strip().lower()
        if "tiny" in pref_clean or "nano" in pref_clean:
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
    Runs with device='cpu', compute_type='int8', cpu_threads=2, local_files_only=True.
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
        logger.info(f"Loading local Whisper model from '{resolved_path}' (INT8 CPU, 2 threads)...")

        try:
            from faster_whisper import WhisperModel
            compute_types = ["int8_float32", "int8", "float32"]
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
                        logger.info(f"Loading WhisperModel from '{os.path.basename(target_path)}' (compute_type={c_type}, threads=2)...")
                        model = WhisperModel(
                            target_path,
                            device="cpu",
                            compute_type=c_type,
                            cpu_threads=2,
                            local_files_only=True
                        )
                        resolved_path = target_path
                        break
                    except Exception as try_err:
                        last_err = try_err
                        logger.warning(f"WhisperModel init notice ({os.path.basename(target_path)}, {c_type}): {try_err}")
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
        "threads": 2
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


def transcribe_local_audio(
    media_input: Union[bytes, bytearray, io.BytesIO, str],
    language: Optional[str] = None,
    prompt: Optional[str] = None,
    beam_size: int = 1,
    temperature: float = 0.0,
    mime_type: str = "audio/webm",
    model_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Transcribe audio using the embedded local faster-whisper model.
    
    Args:
        media_input: Raw audio bytes, BytesIO buffer, or path to audio file.
        language: Language code ('bn', 'en') or None/'auto' for auto-detection.
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
            "language": "bn",
            "segments": []
        }

    if isinstance(media_input, (bytes, bytearray)) and len(media_input) < 32:
        return {
            "status": "success",
            "text": "",
            "raw_transcript": "",
            "clean_text": "",
            "language": "bn",
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

    lang_code = normalize_language_code(language)
    init_prompt = prompt or DEFAULT_BILINGUAL_PROMPT

    # Run faster-whisper transcribe with robust anti-hallucination & anti-repetition settings
    try:
        segments, info = model.transcribe(
            temp_audio_file,
            beam_size=beam_size,
            temperature=temperature,
            initial_prompt=init_prompt,
            language=lang_code,
            condition_on_previous_text=False,
            compression_ratio_threshold=2.4,
            no_speech_threshold=0.6,
            log_prob_threshold=-1.0,
            repetition_penalty=1.2,
            no_repeat_ngram_size=4,
            vad_filter=False  # Keep False to avoid MKL malloc crashes on Windows CPU
        )

        formatted_lines = []
        raw_text_parts = []
        segments_data = []
        current_spk = 1
        last_end = 0.0
        last_clean_text = ""

        for segment in segments:
            # 1. Skip pure silence / high no_speech_prob segments (> 0.65 probability of no speech)
            if getattr(segment, "no_speech_prob", 0.0) > 0.65:
                continue

            # 2. Skip extreme repetitive loops flagged by compression ratio (> 2.4)
            if getattr(segment, "compression_ratio", 1.0) > 2.4:
                continue

            raw_text = (segment.text or "").strip()
            if not raw_text:
                continue

            # 3. Sanitize text: collapse repetition loops, strip Tibetan/alien tokens, strip \uFFFD
            text = sanitize_whisper_text(raw_text)
            if not text:
                continue

            # 4. Deduplicate consecutive identical segments (e.g. repeated hallucination across segment boundaries)
            if text == last_clean_text:
                continue

            # Detect conversational turn shifts when speech pause > 1.8s
            if last_end > 0 and (segment.start - last_end) > 1.8:
                current_spk = 2 if current_spk == 1 else 1

            m = int(segment.start // 60)
            s = int(segment.start % 60)
            timestamp_str = f"[{m:02d}:{s:02d}]"
            line = f"{timestamp_str} Speaker {current_spk}: {text}"
            formatted_lines.append(line)
            raw_text_parts.append(text)
            last_end = segment.end
            last_clean_text = text
            segments_data.append({
                "start": segment.start,
                "end": segment.end,
                "text": text,
                "speaker": f"Speaker {current_spk}",
                "timestamp": timestamp_str
            })

        elapsed = round(time.time() - t_start, 2)
        raw_transcript = "\n".join(formatted_lines)
        clean_text = " ".join(raw_text_parts)

        # Fallback if text present but no line generated
        if not raw_transcript and clean_text:
            raw_transcript = f"[00:00] Speaker 1: {clean_text}"

        detected_lang = getattr(info, "language", None) or lang_code or "bn"
        duration_sec = getattr(info, "duration", 0.0) or 0.0

        return {
            "status": "success",
            "provider": "local_whisper",
            "model": os.path.basename(get_model_path(model_name)),
            "text": raw_transcript,
            "raw_transcript": raw_transcript,
            "transcript": raw_transcript,
            "clean_text": clean_text,
            "language": detected_lang,
            "detected_language": detected_lang,
            "duration": round(float(duration_sec), 2),
            "segments": segments_data,
            "segments_count": len(formatted_lines),
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
            "language": "bn",
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
