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
Gemma 4 E2B (GGUF Q4_0, ~2.8 GB) is the only model (v8.9). It runs through llama-server
from TheTom's TurboQuant llama.cpp fork (bin/llama-server, built by scripts/build_llama_server.*)
with the turbo4 KV cache and Vulkan GPU offload; llama-cpp-python is the fallback.

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
    "gemma-4-e2b": {
        "repo_id": "ggml-org/gemma-4-E2B-it-GGUF",
        "filename": "gemma-4-E2B-it-Q4_0.gguf",
        "size": "~2.8 GB",
        "note": "Google Gemma 4 E2B (default). Good Bangla; Q4_0 is the fastest quant on CPUs and Vulkan iGPUs."
    },
}
DEFAULT_MODEL_KEY = os.environ.get("EASD_LOCAL_LLM_MODEL", "gemma-4-e2b")

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
    if docker_mode():
        return True  # the container downloads the model itself on first start
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
        vk.vkCreateInstance.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        vk.vkCreateInstance.restype = ctypes.c_int32
        vk.vkEnumeratePhysicalDevices.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        vk.vkEnumeratePhysicalDevices.restype = ctypes.c_int32
        if hasattr(vk, "vkGetPhysicalDeviceProperties"):
            vk.vkGetPhysicalDeviceProperties.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            vk.vkGetPhysicalDeviceProperties.restype = None

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
            if not d:
                continue
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
                vk.vkDestroyInstance.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
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
    llama_offload_supported = False
    try:
        import llama_cpp.llama_cpp as _c
        llama_offload_supported = bool(getattr(_c, "llama_supports_gpu_offload", lambda: False)())
    except Exception:
        pass

    installed_gpus = get_installed_gpus()
    vulkan_capable_gpus = [g for g in installed_gpus if is_gpu_vulkan_capable(g)]

    driver_loaded = False
    vk_devices: List[str] = []
    vk_detail = "llama.cpp CPU binary in use; skipping Vulkan C-API query"

    # Only invoke Vulkan runtime query if llama.cpp actually supports GPU offload
    if llama_offload_supported:
        driver_loaded, vk_devices, vk_detail = query_vulkan_runtime_devices()

    vulkan_capable_vk_devices = [d for d in vk_devices if is_gpu_vulkan_capable(d)]

    has_vulkan_hardware = bool(vulkan_capable_vk_devices) or bool(vulkan_capable_gpus)
    all_vulkan_devices = sorted(list(set(vulkan_capable_vk_devices + vulkan_capable_gpus)))

    if has_vulkan_hardware and llama_offload_supported:
        recommended_backend = "vulkan"
        recommended_gpu_layers = -1  # Default: offload all layers to GPU
        reason = f"Vulkan-capable GPU detected: {', '.join(all_vulkan_devices)}"
    else:
        recommended_backend = "cpu"
        recommended_gpu_layers = 0
        if not llama_offload_supported and (vulkan_capable_gpus or vk_devices):
            dev_list = all_vulkan_devices or installed_gpus
            reason = f"GPU present ({', '.join(dev_list)}), but llama.cpp running with CPU backend; running on CPU"
        elif installed_gpus or vk_devices:
            dev_list = installed_gpus or vk_devices
            reason = f"No Vulkan-capable GPU detected (installed: {', '.join(dev_list)})"
        else:
            reason = "No discrete or integrated GPU detected"

    return {
        "vulkan_supported": has_vulkan_hardware and llama_offload_supported,
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


# KV-cache compression. TurboQuant types exist only in TheTom's llama.cpp fork
# (github.com/TheTom/llama-cpp-turboquant, branch feature/turboquant-kv-cache); the numbers are
# that fork's GGML_TYPE_TURBO*_0 ids. A stock llama.cpp build may abort the process on an
# unknown type, so TurboQuant is strictly opt-in: build llama-cpp-python against the fork
# (scripts/build_llama_turboquant.sh) and set EASD_LOCAL_LLM_KV_CACHE=turbo3 (or turbo4).
# q8_0 works on every build and already halves KV memory.
_KV_CACHE_TYPES = {"f16": 1, "q8_0": 8, "q4_0": 2, "turbo3": 44, "turbo4": 47}


def _kv_cache_kwargs() -> Dict[str, Any]:
    choice = os.environ.get("EASD_LOCAL_LLM_KV_CACHE", "").strip().lower()
    if not choice or choice == "f16":
        return {}
    if choice not in _KV_CACHE_TYPES:
        log.warning("EASD_LOCAL_LLM_KV_CACHE=%r not recognised (use q8_0, turbo3, turbo4) - ignoring", choice)
        return {}
    # Quantised V cache requires flash attention in llama.cpp; the fork enables it for turbo* anyway.
    log.info("local LLM KV cache type: %s (flash attention on)", choice)
    _backend_state["kv_cache"] = choice
    return {"type_k": _KV_CACHE_TYPES[choice], "type_v": _KV_CACHE_TYPES[choice], "flash_attn": True}


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
        kv_kwargs = _kv_cache_kwargs()

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
                    verbose=False,
                    **kv_kwargs
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
                verbose=False,
                **kv_kwargs
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


# ---------------------------------------------------------------------------
# One entry point for on-device chat: OpenVINO on Intel GPUs, llama.cpp everywhere else
# ---------------------------------------------------------------------------
_OV_LLM: Dict[str, Any] = {"pipe": None, "repo": None, "device": None}


def _openvino_llm_preferred() -> bool:
    """Intel iGPU (Iris Xe / UHD Xe / Arc / Core Ultra) present and no CUDA -> OpenVINO GenAI.
    EASD_LLM_BACKEND=openvino|llamacpp overrides."""
    mode = os.environ.get("EASD_LLM_BACKEND", "auto").strip().lower()
    if mode == "llamacpp":
        return False
    try:
        import openvino_genai  # noqa: F401
    except Exception:
        return False
    if mode == "openvino":
        return True
    import openvino_whisper_engine
    import local_whisper_engine
    return any(d.startswith("GPU") for d in openvino_whisper_engine.available_devices()) \
        and local_whisper_engine._cuda_device_count() == 0


def _openvino_llm_repo() -> str:
    """Pre-converted OpenVINO model: Gemma-3-4B (better Bangla) with >= 12 GB RAM, else Qwen2.5-1.5B."""
    if os.environ.get("EASD_OV_LLM_MODEL"):
        return os.environ["EASD_OV_LLM_MODEL"]
    import local_whisper_engine
    big = local_whisper_engine.get_system_ram_specs().get("total_ram_gb", 8.0) >= 12
    return "OpenVINO/gemma-3-4b-it-int4-ov" if big else "OpenVINO/Qwen2.5-1.5B-Instruct-int4-ov"


def _openvino_pipeline():
    repo = _openvino_llm_repo()
    with _cache_lock:
        if _OV_LLM["pipe"] is not None and _OV_LLM["repo"] == repo:
            return _OV_LLM["pipe"]
        import openvino_genai
        from huggingface_hub import snapshot_download
        path = os.path.join(BASE_DIR, "models", repo.split("/")[-1])
        if not os.path.isfile(os.path.join(path, "openvino_model.xml")):
            log.info("downloading OpenVINO LLM %s (one time) ...", repo)
            snapshot_download(repo_id=repo, local_dir=path)
        cache = os.path.join(BASE_DIR, "models", ".ov_cache")
        os.makedirs(cache, exist_ok=True)
        device = os.environ.get("EASD_OV_DEVICE") or "GPU"
        try:
            pipe = openvino_genai.LLMPipeline(path, device, CACHE_DIR=cache)
        except Exception as e:
            log.warning("OpenVINO LLM could not start on %s (%s) - using OpenVINO CPU", device, e)
            device, pipe = "CPU", openvino_genai.LLMPipeline(path, "CPU", CACHE_DIR=cache)
        _OV_LLM.update(pipe=pipe, repo=repo, device=device)
        _backend_state.update(active_backend=f"openvino-{device.lower()}", model_key=repo, loaded=True)
        log.info("OpenVINO LLM ready: %s on %s", repo, device)
        return pipe


# ---------------------------------------------------------------------------
# llama-server from TheTom's TurboQuant fork (scripts/build_llama_server.sh -> bin/llama-server).
# Preferred over the Python binding: the fork moves faster than llama-cpp-python's bindings, and
# the server gives turbo4 KV cache + Vulkan GPU offload (Intel Iris Xe, AMD, NVIDIA) on low-end PCs.
# ---------------------------------------------------------------------------
_SERVER: Dict[str, Any] = {"proc": None, "port": None, "key": None, "gpu": None}


# ---------------------------------------------------------------------------
# v9.0: llama-server in Docker (docker/llama/). When a container named EASD_LLAMA_DOCKER (default
# "easd-llama") exists and this user can run `docker`, the app uses it instead of bin/llama-server.
# The container tunes its own flags to the hardware (docker/llama/entrypoint.sh). The app starts it
# before a local request and stops it to free RAM for Whisper, exactly like the bin/ server.
# ---------------------------------------------------------------------------
_DOCKER_NAME = os.environ.get("EASD_LLAMA_DOCKER", "easd-llama").strip()
_DOCKER_URL = os.environ.get("EASD_LLAMA_SERVER_URL", "http://127.0.0.1:8081").strip().rstrip("/")
_docker_probe: Dict[str, Any] = {"at": 0.0, "ok": False}


def _docker_cmd(*args: str, timeout: int = 60):
    import subprocess
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def docker_mode() -> bool:
    """True when the easd-llama container exists and is usable (result cached for 60 s)."""
    import shutil
    if not _DOCKER_NAME or _DOCKER_NAME.lower() in ("0", "off", "none") or not shutil.which("docker"):
        return False
    if time.time() - _docker_probe["at"] < 60:
        return _docker_probe["ok"]
    try:
        ok = _docker_cmd("inspect", "-f", "{{.Name}}", _DOCKER_NAME, timeout=15).returncode == 0
    except Exception:
        ok = False
    _docker_probe.update(at=time.time(), ok=ok)
    return ok


def _docker_healthy(timeout: float = 2.0) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"{_DOCKER_URL}/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _ensure_docker_server(key: str) -> str:
    """Starts the container if needed and waits until llama-server answers. Returns its base URL."""
    if _docker_healthy():
        return _DOCKER_URL
    t0 = time.time()
    log.info("starting Docker llama-server container %r", _DOCKER_NAME)
    res = _docker_cmd("start", _DOCKER_NAME)
    if res.returncode != 0:
        raise LocalLLMUnavailable(f"docker start {_DOCKER_NAME} failed: {(res.stderr or res.stdout).strip()[:300]}")
    # The first start on new hardware downloads the model and benchmarks it, so allow a long wait.
    limit = float(os.environ.get("EASD_LLAMA_DOCKER_START_TIMEOUT", "1800"))
    while time.time() - t0 < limit:
        if _docker_healthy():
            _backend_state.update(active_backend="llama-server-docker", model_key=key, loaded=True,
                                  load_time=round(time.time() - t0, 2))
            log.info("Docker llama-server ready in %.1fs at %s", time.time() - t0, _DOCKER_URL)
            return _DOCKER_URL
        state = _docker_cmd("inspect", "-f", "{{.State.Running}}", _DOCKER_NAME, timeout=15).stdout.strip()
        if state != "true":
            tail = _docker_cmd("logs", "--tail", "20", _DOCKER_NAME).stdout
            raise LocalLLMUnavailable(f"Docker llama-server stopped during start-up:\n{tail[-800:]}")
        time.sleep(2)
    raise LocalLLMUnavailable(f"Docker llama-server did not become ready within {limit:.0f}s "
                              f"(see: docker logs {_DOCKER_NAME})")


def _server_binary() -> Optional[str]:
    exe = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    path = os.environ.get("EASD_LLAMA_SERVER") or os.path.join(BASE_DIR, "bin", exe)
    return path if os.path.isfile(path) else None


_PID_FILE = os.path.join(BASE_DIR, ".llama_server.pid")


_SERVER_GPUS: Optional[List[str]] = None


def _server_gpu_devices() -> List[str]:
    """GPUs llama-server itself can use (from `llama-server --list-devices`): Vulkan, CUDA or Metal devices.
    Software renderers (llvmpipe, lavapipe, SwiftShader) are ignored. Cached for the app's lifetime."""
    global _SERVER_GPUS
    if _SERVER_GPUS is not None:
        return _SERVER_GPUS
    found: List[str] = []
    try:
        import subprocess
        out = subprocess.run([_server_binary(), "--list-devices"], capture_output=True, text=True, timeout=60,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for line in (out.stdout + out.stderr).splitlines():
            m = re.match(r"\s+(\w+\d+):\s*(.+)", line)
            if m and not re.search(r"llvmpipe|lavapipe|swiftshader|software", m.group(2), re.I):
                found.append(f"{m.group(1)}: {m.group(2).strip()}")
    except Exception as e:
        log.warning("llama-server --list-devices failed: %s", e)
    _SERVER_GPUS = found
    return found


def _available_ram_mb() -> Optional[int]:
    try:
        import psutil  # optional
        return int(psutil.virtual_memory().available / 1048576)
    except Exception:
        pass
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) // 1024
        if sys.platform == "win32":
            class _MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            ms = _MS()
            ms.dwLength = ctypes.sizeof(_MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
            return int(ms.ullAvailPhys / 1048576)
        if sys.platform == "darwin":
            import subprocess
            out = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5).stdout
            page = int(re.search(r"page size of (\d+)", out).group(1))
            free = sum(int(re.search(rf"{k}:\s+(\d+)", out).group(1)) for k in ("Pages free", "Pages inactive"))
            return free * page // 1048576
    except Exception:
        pass
    return None


# Capable device = llama-server sees a real GPU AND at least this much RAM is free (stays within ~4 GB).
_CAPABLE_MIN_FREE_MB = int(os.environ.get("EASD_LOCAL_LLM_CAPABLE_MIN_FREE_MB", "3000") or 3000)


def _kv_cache_types(gpu_attempt: bool) -> Tuple[str, str, str]:
    """Returns (K type, V type, reason). Capable device -> turbo6/turbo6, otherwise turbo3/turbo4.
    The context size is NOT changed here: it stays fixed (EASD_LOCAL_LLM_CTX, default 10000).
    EASD_LOCAL_LLM_KV_CACHE / _K / _V still override the automatic choice."""
    both = os.environ.get("EASD_LOCAL_LLM_KV_CACHE", "").strip().lower()
    env_k = os.environ.get("EASD_LOCAL_LLM_KV_CACHE_K", "").strip().lower() or both
    env_v = os.environ.get("EASD_LOCAL_LLM_KV_CACHE_V", "").strip().lower() or both
    gpus = _server_gpu_devices() if gpu_attempt else []
    free_mb = _available_ram_mb()
    if gpus and (free_mb is None or free_mb >= _CAPABLE_MIN_FREE_MB):
        k, v, why = "turbo6", "turbo6", f"capable device ({gpus[0]}; {free_mb} MB free)"
    else:
        k, v = "turbo3", "turbo4"
        why = ("no GPU visible to llama-server" if not gpus
               else f"GPU found but only {free_mb} MB RAM free (< {_CAPABLE_MIN_FREE_MB} MB)")
    if env_k or env_v:
        why += " - overridden by EASD_LOCAL_LLM_KV_CACHE*"
    return env_k or k, env_v or v, why


def _physical_cores() -> Optional[int]:
    """Physical CPU core count (no hyper-threads), or None if it can't be read."""
    try:
        import psutil  # optional
        n = psutil.cpu_count(logical=False)
        if n:
            return int(n)
    except Exception:
        pass
    try:
        if sys.platform.startswith("linux"):
            cores, phys = set(), None
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("physical id"):
                        phys = line.split(":", 1)[1].strip()
                    elif line.startswith("core id"):
                        cores.add((phys, line.split(":", 1)[1].strip()))
            return len(cores) or None
        import subprocess
        if sys.platform == "darwin":
            out = subprocess.run(["sysctl", "-n", "hw.physicalcpu"], capture_output=True, text=True, timeout=5)
            return int(out.stdout.strip()) or None
        if sys.platform == "win32":
            out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  "(Get-CimInstance Win32_Processor | Measure-Object NumberOfCores -Sum).Sum"],
                                 capture_output=True, text=True, timeout=15,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return int(out.stdout.strip()) or None
    except Exception:
        pass
    return None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            import subprocess
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            return str(pid) in out
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except Exception:
        return False


