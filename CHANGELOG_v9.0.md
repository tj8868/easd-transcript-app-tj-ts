# Changelog v9.0 (committed 2026-11-14; switching still off by default)

This file records the Bangla/English switching work in detail. Other v9.0 work in the same
working tree is listed at the end and documented elsewhere; this file is not the full v9.0 record.

## Bangla/English switching in local transcription — Phase 1 (2026-11-14)

Design: [docs/designs/bilingual_local_transcription.md](docs/designs/bilingual_local_transcription.md).

**Problem.** Local transcription with `whisper-bengaliai` always decoded every word as Bangla
(`is_banglish` forced `bn`), so English speech came out garbled or as Bengali-script sound-alikes.

**What changed (switching is OFF by default until measured):**

- `local_whisper_engine.py`
  - With `EASD_CODE_SWITCH=1`, each 3-minute slice is split at pauses (≥ 0.6 s) into speech
    stretches (≤ 30 s), a detector tags each stretch of ≥ 2 s as Bangla or English (English only
    when p(en) ≥ 0.6; Hindi/Nepali/Urdu/Assamese count as Bangla), short stretches follow their
    neighbours, and equal neighbours merge into runs. Bangla runs decode on `whisper-bengaliai`
    exactly as before; English runs decode on `small.en`.
  - New public functions: `code_switch_enabled`, `code_switch_detector`, `ensure_aux_model`,
    `ensure_code_switch_models`, `code_switch_status` (also in `get_engine_status()["code_switch"]`
    and so in `/api/system_audit`).
  - One-time model download at app start (warm-up thread) into `models/whisper-small.en/` and the
    detector folder, via `<folder>.partial` renamed only when complete. No network call once
    installed; a failed download is not retried until the next app start.
  - Fail soft: missing models, < 1200 MB free RAM, a planner/VAD/detector error, or a `small.en`
    decode error all fall back to Bangla-only decoding for the affected audio.
  - The VAD stretch splitter joins stretches cut only by Silero's 30 s block edge.
  - `transcribe_local_audio(..., code_switch=True)`: new keyword; a caller-forced language never
    switches.
- `stt_pipeline.whisper_transcribe_bytes(..., code_switch=True)` passes the flag through.
- `ai_providers.live_transcribe_audio_chunk`: the live preview passes `code_switch=False`.
- New settings (read at call time): `EASD_CODE_SWITCH` (0), `EASD_CS_DETECTOR` (tiny),
  `EASD_CS_MIN_PAUSE_SEC` (0.6), `EASD_CS_MAX_STRETCH_SEC` (30), `EASD_CS_MIN_LID_SEC` (2.0),
  `EASD_CS_EN_THRESHOLD` (0.6), `EASD_CS_MIN_FREE_MB` (1200).
- New `scripts/measure_language_id.py` (`stretches` / `score` / `compare`) for Phase 2.
- New `tests/test_code_switch.py` (25 tests, fake models, no downloads); `tests/conftest.py` sets
  `EASD_CODE_SWITCH=0` by default.
- `pytest` 9.2.0 installed into `.venv` (it was missing; needed by the documented test command).

**Rollback:** `EASD_CODE_SWITCH=0` (the default) restores the previous behaviour exactly.

**Still to do (Phases 2–3):** label a 5–10 minute mixed excerpt, run `score` and `compare`,
write the winning detector / threshold as defaults, and turn switching on only if G1, G2 and G4 pass.

## Other uncommitted v9.0 work (documented elsewhere)

- Silence trimming before STT (`silence_trimmer.py`).
- Docker llama-server mode (`docker/llama/`, `local_llm_engine.docker_mode`).
- Upload limit raised to 2 GB.
