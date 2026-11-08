# EASD Meeting Minutes / eCommunicator Blueprint

## System Overview

A local FastAPI app (`app.py`, bound to 127.0.0.1:8000, launched by `run_app.pyw`) that
serves the React SPA in `frontend/dist`. It turns uploads or live microphone audio into a
verbatim `[MM:SS] Speaker N:` transcript, optionally converts it to English-only or
Bangla-only, and fills `.docx` templates from it.

Pipeline: `media_processor.process_uploaded_media` → `ai_providers.process_ai_request` →
`stt_pipeline.transcribe_chunks` (Gemini, then local Whisper) → `speaker_diarization` →
template fill (Gemini / OpenAI-compatible endpoint, then `ai_providers.fill_template_locally`
→ `local_llm_engine.generate_template_fill`) → `document_engine` / `template_engine` → `.docx`.

There is **no SQL database**: state lives in JSON files and browser `localStorage`. See
[CODEMAP.md](./CODEMAP.md) for the full route table, record schemas and per-module function map.

## Local Interface & Invariants

**Interface** (root `.py` files)
- `[app.py]` 37 `@app.get/post` decorators over 29 unique `/api/*` paths (`/api/verify_key` and `/api/verify_api_key` share one handler) plus `WS /ws/live_transcribe`; Pydantic payloads `MeetingDocPayload`, `ApiSettingsPayload`, `SaveTemplatePayload`, `SaveSkillPayload`, `TranslatePayload`, `CloudImportPayload`, and others; helpers `find_available_port`, `is_server_already_running`, `open_native_app_window`.
- `[ai_providers.py:process_ai_request]` orchestration entry; `detect_text_language`, `transcribe_audio_chunks_detailed`, `live_transcribe_audio_chunk`, `summarize_text_gemini`, `summarize_text_openai_compatible`, `fill_template_locally`, `match_attendance_list`, `verify_ai_api_key`, `load_api_settings_from_disk` / `save_api_settings_to_disk`, `get_default_api_key_from_disk`.
- `[stt_pipeline.py]` `transcribe_chunks`, `gemini_transcribe_bytes`, `whisper_transcribe_bytes`, `format_ts`, `shift_line_timestamp`, `clamp_line_timestamp`.
- `[local_whisper_engine.py]` `transcribe_local_audio`, `get_local_whisper_model`, `detect_audio_language(_detail)` (alias `detect_bilingual_audio_language`), `convert_to_wav_pcm16k`, `get_engine_status`.
- `[openvino_whisper_engine.py]` `should_use`, `transcribe_samples`, `available_devices`, `status`.
- `[speaker_diarization.py]` `diarize_wav_segments`, `unify_chunk_speakers`, `cluster_embeddings`, `active_backend`.
- `[transcript_translator.py:translate_transcript]`.
- `[local_llm_engine.py]` `chat`, `generate_template_fill`, `get_local_llm_status`, `ensure_model_downloaded`, `LocalLLMUnavailable`.
- `[template_engine.py]` `load_saved_templates`, `get_template_by_id`, `save_custom_template`, `delete_custom_template`, `analyze_and_generalize_docx`, `generate_custom_template_docx_bytes`, `get_template_json_schema` / `get_template_json_example`.
- `[document_engine.py]` `generate_meeting_minutes_docx_bytes`, `DEFAULT_MEMBERS`.
- `[media_processor.py]` `process_uploaded_media`, `convert_media_to_speech_audio`, `split_audio_into_chunks`, `find_ffmpeg_binary`.
- `[ocr_engine.py]` `perform_local_ocr`, `perform_ai_vision_ocr`, `extract_pdf_content`, `optimize_ocr_text`.
- `[skills_engine.py]` `load_saved_skills`, `save_custom_skill`, `delete_custom_skill`.
- `[gdrive_service.py]` `upload_docx_to_gdrive`, `get_or_create_easd_folder`.
- `[diag_logging.py]` `setup_logging`, `get_logger`, `new_job_id`, `bind_job_id`, `redact_key`; env `EASD_LOG_FILE`, `EASD_LOG_LEVEL`.
- Environment variables:

  | Area | Variables (default) | Source |
  |---|---|---|
  | Server | `HOST` (127.0.0.1), `NO_BROWSER`, `CODESPACES`, `EASD_ALLOWED_ORIGINS` | `app.py` |
  | Keys | `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `CUSTOM_API_KEY`, `CUSTOM_API_BASE_URL`, `CUSTOM_API_MODEL` | `app.py`, `ai_providers.py` |
  | Gemini STT | `EASD_GEMINI_STT_MODEL` (gemini-3.5-transcribe), `EASD_GEMINI_STT_FALLBACK_MODELS` (gemini-2.5-flash), `EASD_GEMINI_MAX_PARALLEL` (2), `EASD_GEMINI_STAGGER_SEC` (1.5), `EASD_GEMINI_MAX_ATTEMPTS` (4), `EASD_GEMINI_BACKOFF_BASE_SEC` (4), `EASD_GEMINI_BACKOFF_MAX_SEC` (60), `EASD_GEMINI_HTTP_TIMEOUT_MS` (600000), `EASD_GEMINI_INLINE_MAX_BYTES` (14 MiB) | `stt_pipeline.py:47-56` |
  | Whisper | `EASD_WHISPER_BACKEND` (auto), `EASD_WHISPER_DEVICE` (auto), `EASD_WHISPER_EN_CONFIDENCE` (0.5), `EASD_WHISPER_GPU_TURBO` (1), `EASD_DEBUG_SAVE_TRANSCRIPT`, `EASD_OV_WHISPER_MODEL`, `EASD_OV_DEVICE` | `local_whisper_engine.py`, `openvino_whisper_engine.py` |
  | Diarization | `EASD_DIARIZATION` (on), `EASD_DIARIZATION_THRESHOLD`, `EASD_DIARIZATION_MAX_SPEAKERS` (10), `EASD_DIARIZATION_DEVICE`, `EASD_DIARIZATION_NO_DOWNLOAD` | `speaker_diarization.py` |
  | Local LLM | `EASD_LOCAL_LLM_MODEL` (gemma-4-e2b), `EASD_LOCAL_LLM_DIR`, `EASD_LOCAL_LLM_BACKEND`, `EASD_LOCAL_LLM_GPU_LAYERS` (99), `EASD_LOCAL_LLM_KV_CACHE` (`""` in-process at `local_llm_engine.py:424`; `turbo4` for `bin/llama-server` at `:620`), `EASD_LLM_BACKEND`, `EASD_OV_LLM_MODEL`, `EASD_LLAMA_SERVER` | `local_llm_engine.py` |
  | Logging | `EASD_LOG_FILE` (`app_service.log`), `EASD_LOG_LEVEL` (INFO) | `diag_logging.py` |
- Legacy standalone scripts: `default_whisper_transcribe.py`, `diag_long_audio_repro.py`.

**Invariants**
- `[app.py:_save_upload_limited]` uploads are rejected once they exceed `MAX_UPLOAD_SIZE` (1 GB). `frontend/src/components/LiveRecordStudio.jsx:MAX_UPLOAD_BYTES` must match.
- `[app.py:_extra_origins]` CORS allows only localhost / 127.0.0.1 / [::1] plus `EASD_ALLOWED_ORIGINS`.
- `[stt_pipeline.py:_TS_RE]`, `[transcript_translator.py:_PREFIX_RE]` keep the `[MM:SS] Speaker N:` prefix; it is never sent to a translation model.
- `[stt_pipeline.py:transcribe_chunks]` if Gemini fails for a chunk, that chunk falls back to local Whisper. Retries are capped by `EASD_GEMINI_MAX_ATTEMPTS` (4), and parallel Gemini calls by `EASD_GEMINI_MAX_PARALLEL` (2). A second cap, `ai_providers.MAX_CONCURRENT_CHUNKS` (5, `ai_providers.py:1153`), limits async chunk transcription.
- `[local_whisper_engine.py:detect_audio_language_detail]` picks only `bn` or `en` (en when p(en) ≥ `EASD_WHISPER_EN_CONFIDENCE`). If detection fails it returns no language and Whisper auto-detects (`local_whisper_engine.py:116-135`). `_max_compression` is 3.0 for bn and 2.4 for other languages.
- `[speaker_diarization.py:_THRESHOLDS]` defaults: neural 0.55, MFCC 0.9.
- `[template_engine.py:delete_custom_template]`, `[skills_engine.py:delete_custom_skill]` refuse to delete built-in records. Custom ids are `custom_tpl_<8hex>` and `custom_<8hex>`.
- `[ai_providers.py:get_default_api_key_from_disk]` key order: `api_settings.json`, then `GeminiAPI.txt`, then `GEMINI_API_KEY`, then `GOOGLE_API_KEY`.

## Subdirectories & System Boundaries

- frontend: [./frontend/EGM.md](./frontend/EGM.md) - Vite + React 19 SPA. Talks to the backend only over relative `/api` and `/ws` URLs and keeps settings and API keys in `localStorage`.
- scripts: [./scripts/EGM.md](./scripts/EGM.md) - builds `bin/llama-server` from the TurboQuant llama.cpp fork (vulkan / cuda / cpu).
- docs: [./docs/EGM.md](./docs/EGM.md) - reference material only, including a standalone Gemini 3.5 Transcribe Live sample.
- Transcription Module: [./Transcription%20Module/EGM.md](./Transcription%20Module/EGM.md) - legacy standalone FastAPI transcription server (port 8085), not used by the app.
- useless: [./useless/EGM.md](./useless/EGM.md) - legacy packaging, launch and WhisperX scripts, not used by the app.
- Data stores (no code): `templates_store/` (`templates.json`, `custom_docx/`), `skills_store/skills.json`, `models/`, `bin/`. Their schemas are in [CODEMAP.md](./CODEMAP.md).
- Excluded: `tests/` (test-only), `static/` (built bundle), `Architecture/`, `evals/` (no source).

## Global Invariants

- Fail soft: transcription must still succeed if diarization, GPU or translation pieces fail.
- Cloud first, then local: STT goes Gemini → Whisper; template fill goes Gemini/custom → local LLM → offline extraction; translation goes cloud → local LLM.
- Keys pass through `diag_logging.redact_key` before logging. `.env`, `api_settings.json` and `GeminiAPI.txt` are git-ignored and must never be printed.

## Global Side Effects

- Disk writes: `api_settings.json`, `.env`, `GeminiAPI.txt` (`ai_providers.save_api_settings_to_disk`), `templates_store/*`, `skills_store/skills.json`, `app_service.log`, `llama_server.log`, `models/.ov_cache`, and temp WAV files.
- Network: Google GenAI (STT, LLM, Live); OpenAI-compatible endpoints; Google Drive API (`gdrive_service`); Drive/OneDrive downloads (`app.py:import_cloud_file`); Hugging Face model downloads (Whisper, WeSpeaker, GGUF, OpenVINO).
- Subprocesses: ffmpeg/ffprobe, tesseract, `bin/llama-server` (local HTTP on 127.0.0.1), and an Edge/Chrome app window.
- Process-wide: `os.environ` keys are updated on settings save; `OMP_NUM_THREADS` / `MKL_NUM_THREADS` get a default at import via `os.environ.setdefault`, so a value already set is never overridden (`local_whisper_engine.py:32`).

## System Verification

- Run: `EASD_WHISPER_BACKEND=ctranslate2 .venv/bin/python -m pytest tests -q -p no:cacheprovider`
- Frontend: `cd frontend && npm test`
