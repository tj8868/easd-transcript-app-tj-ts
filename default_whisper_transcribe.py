import sys
import os
import psutil
from faster_whisper import WhisperModel

def get_model_for_system_capacity() -> str:
    """
    Select optimal Whisper model based on host hardware capacity:
      - >= 16 GB RAM -> 'medium' (best for nuanced academic or medical interviews)
      - 8 - 16 GB RAM -> 'small'
      - 4 - 8 GB RAM  -> 'base'
      - < 4 GB RAM    -> 'tiny'
    """
    try:
        mem = psutil.virtual_memory()
        total_ram_gb = mem.total / (1024 ** 3)
        avail_ram_gb = mem.available / (1024 ** 3)

        if total_ram_gb >= 16.0 and avail_ram_gb >= 4.0:
            return "medium"
        elif total_ram_gb >= 8.0 and avail_ram_gb >= 1.5:
            return "small"
        elif total_ram_gb >= 4.0:
            return "base"
        else:
            return "tiny"
    except Exception:
        return "base"

def format_seconds_to_min_sec(seconds: float) -> str:
    """Formats duration in seconds into 'MM:SS' (or 'HH:MM:SS' if duration >= 1 hour)."""
    try:
        total_sec = round(max(0.0, float(seconds)))
    except (ValueError, TypeError):
        return "00:00"
    hrs = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"

# Determine model size based on system capacity (or user command-line override)
cli_model = sys.argv[2] if len(sys.argv) > 2 else ""
model_name = get_model_for_system_capacity() if (not cli_model or cli_model.lower() in ["auto", "detect", "default"]) else cli_model
audio_file = sys.argv[1] if len(sys.argv) > 1 else "interview_input.mp3"
output_file = sys.argv[3] if len(sys.argv) > 3 else "raw_transcript.txt"

print(f"System capacity detected: Loading '{model_name}' model...")

# If specified audio_file doesn't exist, check for workspace demo audio
if not os.path.exists(audio_file):
    if os.path.exists("test_slice2.mp3"):
        audio_file = "test_slice2.mp3"
        print(f"Notice: 'interview_input.mp3' not found, defaulting to '{audio_file}'")

# Check if model exists locally in models directory
local_dir = os.path.join("models", f"whisper-{model_name}")
target_model = local_dir if os.path.isdir(local_dir) else model_name

try:
    model = WhisperModel(target_model, device="cpu", compute_type="int8")
except Exception as e:
    # Fallback to local base, small, or tiny model if selected model weights are not downloaded
    for fb in ["whisper-base", "whisper-small", "whisper-tiny"]:
        fb_path = os.path.join("models", fb)
        if os.path.isdir(fb_path):
            print(f"Loading fallback local model from {fb_path}...")
            model = WhisperModel(fb_path, device="cpu", compute_type="int8")
            break
    else:
        raise e

print(f"Transcribing audio file: {audio_file} (Verbatim in exact source language)...")
segments, info = model.transcribe(
    audio_file,
    task="transcribe",
    temperature=0.0,
    beam_size=5,
    initial_prompt="EASD Eminence. বাংলা এবং English কার্যবিবরণী। Verbatim exact source language transcription without translation."
)

# Combine segments into a structured layout ready for your SOAK template
transcript_text = ""
current_spk = 1
last_end = 0.0
for segment in segments:
    # Autodetect conversational turn shifts based on speech pause (> 1.8s)
    if last_end > 0 and (segment.start - last_end) > 1.8:
        current_spk = 2 if current_spk == 1 else 1
    # Captures timestamps to maintain context anchor points in min and sec
    start_ts = format_seconds_to_min_sec(segment.start)
    end_ts = format_seconds_to_min_sec(segment.end)
    clean_text = (segment.text or "").strip()
    if clean_text:
        transcript_text += f"[{start_ts} - {end_ts}] Speaker {current_spk}: {clean_text}\n"
    last_end = segment.end

# Save the raw transcript if non-empty
if transcript_text.strip():
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(transcript_text)

print(f"Transcription complete! Saved to {output_file}.")
