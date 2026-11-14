# EGM Drift Report — 2026-11-14

Scope: the 12 `EGM.md` contracts and `CODEMAP.md` (the same set as `2026-11-08_DRIFT_REPORT.md`). They were checked
against the current working tree on branch `v8.9`. That tree includes the uncommitted v9.0 work:
`silence_trimmer.py`, `docker/llama/`, the Docker mode in `local_llm_engine.py`, and the 2 GB upload limit.
Only divergences are listed. **Wrong** means the doc states something false. **Gap** means the doc leaves
something out. **New** marks drift that came in after the 11-08 report. Items without the mark were reported
on 11-08 and are still open.

## EGM.md

- **New, Gap:** `silence_trimmer.py` is missing from the Interface list and from the Pipeline line. `media_processor._process_uploaded_media_impl` now runs `silence_trimmer.trim_silence` before chunking (`media_processor.py:550-562`). It returns `time_map` / `silence_removed_sec` and reports `total_duration_sec` as the original length (`:586-589`). Public API: `trim_silence`, `remap_seconds`, `remap_line_timestamp`, `STT_PROMPT_NOTE`, `LLM_TRANSCRIPT_NOTE` (`silence_trimmer.py:53-195`).
- **New, Gap:** a timestamp invariant is missing. When silence was trimmed, `stt_pipeline.transcribe_chunks(time_map=...)` maps every line timestamp and chunk range back to the original recording. It also adds `trimmed_start_sec` / `trimmed_end_sec` (`stt_pipeline.py:645-657`). The chain `app.py:700,1291` → `ai_providers.transcribe_audio_chunks_detailed(time_map=)` (`ai_providers.py:1213,1233,1711`) isn't mentioned either.
- **New, Gap:** prompt changes aren't documented. Gemini prompt mode appends `STT_PROMPT_NOTE` when audio was trimmed (`stt_pipeline.py:277-282`). `build_template_system_prompt` appends `LLM_TRANSCRIPT_NOTE` whenever `TRIM_ENABLED` is set (`ai_providers.py:478-484`).
- **New, Gap:** env vars missing from the table:
  - `EASD_TRIM_SILENCE` (1), `EASD_TRIM_MIN_SILENCE_SEC` (2.0), `EASD_TRIM_PAD_SEC` (0.4), `EASD_TRIM_MIN_SAVING` (0.03), `EASD_TRIM_VAD_THRESHOLD` (0.5), from `silence_trimmer.py:42-46`
  - `EASD_LLAMA_DOCKER` (`easd-llama`), `EASD_LLAMA_SERVER_URL` (`http://127.0.0.1:8081`), `EASD_LLAMA_DOCKER_START_TIMEOUT` (1800), from `local_llm_engine.py:608-609,653`
  - `EASD_LOCAL_LLM_KV_CACHE_K` / `_V`, `EASD_LOCAL_LLM_CAPABLE_MIN_FREE_MB` (3000), `EASD_LOCAL_LLM_PRELOAD` (1), `EASD_LOCAL_LLM_PRELOAD_MIN_FREE_MB` (3000), `EASD_LOCAL_LLM_KEEP_MIN_FREE_MB` (2500), `EASD_LOCAL_LLM_CTX` (10000), `EASD_LOCAL_LLM_THREADS`, from `local_llm_engine.py:737-746,861,930-931,972-977`
  - `EASD_ALLOWED_HOSTS`, from `app.py:189`
- **New, Gap:** Docker llama-server mode is missing. If a container named `EASD_LLAMA_DOCKER` exists and `docker` is on PATH, `docker_mode()` is true (`local_llm_engine.py:619-631`). In that mode `chat` / `_server_chat_once` use the container instead of `bin/llama-server` (`:1037,1062`), and `is_local_llm_available` always returns True (`:83-84`). `start_server_in_background`, `stop_server` and `release_for_transcription` gain Docker branches (`:866-872,902-910,937-944`). Those public functions are missing from the Interface list too.
- **New, Gap:** `docker/` is missing from "Subdirectories & System Boundaries", and it has no `EGM.md` of its own. Global Side Effects also leaves out the `docker inspect|start|stop|logs` subprocesses and the HTTP calls to `127.0.0.1:8081`.
- **New, Wrong:** the doc says `EASD_LOCAL_LLM_KV_CACHE` defaults to "`turbo4` for `bin/llama-server` at `:620`". `_kv_cache_types` now picks the cache automatically (`local_llm_engine.py:739-757`):
  - `turbo6`/`turbo6` when llama-server sees a GPU and at least `EASD_LOCAL_LLM_CAPABLE_MIN_FREE_MB` of RAM is free
  - otherwise `turbo3` (K) / `turbo4` (V)

  The in-process `""` default is now at `:426`, not `:424`.
