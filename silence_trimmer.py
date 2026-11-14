"""
Silence trimming before speech-to-text (v9.0).

Long silent stretches (gaps between speakers, breaks, a recorder left running) are cut out of the
16 kHz mono audio before it is chunked and sent to Gemini or Whisper, so every chunk the model
receives is mostly speech. Each silence of TRIM_MIN_SILENCE_SEC or longer is shortened to about
2 x TRIM_PAD_SEC; shorter pauses are left alone so speech keeps its natural rhythm.

Because cutting audio moves everything after the cut earlier in time, trim_silence() returns a
time map, and remap_seconds() / remap_transcript_timestamps() convert timestamps on the trimmed
audio back to the original recording. Transcript timestamps therefore always refer to the
original file.

Memory stays flat for long recordings: the audio is decoded to a raw 16-bit file on disk and
read through numpy.memmap, and Silero VAD runs on fixed blocks (TRIM_VAD_BLOCK_SEC). Independent
blocks also stop the VAD's internal state from saturating on long noise stretches, the failure
local_whisper_engine.py works around with its 30 s-block cross-check.

Settings (environment variables):
  EASD_TRIM_SILENCE            1 (default) / 0 to switch trimming off
  EASD_TRIM_MIN_SILENCE_SEC    shortest silence that is cut (default 2.0)
  EASD_TRIM_PAD_SEC            speech padding kept on each side of a cut (default 0.4)
  EASD_TRIM_MIN_SAVING         skip trimming when less than this fraction would be removed (default 0.03)
  EASD_TRIM_VAD_THRESHOLD      Silero speech probability threshold (default 0.5)
"""
from __future__ import annotations

import bisect
import os
import re
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

from diag_logging import get_logger

_log = get_logger("silence")

SAMPLE_RATE = 16000
TRIM_ENABLED = os.environ.get("EASD_TRIM_SILENCE", "1").strip().lower() not in ("0", "false", "no", "off")
TRIM_MIN_SILENCE_SEC = float(os.environ.get("EASD_TRIM_MIN_SILENCE_SEC", "2.0"))
TRIM_PAD_SEC = float(os.environ.get("EASD_TRIM_PAD_SEC", "0.4"))
TRIM_MIN_SAVING = float(os.environ.get("EASD_TRIM_MIN_SAVING", "0.03"))
TRIM_VAD_THRESHOLD = float(os.environ.get("EASD_TRIM_VAD_THRESHOLD", "0.5"))
TRIM_VAD_BLOCK_SEC = 30

# One entry per kept stretch of audio: (start on trimmed audio, start on original audio, length), seconds.
TimeMap = List[Tuple[float, float, float]]

# Sentence appended to the transcription prompt when silence was removed.
STT_PROMPT_NOTE = (
    "Note: silent stretches longer than about {min_sil:g} seconds were removed from this audio before "
    "you received it, so it is continuous speech. Do not add lines for silence or pauses, and give "
    "timestamps for the audio exactly as you hear it - the app maps them back to the original recording."
)

# Sentence added to template-fill / translation prompts when the transcript came from trimmed audio.
LLM_TRANSCRIPT_NOTE = (
    "Silent stretches were removed from the audio before transcription. Timestamps refer to the original "
    "recording, so jumps between timestamps are removed silence, not missing content."
)


def _run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)


def _speech_spans(pcm, total_samples: int) -> List[Tuple[int, int]]:
    """Speech [start, end) sample ranges over the whole file, found block by block, merged."""
    import numpy as np
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    opts = VadOptions(threshold=TRIM_VAD_THRESHOLD, min_speech_duration_ms=250,
                      min_silence_duration_ms=int(TRIM_MIN_SILENCE_SEC * 1000),
                      speech_pad_ms=int(TRIM_PAD_SEC * 1000))
    block = TRIM_VAD_BLOCK_SEC * SAMPLE_RATE
    spans: List[Tuple[int, int]] = []
    for off in range(0, total_samples, block):
        audio = np.asarray(pcm[off:off + block], dtype=np.float32) / 32768.0
        for ts in get_speech_timestamps(audio, vad_options=opts, sampling_rate=SAMPLE_RATE):
            spans.append((off + int(ts["start"]), off + int(ts["end"])))
    # Merge overlaps, and spans split by a block edge or separated by less than the minimum silence.
    min_gap = int(TRIM_MIN_SILENCE_SEC * SAMPLE_RATE)
    merged: List[Tuple[int, int]] = []
    for s, e in spans:
        s, e = max(0, s), min(total_samples, e)
        if merged and s - merged[-1][1] < min_gap:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        elif e > s:
            merged.append((s, e))
    return merged


