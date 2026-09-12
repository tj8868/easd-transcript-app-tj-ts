# Milestone Revision 11: Local Faster-Whisper Offline STT & Pre-warmed Auto-Language Engine

## Overview
Run OpenAI's Whisper model locally and 100% free forever on the user's workstation using `faster-whisper` (CTranslate2 C++ engine). This completely eliminates reliance on fragile cloud STT APIs (Groq 404/403 and Google Gemini 429 quota exhaustion), keeps audio transcription strictly private within local boundaries, auto-detects between **English** and **Bengali (বাংলা)**, and pre-warms the model from `models/whisper-small` upon app startup.

---

## Key Architecture & Deliverables

### 1. Hardware Resource & Concurrency Optimization
- **MKL Allocation Guard**: To prevent `mkl_malloc: failed to allocate memory` crashes on 8 GB RAM machines, the engine uses `int8` quantization, restricts thread allocation (`OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2`, `cpu_threads=2`), and utilizes low-beam search (`beam_size=1` or `2`).
- **Multi-Compute Fallback**: Tries `int8_float32`, `int8`, and `float32` sequentially with CPU thread clamping to guarantee crash-free startup across diverse CPU architectures.

### 2. Anti-Gibberish & Anti-Hallucination Biasing
- **Bilingual Initial Prompt**: An initial bilingual prompt (`"EASD Eminence Associates for Social Development. বাংলা এবং English আলোচনা ও কার্যবিবরণী।"`) combined with `repetition_penalty=1.15` and `no_repeat_ngram_size=3` ensures authentic Bengali script without Romanized phonetic gibberish or silence hallucination loops.
- **Timestamped Diarization Fallback**: Acoustic silence detection detects speaker turn transitions when pause between speech segments exceeds `1.8s`, formatting output with exact `[MM:SS]` timestamps and alternating speaker tags (`Speaker 1:`, `Speaker 2:`).

### 3. Background Pre-Warming Daemon
- Background daemon thread (`warm_up_local_whisper_in_background()`) initiated upon application startup (`@app.on_event("startup")`) in `app.py`.
- Non-blocking warmup ensures that first-time audio chunks or live recordings transcribe with sub-second latency.

### 4. Integration Endpoints & Provider Routing
- Route `/api/live_transcribe_chunk` and `/api/transcribe_take` to `local_whisper_engine.transcribe_local_audio` when provider is `local_whisper` (or when no cloud key is provided).
- Support streaming over WebSocket `/ws/live_transcribe`.
- Retain Google Gemini (e.g. `gemini-3.7-flash` / `gemini-3.8-flash`) as the executive minutes summarizer.

### 5. Frontend Controls & Settings
- `apiKeyStorage.js`: Register `local_whisper` as a primary STT provider with `"⚡ 100% Free & Offline (Embedded)"` and `"No API key needed (Runs on your machine)"`.
- `LiveRecordStudio.jsx`: Display active STT engine badge `Local Whisper (Embedded)` with language selector dropdown.
- `SettingsModal.jsx`: Provide Local Whisper status card with model loading feedback.
