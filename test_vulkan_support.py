"""
test_vulkan_support.py
Automated test suite verifying Vulkan GPU detection and auto-shift in local_llm_engine:
1. GPU classification (NVIDIA, AMD, Intel Arc/Iris/UHD/HD500+, Apple vs legacy/software).
2. Hardware detection across runtime, registry, and display devices.
3. Auto-shifting to llama.cpp Vulkan (n_gpu_layers=-1) by default when Vulkan GPU is present.
4. Graceful fallback to CPU (n_gpu_layers=0) if Vulkan GPU initialization fails.
5. Respecting user environment overrides (EASD_LOCAL_LLM_BACKEND, EASD_LOCAL_LLM_GPU_LAYERS).
6. Integration with FastAPI /api/system_audit endpoint.
"""
import os
import sys
import types
import json
from unittest.mock import patch, MagicMock

import local_llm_engine
from app import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_gpu_vulkan_capability_classification():
    print("\n[TEST 1] Testing GPU Model Vulkan Capability Classification...")
    capabilities = [
        # NVIDIA
        ("NVIDIA GeForce RTX 4090", True),
        ("NVIDIA GeForce RTX 3060 Laptop GPU", True),
        ("NVIDIA GeForce GTX 1660 Ti", True),
        ("NVIDIA GeForce GTX 1080", True),
        ("NVIDIA RTX A4000", True),
        ("NVIDIA Quadro P2000", True),
        ("NVIDIA GeForce 210", False),
        ("NVIDIA GeForce 9800 GT", False),
        # AMD
        ("AMD Radeon RX 7900 XTX", True),
        ("AMD Radeon RX 6700 XT", True),
        ("AMD Radeon RX 580", True),
        ("AMD Radeon R9 290X", True),
        ("AMD Radeon HD 5450", False),
        ("AMD Radeon HD 6450", False),
        # Intel
        ("Intel(R) Arc(TM) A770 Graphics", True),
        ("Intel(R) Arc(TM) A750 Graphics", True),
        ("Intel(R) Iris(R) Xe Graphics", True),
        ("Intel(R) Iris(R) Plus Graphics 655", True),
        ("Intel(R) UHD Graphics 770", True),
        ("Intel(R) UHD Graphics 630", True),
        ("Intel(R) HD Graphics 530", True),
        ("Intel(R) HD Graphics 620", True),
        ("Intel(R) HD Graphics 4400", False),
        ("Intel(R) HD Graphics 4000", False),
        ("Intel(R) HD Graphics 3000", False),
        # Apple / Virtual / Software
        ("Apple M2 Pro", True),
        ("Apple M1", True),
        ("Microsoft Basic Display Adapter", False),
        ("Microsoft Remote Display Adapter", False),
        ("VMware SVGA 3D", False),
    ]

    for name, expected in capabilities:
        actual = local_llm_engine.is_gpu_vulkan_capable(name)
        assert actual == expected, f"Classification failed for {name}: expected {expected}, got {actual}"
    print(f"   [PASSED] Verified {len(capabilities)} GPU classifications across NVIDIA, AMD, Intel, and Apple.")


def test_vulkan_detection_structure():
    print("\n[TEST 2] Testing detect_vulkan_gpu() Output Structure...")
    status = local_llm_engine.detect_vulkan_gpu()
    assert "vulkan_supported" in status
    assert "driver_installed" in status
    assert "device_names" in status
    assert "vulkan_devices" in status
    assert "llama_offload_supported" in status
    assert "recommended_backend" in status
    assert "recommended_gpu_layers" in status
    assert "reason" in status
    print(f"   Detection result: vulkan_supported={status['vulkan_supported']}, "
          f"devices={status['device_names']}, recommended_backend={status['recommended_backend']}")
    print("   [PASSED] detect_vulkan_gpu() schema and diagnostics validated.")


