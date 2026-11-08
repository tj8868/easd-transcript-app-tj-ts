# Universal Speech-to-Text (ASR) Engine Guide
**Target Languages:** Bangla (বাংলা) & English (including mixed Banglish code-switching)  
**Target Hardware:** Universal (Intel, AMD, NVIDIA, Apple Silicon, Android / Mobile, Multi-core CPUs)

---

## 1. Executive Summary

To achieve **maximum transcription speed and accuracy** without vendor lock-in or crashes across wildly different hardware:

1. **Language Coverage:** Whisper-based architectures remain the gold standard for **Bangla + English** multi-lingual transcription and code-switching.
2. **Universal Hardware Execution:**
   - **NVIDIA:** CUDA acceleration via FP16 Tensor cores.
   - **AMD & Intel (iGPUs / Arc / Radeon):** Hardware-accelerated via **Vulkan** compute or OpenVINO.
   - **Apple Silicon (Mac / iOS):** Accelerated via Apple **Metal** and **MLX** using unified memory.
   - **Android Phones (Snapdragon / MediaTek):** Accelerated via ARM64 NEON vector extensions and Vulkan (Adreno/Mali GPUs).
   - **Multi-core / Legacy CPUs:** Auto-detected thread counts (AVX2 / AVX-512) with INT8 quantization to prevent memory crashes.

---

## 2. Hardware & Backend Support Matrix

| Hardware Type | Chipsets / GPUs | Optimal Runtime Backend | Precision | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Intel (Desktop/Laptop)** | Intel HD, Iris Xe, Arc GPUs, Core CPUs | `faster-whisper` (INT8/AVX2) or `whisper.cpp` (Vulkan/OpenVINO) | INT8 / FP16 | Auto-scales to all available CPU threads. |
| **AMD (Desktop/Laptop)** | Ryzen CPUs, Radeon RX 5000-7000, APUs | `whisper.cpp` (Vulkan) or ROCm | FP16 / INT8 | Vulkan allows cross-vendor AMD GPU acceleration without ROCm headaches. |
| **NVIDIA (Desktop/Server)**| GTX, RTX, Tesla, A100 | `faster-whisper` (CUDA) | FP16 | Ultra-fast throughput via cuDNN / CTranslate2. |
| **Apple Silicon** | M1, M2, M3, M4 (Pro/Max/Ultra) | `mlx-whisper` (Metal) | FP16 | Native zero-copy unified memory; extremely fast and power-efficient. |
| **Android Mobile** | Snapdragon (Adreno), Dimensity (Mali) | `sherpa-onnx` or `whisper.cpp` (Android NDK) | INT8 / FP16 | Can run standalone in APKs or Termux; supports Vulkan and NNAPI. |

---

## 3. Recommended Whisper Model Sizes

For Bangla and English mixed processing:

| Model | Memory (RAM) | Relative Speed | Bengali Accuracy | Recommended Scenario |
| :--- | :--- | :--- | :--- | :--- |
| **`base`** | ~180 MB | Ultra Fast (3x–5x RTFx) | Moderate | Quick drafts, clean English, edge devices / older phones |
| **`small`** *(Recommended)* | ~480 MB | Fast (1.5x–2x RTFx) | High | **Optimal balance** for meeting minutes, interviews, mixed Banglish |
| **`medium`** | ~1.5 GB | Moderate (0.8x–1x RTFx) | Very High | Dedicated GPU/modern multi-core CPU setups |
| **`large-v3-turbo`**| ~1.0 GB | Moderate | State-of-the-Art | When maximum Bengali nuance is required and GPU/fast CPU is present |

---

## 4. Key Performance Optimizations

1. **Dynamic Thread Auto-Detection:**
   Never hardcode CPU thread counts. Use `os.cpu_count()` to dynamically saturate available CPU cores without overwhelming the host operating system.
2. **Voice Activity Detection (VAD):**
   Meeting recordings contain long pauses and silences. Enabling Silero VAD (`vad_filter=True`) automatically skips silence, reducing batch processing time by **30%–50%**.
3. **Beam Size Scaling:**
   - On **CPU / Mobile**: Use `beam_size=1` (Greedy Search) for ~2.5x speed boost with virtually identical quality on clean audio.
   - On **GPU**: Use `beam_size=2` or `5` for maximum transcription fidelity.

---

## 5. Software Requirements & Setup

### Python Environment (Desktop / Server / Termux):
```bash
# Core engine with AVX2/AVX-512 CPU and NVIDIA CUDA support:
pip install faster-whisper torch

# For Apple Silicon Macs (Metal acceleration):
pip install mlx-whisper

# For Vulkan utilities (if running AMD/Intel GPUs on Linux):
sudo apt install vulkan-tools libvulkan-dev
```

### Standalone C++ Engines (Android & Zero-Python Deployments):
* **[whisper.cpp](https://github.com/ggerganov/whisper.cpp):** Pure C/C++ engine supporting Vulkan (`-DGGML_VULKAN=1`) and Apple Metal.
* **[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx):** Pre-built Android APKs and libraries for Snapdragon/Mali acceleration via ONNX Runtime & Vulkan.
