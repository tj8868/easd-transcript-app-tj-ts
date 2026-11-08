"""
Speaker Diarization & Timestamping Sub-Agent
Guarantees timestamps and speaker diarization labels on every transcript.
Generates [MM:SS] Speaker X: <text> formatting and multiple export styles (TXT, SRT, VTT, JSON).
"""

import re
from typing import List, Dict, Any, Optional

def format_seconds(seconds: float) -> str:
    """Formats seconds into MM:SS or HH:MM:SS."""
    sec = max(0, int(seconds))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def format_seconds_srt(seconds: float) -> str:
    """Formats seconds into HH:MM:SS,mmm for SRT."""
    sec = max(0.0, seconds)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def format_seconds_vtt(seconds: float) -> str:
    """Formats seconds into HH:MM:SS.mmm for VTT."""
    sec = max(0.0, seconds)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

class DiarizationWorkerSubAgent:
    """Sub-agent that processes raw audio transcription segments into speaker-attributed, timestamped outputs."""

    def __init__(self, pause_threshold_sec: float = 1.6, max_speakers: int = 4):
        self.pause_threshold_sec = pause_threshold_sec
        self.max_speakers = max_speakers

    def process_segments(
        self,
        raw_segments: List[Dict[str, Any]],
        time_offset: float = 0.0,
        initial_speaker: int = 1
    ) -> Dict[str, Any]:
        """
        Takes raw segments [{'start': 0.0, 'end': 2.5, 'text': '...'}]
        Applies conversational turn shift heuristics based on speech pauses,
        assigns speaker IDs, and attaches formatted timestamps.
        """
        if not raw_segments:
            return {
                "formatted_transcript": "",
                "segments": [],
                "speakers_detected": 1
            }

        processed_segments = []
        formatted_lines = []
        current_speaker = initial_speaker
        last_end = 0.0
        speakers_set = {initial_speaker}

        for seg in raw_segments:
            raw_text = seg.get("text", "").strip()
            if not raw_text:
                continue

            start = float(seg.get("start", 0.0)) + time_offset
            end = float(seg.get("end", start + 1.0)) + time_offset

            # Acoustic conversational turn shift detection
            # If silence gap between utterances > pause_threshold_sec, alternate speaker
            if last_end > 0.0 and (start - last_end) >= self.pause_threshold_sec:
                current_speaker = (current_speaker % self.max_speakers) + 1
                speakers_set.add(current_speaker)

            ts_str = format_seconds(start)
            speaker_tag = f"Speaker {current_speaker}"
            line = f"[{ts_str}] {speaker_tag}: {raw_text}"
            formatted_lines.append(line)

            processed_segments.append({
                "start": round(start, 2),
                "end": round(end, 2),
                "timestamp": f"[{ts_str}]",
                "speaker": speaker_tag,
                "speaker_id": current_speaker,
                "text": raw_text
            })

            last_end = end

        formatted_transcript = "\n".join(formatted_lines)
        return {
            "formatted_transcript": formatted_transcript,
            "segments": processed_segments,
            "speakers_detected": len(speakers_set)
        }

    def align_live_chunk(
        self,
        text: str,
        start_time: float,
        duration: float,
        current_speaker: int = 1
    ) -> Dict[str, Any]:
        """Aligns a single live chunk with speaker and timestamp."""
        ts_str = format_seconds(start_time)
        speaker_tag = f"Speaker {current_speaker}"
        formatted_line = f"[{ts_str}] {speaker_tag}: {text.strip()}"
        return {
            "formatted_line": formatted_line,
            "segment": {
                "start": round(start_time, 2),
                "end": round(start_time + duration, 2),
                "timestamp": f"[{ts_str}]",
                "speaker": speaker_tag,
                "speaker_id": current_speaker,
                "text": text.strip()
            }
        }

    def export_srt(self, segments: List[Dict[str, Any]]) -> str:
        """Converts segments to SubRip (.srt) subtitle format."""
        srt_lines = []
        for idx, seg in enumerate(segments, 1):
            start = format_seconds_srt(seg["start"])
            end = format_seconds_srt(seg["end"])
            speaker = seg.get("speaker", "Speaker 1")
            text = seg.get("text", "")
            srt_lines.append(f"{idx}\n{start} --> {end}\n[{speaker}] {text}\n")
        return "\n".join(srt_lines)

    def export_vtt(self, segments: List[Dict[str, Any]]) -> str:
        """Converts segments to WebVTT (.vtt) format."""
        vtt_lines = ["WEBVTT\n"]
        for idx, seg in enumerate(segments, 1):
            start = format_seconds_vtt(seg["start"])
            end = format_seconds_vtt(seg["end"])
            speaker = seg.get("speaker", "Speaker 1")
            text = seg.get("text", "")
            vtt_lines.append(f"{idx}\n{start} --> {end}\n<v {speaker}>{text}\n")
        return "\n".join(vtt_lines)
