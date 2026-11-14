# Code & Data Map (EGM contract) — for agents

Generated 2026-11-08 from the source in this directory. Imported by `CLAUDE.md`.
Every entry cites `file:symbol`. Re-check line numbers with `grep -n` before editing.

## 1. "Database": there is no SQL/ORM database

All persistent state is JSON or files on disk, plus browser `localStorage`.

| Store | Owner (read / write) | Shape |
|---|---|---|
| `templates_store/templates.json` | `template_engine.py:TEMPLATES_JSON_PATH` → `load_saved_templates` / `save_templates_to_disk`, `save_custom_template`, `delete_custom_template` | list of template objects (11 today) |
| `templates_store/custom_docx/*.docx` | `template_engine.analyze_and_generalize_docx`, `generate_custom_template_docx_bytes` | uploaded `.docx` layouts, named `custom_tpl_<hex>.docx` |
| `skills_store/skills.json` | `skills_engine.py:SKILLS_JSON_PATH` → `load_saved_skills` / `save_skills_to_disk`, `save_custom_skill`, `delete_custom_skill` | list of skills (5 today) |
| `api_settings.json` (git-ignored, **holds keys**) | `ai_providers.py:SETTINGS_FILE` → `load_api_settings_from_disk` / `save_api_settings_to_disk` | flat object, see `ApiSettingsPayload` |
| `GeminiAPI.txt` (git-ignored, **key**) | `ai_providers.py:GEMINI_KEY_FILE` → `get_default_api_key_from_disk` | single key string |
| `.env` (git-ignored) | read by `app.py:get_env_keys_endpoint` | env keys |
| `EASD Meeting minutes - Template.docx` | `app.py:TEMPLATE_PATH`, `document_engine.generate_meeting_minutes_docx_bytes` | official minutes layout |
| `models/` | `local_whisper_engine.get_model_path`, `local_llm_engine.get_model_path`, `speaker_diarization._ensure_neural_model` | `whisper-bengaliai/`, `gemma-4-E2B-it-Q4_0.gguf`, `wespeaker_resnet34_LM.onnx`; v9.0 switching (when `EASD_CODE_SWITCH=1`): `whisper-small.en/`, `whisper-tiny/` or `whisper-base/` (`local_whisper_engine.ensure_aux_model`) |
| `temp_outputs/`, `*.log` | runtime scratch / `diag_logging.setup_logging` | disposable |
| in-memory job progress | `app.py:get_transcribe_progress_endpoint` | keyed by `job_id` (`diag_logging.new_job_id`); lost on restart |

### Record schemas

**Template** (`templates.json` item; write payload `app.py:SaveTemplatePayload`):
`id, name, doc_type, category, description, is_default, is_builtin, docx_filename, context, rules, requirements, fields[], sections[], tables[], ai_system_prompt, json_schema, json_example`.
Built-in ids: `transcript_summary, blog_article, news_press_release, journal_academic, bangladesh_govt_nothi, easd_default_minutes, executive_project_status, field_survey_investigation`; custom ids `custom_tpl_<8 hex>`.
`json_schema`/`json_example` come from `template_engine.generate_template_json_schema` / `generate_template_json_example`.

**Skill** (`skills.json` item; payload `app.py:SaveSkillPayload`): `id, name, category, is_builtin, description, prompt`.

**API settings** (`app.py:ApiSettingsPayload`): `transcription_provider, transcription_model, summarization_provider, summarization_model, gemini_api_key, local_whisper_model, gemini_live_model, custom_api_base_url, custom_api_key, custom_api_model`.

**Minutes document** (`app.py:MeetingDocPayload`): `title, location, date, time, agendas[str], discussions[DiscussionItem{sn,topic,details}], decisions, attendance[AttendanceItem{serial,name,participation}], transcript, bangla_transcript, english_transcript`. Default member list: `document_engine.DEFAULT_MEMBERS`.

**Other payloads** (`app.py`): `CustomDocxPayload{template_id, doc_data}`, `GDriveUploadPayload{doc_data, access_token, folder_name}`, `VerifyKeyPayload`, `TestEnginePayload`, `DeleteTemplatePayload`, `DeleteSkillPayload`, `TranslatePayload`, `CloudImportPayload`.

**Browser localStorage** (`frontend/src/App.jsx`, `frontend/src/utils/apiKeyStorage.js`):
`theme, appSettings, customAppLogo, documentType, activeTemplateId, aiProvider, apiKey, baseUrl, transcriptionModel, summarizationModel, modelName, orgContext, activeSkills, customSkillsList, custom_api_model, apiKey_<providerId>, easd_api_keys_list`.

## 2. HTTP API → handler → engine functions (`app.py`)