def _read_pid_file() -> Tuple[int, int]:
    """(llama-server pid, pid of the app process that started it); (0, 0) if missing/unreadable."""
    try:
        with open(_PID_FILE) as f:
            parts = f.read().split()
        return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except Exception:
        return 0, 0


def _kill_leftover_server() -> None:
    """Stops a llama-server left behind by an app run that died (e.g. killed when RAM ran out), so it
    doesn't keep the model in memory. Never touches a server whose owning app process is still running
    (a second app window must not kill the first one's server mid-Generate)."""
    pid, owner = _read_pid_file()
    if pid <= 0 or (owner and owner != os.getpid() and _pid_alive(owner)):
        return
    try:
        if sys.platform == "win32":
            import subprocess
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            if "llama-server" in out.lower():
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            cmdline = ""
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    cmdline = f.read().decode(errors="ignore")
            except Exception:
                import subprocess
                cmdline = subprocess.run(["ps", "-o", "command=", "-p", str(pid)],
                                         capture_output=True, text=True).stdout
            if "llama-server" in cmdline:
                import signal
                os.kill(pid, signal.SIGTERM)
                log.info("stopped leftover llama-server from an earlier run (pid %d)", pid)
    except Exception:
        pass
    try:
        os.remove(_PID_FILE)
    except Exception:
        pass


