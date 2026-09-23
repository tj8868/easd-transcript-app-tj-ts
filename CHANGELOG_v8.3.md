# eCommunicator / EASD Meeting Minutes – v8.3

Fixes long recordings (30–60+ minutes) that came back as an **empty transcript**, and removes every place where the app silently filled in invented text.

## The pipeline

| Step | What happens | What changed in 8.3 |
|---|---|---|
| 1. Ingest | Any audio/video format, up to 1 GB | The upload is streamed to disk and stops as soon as it passes 1 GB (it used to load the whole file first). The browser checks the size before uploading. Corrupt files, files with no audio and a missing FFmpeg now return a clear error instead of passing raw bytes on. |
| 2. Convert | FFmpeg → 16 kHz mono MP3 at 48 kbps, first audio track only | Every file is always converted. The old shortcut for files that were already 16 kHz WAV produced chunks of about 18 MB, which is over Gemini's 20 MB limit per request. Chunks are exactly 10 minutes each (`-reset_timestamps`), and each chunk's real length is measured. |
| 3. Transcribe | New module `stt_pipeline.py` | Each chunk goes to Gemini transcribe, is **retried with backoff** on 429/5xx/timeouts, then tries a prompt-mode fallback model (`gemini-2.5-flash`), then Local Whisper. At most 2 chunks go to Gemini at the same time, started 1.5 s apart. A bad API key is not retried. Speaker labels (`spk_1`, `spk_2`) are now told apart; before, everyone came out as "Speaker 1". Timestamps are shifted by each chunk's real start time and kept inside the chunk. |
| 4. Show | Transcript box | The transcript now arrives with a status: `success`, `partial` or `error`. Chunks that fail are **kept as visible gap lines**: `[20:00] ⚠ TRANSCRIPT GAP 20:00-30:00: audio not transcribed (<reason>)`. A banner that stays until dismissed lists each failed chunk, its time range and the reason. Previously the status text was never shown on screen. |
| 5. Fill template | Gemini JSON-mode fills the schema of the selected template | Retries on 429/5xx. If the JSON is cut off, it tries again asking for a shorter version. The prompt forbids inventing names, dates or venues and tells the model to respect gap lines. The original transcript can never be replaced by the model's rewrite. |
| 6. Verify | Output checks | The **hard-coded placeholder transcript was removed**. The offline fallback no longer writes sample content (fake dates, quotes, statistics, signatories); it only uses text found in the transcript, plus standing values such as the venue. The sample date "29 August 2026" was removed from the UI defaults, the preview and the DOCX. Empty values from the model no longer wipe fields you already filled in. |

## Logs

Everything is written to `app_service.log` next to `app.py`, in both console and pythonw/.vbs modes. For each chunk the log records the provider, attempt number, exact error (including the HTTP status), fallbacks and timing. `diag_long_audio_repro.py <file>` runs one file through the whole path and saves that run's log.

## API response of `/api/transcribe_take`

```json
{"status": "partial", "transcript": "...", "message": "Transcribed 4 of 5 chunk(s); 1 time range(s) are missing...",
 "errors": ["Chunk 3 of 5 (20:00-30:00) failed: Gemini: Gemini rate limit / quota exceeded (HTTP 429 ...)"],
 "missing_ranges": [{"index": 3, "range": "20:00-30:00", "reason": "..."}], "chunks": [...], "duration_sec": 2424.5}
```

## Settings you can change (environment variables)

`EASD_GEMINI_MAX_PARALLEL` (2), `EASD_GEMINI_STAGGER_SEC` (1.5), `EASD_GEMINI_MAX_ATTEMPTS` (4),
`EASD_GEMINI_BACKOFF_BASE_SEC` (4), `EASD_GEMINI_STT_MODEL` (gemini-3.5-transcribe),
`EASD_GEMINI_STT_FALLBACK_MODELS` (gemini-2.5-flash), `EASD_LOG_LEVEL` (INFO).

## Tests

`python test_long_audio_pipeline.py "Recording\Meeting minutes 15Sep2026.m4a"` runs 52 checks with no network needed: real FFmpeg, and real google-genai response objects through a fake transport.