| Route | Handler | Calls |
|---|---|---|
| GET/POST `/api/default_config` | `get_default_config`, `post_default_config` | `ai_providers.get_default_api_key_from_disk` |
| GET/POST `/api/settings` | `get_settings_endpoint`, `save_settings_endpoint` | `load_api_settings_from_disk` / `save_api_settings_to_disk` |
| POST `/api/test_engine` | `test_engine_endpoint` | `test_transcription_engine`, `test_summarization_engine` |
| GET/POST `/api/env_keys` | `get_env_keys_endpoint` | reads `.env` |
| GET/POST `/api/document_types` | `get_document_types_endpoint` | `template_engine.get_document_types` |
| GET/POST `/api/template_members` | `get_template_members` | `document_engine.DEFAULT_MEMBERS` |
| GET/POST `/api/templates` | `get_templates` | `load_saved_templates` |
| GET/POST `/api/template_schema` | `get_template_schema_endpoint` | `get_template_by_id`, `get_template_json_schema`, `get_template_json_example` |
| POST `/api/generalize_template` | `generalize_template_endpoint` | `analyze_and_generalize_docx` |
| POST `/api/save_template` / `/api/delete_template` | `save_template_endpoint` / `delete_template_endpoint` | `save_custom_template` / `delete_custom_template` |
| GET/POST `/api/skills`, POST `/api/save_skill`, `/api/delete_skill` | `get_skills`, `save_skill_endpoint`, `delete_skill_endpoint` | `skills_engine.*` |
| POST `/api/verify_key`, `/api/verify_api_key` | `verify_key_endpoint` | `ai_providers.verify_ai_api_key` |
| POST `/api/transcribe_and_summarize` | `transcribe_and_summarize` | `media_processor.process_uploaded_media` → `ai_providers.process_ai_request` |
| POST `/api/summarize_transcript` | `summarize_transcript_endpoint` | `get_template_by_id` → `process_ai_request` |
| POST `/api/ocr_extract_and_optimize` | `ocr_extract_and_optimize_endpoint` | `process_uploaded_media`, `ocr_engine.preprocess_image_for_ocr`, `optimize_ocr_text`, `process_ai_request` |
| GET `/api/system_audit` | `system_audit_endpoint` | `local_whisper_engine.get_engine_status`, `get_system_ram_specs`, `resolve_whisper_model_choice`, `local_llm_engine.get_local_llm_status` |
| WS `/ws/live_transcribe` | `websocket_live_transcribe` | `ai_providers.live_transcribe_audio_chunk` |
| POST `/api/live_transcribe_chunk` | `live_transcribe_chunk_endpoint` | `live_transcribe_audio_chunk` |
| POST `/api/detect_language` | `detect_language_endpoint` | `local_whisper_engine.convert_to_wav_pcm16k`, `detect_bilingual_audio_language` (alias of `detect_audio_language`, `local_whisper_engine.py:225`) |
| GET `/api/transcribe_progress/{job_id}` | `get_transcribe_progress_endpoint` | in-memory progress |
| POST `/api/transcribe_take` | `transcribe_take_endpoint` | `process_uploaded_media`, `detect_text_language` |
| POST `/api/translate_transcript` | `translate_transcript_endpoint` | `transcript_translator.translate_transcript` |
| POST `/api/generate_docx` | `generate_docx` | `document_engine.generate_meeting_minutes_docx_bytes` |
| POST `/api/generate_custom_docx` | `generate_custom_docx_endpoint` | `generate_custom_template_docx_bytes` (or minutes builder for the default id) |
| POST `/api/upload_gdrive` | `upload_gdrive` | `generate_meeting_minutes_docx_bytes` → `gdrive_service.upload_docx_to_gdrive` |
| POST `/api/import_cloud_file` | `import_cloud_file` | downloads Google Drive / OneDrive share links (outbound HTTP) |

App lifecycle: `_lifespan`, `app_startup_warmup` (→ `warm_up_local_whisper_in_background`), `add_security_headers`, `find_available_port`, `is_server_already_running`, `open_native_app_window`.

## 3. Module function map