def start_server_in_background(model_key: Optional[str] = None) -> bool:
    """Starts llama-server in a hidden background thread when the app loads, so the first Generate
    doesn't wait for the model. Skipped (returns False) when the binary or model file is missing,
    or when EASD_LOCAL_LLM_PRELOAD=0. Never downloads anything and never raises."""
    if os.environ.get("EASD_LOCAL_LLM_PRELOAD", "1").strip().lower() in ("0", "false", "no", "off"):
        log.info("llama-server preload disabled (EASD_LOCAL_LLM_PRELOAD=0)")
        return False
    _kill_leftover_server()
    key = model_key or DEFAULT_MODEL_KEY
    if docker_mode():
        free_mb = _available_ram_mb()
        if free_mb is not None and free_mb < _PRELOAD_MIN_FREE_MB:
            log.info("Docker llama-server preload skipped: %d MB RAM free (< %d MB)", free_mb, _PRELOAD_MIN_FREE_MB)
            return False
        threading.Thread(target=lambda: _safe_preload_docker(key), name="llama-docker-preload", daemon=True).start()
        return True
    if not _server_binary() or not os.path.isfile(get_model_path(key)):
        log.info("llama-server preload skipped: binary or model file not found")
        return False
    free_mb = _available_ram_mb()
    if free_mb is not None and free_mb < _PRELOAD_MIN_FREE_MB:
        log.info("llama-server preload skipped: %d MB RAM free (< %d MB); it starts on the first local Generate",
                 free_mb, _PRELOAD_MIN_FREE_MB)
        return False

    def _run():
        try:
            _start_server(key)
        except Exception as e:
            log.warning("llama-server preload failed (will retry on first Generate): %s", e)

    threading.Thread(target=_run, name="llama-server-preload", daemon=True).start()
    return True


