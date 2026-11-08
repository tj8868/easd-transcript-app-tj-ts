"""
Hardware Profiler Sub-Agent
Analyzes CPU, RAM, GPU, and OS environment to dynamically recommend
and select either 'faster-whisper-int8' (for resource-constrained/low-end systems)
or 'whisper-large-v3-turbo' (for modern multi-core/GPU systems).
"""

import os
import sys
import platform
import shutil
import subprocess
from typing import Dict, Any

class HardwareProfilerSubAgent:
    """Sub-agent responsible for hardware evaluation and performance tuning."""

    def __init__(self):
        self.profile = self.evaluate_hardware()

    def evaluate_hardware(self) -> Dict[str, Any]:
        system_os = platform.system()
        arch = platform.machine().lower()
        cpu_count = os.cpu_count() or 2
        
        # Memory evaluation
        total_ram_gb = 4.0
        avail_ram_gb = 2.0
        try:
            import psutil
            mem = psutil.virtual_memory()
            total_ram_gb = round(mem.total / (1024 ** 3), 2)
            avail_ram_gb = round(mem.available / (1024 ** 3), 2)
        except Exception:
            # Fallback for Linux /proc/meminfo if psutil fails
            if os.path.exists("/proc/meminfo"):
                try:
                    with open("/proc/meminfo", "r") as f:
                        lines = f.readlines()
                    mem_info = {}
                    for line in lines:
                        parts = line.split(":")
                        if len(parts) == 2:
                            mem_info[parts[0].strip()] = parts[1].strip()
                    if "MemTotal" in mem_info:
                        kb = float(mem_info["MemTotal"].split()[0])
                        total_ram_gb = round(kb / (1024 ** 2), 2)
                    if "MemAvailable" in mem_info:
                        kb = float(mem_info["MemAvailable"].split()[0])
                        avail_ram_gb = round(kb / (1024 ** 2), 2)
                except Exception:
                    pass

        # GPU / Accelerator Detection
        gpu_type = "none"
        gpu_name = ""
        has_cuda = False
        has_metal = False
        has_vulkan = False

        # 1. Apple Metal
        if system_os == "Darwin" and ("arm" in arch or "aarch64" in arch):
            gpu_type = "metal"
            gpu_name = "Apple Silicon GPU (Metal)"
            has_metal = True

        # 2. NVIDIA CUDA
        if not has_metal:
            try:
                import torch
                if torch.cuda.is_available():
                    has_cuda = True
                    gpu_type = "cuda"
                    gpu_name = torch.cuda.get_device_name(0)
            except Exception:
                if shutil.which("nvidia-smi"):
                    try:
                        res = subprocess.run(
                            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2
                        )
                        if res.returncode == 0 and res.stdout.strip():
                            has_cuda = True
                            gpu_type = "cuda"
                            gpu_name = res.stdout.strip().split("\n")[0]
                    except Exception:
                        pass

        # 3. Vulkan (Cross-vendor AMD/Intel/NVIDIA)
        if gpu_type == "none" and shutil.which("vulkaninfo"):
            try:
                res = subprocess.run(["vulkaninfo", "--summary"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2)
                if res.returncode == 0:
                    has_vulkan = True
                    gpu_type = "vulkan"
                    gpu_name = "Vulkan Compute Accelerator"
            except Exception:
                pass

        # Low-End Classification:
        # If total RAM < 8GB or available RAM < 3GB, or CPU cores <= 4 without dedicated GPU,
        # it is considered a resource-constrained machine.
        is_low_end = False
        reasons = []

        if not has_cuda and not has_metal:
            if total_ram_gb < 8.5:
                is_low_end = True
                reasons.append(f"RAM is limited ({total_ram_gb} GB total, {avail_ram_gb} GB available)")
            if cpu_count <= 4:
                is_low_end = True
                reasons.append(f"CPU threads limited ({cpu_count} logical cores)")
            if avail_ram_gb < 2.5:
                is_low_end = True
                reasons.append(f"Low free memory ({avail_ram_gb} GB available)")
        else:
            # Has GPU, check if high-end
            is_low_end = False

        if is_low_end:
            recommended_engine = "faster-whisper-int8"
            recommended_model = "whisper-small" # or whisper-base fallback
            compute_type = "int8"
            device = "cpu"
            tier_label = "Low-End / Resource-Constrained (Optimized INT8)"
            summary = (
                f"Low-end hardware detected ({', '.join(reasons)}). "
                f"Using Faster-Whisper with INT8 quantization to ensure fluid transcription without system freezing."
            )
        else:
            recommended_engine = "whisper-turbo"
            recommended_model = "whisper-large-v3-turbo"
            compute_type = "float16" if has_cuda or has_metal else "int8"
            device = "cuda" if has_cuda else ("mps" if has_metal else "cpu")
            tier_label = "High-End / Accelerated (Whisper Turbo)"
            summary = (
                f"High-performance hardware detected ({gpu_name or f'{cpu_count} CPU cores with {total_ram_gb}GB RAM'}). "
                f"Whisper-Turbo selected for maximum transcription fidelity and speed."
            )

        # Thread tuning
        safe_threads = max(1, min(cpu_count - 1, 3)) if is_low_end else max(1, cpu_count - 1)
        os.environ.setdefault("OMP_NUM_THREADS", str(safe_threads))
        os.environ.setdefault("MKL_NUM_THREADS", str(safe_threads))

        return {
            "os": system_os,
            "arch": arch,
            "cpu_count": cpu_count,
            "total_ram_gb": total_ram_gb,
            "available_ram_gb": avail_ram_gb,
            "gpu_type": gpu_type,
            "gpu_name": gpu_name or "Integrated / None",
            "is_low_end": is_low_end,
            "tier_label": tier_label,
            "recommended_engine": recommended_engine,
            "recommended_model": recommended_model,
            "compute_type": compute_type,
            "device": device,
            "safe_threads": safe_threads,
            "summary": summary
        }

    def get_profile(self) -> Dict[str, Any]:
        return self.profile

    def refresh(self) -> Dict[str, Any]:
        self.profile = self.evaluate_hardware()
        return self.profile
