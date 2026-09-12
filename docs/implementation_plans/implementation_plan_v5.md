# Implementation Plan (Branch: v5 / Version: v5)
**Status**: Active Specification & Canon  
**Target Branch**: `v5`  
**Standard**: RFC / Docs-as-Code Specification v5  
**Date**: September 2026  

---

## Branch Specification Overview
This specification governs all architectural, AI pipeline, multi-speaker diarization, real-time live studio, multi-document template synthesis, and cloud/offline speech recognition implementations on branch **`v5`**. In accordance with EASD Docs-as-Code standards:
- The major specification number maps directly to the active git branch (`v5`).
- Revisions are tracked across Milestones `5.1` through `5.7`.
- **v5 Canon** represents the unified enterprise milestone: **Multimodal Multi-Engine Transcription (Gemini 3.5 Transcribe & Local Faster-Whisper), WhisperX Neural Acoustic Diarization with Silence Fallback, Gemini 3.8 / 3.7 Flash Executive Summarization, Real-Time Live Speech Studio with Interim Preview, 100% Verbatim Speaker Controls, and Official EASD Multi-Document Template Generation**.

---

## Progressive Branch Evolution (v1 -> v5)

```
[Branch main (v1)]
   └── Baseline Multi-Document Template Engine & Core Transcriber
        │
        ▼
[Branch v2]
   └── Dynamic Reordering, Deep Dark Mode, Mobile Responsive Layout & Multi-Take Studio
        │
        ▼
[Branch v3]
   └── Decoupled STT/LLM, Masked Vault, Official EASD Word Template, Gemini 3.7 Interactions
        │
        ▼
[Branch v4]
   └── WhisperX Neural Diarization, Silence Fallback, Authentic Bengali STT, Live Auto-Preview
        │
        ▼
[Branch v5 (Current Active)]
   └── Enterprise Multimodal AI Hub: Gemini 3.8/3.7 Flash, Gemini 3.5 Transcribe,
       Local Faster-Whisper Offline STT, WhisperX Neural Diarization, Real-Time Auto-Preview Studio,
       and Unified Multi-Document Production Suite
```

---

## Revision Changelog (Branch: v5)

| Milestone | Scope & Deliverables | Status |
| :--- | :--- | :--- |
| **5.1** | **Gemini 3.5 Multilingual Audio Transcribe**: Integrated `gemini-3.5-transcribe` and `gemini-3.5-flash-lite` into STT pipelines with strict authentic Bengali script prompt enforcement and zero Romanized English gibberish. | Canonized |
| **5.2** | **Embedded Local Faster-Whisper Offline STT**: Full CTranslate2 offline speech engine with background startup daemon pre-warming, int8 memory clamping (`OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2`), bilingual prompt biasing, and repetition penalties. | Canonized |
| **5.3** | **Neural Diarization & Acoustic Silence Fallback**: Pyannote community pipeline (`pyannote/speaker-diarization-community-1`) with Hugging Face token vault, plus conversational pause turn-shift fallback (`> 1.8s`) for robust speaker segmentation. | Canonized |
| **5.4** | **Executive Summarization with Gemini 3.8 & 3.7 Flash**: High-speed thinking-level controlled synthesis producing structured agendas, 4-row discussions tables, and decision matrices with 100% template schema alignment. | Canonized |
| **5.5** | **Real-Time Live Speech Studio & Interim Auto-Preview**: Cross-browser audio recorder with animated waveform visualizer, pulsating live preview banner (`🎙️ Live Audio Instant Preview: AUTO-SYNCING`), multi-take manager, and instant take auto-transcription. | Canonized |
| **5.6** | **Interactive Speaker Controls & Verbatim Transcript Editor**: Single-stream transcript tier with timestamp badges (`[MM:SS]`), manual speaker chips (`+ Speaker 1`, `+ Speaker 2`, `+ Speaker 3`, `+ Current Time`), and 1-click `Auto-Tag Speakers & Time` wizard. | Canonized |
| **5.7** | **FastAPI Async Worker Concurrency & Multi-Device LAN Binding**: Non-blocking `asyncio.to_thread` execution for long-running STT/LLM requests, automatic MIME container resolution, and universal `0.0.0.0` LAN binding. | Canonized |

---

## Technical Specifications (v5 Canon)

### 1. Multimodal Multi-Engine Transcription Pipeline (`ai_providers.py`, `local_whisper_engine.py`)
- **Cloud STT Tier (Google Gemini)**:
  - Models: `gemini-3.5-transcribe`, `gemini-3.5-flash-lite`, `gemini-3.7-flash`.
  - SDK: Google GenAI SDK `client.models.generate_content` with raw audio bytes and MIME packaging, with graceful fallback to `client.interactions.create`.
  - Orthography: Mandatory prompt enforcement: Spoken Bengali is strictly transcribed into authentic Bengali script (`বাংলা লিপি`), and English into English script.
