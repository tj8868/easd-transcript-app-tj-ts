"""
Local, on-device LLM for filling the template JSON schema from a transcript --
no network call, runs on a phone-class CPU.

Why this exists
----------------
Previously "local" summarization meant `deep_semantic_synthesis`: pure regex/
keyword extraction, not a model at all. That's a fine last-resort fallback,
but it isn't what most people mean by "local model". This module adds a real
small instruction-tuned LLM (Qwen2.5-Instruct, GGUF, via llama.cpp) as the
actual local model, so the "Local Model" choice on the Generate button runs
real inference, with the template's JSON schema given to the model as
context exactly the way the cloud prompt does.

Model choice
------------
Qwen2.5-1.5B-Instruct (GGUF, Q4_K_M, ~1.0 GB) is the default: small enough
for a phone or an old laptop CPU, and Qwen2.5 was specifically trained to be
good at following structured/JSON output instructions. Qwen2.5-0.5B-Instruct
(~0.4 GB) is offered as an even-lighter fallback for very weak hardware via
EASD_LOCAL_LLM_MODEL=qwen2.5-0.5b. Gemma-2-2b-it is listed as an alternative
if the org prefers Google's model family.

Getting the weights onto the machine
-------------------------------------
This module does NOT bundle model weights (they're gigabytes and licensed
separately). On first use it tries to download the configured model from
Hugging Face straight into models/. If the machine has no internet access at
that moment (e.g. air-gapped office PCs), download it once on any machine
that does and copy the .gguf file into the app's models/ folder -- the exact
expected filename is printed in the error raised by ensure_model_ready().

Call flow
---------
    from local_llm_engine import generate_template_fill
    result = generate_template_fill(transcript, template_schema, org_context, custom_skills)

`generate_template_fill` raises `LocalLLMUnavailable` if llama-cpp-python
isn't installed or no model file is present -- callers (ai_providers.process_ai_request)
catch this and fall back to the regex-based deep_semantic_synthesis, logging
*why* the real model didn't run so that's visible instead of silently swapped.
"""
import os
import sys
import time
import threading
import re
import ctypes
from typing import Any, Dict, Optional, List, Tuple

from diag_logging import get_logger

log = get_logger("local_llm")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.environ.get("EASD_LOCAL_LLM_DIR") or os.path.join(BASE_DIR, "models")

# repo_id / filename on Hugging Face, + a human size for the log/error messages.
# All are Apache-2.0 / Gemma-license instruction-tuned models with small quantized GGUF builds.
SUPPORTED_MODELS: Dict[str, Dict[str, str]] = {
    "qwen2.5-1.5b": {
        "repo_id": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "size": "~1.0 GB",
        "note": "Default. Good JSON-following quality, still fine on a phone/old laptop CPU."
    },
    "qwen2.5-0.5b": {
        "repo_id": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        "filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "size": "~0.4 GB",
        "note": "For very weak/low-RAM devices. Lower quality template fills."
    },
    "gemma-2-2b": {
        "repo_id": "google/gemma-2-2b-it-GGUF",
        "filename": "gemma-2-2b-it-Q4_K_M.gguf",
        "size": "~1.6 GB",
        "note": "Alternative if you prefer Google's model family. Needs a bit more RAM."
    },
}
DEFAULT_MODEL_KEY = os.environ.get("EASD_LOCAL_LLM_MODEL", "qwen2.5-1.5b")

_llm_cache: Dict[str, Any] = {}
_cache_lock = threading.Lock()


class LocalLLMUnavailable(Exception):
    """Raised when the local model can't run: dependency missing or weights not on disk."""
    pass


def get_model_path(model_key: Optional[str] = None) -> str:
    key = model_key or DEFAULT_MODEL_KEY
    info = SUPPORTED_MODELS.get(key, SUPPORTED_MODELS[DEFAULT_MODEL_KEY])
    return os.path.join(MODEL_DIR, info["filename"])