- **New, Gap:** Invariants mention only CORS. The DNS-rebinding / WebSocket-origin guard `_HostOriginGuard` (`app.py:178-240`) isn't mentioned. It checks the Host header against localhost, raw IPs, `EASD_ALLOWED_HOSTS` / `EASD_ALLOWED_ORIGINS` hosts, or Codespaces domains, and the WS Origin against loopback or the same host. Requests that fail get a 403 or close code 1008.
- **New, Wrong:** stale line anchors:
  - `ai_providers.py:1153` is now `:1160`
  - `local_whisper_engine.py:32` (`OMP_NUM_THREADS`) is now `:57-58`
  - `local_whisper_engine.py:116-135` (`detect_audio_language_detail`) is now `:140+`
- **New, Wrong:** "Excluded: … `evals/`" names a directory that doesn't exist.
- **Gap:** root folders and files that neither the Subdirectories list nor the Excluded list mentions:
  - `.agents/workflows/appbuilder.md`
  - `Requrements and updates/` (UI screenshots)
  - `Whisper -local -plan/implementation_plan.md`
  - `.fallowrc.json` (dead-code tool config, entry `frontend/src/main.jsx`)
  - `__pycache__/`, `.venv/`
- **Wrong:** "Data stores" lists `bin/`, but this checkout has no `bin/` folder.

## CODEMAP.md

- **New, Gap:** `silence_trimmer.py` is missing from §3 (module map), §5 (side effects: ffmpeg decode, a temp raw PCM memmap, `speech_trimmed.mp3`) and §6.
- **New, Gap:** §3 `local_llm_engine` leaves out `docker_mode`, `start_server_in_background`, `stop_server`, `release_for_transcription`, `is_local_llm_available`, `get_installed_gpus`, `is_gpu_vulkan_capable` and `query_vulkan_runtime_devices`. §5 leaves out the Docker container control and `127.0.0.1:8081`. The `docker/llama/` image isn't in the map at all.
- **New, Gap:** the `media_processor.process_uploaded_media` return keys `time_map` and `silence_removed_sec`, and the `time_map` parameter of `stt_pipeline.transcribe_chunks` / `ai_providers.transcribe_audio_chunks_detailed`, aren't documented.
- **New, Wrong:** the `models/` row lists `gemma-4-E2B-it-Q4_0.gguf`, but the file isn't on disk. Only `wespeaker_resnet34_LM.onnx` and `whisper-bengaliai/` are there. In Docker mode the container downloads the GGUF into `models/` and writes `models/.easd-llama-tune/` (`docker/llama/entrypoint.sh:18-29,47-50`). That write isn't documented.
- **New, Gap:** `MAX_UPLOAD_SIZE` (now 2 GB, `app.py:82`) and the `LiveRecordStudio.jsx:MAX_UPLOAD_BYTES` mirror, which `App.jsx:17,503` now imports, aren't mentioned.
- **Wrong:** the `/api/transcribe_take` row leaves out `transcribe_audio_chunks_detailed`, which the handler calls (`app.py:1285-1292`).
- **Wrong:** the `/api/env_keys` row says "reads `.env`". `.env` is loaded into `os.environ` at import (`app.py:24-25`). The handler reads `os.environ` and falls back to `GeminiAPI.txt` (`app.py:425-443`).
- **Gap:** the `/api/detect_language` row leaves out `get_local_whisper_model`.
- **Gap:** localStorage keys missing from the list:
  - `gdriveToken` (plaintext, `GDriveModal.jsx`), `activeCustomApiName`, `activeCustomApiId`, `baseUrl_<id>`
  - `transcriptionProvider`, `summarizationProvider`, `local_whisper_model`, `gemini_llm_model`, `local_llm_model` (`SettingsModal.jsx`)
