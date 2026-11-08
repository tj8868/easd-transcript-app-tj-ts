# EASD Meeting Minutes / eCommunicator — project notes for Claude

Code & data map (routes, functions, JSON stores, schemas): @CODEMAP.md

## What the app must do (the user's requirements)
1. Take bulk uploads (audio/video/text/images/PDF) or a live microphone recording.
2. Transcribe **verbatim** into the transcript box as `[MM:SS] Speaker N: text`
   (timestamps + speaker diarization; mixed Bangla/English kept as spoken).
3. Optionally convert the verbatim transcript to **English only** or **Bangla only**.
4. Fill the EASD `.docx` template (`EASD Meeting minutes - Template.docx`) from the transcript,
   via the JSON template definitions in `templates_store/templates.json`.

Target users are non-technical; UI must work on PC, tablet and phone.
Model preference: batch STT `gemini-3.5-transcribe`, live STT `gemini-3.5-transcribe-live`,
text LLM `gemini-3.8-flash` (confirmed working 2026-10-28). The two transcribe model IDs are
the app defaults but have not been confirmed against Google's model list.
Local models should use whatever GPU exists (NVIDIA, AMD, Intel Iris Xe / Arc / Core Ultra).
Cloud first, local automatically when the cloud is unavailable: STT Gemini → local Whisper
(stt_pipeline), template fill Gemini/Custom → local LLM → offline extraction
(`ai_providers.fill_template_locally`), translation cloud → local LLM for unconverted lines.
Local models (v8.9, 2026-10-29; all others deleted): STT `models/whisper-bengaliai`
(IamSanjid/tugstugi_bengaliai-regional-asr_whisper-medium-ct2, forced bn, no prompt, Bengali script;
large-v3-turbo auto on NVIDIA). LLM `models/gemma-4-E2B-it-Q4_0.gguf` via `bin/llama-server` built from
TheTom's TurboQuant fork (`scripts/build_llama_server.sh|.bat [vulkan|cuda|cpu]`), KV cache turbo4
(fork auto-upgrades K to q8_0 on Gemma 4). This PC's bin/ is a CPU build; the i3-1315U needs a vulkan build.
Language detection is restricted to bn/en; Bengali loop cut-off is compression 3.0 (2.4 dropped real speech).
On this 8 GB PC, parallel downloads/builds/transcriptions get OOM-killed: run them one at a time.

## Layout
- Launcher (the only one, all platforms): `run_app.pyw` [`console` | `shortcut`]. It hands off to `.venv`.
- Backend: FastAPI `app.py` (serves `frontend/dist`), run with `.venv/bin/python app.py`
  (binds 127.0.0.1:8000; `NO_BROWSER=true` to skip the app window).
- STT orchestration: `stt_pipeline.py` (chunking, Gemini → fallback model → local Whisper).
- `ai_providers.py`: `process_ai_request` (STT + template fill), live chunks, attendance.
- `local_whisper_engine.py` (faster-whisper / CTranslate2), `openvino_whisper_engine.py` (Intel GPU).
- `speaker_diarization.py`: local WeSpeaker ONNX voice embeddings + clustering
  (`models/wespeaker_resnet34_LM.onnx`, MFCC fallback).
- `transcript_translator.py`: English-only / Bangla-only conversion, `/api/translate_transcript`.
- `local_llm_engine.py`: `chat()` is the single local-LLM entry point: OpenVINO GenAI on Intel iGPUs
  (target laptop: i3-1315U), else llama-cpp-python (CPU wheel installed; Vulkan/TurboQuant optional builds).
- `template_engine.py`, `document_engine.py`: template JSON → .docx.
- Frontend: React + Vite in `frontend/` (`App.jsx`, `components/Transcripts.jsx`,
  `components/LiveRecordStudio.jsx`, `index.css`). Build: `cd frontend && npm run build`.
  On Linux the rolldown binding may be missing: `npm install --no-save @rolldown/binding-linux-x64-gnu@<rolldown version>`.
- `Transcription Module/`, `useless/`, `default_whisper_transcribe.py` are legacy/standalone; not used by the app.
- ffmpeg comes from the `static_ffmpeg` package in `.venv` (no system ffmpeg).

## Status (v8.9, branch `v8.9`, as of 2026-10-28)
All v8.9 work is **uncommitted** in the working tree. Full details: `v8.9_Fix_Report.html`
and `CHANGELOG_v8.9.md`. Files like `diag_logging.py`, `template_engine.py` and `Launch_App.bat`
were already modified (mostly line endings) before v8.9; leave them alone unless asked.

Done and verified: translation tabs, voice-based diarization + cross-chunk speaker matching,
timestamp fallback, live preview offset/timeline + live model + no event-loop blocking,
summarize error status, no shared `raw_transcript.txt`, attendance matching, CORS limited to
localhost, test import fixes, `tests/test_v89_fixes.py` (8 tests), GPU auto-selection, UI comfort CSS.

## Open items / next steps
- Try diarization on a real meeting recording; tune `EASD_DIARIZATION_THRESHOLD` (default 0.55) if needed.
- Confirm `gemini-3.5-transcribe` / `gemini-3.5-transcribe-live` exist in Google AI Studio.
- OpenVINO Whisper on a real Intel iGPU is untested (this PC's Haswell GPU is unsupported;
  only OpenVINO-CPU was tested). Look for the log line `OpenVINO Whisper ready: … device=GPU`.
- TurboQuant fork build (`scripts/build_llama_turboquant.sh`) not yet run; enable with
  `EASD_LOCAL_LLM_KV_CACHE=turbo3` only on that build (stock builds may crash on turbo types).
- The Gemini key used by the tests is rejected by Google (401); the test-suite failures are all environmental/outdated
  (see the report's test table). Wider UI redesign of Settings/Templates sections not done.
- Commit v8.9 when the user approves.

## Working conventions
- Run tests: `EASD_WHISPER_BACKEND=ctranslate2 .venv/bin/python -m pytest tests -q -p no:cacheprovider` (~7 min).
- Never print or commit API keys (`.env`, `api_settings.json`, `GeminiAPI.txt` are git-ignored).
- Keep every transcript line's `[MM:SS] Speaker N:` prefix intact in any processing step.
- Fail soft: transcription must still succeed if diarization/GPU/translation pieces fail.
- Write a `CHANGELOG_v<version>.md` and a human-readable fix report for each release.