def _safe_preload_docker(key: str) -> None:
    try:
        _ensure_docker_server(key)
    except Exception as e:
        log.warning("Docker llama-server preload failed (will retry on first Generate): %s", e)


def stop_server() -> None:
    """Stops this app's background llama-server (app shutdown, or to free RAM for Whisper).
    It is started again automatically by the next local Generate."""
    if docker_mode():
        try:
            if _docker_cmd("inspect", "-f", "{{.State.Running}}", _DOCKER_NAME, timeout=15).stdout.strip() == "true":
                _docker_cmd("stop", "-t", "10", _DOCKER_NAME)
                log.info("stopped Docker llama-server container %r", _DOCKER_NAME)
        except Exception as e:
            log.warning("could not stop Docker llama-server: %s", e)
        _backend_state["loaded"] = False
        return
    with _cache_lock:
        proc = _SERVER.get("proc")
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
        if proc is not None and _read_pid_file()[0] == proc.pid:
            try:
                os.remove(_PID_FILE)
            except Exception:
                pass
        _SERVER.update(proc=None, port=None, key=None, gpu=None)
        _backend_state["loaded"] = False


# RAM the model may hold while other work runs. On an 8 GB PC, Whisper (~1.6 GB) plus the preloaded
# model (~1.4 GB) plus the desktop ran out of memory, so the model is only kept loaded when enough is free.
_PRELOAD_MIN_FREE_MB = int(os.environ.get("EASD_LOCAL_LLM_PRELOAD_MIN_FREE_MB", "3000") or 3000)
_KEEP_DURING_STT_MIN_FREE_MB = int(os.environ.get("EASD_LOCAL_LLM_KEEP_MIN_FREE_MB", "2500") or 2500)