- **Gap:** `SaveTemplatePayload` differs from the stored record. It has `save_as_new` and lacks `is_default`, `is_builtin`, `json_schema` and `json_example` (`app.py:329-344`).
- **Gap:** the custom skill id format `custom_<8hex>` isn't documented.
- **Gap:** field details are missing for `TranslatePayload` (`transcript, target, provider, api_key, model_name, base_url`), `CloudImportPayload` (`url, provider`), `VerifyKeyPayload`, `TestEnginePayload`, `DeleteTemplatePayload` and `DeleteSkillPayload`.
- **Gap:** functions missing from §3:
  - `ai_providers`: `clean_agenda_item`, `clean_bullet_points`, `format_seconds_to_timestamp`, `OpenAICompatibleError`
  - `local_whisper_engine`: `get_optimal_cpu_threads`, `format_seconds_to_min_sec`, `is_low_ram_system`, `get_loaded_model_name`, `normalize_language_code`, `transcribe_default_whisper`
  - `speaker_diarization`: `read_wav_pcm16k`
  - `media_processor`: `find_ffprobe_binary`, `is_already_speech_normalized`
  - `ocr_engine`: `find_tesseract_binary`, `is_tesseract_available`
  - `diag_logging`: `current_job_id`, `fmt_ts`, `probe_duration_sec`
  - `document_engine`: `clean_agenda_item`, `clean_bullet_points`
- **Gap:** constants aren't documented: the CORS regex and Host guard, `media_processor` `MAX_CHUNK_BYTES` / `CHUNK_SPLIT_THRESHOLD_BYTES` / `SEGMENT_SECONDS`, and `transcript_translator` `BATCH_MAX_LINES` / `BATCH_MAX_CHARS`.

## frontend/EGM.md

- **Gap (minor):** `test_live_verify_endpoints.js` and `test_unified_transcript_realtime.js` sit next to the three `npm test` scripts but aren't mentioned. They are also not run by `npm test`.

## frontend/src/EGM.md

- **Gap:** the `custom_api_model` key, read by `App.jsx`, isn't in the localStorage list.
- **Wrong (minor):** `customAppLogo` is listed as persisted "in `App.jsx`", but `App.jsx` only reads it (`:77,91`). `components/SettingsModal.jsx` writes and removes it.
- **New, Gap:** `App.jsx` imports the named export `MAX_UPLOAD_BYTES` from `./components/LiveRecordStudio` (`:17`) to check upload size (`:503`). The doc doesn't mention this coupling.
- **New, Gap:** `utils/download.js` (`downloadBlob`, imported at `App.jsx:40`) isn't listed under utils.

## frontend/src/components/EGM.md

- **New, Wrong:** the doc lists one named export, `SettingsModal.jsx:ACCENT_PALETTES`. `LiveRecordStudio.jsx:MAX_UPLOAD_BYTES` is now exported too (`:391`) and imported by `../App.jsx`. The doc still lists it only as a module constant.
- **Wrong:** the doc says only `LiveRecordStudio` writes localStorage. `AiSkillsSelector.jsx` also writes `orgContext`, `customSkillsList` and `activeSkills`.
- **Gap:** `GDriveModal.jsx` reads and writes `gdriveToken` in plaintext.
- **Gap:** `SettingsModal.jsx` writes keys the doc doesn't list: `custom_api_model`, `transcriptionProvider`, `transcriptionModel`, `local_whisper_model`, `summarizationProvider`, `summarizationModel`, `gemini_llm_model`, `local_llm_model` and `customAppLogo`.
- **Wrong (minor):** `SettingsModal` doesn't call `/api/test_engine` directly. It goes through `utils/apiKeyStorage.testAiEngine` (`SettingsModal.jsx:507-516`).
- **New, Gap:** `DocumentPreview.jsx` and `Transcripts.jsx` import `downloadTextFile` from `../utils/download`. This client-side file download side effect isn't listed.

## frontend/src/utils/EGM.md

- **New, Gap:** `download.js` isn't documented. It exports `downloadBlob(blob, filename)` and `downloadTextFile(filename, content)`, and revokes the object URL after 30 s.
- **Wrong (minor):** `activateProvider` writes the raw unknown `providerId` to `aiProvider` and uses it for key/baseUrl lookups (`apiKeyStorage.js:150-163`). Only the model defaults come from `PROVIDERS[0]`.
- **Wrong (minor):** `activeCustomApiId` is only ever removed. `activeCustomApiName` is read (`:128,138`) and removed. The doc lists both as read/written.

## scripts/EGM.md

