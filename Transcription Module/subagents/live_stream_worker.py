"""
Live Stream Worker Sub-Agent
Handles real-time streaming audio ingestion from the Record button / Microphone.
Supports WebSocket and HTTP streaming chunk transcription with instant speaker diarization & timestamps.
"""

import os
import io
import time
import tempfile
import subprocess
import shutil
from typing import Dict, Any, Optional, List
try:
    from .diarization_worker import DiarizationWorkerSubAgent, format_seconds
except (ImportError, ValueError):
    from diarization_worker import DiarizationWorkerSubAgent, format_seconds

def find_ffmpeg_bin() -> str:
    """Finds ffmpeg from static_ffmpeg or system path."""
    bin_path = shutil.which("ffmpeg")
    if bin_path:
        return bin_path
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
        bin_path = shutil.which("ffmpeg")
        if bin_path:
            return bin_path
    except Exception:
        pass
    return "ffmpeg"

class LiveStreamWorkerSubAgent:
    """Sub-agent dedicated to low-latency Live Record transcription."""

    def __init__(self, whisper_worker, custom_api_gateway, diarizer: DiarizationWorkerSubAgent):
        self.whisper_worker = whisper_worker
        self.custom_api_gateway = custom_api_gateway
        self.diarizer = diarizer
        self.ffmpeg_bin = find_ffmpeg_bin()
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    def start_session(self, session_id: str, language: str = "auto") -> Dict[str, Any]:
        """Starts a new live recording session."""
        self.active_sessions[session_id] = {
            "session_id": session_id,
            "created_at": time.time(),
            "elapsed_sec": 0.0,
            "current_speaker": 1,
            "language": language,
            "segments": [],
            "full_transcript_lines": []
        }
        return {"status": "ready", "session_id": session_id}

    def convert_to_wav(self, audio_bytes: bytes, in_ext: str = "webm") -> Optional[str]:
        """Converts raw audio bytes (WebM, OGG, WAV) into 16kHz mono WAV for Whisper."""
        try:
            with tempfile.NamedTemporaryFile(suffix=f".{in_ext}", delete=False) as in_f:
                in_f.write(audio_bytes)
                in_path = in_f.name

            out_wav = in_path + ".wav"
            cmd = [
                self.ffmpeg_bin, "-y", "-i", in_path,
                "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                out_wav
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            try:
                os.remove(in_path)
            except Exception:
                pass

            if res.returncode == 0 and os.path.exists(out_wav) and os.path.getsize(out_wav) > 100:
                return out_wav
            if os.path.exists(out_wav):
                try:
                    os.remove(out_wav)
                except Exception:
                    pass
        except Exception as e:
            print(f"[LiveStreamWorker] FFmpeg audio conversion error: {e}")
        return None

    def process_live_chunk(
        self,
        session_id: str,
        audio_bytes: bytes,
        mime_type: str = "audio/webm",
        is_final: bool = False
    ) -> Dict[str, Any]:
        """Processes a live audio chunk, extracts speech, applies diarization and timestamps."""
        if not audio_bytes or len(audio_bytes) < 64:
            return {"text": "", "formatted_line": "", "segments": []}

        session = self.active_sessions.get(session_id)
        if not session:
            self.start_session(session_id)
            session = self.active_sessions[session_id]

        ext = "webm"
        if "wav" in mime_type:
            ext = "wav"
        elif "ogg" in mime_type or "opus" in mime_type:
            ext = "ogg"
        elif "mp4" in mime_type or "m4a" in mime_type:
            ext = "m4a"

        wav_path = self.convert_to_wav(audio_bytes, in_ext=ext)
        if not wav_path:
            return {"text": "", "formatted_line": "", "segments": []}

        try:
            raw_text = ""
            raw_segments = []

            # 1. Check if Custom API is enabled by user
            if self.custom_api_gateway.is_enabled():
                try:
                    api_res = self.custom_api_gateway.transcribe_audio_bytes(
                        audio_bytes=audio_bytes,
                        mime_type=mime_type,
                        language=session.get("language")
                    )
                    raw_text = api_res.get("text", "").strip()
                    raw_segments = api_res.get("raw_segments", [])
                except Exception as e:
                    print(f"[LiveStreamWorker] Custom API failed, falling back to local whisper: {e}")

            # 2. Local Whisper Inference
            if not raw_text:
                whisper_res = self.whisper_worker.transcribe(
                    audio_input=wav_path,
                    language=session.get("language"),
                    beam_size=1,  # greedy search for lowest latency
                    vad_filter=True
                )
                raw_text = whisper_res.get("text", "").strip()
                raw_segments = whisper_res.get("raw_segments", [])

            if not raw_text:
                return {"text": "", "formatted_line": "", "segments": []}

            # Align with session timestamps and speaker diarization
            chunk_start = session["elapsed_sec"]
            # Diarize segments
            diarized = self.diarizer.process_segments(
                raw_segments=raw_segments if raw_segments else [{"start": 0.0, "end": 2.0, "text": raw_text}],
                time_offset=chunk_start,
                initial_speaker=session["current_speaker"]
            )

            # Update session state
            for seg in diarized["segments"]:
                session["segments"].append(seg)
                session["full_transcript_lines"].append(f"[{seg['timestamp']}] {seg['speaker']}: {seg['text']}")
                session["current_speaker"] = seg["speaker_id"]
                session["elapsed_sec"] = max(session["elapsed_sec"], seg["end"])

            return {
                "text": raw_text,
                "formatted_transcript": diarized["formatted_transcript"],
                "segments": diarized["segments"],
                "is_final": is_final,
                "speakers_detected": diarized["speakers_detected"]
            }

        finally:
            if wav_path and os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except Exception:
                    pass

    def stop_session(self, session_id: str) -> Dict[str, Any]:
        """Finalizes session and returns full formatted transcript."""
        session = self.active_sessions.pop(session_id, None)
        if not session:
            return {"formatted_transcript": "", "segments": []}

        full_text = "\n".join(session["full_transcript_lines"])
        return {
            "formatted_transcript": full_text,
            "segments": session["segments"],
            "total_duration_sec": session["elapsed_sec"]
        }