def release_for_transcription() -> bool:
    """Called before local Whisper transcribes: stops the idle llama-server when free RAM is below
    EASD_LOCAL_LLM_KEEP_MIN_FREE_MB, so the two models never compete for memory. Returns True if stopped."""
    if _SERVER.get("busy", 0) > 0:
        return False
    if docker_mode():
        running = _docker_healthy(timeout=1.0)
    else:
        proc = _SERVER.get("proc")
        running = proc is not None and proc.poll() is None
    if not running:
        return False
    free_mb = _available_ram_mb()
    if free_mb is not None and free_mb < _KEEP_DURING_STT_MIN_FREE_MB:
        log.info("stopping llama-server to free RAM for transcription (%d MB free < %d MB); "
                 "it restarts on the next local Generate", free_mb, _KEEP_DURING_STT_MIN_FREE_MB)
        stop_server()
        return True
    return False


def _start_server(key: str) -> int:
    """Starts (or reuses) llama-server for this model. Tries full GPU offload, then CPU only."""
    import socket
    import subprocess
    import urllib.request
    with _cache_lock:
        proc = _SERVER["proc"]
        if proc is not None and proc.poll() is None and _SERVER["key"] == key:
            return _SERVER["port"]
        if proc is not None and proc.poll() is None:
            proc.terminate()
        path = get_model_path(key)
        if not os.path.isfile(path):
            path = ensure_model_downloaded(key)
        # Defaults: -fa on -c 10000 -lm mmap -np 1 (one slot keeps RAM low on 8 GB PCs).
        # KV cache: turbo6/turbo6 on a capable device, else -ctk turbo3 -ctv turbo4 (see _kv_cache_types).
        # The context is fixed: one batch audio session's transcript plus the template prompt.
        ctx = os.environ.get("EASD_LOCAL_LLM_CTX", "10000").strip() or "10000"
        # Scale with the machine: generation uses the physical cores (hyper-threads slow it down),
        # prompt reading (-tb) uses every logical core. A GPU, when found, takes all layers (-ngl 99).
        logical = os.cpu_count() or 4
        physical = _physical_cores() or logical
        threads = os.environ.get("EASD_LOCAL_LLM_THREADS", "").strip() or str(max(1, physical))
        batch_threads = str(max(1, logical))
        log_path = os.path.join(BASE_DIR, "llama_server.log")
        for ngl in (os.environ.get("EASD_LOCAL_LLM_GPU_LAYERS", "99"), "0"):
            with socket.socket() as sk:
                sk.bind(("127.0.0.1", 0))
                port = sk.getsockname()[1]
            kv_k, kv_v, kv_why = _kv_cache_types(gpu_attempt=ngl != "0")
            log.info("KV cache K=%s V=%s: %s", kv_k, kv_v, kv_why)
            cmd = [_server_binary(), "-m", path, "--host", "127.0.0.1", "--port", str(port),
                   "-c", ctx, "-np", "1", "-lm", "mmap", "-t", threads, "-tb", batch_threads, "-ngl", ngl, "-fa", "on",
                   "-ctk", kv_k, "-ctv", kv_v, "--jinja", "--no-webui"]
            log.info("starting llama-server: model=%s ctx=%s kv=K:%s/V:%s gpu_layers=%s threads=%s/%s",
                     os.path.basename(path), ctx, kv_k, kv_v, ngl, threads, batch_threads)
            t0 = time.time()
            proc = subprocess.Popen(cmd, stdout=open(log_path, "a"), stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            try:
                with open(_PID_FILE, "w") as f:
                    f.write(f"{proc.pid} {os.getpid()}")
            except Exception:
                pass
            while proc.poll() is None and time.time() - t0 < 600:
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                        if r.status == 200:
                            break
                except Exception:
                    time.sleep(1)
            if proc.poll() is None:
                if not _SERVER.get("atexit"):  # first start: stop the server when the app exits
                    import atexit
                    atexit.register(lambda: (_SERVER.get("proc") is not None and _SERVER["proc"].poll() is None
                                             and _SERVER["proc"].terminate()))
                    _SERVER["atexit"] = True
                _SERVER.update(proc=proc, port=port, key=key, gpu=ngl != "0")
                _backend_state.update(active_backend=f"llama-server-{'gpu' if ngl != '0' else 'cpu'}",
                                      active_gpu_layers=int(ngl), model_key=key, loaded=True,
                                      kv_cache=f"K={kv_k},V={kv_v}",
                                      load_time=round(time.time() - t0, 2))
                log.info("llama-server ready in %.1fs (port %d, gpu_layers=%s)", time.time() - t0, port, ngl)
                return port
            log.warning("llama-server exited (code %s) with gpu_layers=%s - see llama_server.log", proc.returncode, ngl)
        raise LocalLLMUnavailable("llama-server could not start (see llama_server.log)")


def _server_chat(system: str, user: str, key: str, max_tokens: int, temperature: float, json_mode: bool) -> str:
    with _cache_lock:
        _SERVER["busy"] = _SERVER.get("busy", 0) + 1  # release_for_transcription() won't stop a busy server
    try:
        return _server_chat_once(system, user, key, max_tokens, temperature, json_mode)
    finally:
        with _cache_lock:
            _SERVER["busy"] = max(0, _SERVER.get("busy", 0) - 1)


def _server_chat_once(system: str, user: str, key: str, max_tokens: int, temperature: float, json_mode: bool) -> str:
    import json as _json
    import urllib.request
    base = _ensure_docker_server(key) if docker_mode() else f"http://127.0.0.1:{_start_server(key)}"
    body = {"messages": _messages(system, user, key), "temperature": temperature, "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": False}}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(f"{base}/v1/chat/completions", data=_json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3600) as r:
        data = _json.loads(r.read())
    return data.get("choices", [{}])[0].get("message", {}).get("content") or ""