def is_local_llm_available(model_key: Optional[str] = None) -> bool:
    try:
        import llama_cpp  # noqa: F401
    except ImportError:
        return False
    return os.path.isfile(get_model_path(model_key))


def ensure_model_downloaded(model_key: Optional[str] = None) -> str:
    """
    Best-effort download of the configured model into MODEL_DIR. Returns the
    local path on success. Raises LocalLLMUnavailable with clear manual-install
    instructions if the download can't happen (no internet, huggingface_hub not
    installed, etc.) -- this is expected on machines without outbound internet;
    the model file can be copied in manually instead.
    """
    key = model_key or DEFAULT_MODEL_KEY
    info = SUPPORTED_MODELS.get(key, SUPPORTED_MODELS[DEFAULT_MODEL_KEY])
    dest_path = get_model_path(key)
    os.makedirs(MODEL_DIR, exist_ok=True)

    if os.path.isfile(dest_path):
        return dest_path

    log.info("Local LLM weights not found at %s -- attempting download (%s, %s)...",
              dest_path, info["repo_id"], info["size"])
    try:
        from huggingface_hub import hf_hub_download
        t0 = time.time()
        downloaded = hf_hub_download(repo_id=info["repo_id"], filename=info["filename"], local_dir=MODEL_DIR)
        if downloaded != dest_path and os.path.isfile(downloaded):
            try:
                os.replace(downloaded, dest_path)
            except Exception:
                dest_path = downloaded
        log.info("Downloaded local LLM weights to %s in %.1fs", dest_path, time.time() - t0)
        return dest_path
    except Exception as e:
        msg = (
            f"Could not auto-download the local model ({type(e).__name__}: {e}). "
            f"Place '{info['filename']}' ({info['size']}) manually in '{MODEL_DIR}' -- "
            f"download it from https://huggingface.co/{info['repo_id']} on any machine with "
            f"internet access and copy the file over."
        )
        log.warning(msg)
        raise LocalLLMUnavailable(msg) from e


# ---------------------------------------------------------------------------
# Vulkan GPU Detection & llama.cpp Acceleration
# ---------------------------------------------------------------------------
_backend_state: Dict[str, Any] = {
    "active_backend": "unloaded",
    "active_gpu_layers": 0,
    "vulkan_detected": False,
    "vulkan_devices": [],
    "model_key": None,
    "loaded": False,
    "load_time": 0.0,
}


def is_gpu_vulkan_capable(name: str) -> bool:
    """
    Classifies whether a display adapter or GPU model supports Vulkan hardware acceleration.
    Excludes software renderers and older legacy integrated GPUs that lack Vulkan drivers.
    """
    n = (name or "").lower()
    if any(k in n for k in ["microsoft basic", "basic render", "vbox", "vmware", "remote display", "rdp"]):
        return False
    # NVIDIA: GeForce 600+ (Kepler, Maxwell, Pascal, Turing, Ampere, Ada Lovelace, Blackwell, RTX, GTX, Quadro, Tesla, TITAN)
    if any(k in n for k in ["nvidia", "geforce", "rtx", "gtx", "quadro", "tesla", "titan"]):
        if re.search(r"\b(geforce\s+(?:[1-5]\d{2}|[89]\d{3}|g?210))\b", n):
            return False
        return True
    # AMD: GCN 1+, RDNA 1/2/3+, Radeon RX, R5/R7/R9, HD 7000+
    if any(k in n for k in ["amd", "radeon"]):
        if re.search(r"\bhd\s+[1-6]\d{3}\b", n):
            return False
        return True
    # Intel: Arc, Iris Xe, Iris Plus, UHD Graphics, and HD Graphics 500-600 series (Skylake/Kaby Lake Gen9+)
    if "intel" in n:
        if any(k in n for k in ["arc", "iris", "uhd", "xe"]):
            return True
        m = re.search(r"hd\s+graphics\s+(\d{3,4})", n)
        if m:
            model_num = int(m.group(1))
            # 3-digit: 500..630 is Gen9/Gen9.5 -> Vulkan supported
            # 4-digit: 2000..6000 is Gen6/Gen7/Gen8 -> No Vulkan on Windows
            if 500 <= model_num < 1000:
                return True
            return False
        return False
    # Apple Silicon
    if any(k in n for k in ["apple", "m1", "m2", "m3", "m4"]):
        return True
    return False


