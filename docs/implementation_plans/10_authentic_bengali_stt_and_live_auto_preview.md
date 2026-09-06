# Milestone Revision v3.10: Authentic Bengali Speech-to-Text & Real-Time Auto-Preview Live Speech Studio

## Overview
This revision resolves two interconnected critical issues:
1. Spoken Bengali being transcribed into phonetic/Romanized English gibberish (*"Christian brothers. Christian brothers, Heolah..."*).
2. Live recording text monitor showing `"0 words captured"` without previewing words as the user speaks.

## Root Causes
1. **Groq Whisper Model Interception**: `api_settings.json` held a Groq key in `transcription_api_key`. `process_ai_request` redirected to Groq Whisper instead of Gemini. Groq Whisper was called without enforcing `language="bn"`, causing severe hallucination of English phonetics for Bengali speech.
2. **SpeechRecognition Language Misconfiguration**: In `LiveRecordStudio.jsx`, `language = 'auto'` defaulted `recognition.lang` to `'en-US'` on English Windows 11.
3. **Lack of Fallback Preview**: Browser `webkitSpeechRecognition` fails silently if Google cloud speech endpoints are unreachable or on network errors. There was no automatic backend auto-preview streaming or post-take auto-transcribe.

## Solution Architecture
1. **AI Routing & Language Enforcement (`ai_providers.py`)**:
   - Explicitly decouple provider keys: if `stt_prov == 'gemini'`, ignore any `gsk_` keys and enforce Gemini API key.
   - Enforce authentic Bengali script prompt in `transcribe_audio_gemini`.
   - Default Groq STT language to `"bn"` if Groq is ever invoked.
2. **Dedicated Backend Transcribe Endpoints (`app.py`)**:
   - `/api/live_transcribe_chunk`: streaming audio slice transcription.
   - `/api/transcribe_take`: instant auto-transcription of saved take blobs upon recording stop.
3. **Front-End Auto-Preview Live Speech Studio (`LiveRecordStudio.jsx`)**:
   - Default language set to `'bn'` (`bn-BD`).
   - Periodic chunk streaming to backend during recording so text appears live.
   - Immediate auto-transcribe on stop if client recognition produced no text.
   - Fixed `handleTranscribeAllTakes` key resolution to use Gemini key by default.
