# Implementation Plan (Branch: v4 / Version: v4)
**Status**: Completed & Canonized  
**Target Branch**: `v4`  
**Standard**: RFC / Docs-as-Code Specification v4  
**Date**: September 2026  

---

## Branch Specification Overview
This plan governs all architectural, AI pipeline, multi-speaker diarization, real-time live studio, and speech recognition implementations on branch **`v4`**. In accordance with EASD Docs-as-Code standards:
- The major specification number maps directly to the active git branch (`v4`).
- Revisions are tracked across Milestones `4.1` through `4.6`.
- **v4 Canon** represents the current production-ready version: **Neural Speaker Diarization (WhisperX & Pyannote), Authentic Bengali STT, Real-Time Live Audio Auto-Preview Studio, Asynchronous Non-Blocking Dispatch, and Decoupled Multi-Provider Architecture**.

---

## Revision Changelog (Branch: v4)

| Milestone | Scope & Deliverables | Status |
| :--- | :--- | :--- |
| **4.1** | **WhisperX & Pyannote Neural Diarization Engine**: Integrated `whisperx_diarization_engine.py` supporting Pyannote Community Pipeline (`pyannote/speaker-diarization-community-1` / `3.1`), Hugging Face authentication, and phoneme-level forced alignment. | Completed |
| **4.2** | **Acoustic Silence Fallback Diarizer**: Implemented local faster-whisper multi-compute fallback (`int8_float32`, `int8`, `float32`) with silence duration turn-shift detection (`> 1.8s`) automatically labeling speakers (`Speaker 1`, `Speaker 2`) and timestamps (`[MM:SS]`). | Completed |
| **4.3** | **Authentic Bengali Script & 100% Raw Speech Enforcement**: Strict prompt engineering in `ai_providers.py` preventing phonetic English Romanization of Bengali speech (ensuring pure বাংলা লিপি); dual-mode Gemini STT (`generate_content` + `interactions` fallback). | Completed |
| **4.4** | **Real-Time Live Speech Studio & Auto-Preview**: Real-time interim preview banner (`🎙️ Live Audio Instant Preview: AUTO-SYNCING`) in `Transcripts.jsx` and `LiveRecordStudio.jsx`; multi-take manager with live audio visualizer and instant take auto-transcription. | Completed |
| **4.5** | **Interactive Speaker Controls & Verbatim Editor**: Single unified transcript editor with manual speaker insertion buttons (`+ Speaker 1`, `+ Speaker 2`, `+ Speaker 3`, `+ Current Time`) and 1-click `Auto-Tag Speakers & Time` wizard. | Completed |
| **4.6** | **FastAPI Async Concurrency & Decoupled Providers**: Non-blocking `asyncio.to_thread` execution for long-running STT, OCR, and LLM jobs in `app.py`; audio MIME auto-detection; Groq Cloud decoupling; and LAN `0.0.0.0` binding. | Completed |

---

## Technical Specifications (v4 Canon)

### 1. Neural Speaker Diarization Engine (`whisperx_diarization_engine.py`)
- **Pyannote Community Pipeline**:
  - Pretrained pipeline: `pyannote/speaker-diarization-community-1` (fallback: `pyannote/speaker-diarization-3.1`).
  - Hugging Face token resolution from: function argument, `HF_TOKEN` / `HUGGINGFACE_TOKEN` env vars, `HuggingFaceAPI.txt`, or `api_settings.json`.
  - Secure token handling: Token files (`HuggingFaceAPI.txt`, `HF_TOKEN.txt`) strictly ignored in `.gitignore`.
- **Hybrid Temporal Overlap Matcher**:
  - Matches Pyannote acoustic speaker intervals to faster-whisper ASR segments based on maximum intersection-over-duration.
  - Generates standardized speaker lines: `[MM:SS] Speaker X: <text>`.
- **Memory & Hardware Optimizations**:
  - Automatic CUDA vs. CPU detection with INT8 quantization on CPU.
  - Explicit garbage collection and `torch.cuda.empty_cache()` between pipeline steps to run comfortably on standard workstations.

