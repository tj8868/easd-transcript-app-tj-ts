# subagents

## Overview
Worker components ("sub-agents") composed by `../orchestrator.py:TranscriptionOrchestrator`. Covers hardware profiling, local faster-whisper inference, an optional remote ASR gateway, live chunk transcription, batch file transcription, and speaker/timestamp formatting. Legacy/standalone module; not used by the main app (see repo `CLAUDE.md`).

## Interface
- `__init__.py:__all__` exports the six classes below.
- `hardware_profiler.py:HardwareProfilerSubAgent` - `evaluate_hardware()`, `get_profile()`, `refresh()`.
- `whisper_worker.py:WhisperWorkerSubAgent(hardware_profile)` - `load_model(model_choice=None, force_reload=False)`, `transcribe(...)`, `BILINGUAL_PROMPT`.
- `custom_api_gateway.py:CustomApiGatewaySubAgent(config_path=None)` - `save_config`, `get_safe_config`, `is_enabled`, `test_connection`, `transcribe_audio_bytes`, `DEFAULT_CONFIG` (`provider_type`: `openai_compatible` | `gemini` | `custom_http`).
- `live_stream_worker.py:LiveStreamWorkerSubAgent(whisper_worker, custom_api_gateway, diarizer)` - `start_session`, `convert_to_wav`, `process_live_chunk`, `stop_session`; helper `find_ffmpeg_bin()`.
- `batch_processor.py:BatchProcessorSubAgent(whisper_worker, custom_api_gateway, diarizer)` - `process_file`, `get_job_status`; helpers `get_ffmpeg()`, `probe_duration()`.
- `diarization_worker.py:DiarizationWorkerSubAgent` - `process_segments`, `align_live_chunk`, `export_srt`, `export_vtt`; helpers `format_seconds`, `format_seconds_srt`, `format_seconds_vtt`.

## Invariants
- `WhisperWorkerSubAgent.lock` (`threading.Lock`) serializes model load/inference.
- `_resolve_model_path` prefers local `models/` (module dir, then parent repo `models/`) containing `model.bin` or `model.safetensors`; otherwise returns a HuggingFace id.
- `CustomApiGatewaySubAgent` merges stored config over `DEFAULT_CONFIG`. `get_safe_config` adds `masked_key` but still returns the raw `api_key` field.
- Live sessions (`active_sessions`) and batch jobs (`jobs`) are in-memory dicts only; lost on restart. Unknown job id returns `status: "not_found"`.

## Side Effects
- Reads and writes `../custom_api_config.json` (contains credentials).
- Network: `urllib.request.urlopen` (`test_connection`) and `requests.post` (`transcribe_audio_bytes`) to the configured `base_url`. Model download from HuggingFace if no local model.
- Subprocesses: ffmpeg/ffprobe (convert, probe), `vulkaninfo`, and GPU probes in `hardware_profiler.py`; reads `/proc/meminfo`.
- Sets `OMP_NUM_THREADS` / `MKL_NUM_THREADS` via `os.environ.setdefault`.
- Writes temporary WAV files during conversion.

## Verification
- No tests exist for this module. Manual: run `python app.py` from `Transcription Module/` and exercise `/api/status`.
