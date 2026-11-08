"""
Whisper Worker Sub-Agent
Local Speech-to-Text inference powered by faster-whisper (CTranslate2).
Supports dynamic model switching:
- 'faster-whisper-int8' (INT8 quantized, fast, minimal RAM for low-end PCs)
- 'whisper-turbo' ('large-v3-turbo' for modern multi-core/GPU systems)
"""

import os
import io
import sys
import time
import threading
from typing import Dict, Any, Optional, List, Tuple

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PARENT_MODELS_DIR = os.path.join(os.path.dirname(_BASE_DIR), "models")
_LOCAL_MODELS_DIR = os.path.join(_BASE_DIR, "models")

class WhisperWorkerSubAgent:
    """Sub-agent managing faster-whisper model loading and audio transcription."""

    BILINGUAL_PROMPT = (
        "আজকের meeting এর agenda এবং আলোচনা। "
        "Budget review তে participants সবাই present ছিলেন। "
        "Action items ঠিক করা হয়েছে, decisions finalize হয়েছে। "
        "Proceedings verbatim transcription with speaker tags."
    )

    def __init__(self, hardware_profile: Dict[str, Any]):
        self.hw = hardware_profile
        self.lock = threading.Lock()
        self.loaded_model = None
        self.loaded_model_id = None
        self.loaded_compute_type = None

    def _resolve_model_path(self, model_choice: str) -> str:
        """
        Resolves local disk directory for model if available,
        otherwise returns the HuggingFace identifier.
        """
        m = (model_choice or "").strip().lower()

        # Map aliases
        if m in ("whisper-turbo", "turbo", "whisper-large-v3-turbo"):
            target_folders = ["whisper-large-v3-turbo", "large-v3-turbo"]
            default_hf = "deepdml/faster-whisper-large-v3-turbo"
        elif m in ("whisper-small", "small"):
            target_folders = ["whisper-small", "small"]
            default_hf = "small"
        elif m in ("whisper-base", "base"):
            target_folders = ["whisper-base", "base"]
            default_hf = "base"
        elif m in ("whisper-tiny", "tiny"):
            target_folders = ["whisper-tiny", "tiny"]
            default_hf = "tiny"
        else:
            target_folders = [m]
            default_hf = model_choice

        # Check local and parent model directories
        for check_dir in [_LOCAL_MODELS_DIR, _PARENT_MODELS_DIR]:
            if not os.path.exists(check_dir):
                continue
            for folder in target_folders:
                candidate = os.path.join(check_dir, folder)
                if os.path.isdir(candidate) and (
                    os.path.isfile(os.path.join(candidate, "model.bin")) or
                    os.path.isfile(os.path.join(candidate, "model.safetensors"))
                ):
                    return candidate

        return default_hf

    def load_model(self, model_choice: Optional[str] = None, force_reload: bool = False):
        """Loads or reuses the faster-whisper model based on requested choice."""
        with self.lock:
            # Determine target model
            if not model_choice:
                model_choice = self.hw.get("recommended_model", "whisper-small")

            model_path = self._resolve_model_path(model_choice)
            device = self.hw.get("device", "cpu")
            compute_type = self.hw.get("compute_type", "int8")
            cpu_threads = self.hw.get("safe_threads", 2)

            if not force_reload and self.loaded_model and self.loaded_model_id == model_choice:
                return self.loaded_model

            print(f"[WhisperWorker] Loading model '{model_choice}' (path={model_path}, device={device}, compute_type={compute_type}, threads={cpu_threads})...")
            from faster_whisper import WhisperModel

            t0 = time.time()
            model = WhisperModel(
                model_path,
                device=device,
                compute_type=compute_type,
                cpu_threads=cpu_threads,
                download_root=os.path.join(_BASE_DIR, "models")
            )
            elapsed = round(time.time() - t0, 2)
            print(f"[WhisperWorker] Model '{model_choice}' successfully loaded in {elapsed}s.")

            self.loaded_model = model
            self.loaded_model_id = model_choice
            self.loaded_compute_type = compute_type
            return self.loaded_model

    def transcribe(
        self,
        audio_input: Any,  # file path, audio bytes, or numpy array
        model_choice: Optional[str] = None,
        language: Optional[str] = None,
        beam_size: Optional[int] = None,
        vad_filter: bool = True
    ) -> Dict[str, Any]:
        """
        Executes faster-whisper transcription on the given audio.
        Returns {'text': str, 'segments': List[Dict], 'language': str, 'duration': float}
        """
        model = self.load_model(model_choice)

        if beam_size is None:
            # On low-end CPU, beam_size=1 (greedy search) is 2.5x faster without quality loss
            beam_size = 1 if self.hw.get("is_low_end") else 2

        vad_params = dict(
            threshold=0.5,
            min_speech_duration_ms=250,
            min_silence_duration_ms=600,
            speech_pad_ms=400
        )

        lang_arg = None if (not language or language in ("auto", "none")) else language

        t0 = time.time()
        segments_gen, info = model.transcribe(
            audio_input,
            beam_size=beam_size,
            language=lang_arg,
            initial_prompt=self.BILINGUAL_PROMPT,
            vad_filter=vad_filter,
            vad_parameters=vad_params,
            word_timestamps=False
        )

        raw_segments = []
        raw_texts = []
        for s in segments_gen:
            clean_text = s.text.strip()
            if clean_text:
                raw_segments.append({
                    "start": round(s.start, 2),
                    "end": round(s.end, 2),
                    "text": clean_text
                })
                raw_texts.append(clean_text)

        elapsed = round(time.time() - t0, 2)
        total_duration = round(getattr(info, "duration", 0.0), 2)
        detected_lang = getattr(info, "language", "auto")

        return {
            "text": " ".join(raw_texts),
            "raw_segments": raw_segments,
            "detected_language": detected_lang,
            "duration": total_duration,
            "inference_time_sec": elapsed,
            "model_used": self.loaded_model_id
        }