- **Offline STT Tier (Local Faster-Whisper)**:
  - Engine: CTranslate2 with `models/whisper-small` (fallback to `models/whisper-base`).
  - Threading & Memory: `OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2`, `cpu_threads=2`, `compute_type="int8"` preventing memory allocation exceptions on 8 GB RAM machines.
  - Zero Cloud Dependency: 100% private, zero cost, zero quota limitations (429), and zero API keys required.

### 2. Neural Multi-Speaker Diarization (`whisperx_diarization_engine.py`)
- **Acoustic Clustering & Temporal Alignment**:
  - Utilizes `pyannote/speaker-diarization-community-1` (or `pyannote/speaker-diarization-3.1`).
  - Token resolution hierarchy: CLI argument -> `HF_TOKEN` environment variable -> `HuggingFaceAPI.txt` -> `api_settings.json`.
  - Overlap matcher aligns acoustic speaker timestamps with faster-whisper ASR word segments.
- **Silence Duration Fallback**:
  - When Pyannote or GPU is unavailable, detects conversational pauses exceeding `1.8s` to alternate speaker turns (`Speaker 1:`, `Speaker 2:`) with exact timestamps (`[MM:SS]`).

### 3. Executive Summarization & Template Synthesis (`app.py`, `ai_providers.py`, `docx_engine.py`)
- **Multi-Model LLM Support**:
  - Primary: `gemini-3.8-flash` / `gemini-3.7-flash` (with low thinking latency).
  - Alternative: OpenAI `gpt-4o`, `gpt-4o-mini`, and local custom LLMs.
- **Template Registry**:
  - **Meeting Minutes**: Official EASD 4-row framework (Followup, Action items, Task assignments, Decisions) + 21-member attendance sheet.
  - **Government Report**: Bangladesh Secretariat Nothi format (স্মারক নং, পটভূমি, পর্যবেক্ষণ, সিদ্ধান্ত).
  - **Academic Journal & Press Release**: Specialized structured formats.
  - **Custom `.docx`**: Dynamic extraction of custom tags and tables from uploaded organizational documents.

### 4. Real-Time Live Speech Studio (`LiveRecordStudio.jsx`, `Transcripts.jsx`)
- **High-Fidelity Audio Capture**:
  - Multi-codec cross-browser recording (`audio/webm`, `audio/mp4`, `audio/wav`).
  - Real-time animated audio visualizer reflecting microphone gain.
- **Interim Speech Auto-Preview**:
  - High-visibility pulsating emerald bar displays transcribed words in real time.
  - Periodic chunk streaming to backend endpoints (`/api/live_transcribe_chunk`).
  - Auto-transcription trigger upon take completion.

### 5. Interactive Speaker Tagging & Verbatim Stream
- **Verbatim Tier Integrity**:
  - Verbatim audio transcription is strictly separated from executive summarization; raw speech is never truncated or synthetic.
- **1-Click Tagging Wizard**:
  - Insert speaker identifiers and timestamps dynamically.
  - Instant `Auto-Tag Speakers & Time` wizard for conversational formatting.

### 6. Security, Settings Vault & Network Accessibility
- **Masked Key Vault (`apiKeyStorage.js`, `SettingsModal.jsx`)**:
  - AES-encrypted or masked local storage for Gemini, OpenAI, Groq, and Hugging Face keys.
  - Live two-way verification endpoint (`/api/verify_ai_key`).
- **Network Deployment**:
  - Backend binds to `0.0.0.0:8000` for LAN access from smartphones, iPads, and conference room terminals.
  - Windows Unicode terminal output (`sys.stdout.reconfigure(encoding='utf-8')`) preventing cp1252 exceptions.

---

## Progressive Roadmap for v5 Evolution
- **v5.1 (Current Canon)**: Complete stabilization of dual-mode transcription, neural diarization, live speech studio, and EASD document generation.
- **v5.2 (Upcoming)**: WebSocket bidirectional live audio streaming with Gemini 3.5 Live API.
- **v5.3 (Upcoming)**: Multi-language auto-translation of meeting minutes into simultaneous English and Bengali editions.

---

## Verification & Build Instructions
1. **Frontend Production Build**:
   ```bash
   cd frontend
   npm run build
   ```
2. **Synchronize Static Bundle**:
   Verify `frontend/dist/` is deployed to `static/`.
3. **Launch Server**:
   ```cmd
   Launch_App.bat
   ```
   Or:
   ```bash
   python app.py
   ```
4. **Access Web Interface**:
   Navigate to `http://localhost:8000`.
