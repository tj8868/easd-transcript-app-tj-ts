"""
openvino_whisper_engine.py - local Whisper on Intel GPUs (Iris Xe, Arc, Core Ultra iGPU/NPU) (v8.9).

faster-whisper (CTranslate2) can only use NVIDIA GPUs. On Intel machines this module runs
Whisper through OpenVINO GenAI instead, on the integrated GPU, using a pre-converted model
from the OpenVINO organisation on Hugging Face (downloaded once into models/).

Selection (see local_whisper_engine.transcribe_local_audio):
  - used automatically when openvino-genai is installed, OpenVINO sees a "GPU" device
    and no CUDA GPU is present;
  - EASD_WHISPER_BACKEND=openvino forces it (also on OpenVINO-CPU, useful for testing),
    EASD_WHISPER_BACKEND=ctranslate2 disables it.
  - EASD_OV_WHISPER_MODEL picks the model (default OpenVINO/whisper-large-v3-turbo-int8-ov,
    ~0.9 GB; OpenVINO/whisper-small-int8-ov is a lighter option for older iGPUs).
  - EASD_OV_DEVICE overrides the device (GPU, NPU, CPU, AUTO).
"""
import functools
import os
import threading
from typing import Any, Dict, List, Optional

from diag_logging import get_logger

log = get_logger("whisper.openvino")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODEL = "OpenVINO/whisper-large-v3-turbo-int8-ov"

_state: Dict[str, Any] = {"pipe": None, "key": None, "error": None}
_lock = threading.Lock()


def _backend_setting() -> str:
    return os.environ.get("EASD_WHISPER_BACKEND", "auto").strip().lower()


@functools.lru_cache(maxsize=1)
def available_devices() -> List[str]:
    """Probed once per process: creating an OpenVINO Core loads every device plugin."""
    try:
        import openvino as ov
        return list(ov.Core().available_devices)
    except Exception:
        return []


def should_use() -> bool:
    """True when transcription should go through OpenVINO instead of CTranslate2."""
    mode = _backend_setting()
    if mode in ("ctranslate2", "faster-whisper", "off"):
        return False
    try:
        import openvino_genai  # noqa: F401
    except Exception:
        return False
    if mode == "openvino":
        return True
    # auto: an Intel GPU is visible and there is no CUDA GPU (CUDA + faster-whisper is faster)
    if not any(d.startswith("GPU") for d in available_devices()):
        return False
    import local_whisper_engine
    return local_whisper_engine._cuda_device_count() == 0


def _device() -> str:
    forced = os.environ.get("EASD_OV_DEVICE", "").strip().upper()
    if forced:
        return forced
    devs = available_devices()
    return "GPU" if any(d.startswith("GPU") for d in devs) else "CPU"


def _model_dir(repo: str) -> str:
    local = os.path.join(BASE_DIR, "models", repo.split("/")[-1])
    if os.path.isfile(os.path.join(local, "openvino_encoder_model.xml")):
        return local
    from huggingface_hub import snapshot_download
    log.info("downloading OpenVINO Whisper model %s (one time) ...", repo)
    snapshot_download(repo_id=repo, local_dir=local)
    return local


def _pipeline():
    repo = os.environ.get("EASD_OV_WHISPER_MODEL", DEFAULT_MODEL)
    device = _device()
    key = (repo, device)
    with _lock:
        if _state["pipe"] is not None and _state["key"] == key:
            return _state["pipe"], device, repo
        import openvino_genai
        path = _model_dir(repo)
        cache = os.path.join(BASE_DIR, "models", ".ov_cache")  # compiled-kernel cache: fast 2nd start
        os.makedirs(cache, exist_ok=True)
        try:
            pipe = openvino_genai.WhisperPipeline(path, device, CACHE_DIR=cache)
        except Exception as e:
            if device == "CPU":
                raise
            log.warning("OpenVINO Whisper could not start on %s (%s) - using OpenVINO CPU", device, e)
            device = "CPU"
            pipe = openvino_genai.WhisperPipeline(path, device, CACHE_DIR=cache)
        _state.update(pipe=pipe, key=(repo, device))
        log.info("OpenVINO Whisper ready: model=%s device=%s", repo, device)
        return pipe, device, repo


def status() -> Dict[str, Any]:
    return {"enabled": should_use(), "devices": available_devices(),
            "model": os.environ.get("EASD_OV_WHISPER_MODEL", DEFAULT_MODEL),
            "loaded_device": (_state["key"] or (None, None))[1]}


def transcribe_samples(samples, language: Optional[str] = None, prompt: str = "") -> Dict[str, Any]:
    """
    samples: float32 mono 16 kHz numpy array.
    Returns {"segments": [{"start", "end", "text"}], "model", "device"}. Raises on failure.
    """
    pipe, device, repo = _pipeline()
    cfg = pipe.get_generation_config()
    cfg.task = "transcribe"
    cfg.return_timestamps = True
    cfg.max_new_tokens = 440
    if language in ("bn", "en"):
        cfg.language = f"<|{language}|>"
    if prompt:
        try:
            cfg.initial_prompt = prompt
        except Exception:
            pass
    res = pipe.generate(samples.tolist() if hasattr(samples, "tolist") else list(samples), cfg)
    segs = []
    for ch in (getattr(res, "chunks", None) or []):
        txt = (ch.text or "").strip()
        if txt:
            segs.append({"start": float(ch.start_ts), "end": float(ch.end_ts if ch.end_ts > 0 else ch.start_ts + 2),
                         "text": txt})
    if not segs:
        full = " ".join(getattr(res, "texts", []) or []).strip()
        if full:
            segs.append({"start": 0.0, "end": len(samples) / 16000.0, "text": full})
    return {"segments": segs, "model": repo, "device": device}