- **`ai_providers.py`**: orchestration hub. Entry `process_ai_request`. STT: `transcribe_audio_gemini`, `transcribe_single_chunk`, `transcribe_chunks_parallel`, `transcribe_audio_chunks_detailed`, `transcribe_normalized_audio_chunks` (→ `stt_pipeline.transcribe_chunks`), `live_transcribe_audio_chunk`. Fill: `summarize_text_gemini`, `summarize_text_openai_compatible`, `transcribe_and_summarize_gemini`, `fill_template_locally` (→ `local_llm_engine.generate_template_fill`), `build_template_system_prompt`, `deep_semantic_synthesis`, `process_extracted_payload`, `extract_and_repair_json`. Attendance: `match_attendance_list`. Keys/settings: `get_default_api_key_from_disk`, `load_api_settings_from_disk`, `save_api_settings_to_disk`, `verify_ai_api_key`, `ping_openai_compatible`, `is_fatal_auth_error`. Tests: `test_transcription_engine`, `test_summarization_engine`, `generate_synthetic_test_wav`.
- **`stt_pipeline.py`**: `transcribe_chunks` (Gemini → fallback → Whisper), `gemini_transcribe_bytes`, `whisper_transcribe_bytes`, `whisper_status`, `_unify_speakers_across_chunks` (→ `speaker_diarization`), timestamp helpers `format_ts`, `shift_line_timestamp`, `clamp_line_timestamp`; retry `_is_retryable`, `_retry_delay_hint`.
- **`local_whisper_engine.py`**: `transcribe_local_audio`, `get_local_whisper_model`, `warm_up_local_whisper_in_background`, `detect_audio_language(_detail)`, `resolve_whisper_model_choice`, `select_optimal_model_name`, `get_engine_status`, `convert_to_wav_pcm16k`, `slice_wav_pcm16k`, `sanitize_whisper_text`, `_transcribe_local_audio_openvino`, `test_local_engine`. Bangla/English switching (v9.0): `code_switch_enabled`, `code_switch_detector`, `ensure_aux_model`, `ensure_code_switch_models`, `code_switch_status`, `_split_speech_stretches`, `_stretch_language`, `_plan_bilingual_runs`, `_load_aux_model`, `_code_switch_ready`.
- **`openvino_whisper_engine.py`**: `should_use`, `available_devices`, `transcribe_samples`, `status`.
- **`speaker_diarization.py`**: `diarize_wav_segments`, `unify_chunk_speakers`, `voice_embedding`, `cluster_embeddings`, `speaker_model_status`, `active_backend` (WeSpeaker ONNX, MFCC fallback; threshold `EASD_DIARIZATION_THRESHOLD`).
- **`transcript_translator.py`**: `translate_transcript` with callers `_gemini_caller`, `_openai_caller`, `_local_caller`; `_split_prefix` keeps `[MM:SS] Speaker N:`.
- **`local_llm_engine.py`**: `chat` (single entry point), `generate_template_fill`, `get_local_llm_status`, `ensure_model_downloaded`, `detect_vulkan_gpu`, `_start_server` (`bin/llama-server`), `_openvino_pipeline`; error `LocalLLMUnavailable`.
- **`template_engine.py`**: `load_saved_templates`, `save_templates_to_disk`, `get_template_by_id`, `get_document_types`, `analyze_and_generalize_docx`, `save_custom_template`, `delete_custom_template`, `generate_custom_template_docx_bytes`, `get_template_json_schema/example`.
- **`document_engine.py`**: `generate_meeting_minutes_docx_bytes`, `generate_meeting_minutes_docx`, run-preserving helpers `replace_paragraph_text_preserving_runs`, `set_cell_text_formatted`, `duplicate_tr_with_formatting`.
- **`media_processor.py`**: `process_uploaded_media`, `convert_media_to_speech_audio`, `split_audio_into_chunks`, `normalize_audio_chunk_for_stt`, `extract_text_from_docx_bytes`, `parse_subtitle_file`, `offset_transcript_timestamps`, `find_ffmpeg_binary`.
- **`ocr_engine.py`**: `perform_local_ocr` (Tesseract), `perform_ai_vision_ocr`, `extract_pdf_content`, `optimize_ocr_text`, `preprocess_image_for_ocr`.
- **`skills_engine.py`**: `load_saved_skills`, `save_skills_to_disk`, `save_custom_skill`, `delete_custom_skill`.
- **`gdrive_service.py`**: `get_or_create_easd_folder`, `upload_docx_to_gdrive`.
- **`diag_logging.py`**: `setup_logging`, `get_logger`, `new_job_id`, `bind_job_id`, `redact_key`, `describe_exception`.
- **Frontend `frontend/src/`**: `App.jsx` (state + API calls), `components/Transcripts.jsx`, `LiveRecordStudio.jsx` (WS live), `TemplateGenerator.jsx`, `SettingsModal.jsx`, `AiSkillsSelector.jsx`, `GDriveModal.jsx`, `CloudImportModal.jsx`, `Attendance.jsx`, `Discussions.jsx`, `MetaAgendas.jsx`; `utils/apiKeyStorage.js`, `utils/aiModelConstants.js`.

## 4. Invariants

- Transcript lines keep the `[MM:SS] Speaker N:` prefix (`transcript_translator._split_prefix`, `stt_pipeline.shift_line_timestamp`).
- Fallback order: STT Gemini → local Whisper; fill Gemini/custom → `fill_template_locally` → offline extraction.
- Keys pass through `diag_logging.redact_key` before logging; never print `api_settings.json`, `GeminiAPI.txt`, `.env`.

## 5. Side effects

- Writes `templates.json`, `skills.json`, `api_settings.json`, `GeminiAPI.txt`, `custom_docx/*.docx`.
- Outbound HTTP: Google GenAI, OpenAI-compatible endpoints, Google Drive upload, Drive/OneDrive downloads, model downloads (`ensure_model_downloaded`; `local_whisper_engine.ensure_aux_model`, one time, at app start when switching is on).
- Spawns `bin/llama-server` and ffmpeg subprocesses.

## 6. Not part of the app

`Transcription Module/`, `useless/`, `default_whisper_transcribe.py`, `diag_long_audio_repro.py`, and the workspace `../Scripts/` one-off meeting builders.

## Verification

```bash
EASD_WHISPER_BACKEND=ctranslate2 .venv/bin/python -m pytest tests -q -p no:cacheprovider
```