def get_installed_gpus() -> List[str]:
    """Retrieves installed display adapter names across Windows and Linux."""
    gpus: List[str] = []
    if sys.platform == "win32":
        try:
            from ctypes import wintypes
            class DISPLAY_DEVICEW(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("DeviceName", wintypes.WCHAR * 32),
                    ("DeviceString", wintypes.WCHAR * 128),
                    ("StateFlags", wintypes.DWORD),
                    ("DeviceID", wintypes.WCHAR * 128),
                    ("DeviceKey", wintypes.WCHAR * 128),
                ]
            user32 = ctypes.windll.user32
            dev = DISPLAY_DEVICEW()
            dev.cb = ctypes.sizeof(DISPLAY_DEVICEW)
            i = 0
            while user32.EnumDisplayDevicesW(None, i, ctypes.byref(dev), 0):
                if dev.DeviceString:
                    gpus.append(dev.DeviceString)
                i += 1
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        try:
            drm_path = "/sys/class/drm"
            if os.path.isdir(drm_path):
                for card in os.listdir(drm_path):
                    dev_path = os.path.join(drm_path, card, "device", "uevent")
                    if os.path.isfile(dev_path):
                        with open(dev_path, "r", errors="ignore") as f:
                            content = f.read()
                            if "PCI_ID" in content or "DRIVER" in content:
                                gpus.append(f"Linux DRM Device ({card})")
        except Exception:
            pass
    return sorted(list(set(gpus)))


def query_vulkan_runtime_devices() -> Tuple[bool, List[str], str]:
    """
    Attempts to query physical devices directly via the Vulkan C-API.
    Returns: (driver_loaded, [device_name, ...], detail)
    """
    try:
        if sys.platform == "win32":
            vk = ctypes.CDLL("vulkan-1.dll")
        elif sys.platform == "darwin":
            vk = ctypes.CDLL("libvulkan.dylib")
        else:
            vk = ctypes.CDLL("libvulkan.so.1")
    except OSError:
        return False, [], "Vulkan runtime library (vulkan-1.dll/libvulkan) not found on system"
    except Exception as e:
        return False, [], f"Failed to load Vulkan library: {e}"

    if not hasattr(vk, "vkCreateInstance"):
        return False, [], "vkCreateInstance symbol not found in Vulkan library"

    class VkApplicationInfo(ctypes.Structure):
        _fields_ = [
            ("sType", ctypes.c_uint32),
            ("pNext", ctypes.c_void_p),
            ("pApplicationName", ctypes.c_char_p),
            ("applicationVersion", ctypes.c_uint32),
            ("pEngineName", ctypes.c_char_p),
            ("engineVersion", ctypes.c_uint32),
            ("apiVersion", ctypes.c_uint32),
        ]

    class VkInstanceCreateInfo(ctypes.Structure):
        _fields_ = [
            ("sType", ctypes.c_uint32),
            ("pNext", ctypes.c_void_p),
            ("flags", ctypes.c_uint32),
            ("pApplicationInfo", ctypes.POINTER(VkApplicationInfo)),
            ("enabledLayerCount", ctypes.c_uint32),
            ("ppEnabledLayerNames", ctypes.POINTER(ctypes.c_char_p)),
            ("enabledExtensionCount", ctypes.c_uint32),
            ("ppEnabledExtensionNames", ctypes.POINTER(ctypes.c_char_p)),
        ]

    class VkPhysicalDeviceProperties(ctypes.Structure):
        _fields_ = [
            ("apiVersion", ctypes.c_uint32),
            ("driverVersion", ctypes.c_uint32),
            ("vendorID", ctypes.c_uint32),
            ("deviceID", ctypes.c_uint32),
            ("deviceType", ctypes.c_uint32),
            ("deviceName", ctypes.c_char * 256),
            ("pipelineCacheUUID", ctypes.c_char * 16),
            ("limits", ctypes.c_char * 504),
            ("sparseProperties", ctypes.c_char * 20),
        ]

    instance = ctypes.c_void_p()
    try:
        app_info = VkApplicationInfo()
        app_info.sType = 0  # VK_STRUCTURE_TYPE_APPLICATION_INFO
        app_info.apiVersion = (1 << 22) | (0 << 12)  # Vulkan 1.0

        create_info = VkInstanceCreateInfo()
        create_info.sType = 1  # VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO
        create_info.pApplicationInfo = ctypes.pointer(app_info)

        res = vk.vkCreateInstance(ctypes.byref(create_info), None, ctypes.byref(instance))
        if res != 0 or not instance:
            return True, [], f"vkCreateInstance returned code {res} (no active ICD driver)"

        device_count = ctypes.c_uint32(0)
        vk.vkEnumeratePhysicalDevices(instance, ctypes.byref(device_count), None)
        if device_count.value == 0:
            return True, [], "Vulkan runtime active, but 0 physical devices reported"

        devices = (ctypes.c_void_p * device_count.value)()
        vk.vkEnumeratePhysicalDevices(instance, ctypes.byref(device_count), devices)

        names = []
        for d in devices:
            props = VkPhysicalDeviceProperties()
            vk.vkGetPhysicalDeviceProperties(d, ctypes.byref(props))
            dev_name = props.deviceName.decode("utf-8", errors="replace").strip("\x00").strip()
            if dev_name:
                names.append(dev_name)

        return True, names, f"Detected {len(names)} Vulkan physical device(s) via C-API"
    except Exception as e:
        return True, [], f"Error querying Vulkan physical devices: {e}"
    finally:
        if instance and hasattr(vk, "vkDestroyInstance"):
            try:
                vk.vkDestroyInstance(instance, None)
            except Exception:
                pass


