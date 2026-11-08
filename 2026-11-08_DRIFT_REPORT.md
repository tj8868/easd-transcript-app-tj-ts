# EGM Drift Report — 2026-11-08

Scope: the 12 `EGM.md` contracts and `CODEMAP.md` from today's bootstrap, checked against the current
working tree (uncommitted v8.9 code). Only divergences are listed. Severity: **Wrong** means the
doc says something false; **Gap** means the doc leaves something out.

## EGM.md

- **Wrong:** the doc says "39 routes under `/api/*`". The code has 37 `@app.get/post` decorators covering 29 unique `/api` paths, plus one WebSocket (`app.py:886`). `/api/verify_key` and `/api/verify_api_key` share one handler (`app.py:533-535`).
- **Wrong:** the doc says "only `bn` or `en` is ever chosen". `detect_audio_language_detail` can also return `None` when detection fails, which falls back to Whisper auto-detect (`local_whisper_engine.py:116-135`). The `EASD_WHISPER_EN_CONFIDENCE` cut-off (default 0.5, `:96`) isn't mentioned.
- **Wrong:** `EASD_LOCAL_LLM_KV_CACHE` has two defaults: `""` in-process (`local_llm_engine.py:424`) and `turbo4` for `bin/llama-server` (`:620`).
- **Wrong:** `OMP_NUM_THREADS` is set with `setdefault`, so a value already set is never overridden (`local_whisper_engine.py:32`).
- **Gap:** env vars missing from the doc:
  - `EASD_GEMINI_MAX_ATTEMPTS`, `EASD_GEMINI_STAGGER_SEC`, `EASD_GEMINI_BACKOFF_BASE_SEC`, `EASD_GEMINI_BACKOFF_MAX_SEC`, `EASD_GEMINI_HTTP_TIMEOUT_MS`, `EASD_GEMINI_INLINE_MAX_BYTES`, `EASD_GEMINI_STT_FALLBACK_MODELS` (`stt_pipeline.py:47-56`)
  - `EASD_DIARIZATION`, `EASD_DIARIZATION_MAX_SPEAKERS`, `EASD_DIARIZATION_DEVICE`, `EASD_DIARIZATION_NO_DOWNLOAD` (`speaker_diarization.py`)
  - `EASD_LOCAL_LLM_MODEL`, `EASD_LOCAL_LLM_DIR`, `EASD_LOCAL_LLM_BACKEND`, `EASD_LOCAL_LLM_GPU_LAYERS`, `EASD_LLM_BACKEND`, `EASD_OV_LLM_MODEL` (`local_llm_engine.py`)
  - `EASD_OV_DEVICE`, `EASD_OV_WHISPER_MODEL` (`openvino_whisper_engine.py`)
  - `EASD_WHISPER_GPU_TURBO`, `EASD_DEBUG_SAVE_TRANSCRIPT` (`local_whisper_engine.py`)
  - `HOST`, `CODESPACES`, `CUSTOM_API_*` (`app.py`)
- **Gap:** a second parallelism cap, `ai_providers.MAX_CONCURRENT_CHUNKS = 5` (`ai_providers.py:1153`), isn't mentioned.
- **Gap:** `detect_text_language` (`ai_providers.py:127`, used by `/api/transcribe_take`) is missing from the interface list.

## CODEMAP.md

- **Wrong:** the `/api/transcribe_take` row leaves out `transcribe_audio_chunks_detailed`, which the handler imports and calls (`app.py:1085`).
- **Wrong:** the `/api/env_keys` row says "reads `.env`". It also reads `os.environ` (`GEMINI_API_KEY`, `GOOGLE_API_KEY`, `CUSTOM_API_*`, `app.py:345-364`).
- **Gap:** the `/api/detect_language` row leaves out the Whisper model load (`get_local_whisper_model`, `app.py:1040`).
- **Gap:** localStorage keys missing from the list:
  - `custom_api_model`, `gdriveToken` (plaintext Google token, `GDriveModal.jsx:5,14`), `activeCustomApiName`, `activeCustomApiId`, `baseUrl_<id>`
  - `transcriptionProvider`, `summarizationProvider`, `local_whisper_model`, `gemini_llm_model`, `local_llm_model` (`SettingsModal.jsx`)
