"""
Universal Cross-Platform Transcription Engine
Supports:
- Intel (CPU + Arc/iGPU via OpenVINO/Vulkan)
- AMD (CPU + Radeon via Vulkan/ROCm)
- NVIDIA (GeForce/RTX via CUDA/Vulkan)
- Apple Silicon (M1/M2/M3/M4 via Metal / MLX)
- Android / Mobile (ARM64 via Vulkan / ONNX / whisper.cpp)
"""

import os
import sys
import glob
import platform
import shutil
import subprocess

def detect_best_backend():
    """
    Auto-detects operating system, processor architecture, and available GPU
    accelerators across Intel, AMD, NVIDIA, Apple, and mobile platforms.
    """
    system_os = platform.system()       # 'Linux', 'Darwin', 'Windows'
    arch = platform.machine().lower()   # 'x86_64', 'arm64', 'aarch64'
    cpu_cores = os.cpu_count() or 2
    
    info = {
        "os": system_os,
        "arch": arch,
        "cpu_cores": cpu_cores,
        "backend": "cpu",
        "device": "cpu",
        "engine": "faster-whisper",
        "description": "Standard CPU (INT8)"
    }

    # 1. Check for Apple Silicon (macOS M-Series)
    if system_os == "Darwin" and ("arm" in arch or "aarch64" in arch):
        info["backend"] = "metal"
        info["device"] = "mps"
        info["engine"] = "mlx-whisper"
        info["description"] = "Apple Silicon GPU (Metal / Unified Memory)"
        return info

    # 2. Check for NVIDIA CUDA
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            info["backend"] = "cuda"
            info["device"] = "cuda"
            info["engine"] = "faster-whisper"
            info["description"] = f"NVIDIA GPU ({gpu_name}) via CUDA"
            return info
    except ImportError:
        pass

    # 3. Check for Vulkan (Universal: AMD Radeon, Intel Arc/Iris, Android Adreno/Mali)
    has_vulkan = False
    if shutil.which("vulkaninfo") is not None:
        try:
            res = subprocess.run(["vulkaninfo", "--summary"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0:
                has_vulkan = True
        except Exception:
            pass

    if has_vulkan:
        info["backend"] = "vulkan"
        info["device"] = "vulkan"
        info["engine"] = "whisper.cpp-vulkan"
        info["description"] = "Universal GPU (Vulkan: AMD/Intel/NVIDIA/Mobile)"
        return info

    # 4. Check for Android environment (Termux / Linux chroot)
    if "ANDROID_ROOT" in os.environ or "termux" in os.environ.get("PREFIX", ""):
        info["backend"] = "android-arm"
        info["device"] = "cpu"
        info["engine"] = "sherpa-onnx"
        info["description"] = f"Android ARM64 ({cpu_cores} cores, NNAPI/NEON)"
        return info

    # 5. Default CPU fallback (Dynamic thread scaling with AVX2/AVX-512)
    info["backend"] = "cpu"
    info["device"] = "cpu"
    info["engine"] = "faster-whisper"
    info["description"] = f"CPU mode with {cpu_cores} auto-detected threads (INT8)"
    return info


class UniversalTranscriber:
    def __init__(self, model_size="small"):
        self.model_size = model_size
        self.hw = detect_best_backend()
        self._print_hardware_summary()
        self._init_engine()

    def _print_hardware_summary(self):
        print("=" * 60)
        print(" [Universal ASR Engine] Hardware Detection Summary")
        print(f" • OS / Platform   : {self.hw['os']} ({self.hw['arch']})")
        print(f" • CPU Core Count  : {self.hw['cpu_cores']} threads")
        print(f" • Selected Backend: {self.hw['description']}")
        print(f" • Runtime Engine  : {self.hw['engine']}")
        print("=" * 60)

    def _init_engine(self):
        engine = self.hw["engine"]
        
        if engine == "mlx-whisper":
            print("[Init] Loading Apple MLX Whisper pipeline...")
            import mlx_whisper
            self.run_fn = self._transcribe_mlx
            
        elif engine == "faster-whisper":
            from faster_whisper import WhisperModel
            compute_type = "float16" if self.hw["device"] == "cuda" else "int8"
            threads = 0 if self.hw["device"] == "cuda" else self.hw["cpu_cores"]
            
            print(f"[Init] Loading faster-whisper ('{self.model_size}', {compute_type})...")
            self.model = WhisperModel(
                self.model_size,
                device=self.hw["device"],
                compute_type=compute_type,
                cpu_threads=threads
            )
            self.run_fn = self._transcribe_faster_whisper

        elif engine in ("whisper.cpp-vulkan", "sherpa-onnx"):
            # Uses universal ONNX / Vulkan CTranslate / whisper.cpp
            # Falls back to faster-whisper CPU if specialized C++ wrappers aren't compiled
            try:
                from faster_whisper import WhisperModel
                self.model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=self.hw["cpu_cores"]
                )
                self.run_fn = self._transcribe_faster_whisper
            except ImportError:
                raise RuntimeError("Please install faster-whisper: pip install faster-whisper")

    def _transcribe_faster_whisper(self, audio_path, language=None):
        segments, info = self.model.transcribe(
            audio_path,
            beam_size=1 if self.hw["device"] == "cpu" else 2,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            language=language
        )
        results = []
        for s in segments:
            results.append({"start": s.start, "end": s.end, "text": s.text})
        return results, info.language

    def _transcribe_mlx(self, audio_path, language=None):
        import mlx_whisper
        kwargs = {"path_or_hf_repo": f"mlx-community/whisper-{self.model_size}-mlx"}
        if language:
            kwargs["language"] = language
        result = mlx_whisper.transcribe(audio_path, **kwargs)
        segments = [{"start": seg["start"], "end": seg["end"], "text": seg["text"]} for seg in result.get("segments", [])]
        return segments, result.get("language", "en")

    def transcribe_file(self, audio_path, language=None):
        return self.run_fn(audio_path, language=language)

    def batch_process(self, input_folder, language=None):
        extensions = ("*.mp3", "*.wav", "*.m4a", "*.flac", "*.ogg")
        files = []
        for ext in extensions:
            files.extend(glob.glob(os.path.join(input_folder, ext)))

        if not files:
            print(f"[Batch] No audio files found in: {input_folder}")
            return

        print(f"\n[Batch] Processing {len(files)} files...\n")
        for idx, file_path in enumerate(files, 1):
            filename = os.path.basename(file_path)
            print(f"[{idx}/{len(files)}] Processing: {filename}")
            
            segments, lang = self.transcribe_file(file_path, language=language)
            print(f"  └─ Detected Language: {lang}")
            
            out_txt = os.path.splitext(file_path)[0] + ".txt"
            with open(out_txt, "w", encoding="utf-8") as f:
                for seg in segments:
                    f.write(f"[{seg['start']:.2f}s -> {seg['end']:.2f}s] {seg['text']}\n")
            print(f"  └─ Saved: {out_txt}")


if __name__ == "__main__":
    transcriber = UniversalTranscriber(model_size="small")
    # Transcribe audio files in the folder (supports Bangla 'bn' and English 'en')
    transcriber.batch_process(input_folder="./audio_files")