def detect_vulkan_gpu() -> Dict[str, Any]:
    """
    Comprehensive multi-layer Vulkan GPU detection:
    1. Direct Vulkan C-API runtime (vulkan-1.dll / libvulkan.so.1).
    2. Display adapter hardware inspection (NVIDIA/AMD/Intel Gen9+).
    3. llama_cpp binary GPU offload capability.
    4. Auto-shift decision for llama.cpp Vulkan backend.
    """
    driver_loaded, vk_devices, vk_detail = query_vulkan_runtime_devices()
    installed_gpus = get_installed_gpus()
    vulkan_capable_gpus = [g for g in installed_gpus if is_gpu_vulkan_capable(g)]

    llama_offload_supported = False
    try:
        import llama_cpp.llama_cpp as _c
        llama_offload_supported = bool(getattr(_c, "llama_supports_gpu_offload", lambda: False)())
    except Exception:
        pass

    has_vulkan_hardware = bool(vk_devices) or bool(vulkan_capable_gpus)
    all_vulkan_devices = sorted(list(set(vk_devices + vulkan_capable_gpus)))

    if has_vulkan_hardware:
        recommended_backend = "vulkan"
        recommended_gpu_layers = -1  # Default: offload all layers to GPU
        reason = f"Vulkan-capable GPU detected: {', '.join(all_vulkan_devices)}"
    else:
        recommended_backend = "cpu"
        recommended_gpu_layers = 0
        if installed_gpus:
            reason = f"No Vulkan-capable GPU detected (installed: {', '.join(installed_gpus)})"
        else:
            reason = "No discrete or integrated GPU detected"

    return {
        "vulkan_supported": has_vulkan_hardware,
        "driver_installed": driver_loaded,
        "device_names": installed_gpus,
        "vulkan_devices": all_vulkan_devices,
        "device_summary": ", ".join(all_vulkan_devices) if all_vulkan_devices else (installed_gpus[0] if installed_gpus else "None"),
        "llama_offload_supported": llama_offload_supported,
        "recommended_backend": recommended_backend,
        "recommended_gpu_layers": recommended_gpu_layers,
        "reason": reason,
        "vk_detail": vk_detail
    }


