# Implementation Plan 13: Gemini 3.5 Live Transcribe, Multilingual Code-Switching, Settings Developer Telemetry & Backend Speed Fix

## 1. Overview & Objectives
This plan resolves the core performance, model routing, and user interface requirements requested in Version 6:
1. **Gemini 3.5 Live Transcribe & Gemini 3.8 Flash Low**: Configure `gemini-3.5-transcribe-live` (with fallback to `gemini-3.5-transcribe` and `gemini-3.5-flash`) as the primary STT model, and `gemini-3.8-flash` with `thinking_level="low"` for fast executive meeting minutes synthesis. Purge deprecated `gemini-2.5-flash`.
2. **Eliminate the Backend Sources of 94% Freeze / Stalls**: Eliminate the root causes of backend transcription hangs:
   - Eliminate redundant triple execution of local Whisper in `app.py` `/api/transcribe_take`.
   - Eliminate CPU beam search bottlenecks by setting `beam_size=1` (greedy decoding) for a 3x-4x speedup.
   - Remove deprecated models from fallback cascades to prevent cascading API error timeouts.
   - Eliminate single-language locking in local Whisper (`detect_bilingual_audio_language`) so the engine dynamically detects segments without forcing all speech into one language token.
   - Remove the hardcoded `prev >= 94` freeze in `CircularProgressSpinner.jsx`, adding an active elapsed timer (`⏱️ 3.4s`).
3. **Mid-Sentence Code-Switching with Verbatim Zero-Translation**:
   - Explicit prompt instructions for Gemini and Whisper: Detect language switches dynamically per sentence and phrase (Bengali, English, and any arbitrary language). Output each in authentic native script without translation.
4. **Minimalist Hero Cards**:
   - Remove redundant top squircle buttons (`.hero-action-circle-btn.record-circle` and `.hero-action-circle-btn.upload-circle`). Leave strictly one primary button per card (Record on Card 1, Upload on Card 2).
5. **Settings Developer Mode & Telemetry**:
   - As directed by user, tuck the Live Metrics and Ping diagnostics safely inside **Settings -> Developer Mode**, keeping the main Live Studio interface ultra-clean.

---

## 2. Deliverables & Technical Changes

### 2.1 Backend Acceleration (`app.py`, `ai_providers.py`, `local_whisper_engine.py`)
- **Single-Path Guarded STT in `app.py`**:
  - In `/api/transcribe_take`, run primary STT. On failure, fall back to local Whisper exactly **once** with `beam_size=1` and `language=None`.
  - Remove duplicate Whisper fallbacks (lines 909-921 and lines 927-938).
- **Fast Ping Endpoint**:
  - Add `@app.get("/api/ping")` and `@app.post("/api/ping")` responding in `<5ms` with server timestamp, active engine, and RAM stats.
- **Model Migration**:
  - Replace `gemini-2.5-flash` with `gemini-3.5-flash` across `ai_providers.py`.
  - Set default STT model to `gemini-3.5-transcribe-live`.
  - Set default LLM model to `gemini-3.8-flash` with `types.ThinkingConfig(thinking_level="low")`.
- **Local Whisper Engine Enhancements**:
  - Default `beam_size=1` on CPU.
  - When `language="auto"`, pass `language=None` and `multilingual=True` into `model.transcribe()` instead of forcing single language code.
  - Condition autoregressive decoder with bilingual `initial_prompt`.
  - Expand text sanitizer regex to Unicode word characters (`\w`).

### 2.2 Frontend Streamlining (`LiveRecordStudio.jsx`, `SettingsModal.jsx`, `CircularProgressSpinner.jsx`)
- **Hero Card Minimalism**:
  - Delete `.hero-action-circle-btn.record-circle` and `.hero-action-circle-btn.upload-circle`.
  - Maintain single primary button per hero card.
- **Developer Telemetry in SettingsModal**:
  - Add a dedicated "Developer Diagnostics & Telemetry" section inside `SettingsModal.jsx` with:
    - `Test Server & AI Ping` button
    - Round-trip ping latency (ms)
    - Active STT model and latency
    - Active LLM model and latency
    - Last processing speed multiplier (e.g. `14.5x realtime`)
    - Server RAM and thread stats.
- **Spinner Dynamic Progression**:
  - Remove `if (prev >= 94) return prev;`.
  - Show active elapsed seconds timer (`⏱️ 3.4s`).
  - Smooth progression with dynamic stage labels.

---

## 3. Verification & Testing
1. Automated ping test via `/api/ping`.
2. Model health check on `gemini-3.5-transcribe-live` and `gemini-3.8-flash`.
3. CPU Whisper benchmark with `beam_size=1` verifying 3x-4x speedup.
4. Frontend build with `npm run build` and sync to `static/`.
5. Verify clean minimalist Hero Cards in browser and Developer Telemetry in Settings.