- **Gap:** `SaveTemplatePayload` differs from the stored record. It has `save_as_new` and lacks `is_default`, `is_builtin`, `json_schema` and `json_example` (`app.py:250-264`).
- **Gap:** the custom skill id format `custom_<8hex>` isn't documented (`skills_engine.py:78`).
- **Gap:** field details are missing for `TranslatePayload`, `CloudImportPayload`, `VerifyKeyPayload`, `TestEnginePayload`, `DeleteTemplatePayload` and `DeleteSkillPayload`.
- **Gap:** functions missing from the map:
  - `ai_providers`: `detect_text_language`, `clean_agenda_item`, `clean_bullet_points`, `format_seconds_to_timestamp`, `OpenAICompatibleError`
  - `local_whisper_engine`: `get_system_ram_specs`, `is_low_ram_system`, `get_model_path`, `normalize_language_code`, `transcribe_default_whisper`
  - `local_llm_engine`: `is_local_llm_available`
  - `ocr_engine`: `find_tesseract_binary`, `is_tesseract_available`
  - `media_processor`: `find_ffprobe_binary`, `is_already_speech_normalized`
  - `diag_logging`: `current_job_id`, `fmt_ts`, `probe_duration_sec`
  - `speaker_diarization`: `read_wav_pcm16k`
  - `template_engine`: `generate_template_json_schema` / `_example` (missing from §3)
- **Gap:** constants missing from the doc: `MAX_UPLOAD_SIZE` (1 GB), the CORS regex, `media_processor` `MAX_CHUNK_BYTES` (20 MB) / `CHUNK_SPLIT_THRESHOLD_BYTES` (4 MB) / `SEGMENT_SECONDS` (600), and `transcript_translator` `BATCH_MAX_LINES` (40) / `BATCH_MAX_CHARS` (6000).

## frontend/EGM.md

No drift detected

## frontend/src/EGM.md

- **Gap:** the `custom_api_model` key, read at `App.jsx:585,656`, isn't listed.
- **Wrong (minor):** `customAppLogo` is only read in `App.jsx`. It is written and removed in `components/SettingsModal.jsx:238,256`.

## frontend/src/components/EGM.md

- **Wrong:** the doc says only `LiveRecordStudio` writes localStorage. `AiSkillsSelector.jsx` also writes `orgContext`, `customSkillsList` and `activeSkills` (lines 100-236).
- **Gap:** `GDriveModal.jsx` reads and writes `gdriveToken` in plaintext (lines 5, 14).
- **Gap:** keys `SettingsModal.jsx` writes that aren't listed: `custom_api_model`, `transcriptionProvider`, `transcriptionModel`, `local_whisper_model`, `summarizationProvider`, `summarizationModel`, `gemini_llm_model`, `local_llm_model`, `customAppLogo`.

## frontend/src/utils/EGM.md

- **Wrong (minor):** `activateProvider` still writes the raw unknown `providerId` to `aiProvider` and uses it for key/baseUrl lookups (`apiKeyStorage.js:152-156`). Only the defaults come from `PROVIDERS[0]`.
- **Wrong (minor):** `activeCustomApiId` is only removed, never read or written. `activeCustomApiName` is read and removed (lines 128-163).

## scripts/EGM.md

- **Wrong (minor):** the `HERE` value is quoted inexactly. The real line is `HERE="$(cd "$(dirname "$0")/.." && pwd)"` (`build_llama_server.sh:10`). The unknown-backend message is actually `unknown backend: $GPU` (`:19`).
- **Gap:** Side Effects leaves out the clone flag `-b feature/turboquant-kv-cache` (`.sh:22`, `.bat:15`) and the copy-source paths (`build/bin/llama-server`, `build\bin\Release\llama-server.exe`).

## docs/EGM.md

No drift detected