def test_auto_shift_to_vulkan_when_gpu_detected():
    print("\n[TEST 3] Testing Auto-Shift to llama.cpp Vulkan when Vulkan GPU Detected...")
    call_log = {}

    class FakeLlamaVulkan:
        def __init__(self, model_path, n_ctx, n_threads, n_gpu_layers, verbose):
            call_log["model_path"] = model_path
            call_log["n_gpu_layers"] = n_gpu_layers
            call_log["n_threads"] = n_threads

        def create_chat_completion(self, messages, temperature, max_tokens, response_format=None):
            return {"choices": [{"message": {"content": json.dumps({"summary": {"title": "Vulkan Test"}})}}]}

    fake_llama = types.ModuleType("llama_cpp")
    fake_llama.Llama = FakeLlamaVulkan

    local_llm_engine._llm_cache.clear()

    # Mock a system where NVIDIA RTX 4070 is present
    mock_status = {
        "vulkan_supported": True,
        "driver_installed": True,
        "device_names": ["NVIDIA GeForce RTX 4070"],
        "vulkan_devices": ["NVIDIA GeForce RTX 4070"],
        "device_summary": "NVIDIA GeForce RTX 4070",
        "llama_offload_supported": True,
        "recommended_backend": "vulkan",
        "recommended_gpu_layers": -1,
        "reason": "Vulkan-capable GPU detected",
        "vk_detail": "Detected 1 physical device"
    }

    with patch.dict(sys.modules, {"llama_cpp": fake_llama}):
        with patch.object(local_llm_engine, "detect_vulkan_gpu", return_value=mock_status):
            with patch("os.path.isfile", return_value=True):
                # Ensure no manual env layer override
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("EASD_LOCAL_LLM_GPU_LAYERS", None)
                    os.environ.pop("EASD_LOCAL_LLM_BACKEND", None)
                    llm = local_llm_engine._load_model("qwen2.5-1.5b")

    # When Vulkan GPU is detected, n_gpu_layers should default to -1 (Vulkan offload)
    assert call_log.get("n_gpu_layers") == -1, f"Expected n_gpu_layers=-1 for Vulkan, got {call_log.get('n_gpu_layers')}"
    backend_status = local_llm_engine.get_local_llm_status("qwen2.5-1.5b")
    assert backend_status["active_backend"] == "vulkan"
    assert backend_status["active_gpu_layers"] == -1
    print("   [PASSED] local_llm_engine automatically shifted to llama.cpp Vulkan (n_gpu_layers=-1).")


def test_graceful_cpu_fallback_on_gpu_failure():
    print("\n[TEST 4] Testing Graceful CPU Fallback if Vulkan GPU Initialization Fails...")
    calls = []

    class FailingGpuLlama:
        def __init__(self, model_path, n_ctx, n_threads, n_gpu_layers, verbose):
            calls.append(n_gpu_layers)
            if n_gpu_layers != 0:
                raise RuntimeError("VK_ERROR_OUT_OF_DEVICE_MEMORY: Vulkan device VRAM exhausted")
            # CPU fallback succeeds
            self.model_path = model_path

        def create_chat_completion(self, messages, temperature, max_tokens, response_format=None):
            return {"choices": [{"message": {"content": json.dumps({"summary": {"title": "CPU Fallback"}})}}]}

    fake_llama = types.ModuleType("llama_cpp")
    fake_llama.Llama = FailingGpuLlama

    local_llm_engine._llm_cache.clear()

    mock_status = {
        "vulkan_supported": True,
        "driver_installed": True,
        "device_names": ["Intel(R) Arc(TM) A770 Graphics"],
        "vulkan_devices": ["Intel(R) Arc(TM) A770 Graphics"],
        "device_summary": "Intel(R) Arc(TM) A770 Graphics",
        "llama_offload_supported": True,
        "recommended_backend": "vulkan",
        "recommended_gpu_layers": -1,
        "reason": "Vulkan-capable GPU detected",
        "vk_detail": "Detected 1 physical device"
    }

    with patch.dict(sys.modules, {"llama_cpp": fake_llama}):
        with patch.object(local_llm_engine, "detect_vulkan_gpu", return_value=mock_status):
            with patch("os.path.isfile", return_value=True):
                llm = local_llm_engine._load_model("qwen2.5-1.5b")

    # Verified that it first tried GPU offload (-1), caught failure, and fell back to CPU (0)
    assert calls == [-1, 0], f"Expected calls [-1, 0], got {calls}"
    backend_status = local_llm_engine.get_local_llm_status("qwen2.5-1.5b")
    assert backend_status["active_backend"] == "cpu"
    assert backend_status["active_gpu_layers"] == 0
    print("   [PASSED] Caught Vulkan GPU initialization failure and seamlessly fell back to CPU.")


