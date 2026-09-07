# Local Faster-Whisper Offline STT & Pre-warmed Auto-Language Engine (Revision v3.11)

Run OpenAI's Whisper model locally and 100% free forever on the user's machine using `faster-whisper` (CTranslate2 C++ engine). This completely eliminates reliance on fragile cloud STT APIs (Groq 404/403 and Google Gemini 429 quota exhaustion), keeps transcription strictly private, auto-detects between **English** and **Bengali (বাংলা)**, and pre-warms the model from `models/whisper-small` upon app startup.

## User Review Required

> [!IMPORTANT]
> - **100% Free & Local STT**: No API keys or external server calls are needed for audio transcription.
> - **App Startup Pre-warming**: When `app.py` boots, a lightweight background daemon thread loads `models/whisper-small` (483 MB) into RAM so speech-to-text inference is instant.
> - **Hardware Resource Optimization**: To prevent `mkl_malloc: failed to allocate memory` on 8 GB RAM machines, the engine uses `int8` quantization, restricts thread allocation (`OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2`, `cpu_threads=2`), and uses low-beam search (`beam_size=1` or `2`).
> - **Anti-Gibberish & Anti-Repetition**: An initial bilingual prompt (`"EASD Eminence Associates for Social Development. বাংলা এবং English আলোচনা ও কার্যবিবরণী।"`) combined with `repetition_penalty=1.15` and `no_repeat_ngram_size=3` ensures authentic Bengali script without Romanized gibberish or repetition loops.

## Proposed Changes

---

### Backend Components

#### [NEW] [local_whisper_engine.py](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/local_whisper_engine.py)
- Implements singleton `get_local_whisper_model(model_name="small")`.
- Resolves local model files from `models/whisper-small` (fallback to `models/whisper-base`), ensuring `local_files_only=True`.
- Applies environment variables `OMP_NUM_THREADS=2` and `MKL_NUM_THREADS=2`.
- Implements `warm_up_local_whisper_in_background()` for non-blocking startup caching.
- Implements `transcribe_local_audio(media_bytes, language=None, initial_prompt=...)`:
  - Converts/normalizes audio chunks to 16kHz mono.
  - Auto-detects between English (`en`) and Bengali (`bn`).
  - Formats timestamped output `[MM:SS] Speaker 1: <transcript>`.

#### [MODIFY] [app.py](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/app.py)
- Add `@app.on_event("startup")` hook to trigger `warm_up_local_whisper_in_background()`.
- Update `/api/live_transcribe_chunk` and `/api/transcribe_take` to route to `local_whisper_engine.transcribe_local_audio` when provider is `local_whisper` (or when no cloud key is provided).
- Support streaming over WebSocket `/ws/live_transcribe`.

#### [MODIFY] [ai_providers.py](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/ai_providers.py)
- Route `stt_prov in ["local_whisper", "local", "whisper_local"]` to `local_whisper_engine.transcribe_local_audio` in `process_ai_request` and `live_transcribe_audio_chunk`.
- Retain Google Gemini 3.7 Flash for executive summarization of the locally generated transcript.

#### [MODIFY] [api_settings.json](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/api_settings.json)
- Set `"transcription_provider": "local_whisper"`, `"transcription_model": "small"`.
- Maintain `"summarization_provider": "gemini"`, `"summarization_model": "gemini-3.7-flash"`.

---

### Frontend Components

#### [MODIFY] [apiKeyStorage.js](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/frontend/src/utils/apiKeyStorage.js)
- Register `local_whisper` as a primary STT provider:
  - Name: `"Local Whisper (Faster-Whisper)"`
  - Tag: `"⚡ 100% Free & Offline (Embedded)"`
  - Placeholder: `"No API key needed (Runs on your machine)"`
- Add `Local Whisper Small` to `QUICK_STT_MODELS`.

#### [MODIFY] [LiveRecordStudio.jsx](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/frontend/src/components/LiveRecordStudio.jsx)
- Display active STT engine badge: `Local Whisper (Embedded)`.
- Language selector dropdown: `Auto-Detect (Bangla / English)`, `বাংলা (Bangla)`, `English`.
- Immediate auto-transcribe of recorded takes on stop using local whisper.

#### [MODIFY] [SettingsModal.jsx](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/frontend/src/components/SettingsModal.jsx)
- Add "Local Whisper" card showing status: `Installed in models/whisper-small (Ready)`.

---

## Verification Plan

### Automated Tests
1. Unit test `local_whisper_engine.py`:
   - Verify model loads from `models/whisper-small` in < 4 seconds.
   - Run transcription on audio slice, ensuring no `mkl_malloc` error and correct language detection.
2. Endpoint verification:
   - Send multipart audio to `/api/transcribe_take` with `provider=local_whisper`.
   - Verify HTTP 200 response with timestamped transcript.

### Manual Verification
1. Start backend `python app.py`.
2. Observe startup log confirming background pre-warm of `models/whisper-small`.
3. Open `http://localhost:8000`.
4. Open **Live Record Studio**:
   - Record speech in Bangla: verify recognition in Bengali script.
   - Record speech in English: verify recognition in English.
   - Stop recording: verify instant take auto-transcription with 0 external API calls and 0 cloud errors.
5. Click **Generate Meeting Minutes**: verify Gemini 3.7 Flash produces the executive Word document from the local transcript.
