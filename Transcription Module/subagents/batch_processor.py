"""
Batch Processor Sub-Agent
Handles file uploads and batch processing for audio & video media files.
Performs FFmpeg normalization, long audio segmentation, progress tracking,
and speaker diarization with timestamps.
"""

import os
import sys
import time
import shutil
import tempfile
import subprocess
from typing import Dict, Any, List, Optional
try:
    from .diarization_worker import DiarizationWorkerSubAgent, format_seconds
except (ImportError, ValueError):
    from diarization_worker import DiarizationWorkerSubAgent, format_seconds

def get_ffmpeg() -> str:
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

def probe_duration(file_path: str, ffmpeg_bin: str) -> float:
    """Probes media duration in seconds using ffprobe or ffmpeg."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            cmd = [
                ffprobe, "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", file_path
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if res.returncode == 0 and res.stdout.strip():
                return max(0.0, float(res.stdout.strip()))
        except Exception:
            pass
    # Fallback to ffmpeg parse
    try:
        cmd = [ffmpeg_bin, "-i", file_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        output = res.stderr
        import re
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
        if m:
            h, m_val, s = m.groups()
            return int(h) * 3600 + int(m_val) * 60 + float(s)
    except Exception:
        pass
    return 0.0

class BatchProcessorSubAgent:
    """Sub-agent managing Batch Processing for Upload files."""

    def __init__(self, whisper_worker, custom_api_gateway, diarizer: DiarizationWorkerSubAgent):
        self.whisper_worker = whisper_worker
        self.custom_api_gateway = custom_api_gateway
        self.diarizer = diarizer
        self.ffmpeg_bin = get_ffmpeg()
        self.jobs: Dict[str, Dict[str, Any]] = {}

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        return self.jobs.get(job_id, {"status": "not_found", "progress": 0, "message": "Job not found"})

    def process_file(
        self,
        job_id: str,
        input_path: str,
        original_filename: str,
        language: Optional[str] = "auto"
    ) -> Dict[str, Any]:
        """
        Executes full batch transcription pipeline on an uploaded file.
        Updates job status dynamically and outputs timestamped + diarized results.
        """
        self.jobs[job_id] = {
            "job_id": job_id,
            "filename": original_filename,
            "status": "processing",
            "stage": "converting",
            "progress": 10,
            "message": f"Normalizing audio for '{original_filename}' via FFmpeg...",
            "created_at": time.time()
        }

        temp_files_to_clean = []
        try:
            # 1. Convert media to 16 kHz mono WAV
            total_duration = probe_duration(input_path, self.ffmpeg_bin)
            converted_wav = input_path + "_norm.wav"
            temp_files_to_clean.append(converted_wav)

            cmd = [
                self.ffmpeg_bin, "-y", "-i", input_path,
                "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                converted_wav
            ]
            conv_res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if conv_res.returncode != 0 or not os.path.exists(converted_wav):
                raise RuntimeError(f"FFmpeg failed to extract audio from '{original_filename}'.")

            if total_duration <= 0.0:
                total_duration = probe_duration(converted_wav, self.ffmpeg_bin)

            self.jobs[job_id]["progress"] = 30
            self.jobs[job_id]["stage"] = "transcribing"
            self.jobs[job_id]["message"] = f"Transcribing audio ({format_seconds(total_duration)})..."

            # 2. Determine if Custom API or Local Whisper
            raw_segments = []
            all_text_parts = []
            provider_used = "faster-whisper"

            if self.custom_api_gateway.is_enabled():
                self.jobs[job_id]["message"] = "Sending audio to Custom API Gateway..."
                with open(converted_wav, "rb") as f:
                    audio_bytes = f.read()
                api_res = self.custom_api_gateway.transcribe_audio_bytes(
                    audio_bytes=audio_bytes,
                    filename=original_filename,
                    mime_type="audio/wav",
                    language=language
                )
                raw_segments = api_res.get("raw_segments", [])
                all_text_parts.append(api_res.get("text", ""))
                provider_used = api_res.get("provider", "Custom API")
            else:
                # Local Whisper
                self.jobs[job_id]["message"] = "Processing speech with Local Whisper Engine..."
                whisper_res = self.whisper_worker.transcribe(
                    audio_input=converted_wav,
                    language=language,
                    vad_filter=True
                )
                raw_segments = whisper_res.get("raw_segments", [])
                all_text_parts.append(whisper_res.get("text", ""))
                provider_used = f"Local Whisper ({whisper_res.get('model_used')})"

            self.jobs[job_id]["progress"] = 80
            self.jobs[job_id]["stage"] = "diarizing"
            self.jobs[job_id]["message"] = "Applying speaker diarization and timestamp alignment..."

            # 3. Speaker Diarization & Timestamps Alignment
            diarized = self.diarizer.process_segments(raw_segments)
            formatted_transcript = diarized["formatted_transcript"]
            segments = diarized["segments"]

            # Exports
            srt_content = self.diarizer.export_srt(segments)
            vtt_content = self.diarizer.export_vtt(segments)

            result = {
                "status": "success",
                "job_id": job_id,
                "filename": original_filename,
                "duration_seconds": total_duration,
                "duration_formatted": format_seconds(total_duration),
                "speakers_detected": diarized["speakers_detected"],
                "provider": provider_used,
                "formatted_transcript": formatted_transcript,
                "clean_text": " ".join(all_text_parts).strip(),
                "segments": segments,
                "srt": srt_content,
                "vtt": vtt_content
            }

            self.jobs[job_id].update({
                "status": "success",
                "stage": "completed",
                "progress": 100,
                "message": f"Transcription completed for '{original_filename}'!",
                "result": result
            })

            return result

        except Exception as e:
            err_msg = str(e)
            self.jobs[job_id].update({
                "status": "error",
                "stage": "failed",
                "progress": 0,
                "message": f"Error: {err_msg}",
                "error": err_msg
            })
            return {"status": "error", "error": err_msg, "job_id": job_id}

        finally:
            for tf in temp_files_to_clean:
                if tf and os.path.exists(tf):
                    try:
                        os.remove(tf)
                    except Exception:
                        pass
