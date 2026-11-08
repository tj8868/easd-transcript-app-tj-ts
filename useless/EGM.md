# useless

## Overview

**Legacy folder.** Per the project's `CLAUDE.md`, `useless/` is legacy or standalone and the app does not use it. Nothing in the live application imports these files. Treat them as reference material only.

The folder contains early packaging and launch scripts for several platforms (Windows, Linux, macOS, Android/PWA, Docker, Codespaces), a self-audit script, and a standalone WhisperX/Pyannote speaker-diarization engine. Most scripts resolve paths against their own directory (`BASE_DIR = os.path.dirname(os.path.abspath(__file__))`). They expect `app.py`, `frontend/`, and `static/` next to them, and none of those exist inside `useless/`. These scripts therefore do not work from where they sit now.

`build/` and `dist/` hold build output (PyInstaller) and are not documented. `cert.pem` / `key.pem` are TLS key material. This file does not describe their contents.

## Interface

- `whisperx_diarization_engine.py`: a standalone diarization module and CLI.
  - `get_optimal_device() -> str`: returns `"cuda"` if `torch.cuda.is_available()`, otherwise `"cpu"`.
  - `check_diarization_prerequisites() -> Dict[str, bool]`: checks whether `torch`, `torchaudio`, `pyannote_audio`, `whisperx` and `cuda_available` can be imported or used.
  - `run_pyannote_diarization(audio_path, hf_token, pipeline_model="pyannote/speaker-diarization-community-1", device, min_speakers, max_speakers)`
  - `run_whisperx_pipeline(...)`: runs the full WhisperX pipeline (transcription, alignment, diarization).
  - `merge_whisper_segments_with_pyannote(whisper_segments, diarization_turns)`: gives each ASR segment the speaker whose turn overlaps it the most.
  - `get_huggingface_token(explicit_token=None) -> str`
  - `test_whisperx_engine(hf_token=None, diarize_model_name=...)`: returns a dict with `status` / `valid` / `message` / `prerequisites` / `user`.
  - `transcribe_with_diarization(audio_path=None, audio_bytes=None, hf_token, whisper_model_name="small", language, diarize_model_name, min_speakers, max_speakers)`
  - `main()`: CLI flags `--audio` (required), `--hf_token`, `--mode {whisperx,pyannote}`, `--model`, `--pipeline`, `--device`, `--min_speakers`, `--max_speakers`, `--output`.
- `daily_audit.py`: `check_task_backlog`, `check_security`, `check_setup_and_toolchains`, `check_app_building`, `generate_recommendations`, `perform_daily_audit`. It writes `DAILY_AUDIT_REPORT.md` (the copy in this folder is a past output).
- `package_all_platforms.py`: `main()` runs `ensure_frontend_built`, `generate_windows_package`, `generate_linux_package`, `generate_macos_package` and `generate_mobile_pwa_package`, in that order.
- `build_windows_exe.py`: `build_windows_executable()` runs PyInstaller with `--name EASD_Meeting_Minutes`. It also uses `EASD_Meeting_Minutes.spec`.
- `build_android_apk.py`: `build_android_apk_bundle()` generates `android_package_config.json` and `Build_Android_APK.bat`.
- Launchers (generated or static): `launch_linux.sh`, `launch_mac.command`, `launch_codespaces.sh`, `easd-ai.service` (systemd), `Dockerfile` / `docker-compose.yml` (port 8000, health check on `/api/document_types`), `.devcontainer/devcontainer.json`, `.codesandbox/tasks.json`.
- Docs: `BUILD_GUIDE.md`, `INSTALL.md`. `Test Input .txt` is sample text.

## Invariants

- `get_huggingface_token` looks for a token in this order: the explicit argument, then the environment variables `HF_TOKEN`, `HUGGINGFACE_TOKEN` and `HUGGING_FACE_HUB_TOKEN`, then the files `HuggingFaceAPI.txt` / `HF_TOKEN.txt` / `hf_token.txt` next to the module, then `api_settings.json["hf_token"]`. If none has a token, it returns `""`.
- `run_whisperx_pipeline` raises an error if it has no Hugging Face token.
- `transcribe_with_diarization` accepts either `audio_path` or `audio_bytes`. If it gets bytes, it writes them to a temporary `.wav` file and deletes that file afterwards.
- `build_windows_exe.py` hardcodes `PYTHON_EXE` to a user-specific Windows path (`C:\Users\Emenance-T1\...\python.exe`).
- The launchers all serve `app:app` with uvicorn on `0.0.0.0:8000`. `launch_codespaces.sh` also starts Vite on port 5173.

## Side Effects

- `whisperx_diarization_engine.py`: downloads or loads models through torch/whisperx/pyannote. `test_whisperx_engine` sends an HTTPS GET to `https://huggingface.co/api/whoami-v2` using a bearer token. It creates and deletes temporary WAV files, reads token files from disk, and writes to `--output` when that flag is given.
- `package_all_platforms.py`: runs `npm run build` in `frontend/` (`shell=True`). It deletes and recreates `static/` and overwrites `Launch_App.bat`, `launch_linux.sh`, `easd-ai.service`, `launch_mac.command` and `static/manifest.json`.
- `build_windows_exe.py`: deletes and recreates `static/` from `frontend/dist`, writes `Launch_App.bat`, and runs PyInstaller through `subprocess.run`.
- `build_android_apk.py`: overwrites `android_package_config.json` and `Build_Android_APK.bat`.
- `daily_audit.py`: reads project source files to scan them, runs toolchain checks with `subprocess`, and overwrites `DAILY_AUDIT_REPORT.md`.
- `launch_codespaces.sh`: may run `pip install -r requirements.txt` and `npm install`, and starts background server processes.

## Verification

- No test suite or build manifest exists for this folder. The diarization engine can be smoke-tested by hand with `python3 whisperx_diarization_engine.py --audio <file>`. This needs whisperx/pyannote and a Hugging Face token.