def get_local_llm_status(model_key: Optional[str] = None) -> Dict[str, Any]:
    """Returns runtime diagnostic status of the local LLM and Vulkan GPU support."""
    key = model_key or DEFAULT_MODEL_KEY
    path = get_model_path(key)
    vulkan_info = detect_vulkan_gpu()
    return {
        "model": key,
        "model_path": path,
        "weights_present": os.path.isfile(path),
        "available": is_local_llm_available(key),
        "vulkan_supported": vulkan_info.get("vulkan_supported", False),
        "vulkan_driver_installed": vulkan_info.get("driver_installed", False),
        "gpu_devices": vulkan_info.get("device_names", []),
        "vulkan_devices": vulkan_info.get("vulkan_devices", []),
        "llama_offload_supported": vulkan_info.get("llama_offload_supported", False),
        "recommended_backend": vulkan_info.get("recommended_backend", "cpu"),
        "active_backend": _backend_state.get("active_backend", "unloaded"),
        "active_gpu_layers": _backend_state.get("active_gpu_layers", 0),
        "loaded": _backend_state.get("loaded", False),
        "threads": max(1, (os.cpu_count() or 4) - 1),
    }


def _load_model(model_key: Optional[str] = None):
    key = model_key or DEFAULT_MODEL_KEY
    with _cache_lock:
        if key in _llm_cache:
            return _llm_cache[key]

        try:
            from llama_cpp import Llama
        except ImportError as e:
            raise LocalLLMUnavailable(
                "llama-cpp-python is not installed. Run: pip install llama-cpp-python"
            ) from e

        path = get_model_path(key)
        if not os.path.isfile(path):
            path = ensure_model_downloaded(key)  # raises LocalLLMUnavailable if it can't get the weights

        n_threads = max(1, (os.cpu_count() or 4) - 1)
        vulkan_info = detect_vulkan_gpu()

        # Check explicit user/env overrides:
        # EASD_LOCAL_LLM_GPU_LAYERS: explicit integer (e.g. 0, -1, 32)
        # EASD_LOCAL_LLM_BACKEND: explicit string ("cpu", "vulkan", "auto")
        env_backend = os.environ.get("EASD_LOCAL_LLM_BACKEND", "").strip().lower()
        env_gpu_layers = os.environ.get("EASD_LOCAL_LLM_GPU_LAYERS")

        if env_gpu_layers is not None:
            try:
                target_gpu_layers = int(env_gpu_layers)
            except ValueError:
                target_gpu_layers = -1 if vulkan_info["vulkan_supported"] else 0
        elif env_backend == "cpu":
            target_gpu_layers = 0
        elif env_backend == "vulkan" or vulkan_info["vulkan_supported"]:
            # Default: when a GPU supporting Vulkan is detected, shift to llama.cpp Vulkan!
            target_gpu_layers = -1
        else:
            target_gpu_layers = 0

        t0 = time.time()
        llm = None
        active_backend = "cpu"
        actual_layers = 0

        if target_gpu_layers != 0:
            log.info(
                "Vulkan GPU detected (%s) -> shifting local LLM to llama.cpp Vulkan backend (target n_gpu_layers=%d, threads=%d)...",
                vulkan_info.get("device_summary"), target_gpu_layers, n_threads
            )
            try:
                llm = Llama(
                    model_path=path,
                    n_ctx=8192,
                    n_threads=n_threads,
                    n_gpu_layers=target_gpu_layers,
                    verbose=False
                )
                active_backend = "vulkan"
                actual_layers = target_gpu_layers
                log.info(
                    "Local LLM '%s' loaded successfully with llama.cpp Vulkan backend (layers=%d) in %.1fs",
                    key, actual_layers, time.time() - t0
                )
            except Exception as e_gpu:
                log.warning(
                    "Local LLM failed to initialize with Vulkan GPU offload (layers=%d, %s: %s). Falling back gracefully to CPU...",
                    target_gpu_layers, type(e_gpu).__name__, e_gpu
                )
                llm = None

        if llm is None:
            log.info("Loading local LLM '%s' on CPU from %s (n_threads=%d, reason: %s)...",
                     key, path, n_threads, vulkan_info.get("reason"))
            t_cpu = time.time()
            llm = Llama(
                model_path=path,
                n_ctx=8192,
                n_threads=n_threads,
                n_gpu_layers=0,
                verbose=False
            )
            active_backend = "cpu"
            actual_layers = 0
            log.info("Local LLM '%s' loaded successfully on CPU in %.1fs", key, time.time() - t_cpu)

        _backend_state["active_backend"] = active_backend
        _backend_state["active_gpu_layers"] = actual_layers
        _backend_state["model_key"] = key
        _backend_state["loaded"] = True
        _backend_state["load_time"] = round(time.time() - t0, 2)
        _backend_state["vulkan_info"] = vulkan_info
        _llm_cache[key] = llm
        return llm