- **New, Wrong:** both scripts now default to `auto`, not `vulkan`. The `.sh` accepts `auto|vulkan|cuda|metal|cpu` and the `.bat` accepts `auto|vulkan|cuda|cpu` (`build_llama_server.sh:6,21`, `.bat:9,14`).
- **New, Gap:** the `auto` mode isn't documented:
  - On Linux and Windows it does a plug-in-backend build: `-DBUILD_SHARED_LIBS=ON -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON -DGGML_NATIVE=OFF`. Vulkan is added when `glslc` and the headers exist (`.bat`: `VULKAN_SDK`), and CUDA when `nvcc` exists (`.bat`: `CUDA_PATH`).
  - On macOS it builds Metal (`.sh:32-44`, `.bat:27-33`).
  - It deletes old `libggml*/libllama*/libmtmd*` libraries (`.bat`: `ggml*/llama*/mtmd*.dll`) from `bin/` and copies the new shared libraries there (`.sh:60-65`, `.bat:42-45`).
- **New, Wrong:** the "Static build" invariant is no longer universal. `-DBUILD_SHARED_LIBS=OFF` applies only to the forced backends. `-DLLAMA_BUILD_EXAMPLES=OFF` is added to the common flags. In the `.sh`, `-DCMAKE_BUILD_TYPE=Release` is common to all modes and `-DGGML_NATIVE=ON` applies only to forced backends (`.sh:29,45-48`).
- **New, Wrong:** the doc says the `.bat` doesn't check the backend. It now exits 1 with `unknown backend: %GPU% - use auto|vulkan|cuda|cpu` (`.bat:24`).
- **New, Gap:** builds use two jobs. The `.sh` uses `-j"${JOBS:-2}"`, so `JOBS` overrides it (`:57`). The `.bat` uses `-j 2` (`:40`).
- **New, Wrong:** the Overview says the app runs the model "with the turbo4 KV cache". The scripts' own headers say `-ctk turbo3 -ctv turbo4`, and the app now chooses turbo6/turbo6 or turbo3/turbo4 at run time (`local_llm_engine.py:739-757`).
- **Wrong (minor):** `HERE` is quoted inexactly. The real line is `HERE="$(cd "$(dirname "$0")/.." && pwd)"` (`.sh:22`). The unknown-backend message is now `unknown backend: $GPU (use auto|vulkan|cuda|metal|cpu)` (`.sh:49`).
- **Gap:** Side Effects leaves out the clone branch `-b feature/turboquant-kv-cache` and the copy-source paths `build/bin/llama-server` and `build\bin\Release\llama-server.exe`.
- **New, Gap:** the doc doesn't mention the Docker alternative (`docker/llama/Dockerfile`), which builds the same fork plus `llama-bench`.

## docs/EGM.md

No drift detected

## docs/Google gemni 3.5 Transcribe -Guide/EGM.md

- **Wrong:** the doc says a SIGINT handler is installed at import. It is installed inside `streaming_main` with `loop.add_signal_handler`, and it is skipped on `NotImplementedError` (`gemini_3_5_transcribe_live.py:89-92`).
- **Gap:** `genai.Client(...)` is built at import (`:34`). The defaults `PROJECT_ID="[your-project-id]"` and `LOCATION="global"` (`:31-32`) aren't mentioned.
- **Wrong:** the doc writes `connect(model=MODEL_ID_LIVE)`. The script passes `config=config` (`:103`) and prints the final transcript (`:137`).
- **Wrong:** the doc's setup steps differ from the script's docstring. The doc's `pip install` adds `certifi`, and it leaves out the macOS `brew install portaudio` and `gcloud auth application-default login` steps (`:3-9`).

## Transcription Module/EGM.md

- **Wrong:** only `run_app.py` defines `find_python_executable`, `is_port_open`, `open_browser_delayed` and `main`. `run_app.pyw` just imports `run_app` and calls `main()` (`run_app.pyw:13-16`).
- **Wrong:** the doc says "Launchers spawn the server subprocess". `launch.sh` runs `python3 app.py` directly. Its venv activation also points at `.venv/activate` instead of `.venv/bin/activate` (`launch.sh:10,12`).
- **Gap:** `custom_api_config.json` / `DEFAULT_CONFIG` has a `temperature` key that `CustomApiPayload` doesn't define (`app.py:57-64`, `subagents/custom_api_gateway.py:27`).
- **Gap (minor):** `ios/` (`pwa_offline_transcriber.html`, `SIDELOADING_GUIDE.md`) isn't mentioned. Neither are `IPHONE_PERFORMANCE_BENCHMARKS.md` or `UNIVERSAL_ASR_GUIDE.md`.

## Transcription Module/subagents/EGM.md