def trim_silence(input_audio: str, output_audio: str, ffmpeg_bin: str) -> Optional[Dict[str, Any]]:
    """
    Writes a copy of input_audio with long silences cut out to output_audio (16 kHz mono MP3).

    Returns None when nothing was written (trimming switched off, too little silence to bother, no
    speech found, or any error) - the caller then keeps using input_audio unchanged. Otherwise returns
    {"time_map": TimeMap, "original_sec", "trimmed_sec", "removed_sec", "segments"}.
    """
    if not TRIM_ENABLED:
        return None
    t0 = time.time()
    import numpy as np

    with tempfile.TemporaryDirectory() as tmp:
        raw_in = os.path.join(tmp, "in.s16")
        raw_out = os.path.join(tmp, "out.s16")
        try:
            res = _run([ffmpeg_bin, "-y", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", input_audio,
                        "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", raw_in])
            if res.returncode != 0 or not os.path.isfile(raw_in) or os.path.getsize(raw_in) < SAMPLE_RATE * 2:
                _log.warning("silence trim skipped: could not decode audio (%s)",
                             (res.stderr or b"")[-300:].decode("utf-8", "replace"))
                return None
            pcm = np.memmap(raw_in, dtype=np.int16, mode="r")
            total = int(pcm.shape[0])
            spans = _speech_spans(pcm, total)
            kept = sum(e - s for s, e in spans)
            original_sec, trimmed_sec = total / SAMPLE_RATE, kept / SAMPLE_RATE
            if not spans or kept < SAMPLE_RATE // 2:
                _log.warning("silence trim skipped: VAD found no speech in %.1fs of audio - sending it untrimmed",
                             original_sec)
                return None
            saving = 1.0 - kept / total
            if saving < TRIM_MIN_SAVING:
                _log.info("silence trim skipped: only %.1f%% silence in %.1fs (threshold %.0f%%)",
                          saving * 100, original_sec, TRIM_MIN_SAVING * 100)
                return None

            time_map: TimeMap = []
            pos = 0
            with open(raw_out, "wb") as out:
                for s, e in spans:
                    for b in range(s, e, SAMPLE_RATE * 60):  # copy in <=1 min slices
                        out.write(np.asarray(pcm[b:min(e, b + SAMPLE_RATE * 60)]).tobytes())
                    time_map.append((pos / SAMPLE_RATE, s / SAMPLE_RATE, (e - s) / SAMPLE_RATE))
                    pos += e - s
            del pcm

            res = _run([ffmpeg_bin, "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                        "-f", "s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-i", raw_out,
                        "-c:a", "libmp3lame", "-b:a", "48k", output_audio])
            if res.returncode != 0 or not os.path.isfile(output_audio) or os.path.getsize(output_audio) == 0:
                _log.warning("silence trim skipped: re-encode failed (%s)",
                             (res.stderr or b"")[-300:].decode("utf-8", "replace"))
                return None
        except Exception as e:  # never lose the audio because trimming failed
            _log.warning("silence trim skipped after error: %s: %s", type(e).__name__, e)
            return None

    info = {"time_map": time_map, "original_sec": round(original_sec, 2), "trimmed_sec": round(trimmed_sec, 2),
            "removed_sec": round(original_sec - trimmed_sec, 2), "segments": len(time_map)}
    _log.info("silence trim OK in %.1fs: %.1fs -> %.1fs (removed %.1fs = %.0f%%, %d speech stretches, "
              "cut silences >= %.1fs, pad %.1fs)", time.time() - t0, original_sec, trimmed_sec,
              original_sec - trimmed_sec, saving * 100, len(time_map), TRIM_MIN_SILENCE_SEC, TRIM_PAD_SEC)
    return info


def remap_seconds(t: float, time_map: Optional[TimeMap]) -> float:
    """Converts a time on the trimmed audio to the matching time on the original recording."""
    if not time_map:
        return t
    starts = [m[0] for m in time_map]
    i = max(0, bisect.bisect_right(starts, t) - 1)
    c_start, o_start, length = time_map[i]
    return o_start + min(max(0.0, t - c_start), length)


_TS_RE = re.compile(r"^\[(\d{1,3}):(\d{2})(?::(\d{2}))?\]")


def _fmt(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"[{h:02d}:{m:02d}:{s:02d}]" if h else f"[{m:02d}:{s:02d}]"


def remap_line_timestamp(line: str, time_map: Optional[TimeMap]) -> str:
    """Rewrites only the leading [MM:SS] / [HH:MM:SS] of a transcript line onto the original timeline."""
    if not time_map:
        return line
    m = _TS_RE.match(line)
    if not m:
        return line
    if m.group(3) is not None:
        t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    else:
        t = int(m.group(1)) * 60 + int(m.group(2))
    return _fmt(remap_seconds(t, time_map)) + line[m.end():]
