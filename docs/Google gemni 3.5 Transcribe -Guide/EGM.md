# Google gemni 3.5 Transcribe -Guide

## Overview
Reference material only. It is not imported by the app. It holds a copy of Google's Gemini 3.5 Transcribe guide (`gemini_3_5_transcribe_live.md`) and a standalone sample script (`gemini_3_5_transcribe_live.py`) that streams microphone audio to the Live API.

## Interface
- `gemini_3_5_transcribe_live.py` (sample, run with `python gemini_3_5_transcribe_live.py`):
  - `streaming_main(config, record_seconds=None)`: opens `client.aio.live.connect(model=MODEL_ID_LIVE)`, captures mic audio, and returns the joined final transcript.
  - `send_microphone_audio(session, audio_queue)`: sends PCM blobs (`audio/pcm;rate=16000`) and finishes with `audio_stream_end=True`.
  - `receive_streaming_messages(session, transcript_buffer)`: prints `interim_input_transcription` in place and appends each final `input_transcription` to the buffer.
  - Constants: `MODEL_ID_LIVE = "gemini-3.5-transcribe-live-preview"`, `SEND_SAMPLE_RATE = 16000`, `CHANNELS = 1`, `BLOCK_DURATION = 0.1`.
- `gemini_3_5_transcribe_live.md`: guide text covering feature support and the limits of the live and synchronous endpoints.

## Invariants
- Audio is mono int16 PCM at 16 kHz, sent in 100 ms blocks (`sd.RawInputStream`).
- Mic capture starts only after the live session connects. A `None` sentinel on the queue stops the sender. The receiver gets 5 s to finish, then it is cancelled.
- The `__main__` config uses `response_modalities=["TEXT"]` and `input_audio_transcription=types.AudioTranscriptionConfig()`.

## Side Effects
- Microphone capture via `sounddevice`.
- Network: Gemini Live API through `genai.Client(enterprise=True, project=PROJECT_ID, location=LOCATION)`, using ADC credentials and the `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_REGION` env vars.
- At import, sets the `SSL_CERT_FILE` env var to the certifi bundle if it is unset. Installs a SIGINT handler. Writes to stdout.

## Verification
- Manual only: `pip install google-genai sounddevice certifi`, then `python gemini_3_5_transcribe_live.py`. There are no automated tests.