def test_environment_overrides():
    print("\n[TEST 5] Testing User Environment Overrides (EASD_LOCAL_LLM_BACKEND, EASD_LOCAL_LLM_GPU_LAYERS)...")
    call_log = {}

    class FakeLlamaEnv:
        def __init__(self, model_path, n_ctx, n_threads, n_gpu_layers, verbose):
            call_log["n_gpu_layers"] = n_gpu_layers

        def create_chat_completion(self, messages, temperature, max_tokens, response_format=None):
            return {"choices": [{"message": {"content": json.dumps({"summary": {}})}}]}

    fake_llama = types.ModuleType("llama_cpp")
    fake_llama.Llama = FakeLlamaEnv

    mock_status = {
        "vulkan_supported": True,
        "driver_installed": True,
        "device_names": ["AMD Radeon RX 6800"],
        "vulkan_devices": ["AMD Radeon RX 6800"],
        "device_summary": "AMD Radeon RX 6800",
        "llama_offload_supported": True,
        "recommended_backend": "vulkan",
        "recommended_gpu_layers": -1,
        "reason": "Vulkan-capable GPU detected",
        "vk_detail": "Detected 1 physical device"
    }

    # Case A: Force CPU via EASD_LOCAL_LLM_BACKEND=cpu
    local_llm_engine._llm_cache.clear()
    with patch.dict(sys.modules, {"llama_cpp": fake_llama}):
        with patch.object(local_llm_engine, "detect_vulkan_gpu", return_value=mock_status):
            with patch.dict(os.environ, {"EASD_LOCAL_LLM_BACKEND": "cpu"}):
                with patch("os.path.isfile", return_value=True):
                    local_llm_engine._load_model("qwen2.5-1.5b")
                    assert call_log.get("n_gpu_layers") == 0, f"Expected 0 when forced to CPU, got {call_log.get('n_gpu_layers')}"

    # Case B: Explicit layer count via EASD_LOCAL_LLM_GPU_LAYERS=28
    local_llm_engine._llm_cache.clear()
    with patch.dict(sys.modules, {"llama_cpp": fake_llama}):
        with patch.object(local_llm_engine, "detect_vulkan_gpu", return_value=mock_status):
            with patch.dict(os.environ, {"EASD_LOCAL_LLM_GPU_LAYERS": "28"}):
                with patch("os.path.isfile", return_value=True):
                    local_llm_engine._load_model("qwen2.5-1.5b")
                    assert call_log.get("n_gpu_layers") == 28, f"Expected 28 from env, got {call_log.get('n_gpu_layers')}"

    print("   [PASSED] Explicit user environment variables correctly override automatic detection.")


def test_system_audit_endpoint():
    print("\n[TEST 6] Testing /api/system_audit Integration...")
    resp = client.get("/api/system_audit")
    assert resp.status_code == 200
    data = resp.json()
    report = data.get("report", {})
    assert "local_llm" in report, "local_llm key missing from system audit report"
    llm_audit = report["local_llm"]
    assert "vulkan_supported" in llm_audit
    assert "recommended_backend" in llm_audit
    assert "active_backend" in llm_audit
    assert "gpu_devices" in llm_audit
    print(f"   System Audit local_llm: Vulkan Supported={llm_audit['vulkan_supported']}, "
          f"Backend={llm_audit['active_backend']}, Devices={llm_audit['gpu_devices']}")
    print("   [PASSED] /api/system_audit successfully reports Vulkan hardware and local LLM status.")


def run_all():
    print("=" * 65)
    print("🧪 RUNNING VULKAN GPU DETECTION & LLAMA.CPP ACCELERATION SUITE")
    print("=" * 65)
    test_gpu_vulkan_capability_classification()
    test_vulkan_detection_structure()
    test_auto_shift_to_vulkan_when_gpu_detected()
    test_graceful_cpu_fallback_on_gpu_failure()
    test_environment_overrides()
    test_system_audit_endpoint()
    print("\n" + "=" * 65)
    print("🎉 ALL VULKAN GPU ACCELERATION TESTS PASSED (100% SUCCESS)!")
    print("=" * 65)


if __name__ == "__main__":
    run_all()
