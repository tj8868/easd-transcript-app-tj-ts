# Implementation Plan (Branch: v3 / Version: v3)
**Active Plan File**: [`docs/implementation_plans/implementation_plan_v3.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/implementation_plan_v3.md)  
**Detailed Revision File**: [`docs/implementation_plans/11_local_whisper_fast_offline_stt.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/11_local_whisper_fast_offline_stt.md)  
**Target Branch**: `v3`  
**Current Milestone**: Revision v3.11 — Local Faster-Whisper Offline STT & Pre-warmed Auto-Language Engine

---

## Version History Across Branches
- **Branch `main` (v1 Baseline)**: [`docs/implementation_plans/implementation_plan_v1.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/implementation_plan_v1.md)
- **Branch `v2` (Revisions v2.1 - v2.11)**: [`docs/implementation_plans/implementation_plan_v2.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/implementation_plan_v2.md)
- **Branch `v3` (Current Branch)**: [`docs/implementation_plans/implementation_plan_v3.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/implementation_plan_v3.md)
  - `v3.1`: Decouple STT and LLM models & providers
  - `v3.2`: Settings multi-key storage & masked vault
  - `v3.3`: Front-page top active engine indicator
  - `v3.4`: Official EASD Word template integration
  - `v3.5`: Dynamic multi-document template engine (5 types + custom docx)
  - `v3.6`: Verbatim multi-language STT transcription
  - `v3.7`: Zero sideways scrolling layout across all form factors
  - `v3.8`: Windows Unicode terminal output reconfiguration
  - `v3.9`: Gemini 3.7 Flash Interactions API fix & Fluent neutral dark mode
  - `v3.10`: Authentic Bengali STT engine enforcement, Groq bypass, and Real-Time Auto-Preview Live Speech Studio
  - `v3.11` (Current): Local Faster-Whisper Offline STT & Pre-warmed Auto-Language Engine

---

## Active Deliverables (Revision v3.11)

### 1. Embedded Local Faster-Whisper Model (`models/whisper-small` & `models/whisper-base`)
- Weights reside directly in project directory `models/whisper-small` (483 MB).
- 100% offline with zero cloud API keys, zero cost, and zero rate limits or 429 quota exhaustion.

### 2. Singleton Local Whisper Engine (`local_whisper_engine.py`)
- Background daemon warmup on application startup (`@app.on_event("startup")`).
- Safe threading guards (`OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2`, `cpu_threads=2`, `compute_type="int8"`) to prevent MKL memory allocation errors on 8 GB RAM machines.
- Bilingual prompt biasing (`initial_prompt="EASD Eminence Associates for Social Development. বাংলা এবং English আলোচনা ও কার্যবিবরণী।"`) to guarantee authentic Bengali script instead of Romanized gibberish.
- Repetition penalty (`repetition_penalty=1.15`, `no_repeat_ngram_size=3`, `condition_on_previous_text=False`) to eliminate hallucination loops on silence.

### 3. Application Endpoints & Provider Integration (`app.py`, `ai_providers.py`)
- Route `/api/live_transcribe_chunk` and `/api/transcribe_take` to `local_whisper_engine` when provider is `local_whisper` (or when cloud keys are absent).
- Support streaming audio chunks via WebSocket `/ws/live_transcribe`.
- Integrate into full meeting pipeline `/api/transcribe_and_summarize`.

### 4. Settings & Default Configuration (`api_settings.json`)
- Set `"transcription_provider": "local_whisper"`.
- Set `"transcription_model": "small"`.
- Keep Gemini 3.7 Flash as the executive minutes summarizer.

### 5. Frontend Controls (`apiKeyStorage.js`, `LiveRecordStudio.jsx`, `SettingsModal.jsx`)
- Expose "Local Whisper (100% Free & Offline)" with "No API key needed (Runs on your machine)".
- Provide language selector: Auto-Detect (Bangla/English), বাংলা (Bangla), English.