- **Gap:** the Gemini network path isn't mentioned: `google.genai` `client.models.get` in `test_connection` and `generate_content` in `transcribe_audio_bytes` (`custom_api_gateway.py:127-130,208-221`).
- **Gap:** the GPU probes aren't spelled out. They are `torch.cuda` and `nvidia-smi` (`hardware_profiler.py:71-79`). `/proc/meminfo` is read only as a fallback when psutil fails (`:35-38`).
- **Gap:** the doc doesn't say where models download to: the module's own `models/` (`whisper_worker.py:99`). The `DiarizationWorkerSubAgent(pause_threshold_sec=1.6, max_speakers=4)` defaults (`diarization_worker.py:45`) aren't documented either.

## Transcription Module/static/EGM.md

- **Gap (minor):** the doc doesn't say that live mode uses chunked HTTP only. `WS /ws/live` exists (`../app.py:116`) and `app.js:5` advertises "WebSocket/Chunk Streaming", but `app.js` never opens a WebSocket.
- **Gap (minor):** the doc doesn't mention that `app.js` renders results with `innerHTML`. Some fields go through `escapeHtml`, but `seg.timestamp` / `seg.speaker` don't (`app.js:300-303`).

## useless/EGM.md

- **New, Wrong:** the doc describes `build/` and `cert.pem` / `key.pem`, but none of them exist in the folder. Only `dist/EASD_Meeting_Minutes` is there. `.dockerignore` isn't mentioned.
- **Wrong:** "The launchers all serve `app:app` with uvicorn". `launch_mac.command:7` runs `python3 app.py`, and the generated `Launch_App.bat` runs `app.py` too (`build_windows_exe.py:27`).
- **Wrong:** `build_windows_exe.py` doesn't use `EASD_Meeting_Minutes.spec`. It passes CLI arguments to PyInstaller (`:37-45`) and bundles `EASD Meeting minutes - Template-DDMonthYY.docx` (`:44`).
- **Gap:** `run_pyannote_diarization` sets `os.environ["HF_TOKEN"]` (`whisperx_diarization_engine.py:112`).
- **Gap:** exception types, the full `run_whisperx_pipeline` signature and its fallback pipeline aren't stated.
- **Gap:** CLI defaults aren't documented: `--hf_token` comes from env `HF_TOKEN`, `--mode` is `whisperx`, `--model` is `small`, and `--pipeline` is `pyannote/speaker-diarization-community-1` (`:647-657`).

## Code issues found along the way (not drift; for human triage)

- `silence_trimmer.py`'s docstring names `remap_transcript_timestamps()`, which doesn't exist. The function is `remap_line_timestamp`.
- `LLM_TRANSCRIPT_NOTE` says it is for "template-fill / translation prompts", but `transcript_translator` never adds it. `build_template_system_prompt` adds it whenever `TRIM_ENABLED` is set, even for typed or uploaded-text transcripts that never went through trimming (`ai_providers.py:478-484`).
- In Docker mode the container ignores the app's `EASD_LOCAL_LLM_CTX` / `_KV_CACHE*` / `_THREADS` and uses its own `EASD_LLM_*` variables (`entrypoint.sh:12-14`). Its context defaults to 10240, not the app's 10000.
- `useless/build_windows_exe.py:44` bundles `…Template-DDMonthYY.docx`, a file that doesn't exist. The real template is `EASD Meeting minutes - Template.docx`.
- Still open from 11-08: `Transcription Module` `GET /api/custom_api` returns the raw `api_key`. The frontend stores API keys and `gdriveToken` in plaintext localStorage. `Transcription Module/launch.sh` has a broken venv path. `frontend/vite.config.js` binds `0.0.0.0` with `allowedHosts: true`.
- Environment: `bin/llama-server` and `models/gemma-4-E2B-it-Q4_0.gguf` are both missing on this PC. `CLAUDE.md` says a CPU build is in `bin/`. With neither present, local template fill can only run in Docker mode or through offline extraction.

## Suggested doc links

- Add a `docker/llama/EGM.md` (or a `docker/` section in the root `EGM.md`) that covers the container name/port contract (`easd-llama`, `127.0.0.1:8081`), the `EASD_LLM_*` variables, and the `models/.easd-llama-tune/` cache.
- Add `silence_trimmer.py` to the root `EGM.md` interface list and to the `CODEMAP.md` module map, with its env vars.
- Add `file:line` anchors to the CODEMAP route table, and anchor the root env-var table to `symbol` names instead of line numbers. Four line anchors went stale within a week.