## docs/Google gemni 3.5 Transcribe -Guide/EGM.md

- **Wrong:** the SIGINT handler is installed inside `streaming_main`, not at import, and it is skipped on `NotImplementedError` (`gemini_3_5_transcribe_live.py:90-92`).
- **Gap:** `genai.Client(...)` is built at import (`:34`). The defaults `PROJECT_ID="[your-project-id]"` and `LOCATION="global"` (`:31-32`) aren't mentioned.
- **Wrong:** the setup steps differ from the script's docstring, which also needs `portaudio` on macOS and `gcloud auth application-default login` (`:4-9`).
- **Gap:** the doc doesn't say that `connect(..., config=config)` is called (`:103`) or that the final transcript is printed (`:137`).

## Transcription Module/EGM.md

- **Wrong:** only `run_app.py` defines `find_python_executable`, `is_port_open`, `open_browser_delayed` and `main`. `run_app.pyw` just calls `run_app.main()` (`run_app.pyw:13-16`).
- **Wrong:** not every launcher spawns a subprocess. `launch.sh` runs `python3 app.py` directly. Its venv path is also broken: it uses `.venv/activate` instead of `.venv/bin/activate` (`launch.sh:10,12`).
- **Gap:** `custom_api_config.json` has a `temperature` key that `CustomApiPayload` doesn't define (`app.py:57-64`).

## Transcription Module/subagents/EGM.md

- **Gap:** the Gemini network path, `google.genai` `models.get` / `generate_content`, isn't mentioned (`custom_api_gateway.py:125-230`).
- **Gap:** the GPU probes aren't spelled out. They are `nvidia-smi` and `torch.cuda` (`hardware_profiler.py:66-82`), and `/proc/meminfo` is read only when psutil fails (`:35-38`).
- **Gap:** the model download location (the module's `models/`, `whisper_worker.py:99`) isn't stated. The `DiarizationWorkerSubAgent(pause_threshold_sec=1.6, max_speakers=4)` defaults aren't documented either.

## Transcription Module/static/EGM.md

- **Gap (minor):** the doc doesn't say that the frontend uses chunked HTTP only. `WS /ws/live` exists in `app.py:116`, but `app.js` never uses it.

## useless/EGM.md

- **Wrong:** not every launcher uses uvicorn. `launch_mac.command:7` runs `python3 app.py`, and the generated `Launch_App.bat` runs `app.py` as well (`build_windows_exe.py:27`).
- **Wrong:** `build_windows_exe.py` doesn't use `EASD_Meeting_Minutes.spec`. It passes CLI arguments to PyInstaller (`:37-45`) and bundles the template `.docx` (`:44`).
- **Gap:** `run_pyannote_diarization` sets `os.environ["HF_TOKEN"]` (`whisperx_diarization_engine.py:112`).
- **Gap:** the exception types (`ValueError`, `FileNotFoundError`, `ImportError`) aren't stated. The full `run_whisperx_pipeline` signature and its fallback to `pyannote/speaker-diarization-3.1` (`:210-309`) are missing too.
- **Gap:** the CLI defaults aren't documented: `--hf_token` comes from env `HF_TOKEN`, `--mode` is `whisperx`, `--model` is `small`, and `--pipeline` is `pyannote/speaker-diarization-community-1` (`:648-657`).
- **Gap (minor):** `daily_audit.py:13` also produces structured JSON.

## Code issues found along the way (not drift; for human triage)

- `Transcription Module`: `GET /api/custom_api` returns the raw `api_key` (`subagents/custom_api_gateway.py:get_safe_config`).
- Frontend: API keys and the Google Drive `gdriveToken` are stored in plaintext in `localStorage`.
- `Transcription Module/launch.sh`: the venv activate path is broken.
- `frontend/vite.config.js`: the dev server binds `0.0.0.0` with `allowedHosts: true`.

## Suggested doc links

Contracts that cite symbols without line numbers make the next drift check slower. Two things would help:
- Add `file:line` anchors to the CODEMAP route table.
- Add an env-var table to the root `EGM.md`.
