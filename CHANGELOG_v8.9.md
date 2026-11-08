# v8.9 — Changelog (28 Oct 2026)

Full explanation, steps, test results and settings: **v8.9_Fix_Report.html** (open in any browser).

- NEW: English-only / Bangla-only transcript conversion (timestamps + speakers preserved) — `transcript_translator.py`, `/api/translate_transcript`, tabs in the transcript box.
- FIX: real speaker identification with a local neural model (WeSpeaker ONNX) instead of "flip speaker on pause" — `speaker_diarization.py`.
- FIX: consistent speaker numbers across chunks of long recordings.
- FIX: lines without word timings no longer jump to [00:00].
- FIX: live preview transcribes only new audio, on one timeline, with the live model; server no longer freezes per chunk.
- FIX: template fill reports AI failures instead of "success".
- FIX: no shared `raw_transcript.txt` written to the app folder.
- FIX: attendance no longer marks people present from a common surname.
- FIX: CORS restricted to the app's own pages (API keys were readable by any website).
- FIX: broken test imports; 8 new regression tests.
- NEW: GPU acceleration — NVIDIA (CUDA, large-v3-turbo), Intel Iris Xe/Arc/Core Ultra (OpenVINO), DirectML/ROCm/CoreML for the speaker model.
- NEW: optional TurboQuant KV cache (TheTom's llama.cpp fork) for the local LLM + build scripts.
- UI: plain-language labels, 44 px touch targets, phone/tablet layout fixes.
- CORRECTION to the earlier bug report: template section wiring was already correct (no change).
