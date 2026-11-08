# Transcription Module

## Overview
Standalone FastAPI "Universal Transcription Module" with live recording, batch upload, a local faster-whisper engine, and an optional remote ASR endpoint. Per the project's `CLAUDE.md`, this module is legacy/standalone and is not used by the main app. Do not wire main-app changes through it. The human `README.md` here is left as-is.

## Interface
- `app.py:app` (FastAPI) routes: `GET /api/status`, `POST /api/settings` (`SettingsPayload`), `GET|POST /api/custom_api` (`CustomApiPayload`), `POST /api/custom_api/test`, `POST /api/live/start`, `POST /api/live/chunk`, `POST /api/live/stop`, `WS /ws/live`, `POST /api/batch/upload`, `GET /api/batch/status/{job_id}`, and static mount at `/`.
- `orchestrator.py:TranscriptionOrchestrator` - singleton through `get_instance()`. Methods: `get_system_status`, `start_live_session`, `process_live_chunk`, `stop_live_session`, `process_batch_upload`, `get_batch_job_status`, `get_custom_api_config`, `update_custom_api_config`, `test_custom_api`.
- `config.py` - `load_settings()`, `save_settings()`, `DEFAULT_SETTINGS`, `CONFIG_FILE`.
- `transcribe_engine.py` - `detect_best_backend()`, `UniversalTranscriber` (`transcribe_file`, `batch_process`). Standalone CLI-style engine.
- Launchers: `run_app.py` / `run_app.pyw` (`find_python_executable`, `is_port_open`, `open_browser_delayed`, `main`), `start_ios_server.py` (`get_local_ip`, `print_qr`, `main`), and the `Launch_App.*`, `launch.*`, and `.desktop` shell wrappers.
- Subdirectories: [subagents](./subagents/EGM.md) (worker classes), [static](./static/EGM.md) (frontend).

## Invariants
- The orchestrator builds sub-agents in a fixed order: hardware, then diarization, custom API, whisper, live, and batch. Live and batch share the same whisper, gateway, and diarizer instances.
- Server host/port come from `server_host` / `server_port` in settings (default `127.0.0.1:8085`).
- Batch job ids are `job_<8 hex>`. Uploads run in a background thread (`asyncio.to_thread`), and the temp file is deleted in `finally`.
- `GET /api/custom_api` returns `get_safe_config()`, which still includes the raw `api_key` field next to `masked_key`.

## Side Effects
- Reads and writes `transcription_settings.json` (`config.py`) and `custom_api_config.json` (credentials; never commit or print).
- Writes uploads to `temp_uploads/`. Creates `static/` if it is missing.
- `transcribe_engine.py:batch_process` writes `.txt` outputs next to the inputs. It also runs `vulkaninfo`.
- Launchers spawn the server subprocess and open a web browser.
- See [subagents](./subagents/EGM.md) for network, ffmpeg, and model-loading effects.

## Verification
- No tests target this module (the repo `tests/` covers the main app). Manual: `python app.py`, then open `http://127.0.0.1:8085/`.