def generate_template_fill(
    transcript: str,
    template_schema: Optional[Dict[str, Any]] = None,
    org_context: str = "",
    custom_skills: str = "",
    model_key: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.2
) -> Dict[str, Any]:
    """
    Runs the transcript + the template's JSON schema (as context, via the same
    system prompt the cloud path uses) through the local model and returns the
    same normalized {"summary": {...}, ...} shape summarize_text_gemini returns.

    Raises LocalLLMUnavailable if the model can't be loaded/run at all -- the
    caller should catch that and fall back further (e.g. to deep_semantic_synthesis).
    """
    # Lazy imports to avoid a circular import (ai_providers imports this module).
    from ai_providers import build_template_system_prompt, process_extracted_payload, extract_and_repair_json

    key = model_key or DEFAULT_MODEL_KEY
    llm = _load_model(key)  # raises LocalLLMUnavailable on failure

    system_prompt = build_template_system_prompt(template_schema, org_context=org_context, custom_skills=custom_skills)
    system_prompt += (
        "\n\nYou are running as a small on-device model with limited context. Be concise but complete: "
        "keep 'bangla_transcript' and 'english_transcript' to at most ~350 words each so the whole JSON fits."
    )
    user_prompt = f"Transcript:\n\n{transcript}\n\nReturn only the JSON object, nothing else."

    log.info("[local_llm:%s] generating template fill: transcript_chars=%d, max_tokens=%d",
              key, len(transcript or ""), max_tokens)
    t0 = time.time()
    try:
        resp = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}  # llama.cpp grammar-constrains valid JSON when supported
        )
        raw_text = (resp.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
    except Exception as e:
        log.error("[local_llm:%s] inference FAILED after %.1fs: %s: %s", key, time.time() - t0, type(e).__name__, e)
        raise LocalLLMUnavailable(f"Local model inference failed: {type(e).__name__}: {e}") from e

    elapsed = time.time() - t0
    parsed = extract_and_repair_json(raw_text) if raw_text else None
    log.info("[local_llm:%s] done in %.1fs, chars_out=%d, parsed=%s", key, elapsed, len(raw_text), bool(parsed))

    if not (parsed and isinstance(parsed, dict)):
        raise LocalLLMUnavailable(
            f"Local model returned unparseable JSON ({len(raw_text)} chars, first 200: {raw_text[:200]!r})"
        )

    out = process_extracted_payload(
        raw_text, fallback_content=transcript, custom_skills=custom_skills,
        org_context=org_context, template_schema=template_schema
    )
    out["model"] = f"local:{key}"
    out["backend"] = _backend_state.get("active_backend", "cpu")
    out["gpu_layers"] = _backend_state.get("active_gpu_layers", 0)
    out["local_llm_elapsed_sec"] = round(elapsed, 1)
    return out