### 2. Local Whisper Diarization Fallback (`local_whisper_engine.py`)
- **Robust Multi-Compute Loading**:
  - Tries `int8_float32`, `int8`, and `float32` sequentially with CPU thread clamping (`cpu_threads=2`) to guarantee crash-free startup across diverse Windows CPU architectures.
- **Conversational Silence Detection**:
  - Automatically detects speaker turn transitions when pause between speech segments exceeds `1.8s`.
  - Rotates between `Speaker 1` and `Speaker 2` with exact `[MM:SS]` timestamps.

### 3. Authentic Bengali Script & Verbatim Speech Pipeline (`ai_providers.py`)
- **Orthography Enforcement**:
  - Enforces mandatory rules preventing phonetic Romanization: Spoken Bengali is transcribed strictly in authentic Bengali script (`বাংলা লিপি`), and English in English script.
- **Dual-Mode Gemini Multimodal ASR**:
  - Strategy 1: Modern `client.models.generate_content` with raw audio bytes and MIME packaging.
  - Strategy 2: Graceful fallback to `client.interactions.create`.
- **100% Raw Verbatim Transcript Tier**:
  - Verbatim audio transcription is strictly separated from LLM executive summarization. Spoken words are never summarized, sanitized, or truncated in the transcript tier.

### 4. Real-Time Live Speech Studio & Auto-Preview (`LiveRecordStudio.jsx`, `Transcripts.jsx`)
- **Instant Interim Preview**:
  - High-visibility pulsating emerald bar (`🎙️ Live Audio Instant Preview: AUTO-SYNCING`) displays speech words in real time as the speaker speaks.
- **Auto-Activation Banner**:
  - Displays cyan status banner (`⚡ Initial Transcript Auto-Activated`) while audio is streaming or processing into timestamped diarized text.
- **Multi-Take Studio**:
  - Allows recording discrete takes, playing them back with waveform visualizers, inspecting take raw transcripts, and auto-transcribing upon completion.
- **Manual & Automated Tagging**:
  - Quick-action buttons: `+ Speaker 1`, `+ Speaker 2`, `+ Speaker 3`, `+ Current Time`, and `Auto-Tag Speakers & Time` wizard.

### 5. FastAPI Asynchronous Concurrency (`app.py`)
- **Async Thread Offloading**:
  - Offloads `process_ai_request`, `transcribe_take_endpoint`, and `ocr_extract_and_optimize_endpoint` to worker threads via `asyncio.to_thread`.
  - Prevents blocking the Uvicorn event loop during heavy CPU inference or external API calls.
- **MIME Auto-Detection**:
  - Dynamically inspects file extensions (`.mp3`, `.wav`, `.m4a`, `.ogg`, `.webm`, `.mp4`, `.mov`) when uploaded with generic `application/octet-stream` headers.
- **Network Accessibility**:
  - Binds to `0.0.0.0` by default to enable local network/LAN access from tablets and secondary devices.

### 6. UI Simplification & Settings Architecture (`SettingsModal.jsx`, `apiKeyStorage.js`)
- **Segregated Providers**:
  - **Whisper**: Local offline transcription with zero key requirements.
  - **Gemini**: Unified STT & LLM (`gemini-3.7-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`).
  - **OpenAI**: Dedicated GPT LLM summarizers (`gpt-4o`, `gpt-4o-mini`, `o1-mini`).
  - **WhisperX / Hugging Face**: Dedicated token management for neural acoustic diarization.
- **Visual Design**:
  - Obsidian dark palette (`#090c12`, `#131722`), cyan/emerald status badges, and zero horizontal scroll.

---

## Verification & Deployment Guidelines
1. **Frontend Production Build**:
   ```bash
   cd frontend
   npm run build
   ```
   Synchronize `frontend/dist/` into `static/`.
2. **Launch Application**:
   ```cmd
   Launch_App.bat
   ```
   Access web interface at `http://localhost:8000`.
3. **Run Diarization & STT Verification**:
   - Verify local Whisper model status in Settings.
   - Test audio upload with Bengali speech to verify Bengali script output.
   - Verify multi-speaker diarization tags (`Speaker 1:`, `Speaker 2:`) and timestamps (`[MM:SS]`).