def _messages(system: str, user: str, model_name: str) -> List[Dict[str, str]]:
    # Gemma chat templates have no system role: fold it into the user turn.
    if "gemma" in model_name.lower():
        return [{"role": "user", "content": f"{system}\n\n---\n\n{user}"}]
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def chat(system: str, user: str, model_key: Optional[str] = None, max_tokens: int = 4096,
         temperature: float = 0.2, json_mode: bool = True) -> Tuple[str, str]:
    """Runs one system+user exchange on the best local backend. Returns (text, model_label).
    Raises LocalLLMUnavailable if no backend can run."""
    t0 = time.time()
    try:
        if docker_mode() or _server_binary():
            key = model_key or DEFAULT_MODEL_KEY
            text = _server_chat(system, user, key, max_tokens, temperature, json_mode)
            label = f"{key}@llama-server{'-docker' if docker_mode() else ''}"  # GPU use depends on the build (see llama_server.log)
        elif _openvino_llm_preferred():
            import openvino_genai
            pipe = _openvino_pipeline()
            label = f"openvino:{_OV_LLM['repo'].split('/')[-1]}@{_OV_LLM['device']}"
            prompt = pipe.get_tokenizer().apply_chat_template(_messages(system, user, _OV_LLM["repo"]),
                                                               add_generation_prompt=True)
            cfg = openvino_genai.GenerationConfig()
            cfg.max_new_tokens = max_tokens
            cfg.apply_chat_template = False  # already applied above
            text = str(pipe.generate(prompt, cfg))
        else:
            key = model_key or DEFAULT_MODEL_KEY
            label = key
            resp = _load_model(key).create_chat_completion(
                messages=_messages(system, user, key), temperature=temperature, max_tokens=max_tokens,
                **({"response_format": {"type": "json_object"}} if json_mode else {}))
            text = resp.get("choices", [{}])[0].get("message", {}).get("content") or ""
    except LocalLLMUnavailable:
        raise
    except Exception as e:
        log.error("[local_llm] inference FAILED after %.1fs: %s: %s", time.time() - t0, type(e).__name__, e)
        raise LocalLLMUnavailable(f"Local model inference failed: {type(e).__name__}: {e}") from e
    return text.strip(), label


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
    system_prompt = build_template_system_prompt(template_schema, org_context=org_context, custom_skills=custom_skills)
    system_prompt += (
        "\n\nYou are running as a small on-device model with limited context. Be concise but complete: "
        "keep 'bangla_transcript' and 'english_transcript' to at most ~350 words each so the whole JSON fits."
    )
    user_prompt = f"Transcript:\n\n{transcript}\n\nReturn only the JSON object, nothing else."
    log.info("[local_llm:%s] generating template fill: transcript_chars=%d, max_tokens=%d",
             key, len(transcript or ""), max_tokens)
    t0 = time.time()
    raw_text, key = chat(system_prompt, user_prompt, key, max_tokens=max_tokens, temperature=temperature)
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
