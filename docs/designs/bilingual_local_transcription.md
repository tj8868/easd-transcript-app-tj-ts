# Bangla/English Switching in Local Transcription

*   **Author:** EASD Administrator
*   **Status:** Approved — Phase 1 implemented 2026-11-14 (switching off by default); Phases 2–3 pending measurement
*   **Date:** 2026-11-14

--------------------------------------------------------------------------------

## Overview

EASD meetings mix Bangla and English. One speaker talks in Bangla, the next answers in English, and
some people switch from sentence to sentence. When the app transcribes on the PC itself (local
Whisper, used when there is no Gemini key or the cloud is down), every word is decoded as Bangla.
English speech comes out garbled or written as Bengali-script sound-alikes, so those parts of the
transcript, and the minutes filled from it, are wrong.

This design changes local transcription so that each spoken stretch is decoded in the language
it was spoken in, while keeping the app free, fully offline, and usable on the current office PC
(Intel i3-4150, 2 cores, 8 GB RAM, no usable GPU).

## The Problem

`local_whisper_engine.transcribe_local_audio` uses the `whisper-bengaliai` model by default. This
model was fine-tuned on Bangla only. Because of that, the code always decodes it with the Bangla
language token and no prompt (`local_whisper_engine.py:1029-1033`: `is_banglish` sets
`explicit_lang = "bn"`). Once the language is fixed, the per-slice language detection is skipped
(`:1044`, the log line `Language forced by caller: 'bn' (per-slice detection disabled)`). Every
local job on 2026-11-14, including the 57-minute "EASD Meeting minutes Nov32026.m4a", shows that
line.

The app already has logic for mixed-language audio. `_plan_code_switched_runs`
(`local_whisper_engine.py:756`) splits a slice into 30-second windows and
`_resolve_window_language` (`:224`) picks Bangla or English for each window. But:

1.  That logic never runs for `whisper-bengaliai`, the default and only installed model.
2.  Its window is 30 seconds (`_CODE_SWITCH_WINDOW_SEC`, `:753`). A meeting can hold several
    Bangla/English turns in 30 seconds, so one window still gets one language.
3.  It detects language with the same model it transcribes with. A model fine-tuned on Bangla
    only is not a trustworthy judge of "is this English?"; this is unmeasured.
4.  Even with the right language chosen, the open question is whether `whisper-bengaliai` can
    write English at all. If its English ability was lost in fine-tuning, English stretches need
    a different model.

The other engines are not affected in the same way. Gemini transcription handles mixed speech
in one pass (its prompt asks for mixed Bangla/English kept as spoken). The live browser preview
listens in one language at a time and switches only during a pause; that is a separate
component (`frontend/src/components/LiveRecordStudio.jsx`) and is out of scope here.

Constraints that shape any solution:

*   **Cost:** no paid service and no card. Gemini's free tier is an option for non-confidential
    meetings, but it does not remove the need for a working local path (confidential meetings,
    no internet, free-tier limits).
*   **Hardware:** local Whisper already runs slower than real time on this PC. Measured
    real-time factor (RTF) is 1.47 for chunk 1 of the Nov 3 meeting (600 s of audio in 884 s,
    `int8`, greedy decoding, `beam=1`). Any extra per-stretch work adds directly to the wait.
*   **Memory:** 8 GB total. The app was killed by the kernel's out-of-memory killer on
    2026-11-14 while Whisper (about 1.6 GB) shared the PC with a Docker build and Firefox. A
    second resident model must fit next to `whisper-bengaliai`.
*   **Fail soft (project rule):** if any new piece fails, transcription must still finish,
    falling back to today's Bangla-only behavior.

## Goals

*   **G1. English stretches come out in English.** On a mixed meeting recording, a spoken
    stretch that is mainly English (at least about 2 seconds long) is written in Latin-script
    English, not garbled text or Bengali-script sound-alikes. Measured on a labelled test
    excerpt from a real EASD meeting (see the Open Questions about building it).
*   **G2. No regression for Bangla.** On Bangla-only audio, the output is the same quality as
    today. Bangla stretches are still decoded by `whisper-bengaliai` with the Bangla token and
    no prompt, the configuration chosen in v8.9.
*   **G3. Switching follows the speakers.** A change of language at a pause between sentences
    or speakers is detected, rather than one language per 30-second window or per 3-minute
    slice.
*   **G4. Bounded cost on the office PC.** Total local transcription time for a mixed meeting
    grows by no more than 15% over today's Bangla-only run (target: same or faster, since
    English stretches may use a smaller model). Peak RAM of the app grows by no more than
    0.8 GB.
*   **G5. Fail soft.** If language identification or the English model cannot load (missing
    file, no internet for the one-time download, out of memory), the job logs a warning and
    falls back to today's behavior for the affected audio. The transcript is still produced.
*   **G6. Output contract unchanged.** Lines keep the `[MM:SS] Speaker N:` prefix, timestamps
    stay on the original recording's timeline (including the silence-trimming `time_map`), and
    speaker diarization keeps working across stretches.
*   **G7. One-time download, then offline.** Each new model is a free download that happens
    exactly once per PC. It is saved in the app's own `models/` folder (for example
    `models/whisper-small.en/`), not in a per-user cache such as `~/.cache/huggingface`, so it
    is not downloaded again for another user, after a cache clean-up, or when the app folder is
    copied to another PC. Once the files are in `models/`, the app makes no network call for
    that model: every later transcription loads it from disk, with or without internet. A
    download that fails part-way leaves no half-written model in place, and the next attempt
    resumes or restarts it; it is never treated as installed until complete.

## Non-Goals

*   **Switching inside a sentence.** A sentence like "meeting টা কালকে postpone হয়েছে" stays
    with the Bangla model. English words inside a Bangla sentence may still come out in
    Bengali script. Solving that needs a bilingual model too large for this PC.
*   **Live preview.** The browser speech recognition in `LiveRecordStudio.jsx` and the
    4.5-second backend preview are not changed by this design.
*   **Gemini and other cloud paths.** Their language handling is not changed.
*   **Languages other than Bangla and English.** Detection stays restricted to `bn`/`en`, as
    the project already requires.
*   **Making local transcription live or much faster overall.** The hardware limit (RTF about
    1.5 for the Bangla model) stays. This design only must not make it noticeably worse.
*   **Choosing a new Bangla model.** `whisper-bengaliai` stays the Bangla model.

## Decisions

*   **D1. English model: `small.en`** (`Systran/faster-whisper-small.en`, OpenAI's English-only
    small Whisper in CTranslate2 format). Decided by author on 2026-11-14 over reusing
    `whisper-bengaliai` with the `en` token (untested whether its English survived the Bangla
    fine-tune) and `base.en` (weaker on accented or noisy English). Costs: a one-time download of
    about 480 MB into `models/whisper-small.en/` (never repeated, see G7), about 0.5 GB extra RAM
    while transcribing; it decodes about 2-3x
    faster than `whisper-bengaliai`. A test on a real EASD meeting runs before the feature is
    switched on by default.

*   **D2. Language detector: chosen by measurement.** Decided by author on 2026-11-14. Three
    candidates are measured on a marked excerpt of a real EASD meeting before the detector is
    fixed: `whisper-bengaliai`'s own language detection (no download, no extra RAM),
    `tiny` multilingual (`Systran/faster-whisper-tiny`, about 75 MB, about 0.15 GB RAM) and
    `base` multilingual (`Systran/faster-whisper-base`, about 145 MB, about 0.25 GB RAM). The
    one with the highest stretch-level accuracy wins; on a tie within 2 percentage points the
    smaller one wins. Only the winner is kept in `models/` and downloaded on other PCs. Dedicated
    language-ID models (SpeechBrain VoxLingua107, Meta MMS-LID) were ruled out: they need
    PyTorch (not installed, about 700 MB+) or more RAM than the PC has.

## Open Questions

*   **Q3. What is the shortest stretch whose language can be identified reliably?** The plan
    starts at 2.0 seconds (stretches shorter than that inherit a neighbour's language). The
    measurement in D2 confirms or moves this number.
*   **Q4. Test material.** Which 5–10 minute excerpt of a real EASD meeting has both English
    and Bangla parts? The author (or a colleague) marks which stretches are English using the
    stretch list the measurement script prints (see Detailed Implementation).

## Critical User Journeys (CUJs)

### CUJ 1: Mixed meeting, transcribed locally

*   **Given**: No Gemini key (or the cloud fails). `models/whisper-bengaliai`, the English
    model and the chosen detector are in `models/`. A 57-minute recording where speakers
    alternate between Bangla and English.
*   **When**: The user uploads the recording, or stops a recorded take.
*   **Then**: Bangla turns are written in Bengali script as today; English turns of about 2 s or
    more are written in English. Every line keeps `[MM:SS] Speaker N:` with timestamps on the
    original recording. The log shows, per 3-minute slice, how many stretches were found and
    which runs went to which model. Total time is within G4.

### CUJ 2: First use on a PC without the new models

*   **Given**: A fresh copy of the app with only `whisper-bengaliai` in `models/`, and
    internet.
*   **When**: The app starts.
*   **Then**: In the background, the English model and detector are downloaded once into
    `models/`. Any transcription that starts before both are ready runs exactly as today
    (Bangla only) and logs why. After the download, all later jobs use switching, with or
    without internet. Restarting the app never downloads them again.

### CUJ 3: Something in the new path fails

*   **Given**: The English model is missing and cannot be downloaded (no internet), or free RAM
    is too low to load it, or the detector throws an error.
*   **When**: A local transcription runs.
*   **Then**: The job logs one warning naming the reason and transcribes the affected audio the
    old way (Bangla only). The transcript is produced and the job reports success.

### CUJ 4: Live preview while recording

*   **Given**: Local transcription, recording in progress.
*   **When**: The 4.5-second live preview sends audio to the backend.
*   **Then**: The preview behaves exactly as today (no switching, no extra model loads), so it
    does not compete with the switching work of the real job.

## Technical Plan (Architecture)

### Where the change sits

Only the local Whisper path changes. Today, for each 3-minute slice of a chunk,
`transcribe_local_audio` builds a list of language runs (`runs`: offset, duration, language)
and decodes each run with the one loaded model. For `whisper-bengaliai` that list is always a
single run marked `bn`. The plan keeps that loop and its run list, and changes two things:

1.  **How the run list is built** for `whisper-bengaliai`: from short speech stretches, each
    tagged Bangla or English by the detector, instead of one forced `bn` run.
2.  **Which model decodes each run**: Bangla runs go to `whisper-bengaliai` (Bangla token,
    no prompt, as today); English runs go to `small.en`.

Everything after decoding stays the same: the confidence filters, `sanitize_whisper_text`,
the voice-based speaker labels (`speaker_diarization.diarize_wav_segments`), the
`[MM:SS] Speaker N:` lines, and the silence-trim time map applied later in
`stt_pipeline.transcribe_chunks`.

```text
 chunk (10 min, already silence-trimmed)
   │
   ▼
 3-minute slice ──► stretch splitter (Silero VAD, split at pauses ≥ 0.6 s,
   │                 cap 30 s per stretch)
   │                       │
   │                       ▼
   │                 detector (winner of D2) ── per stretch ≥ 2.0 s:
   │                   p(en) vs p(bn) [hi/ne/ur/as folded into bn]
   │                       │
   │                       ▼
   │                 smoothing: short stretches take a neighbour's language;
   │                 neighbours with the same language merge into one run
   │                       │
   │                       ▼
   │                 runs: [(0-41 s, bn), (41-58 s, en), (58-180 s, bn)]
   │                       │
   ▼                       ▼
 existing run loop ──► bn run ──► whisper-bengaliai (lang=bn, no prompt)
                   └─► en run ──► small.en         (lang=en, English prompt)
   │
   ▼
 existing segment filters → sanitize → speaker labels → "[MM:SS] Speaker N: text"
```

### Component 1: Stretch splitter

*   Uses Silero VAD through `faster_whisper.vad.get_speech_timestamps`, the same VAD the engine
    already uses (`_get_vad_options`, `WHISPER_VAD_PARAMETERS`), on the slice's 16 kHz audio.
    No new dependency and no extra decode of the file.
*   A new stretch starts at every pause of at least 0.6 s (setting
    `EASD_CS_MIN_PAUSE_SEC`). This is shorter than the silence trimmer's 2.0 s cut, so it still
    finds turn changes in audio the trimmer has already shortened.
*   A stretch longer than 30 s is cut at its longest internal pause, because one language
    decision for half a minute or more defeats G3.
*   The silence trimmer's own stretch list is not reused: it is computed on the whole
    recording before chunking and is not passed down to the engine; threading it through
    `media_processor` → `ai_providers` → `stt_pipeline` → the engine would touch four modules
    for a saving of one VAD pass per slice (about 1–2 s of CPU per 3 minutes).

### Component 2: Language detector

*   Runs the detector chosen in D2 on each stretch of at least 2.0 s (setting
    `EASD_CS_MIN_LID_SEC`). It reuses the scoring rule of `_resolve_window_language`
    (`local_whisper_engine.py:224`): only `bn` and `en` compete, and Hindi, Nepali, Urdu and
    Assamese probability is added to Bangla.
*   **Bias towards Bangla.** A stretch is tagged English only when p(en) is at least 0.6
    (setting `EASD_CS_EN_THRESHOLD`). Reason: a Bangla stretch wrongly sent to `small.en`
    produces English-looking nonsense, a new kind of error that breaks G2; an English stretch
    wrongly kept in Bangla is no worse than today. The measurement may move this number.
*   The detector only scores language; it never writes transcript text.

### Component 3: Smoothing and run building

*   Stretches shorter than 2.0 s take the language of the previous stretch in the same slice;
    the first stretch of a slice takes the next one's; a slice with no stretch of 2.0 s or more
    stays all Bangla.
*   Consecutive stretches with the same language merge into one run, and the gap between them
    is included, so the decoders see natural context and the number of decode calls stays
    small. Runs then cover the whole slice with no holes, like today's single run.
*   The result is the same run list shape the loop already consumes, so the decode loop, the
    per-run temporary WAV slicing and the timestamp arithmetic (`chunk_start_sec + run_off +
    segment.start`) are reused unchanged.

### Component 4: Model registry and one-time download

*   Two new model folders next to the existing ones: `models/whisper-small.en/` and the
    detector's folder (`models/whisper-tiny/` or `models/whisper-base/`, per D2; none if
    `whisper-bengaliai` wins).
*   **Download once (G7).** Files are fetched with `huggingface_hub.snapshot_download` into a
    temporary sibling folder (`models/whisper-small.en.partial/`) and renamed to the final name
    only after the download completes and the weights file is present. The engine's existing
    `_model_has_weights` check decides "installed"; a `.partial` folder never counts. Because
    `snapshot_download` is given `local_dir`, the files land in `models/`, not in a per-user
    Hugging Face cache.
*   **When it downloads.** In the background at app start, after the Whisper warm-up, only if a
    folder is missing. A failed download is logged once and retried at the next app start,
    never once per chunk (same pattern as `stt_pipeline._whisper_download_failed`).
*   **Loading.** The English model and detector load lazily the first time a slice needs them,
    with the same `int8`, CPU-threads and `local_files_only=True` settings as the Bangla model,
    and stay loaded in the engine's model cache (`_LOCAL_MODELS`). Before loading, the engine
    checks free RAM; below 1200 MB (setting `EASD_CS_MIN_FREE_MB`) it skips switching for that
    job (CUJ 3). Expected resident cost: about 0.5 GB (`small.en`) plus 0 / 0.15 / 0.25 GB for
    the detector.

### Component 5: Switches and the live preview

*   One master setting, `EASD_CODE_SWITCH` (on by default once the measurement passes; `0`
    restores today's Bangla-only behaviour exactly).
*   `transcribe_local_audio` and `stt_pipeline.whisper_transcribe_bytes` gain a
    `code_switch` flag. Batch callers (`stt_pipeline.transcribe_chunks`) leave it on; the live
    preview caller (`ai_providers.live_transcribe_audio_chunk`, ctx `[live]`) turns it off
    (CUJ 4).
*   Only `whisper-bengaliai` uses the new path. `large-v3-turbo` (NVIDIA) and the OpenVINO path
    keep their current language handling, since they are multilingual models.

### Failure handling (G5)

Each new step is wrapped so that an error degrades to the old behaviour for the affected
slice only:

| Failure | Behaviour |
|---|---|
| English model or detector missing / downloading | whole job runs as today; one log line |
| Low RAM before loading | whole job runs as today; one log line |
| VAD or detector error on a slice | that slice runs as one `bn` run; warning logged |
| `small.en` decode error on a run | that run is re-decoded with `whisper-bengaliai` as `bn` |

### What is logged

Per slice: number of stretches, number tagged English, the resulting runs
(`0s+41s=bn, 41s+17s=en, …`) and the detector time. Per job: total English seconds and
whether switching was active or why it was skipped. This is what makes G1–G4 checkable on
real meetings without re-running anything.

### Effect on time and memory (G4)

*   Added work per 3-minute slice: one VAD pass (about 1–2 s) and one detector call per
    stretch (`tiny`/`base`: a fraction of a second each on this CPU; measured in D2).
*   Saved work: English runs decode on `small.en`, about 2–3 times faster than
    `whisper-bengaliai`.
*   Possible extra cost: more, shorter decode calls. Merging same-language neighbours keeps
    this low; the measurement reports total time against today's run of the same excerpt.

## Alternatives Considered

The alternatives below were raised in the 2026-11-14 working session. Entries marked
"Rejected by author" were decided by the author in that session; the others were set aside
while drafting, with the reason given, and remain open to challenge in review.

### Alternative A: Use Gemini (cloud) for mixed meetings

*   **Pros**: Handles Bangla/English switching inside a sentence, which this design cannot.
    Much faster (minutes instead of about 70 minutes for a 57-minute meeting). A free-tier key
    exists without a card in most cases.
*   **Cons**: Needs internet. Free-tier limits were cut in 2025–26 and are only shown inside
    AI Studio. On the free tier Google may use the audio to improve its products, which rules
    it out for confidential meetings. Not every model is guaranteed on the free tier.
*   **Reason for Rejection**: Rejected by author as the *only* answer: no paid account or card,
    and confidential meetings must stay on the PC. It stays available in the app for
    non-confidential meetings; this design fixes the local path that is used when Gemini is
    not.

### Alternative B: Browser speech recognition (Chrome cloud or Firefox 160 on-device)

*   **Pros**: Free, live, no app models to manage.
*   **Cons**: Only affects the live preview, never the final transcript. Chrome sends audio
    to Google. Firefox 160's on-device recognition has no published language list, and the
    `install()` attempt on this PC downloaded nothing, which suggests no Bangla model. Plain
    Chromium has neither cloud nor on-device recognition. All of them listen in one language
    at a time.
*   **Reason for Rejection**: Does not address the final transcript, which is where the
    problem is. Left out of scope (Non-Goals: live preview).

### Alternative C: One small multilingual Whisper (`tiny`/`base`/`small`) for all speech

*   **Pros**: One model, handles both languages, switching built in.
*   **Cons**: These models produced repetition loops or Latin-script text on Bangla meeting
    audio, which is why v8.9 removed them (`local_whisper_engine.py:select_optimal_model_name`
    docstring); the author also reported garbled output from the tiny models.
*   **Reason for Rejection**: Rejected by author: Bangla quality would fall far below today's,
    breaking G2.

### Alternative D: A large multilingual Whisper on CPU (`medium` multilingual or `large-v3-turbo`)

*   **Pros**: One model with good Bangla and English and built-in switching per 30-second
    window.
*   **Cons**: `large-v3-turbo` is already the app's choice on NVIDIA GPUs, but on this CPU it
    would be several times slower than `whisper-bengaliai`, which already runs at RTF 1.47.
    `medium` multilingual is the same size and speed as `whisper-bengaliai`, but v8.9 chose the
    Bangla fine-tune over it for Bangla quality (the source comment at
    `local_whisper_engine.py:80-81` cites it as the best open Bangla result in arXiv 2602.21741).
    Replacing the fine-tune would trade Bangla quality for English; running either one
    alongside `whisper-bengaliai` breaks the RAM cap.
*   **Reason for Rejection**: Breaks G4 (time and RAM) on the office PC.

### Alternative E: Reuse `whisper-bengaliai` with the `en` token for English stretches

*   **Pros**: No download, no extra RAM, no second model to manage.
*   **Cons**: Untested whether its English survived the Bangla-only fine-tune; if not, English
    stays garbled and G1 fails.
*   **Reason for Rejection**: Rejected by author in favour of `small.en` (decision D1).

### Alternative F: `base.en` instead of `small.en`

*   **Pros**: About 145 MB and 0.2 GB RAM; about 5 times faster than `whisper-bengaliai`.
*   **Cons**: Weaker on accented, fast or noisy English, which is common in meetings.
*   **Reason for Rejection**: Rejected by author in favour of `small.en` (decision D1).

### Alternative G: A dedicated language-ID model (SpeechBrain VoxLingua107, Meta MMS-LID)

*   **Pros**: Built only for language identification; more accurate than small Whisper models
    on short clips.
*   **Cons**: VoxLingua107 needs PyTorch, which is not installed (about 700 MB+ more to
    download, plus RAM). MMS-LID is too large for 8 GB.
*   **Reason for Rejection**: Breaks G4/G7 on this PC. Recorded under decision D2.

### Alternative H: Keep the existing 30-second window switching (`_plan_code_switched_runs`) and just enable it for `whisper-bengaliai`

*   **Pros**: Smallest code change: the logic already exists.
*   **Cons**: A 30-second window holds several Bangla/English turns in a meeting, so one
    language still covers mixed speech (fails G3). It detects language with the model it
    transcribes with, which for a Bangla-only fine-tune is the weakest detector. It still
    decodes English with `whisper-bengaliai` (see Alternative E).
*   **Reason for Rejection**: Fails G3 and depends on Alternative E. Its scoring rule
    (`_resolve_window_language`) is reused by this design.

### Alternative I: Reuse the silence trimmer's speech stretches instead of a second VAD pass

*   **Pros**: Saves one VAD pass per 3-minute slice.
*   **Cons**: The trimmer runs on the whole recording before chunking, and its stretch list is
    not passed down to the engine. Threading it through `media_processor`, `ai_providers`,
    `stt_pipeline` and the engine touches four modules. The trimmer also cuts only pauses of
    2 s or more, coarser than the 0.6 s turn splits this design needs.
*   **Reason for Rejection**: The cost (four modules and coarser splits) outweighs a saving of
    about 1–2 s of CPU per slice.

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Privacy:** all new processing is on the PC. The only network use is the one-time model
    download from Hugging Face; no audio or text leaves the PC.
*   **Performance and memory:** bounded by G4 (+15% time, +0.8 GB RAM) and checked by the
    measurement script before switching is turned on by default.
*   **Rollout and rollback:** `EASD_CODE_SWITCH=0` restores today's Bangla-only behaviour with
    no other change. Deleting `models/whisper-small.en/` has the same effect (switching is
    skipped when the model is missing) until the next app start downloads it again.
*   **Project rules:** fail soft (G5), keep the `[MM:SS] Speaker N:` prefix (G6), run heavy jobs
    one at a time on 8 GB PCs (the measurement script loads one candidate model at a time).

--------------------------------------------------------------------------------

### Additional Resources

*   `local_whisper_engine.py` (the run loop in `transcribe_local_audio`,
    `_resolve_window_language`, `_plan_code_switched_runs`, `get_local_whisper_model`)
*   `stt_pipeline.py` (`whisper_transcribe_bytes`, `transcribe_chunks`)
*   `app_service.log` for 2026-11-14 (job `5dfae6e6`: forced `bn`, RTF 1.47)
*   `tests/test_whisper_language_and_vad.py` (fake-model test pattern reused by the new tests)

### Future Improvements

*   **Switching inside a sentence:** would need a bilingual model small enough for 8 GB, or the
    Gemini path.
*   **Show switching status in Settings → System audit:** the status function added here could
    be displayed in `SettingsModal.jsx`; left out to keep the change backend-only.
*   **Intel iGPU (OpenVINO) for `small.en`:** the target laptop (i3-1315U) could run the
    English model on its GPU; untested hardware, so not part of this design.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

Work happens in four phases, in this order. Phase 2 must finish before Phase 3 sets the
defaults. Nothing heavy runs while another transcription or build is running (8 GB rule).

*   **Phase 1:** engine code, download logic, flags and tests (switching ships off by default:
    `EASD_CODE_SWITCH` default `0`).
*   **Phase 2:** measurement on a marked real excerpt (decides D2, Q3 and the English
    threshold, and checks G1, G2, G4).
*   **Phase 3:** write the measured values in as defaults, turn `EASD_CODE_SWITCH` default to
    `1` if G1, G2 and G4 passed, delete the losing detector models.
*   **Phase 4:** documentation and changelog.

### Target Files to Create/Modify

#### 1. `local_whisper_engine.py` (Modify)

*   **Type / Scope**: Python module, local Whisper engine.
*   **Proposed Changes**:
    *   **New constants**, next to `_BENGALIAI_MODEL_DIR` / `_TURBO_REPO`:
        *   model folders and repos: `models/whisper-small.en` ← `Systran/faster-whisper-small.en`;
            `models/whisper-tiny` ← `Systran/faster-whisper-tiny`; `models/whisper-base` ←
            `Systran/faster-whisper-base`.
        *   settings read **at call time** (not import time, so tests and the measurement
            script can change them): `EASD_CODE_SWITCH` (default `0` in Phase 1, `1` after
            Phase 3), `EASD_CS_DETECTOR` (`bengaliai` | `tiny` | `base`; default set in
            Phase 3), `EASD_CS_MIN_PAUSE_SEC` (0.6), `EASD_CS_MAX_STRETCH_SEC` (30),
            `EASD_CS_MIN_LID_SEC` (2.0), `EASD_CS_EN_THRESHOLD` (0.6), `EASD_CS_MIN_FREE_MB`
            (1200).
    *   **`ensure_aux_model(kind) -> bool`** (new, public). `kind` is `"en"`, `"tiny"` or
        `"base"`. If the folder has weights (`_model_has_weights`), return True with no network
        call. Otherwise download with `snapshot_download(repo, local_dir=<folder>.partial)`,
        check that the weights file exists in `.partial`, remove any stale final folder, rename
        `.partial` to the final name, return True. On any error: log once, delete nothing
        except a `.partial` left by this attempt, record the reason in a module-level
        `_AUX_DOWNLOAD_FAILED[kind]`, return False. While a reason is recorded, later calls in
        the same process return False at once (no retry until app restart).
    *   **`ensure_code_switch_models() -> None`** (new): calls `ensure_aux_model("en")` and,
        unless the detector setting is `bengaliai`, `ensure_aux_model(<detector>)`. Called
        from the existing warm-up worker in `warm_up_local_whisper_in_background`, after
        `get_local_whisper_model()` returns, only when `EASD_CODE_SWITCH` is on.
    *   **`_load_aux_model(kind)`** (new, private): returns a loaded `WhisperModel` from
        `_LOCAL_MODELS` or loads it with `device="cpu"`, `compute_type="int8"`,
        `cpu_threads=get_optimal_cpu_threads()`, `local_files_only=True`, under
        `_MODEL_LOCK`. Never downloads. Returns None if weights are missing or loading fails
        (warning logged).
    *   **`_code_switch_ready(ctx) -> (bool, reason)`** (new, private): True only if the
        setting is on, the English model and detector are installed (or detector is
        `bengaliai`), and either both are already loaded or available RAM
        (`get_system_ram_specs()`) is at least `EASD_CS_MIN_FREE_MB`. Reason strings feed the
        log line of CUJ 2/3.
    *   **`_split_speech_stretches(audio, sr=16000) -> List[(start_sec, end_sec)]`** (new,
        private): `faster_whisper.vad.get_speech_timestamps` with
        `min_silence_duration_ms = EASD_CS_MIN_PAUSE_SEC × 1000` and the engine's VAD
        threshold; stretches longer than `EASD_CS_MAX_STRETCH_SEC` are cut at the
        lowest-energy 100 ms frame inside the stretch (computed from the samples, no model).
    *   **`_stretch_language(detector, audio, start, end) -> (lang, p_en)`** (new, private):
        `detector.detect_language(<samples>)`, then the scoring of `_resolve_window_language`
        restricted to `bn`/`en` (hi/ne/ur/as added to bn); returns `"en"` only if normalised
        p(en) ≥ `EASD_CS_EN_THRESHOLD`, else `"bn"`. Shares one helper with
        `_resolve_window_language` for the scoring so the rule stays in one place.
    *   **`_plan_bilingual_runs(detector, slice_wav, slice_dur, ctx) -> runs`** (new,
        private): decode slice samples once (`faster_whisper.decode_audio`), split, tag
        stretches ≥ `EASD_CS_MIN_LID_SEC`, smooth short ones (previous stretch, else next,
        else `bn`), merge equal neighbours including the gaps, extend the first run to 0 and
        the last to `slice_dur`, and return `[(offset, duration, lang)]` in the same shape as
        `_plan_code_switched_runs`. Logs the run list and timings.
    *   **`transcribe_local_audio`**: new keyword `code_switch: Optional[bool] = None`
        (None = follow `EASD_CODE_SWITCH`).
        *   In the `is_banglish` branch, after `explicit_lang, prompt = "bn", None`: if
            `code_switch` resolves on, call `_code_switch_ready`; if ready, load the English
            model and detector (`bengaliai` = the already loaded `model`) and set a local
            `cs_active = True`; otherwise log the reason once and keep today's path.
        *   In the per-slice language decision: when `cs_active`, `runs =
            _plan_bilingual_runs(...)` inside try/except; on error, warning +
            `runs = [(0.0, chunk_dur_sec, "bn")]`.
        *   In the run loop: decoder = English model when `run_lang == "en"` and `cs_active`,
            else `model`. `initial_prompt` = the existing English prompt string for `en`
            runs, `None` for `bn` runs (today's Bangla setting). `beam_size`, VAD, thresholds
            unchanged. If decoding an `en` run raises, log a warning and decode the same run
            with `model` and `language="bn"`.
        *   The "forced language yielded no speech" retry and `_finalize_result` stay as they
            are. The model label in the result becomes `whisper-bengaliai+small.en` when any
            run used the English model.
    *   **`get_engine_status`**: adds a `code_switch` entry (setting on/off, detector, which
        models are installed / loaded, recorded download failure).

#### 2. `stt_pipeline.py` (Modify)

*   **Type / Scope**: Python module, STT orchestration.
*   **Proposed Changes**: `whisper_transcribe_bytes` gets a keyword
    `code_switch: bool = True` and passes it to `lwe.transcribe_local_audio`. Its log line adds
    `code_switch=<value>`. `transcribe_chunks` keeps the default (on). No other change; the
    `time_map` remapping already runs after Whisper returns.

#### 3. `ai_providers.py` (Modify)

*   **Type / Scope**: Python module, orchestration.
*   **Proposed Changes**: in `live_transcribe_audio_chunk`, the call
    `stt_pipeline.whisper_transcribe_bytes(..., ctx="[live]", ...)` (currently line 1102)
    passes `code_switch=False` (CUJ 4). The other two local-Whisper call sites
    (`transcribe_audio_gemini`'s Whisper fallback at line 1043, `transcribe_single_chunk` at
    line 1138) are batch paths and keep the default.

#### 4. `scripts/measure_language_id.py` (Create)

*   **Type / Scope**: developer command-line tool (Phase 2), not imported by the app.
*   **Proposed Changes**: run with `.venv/bin/python scripts/measure_language_id.py
    <command> …`. Loads one candidate model at a time and frees it before the next.
    *   `stretches <audio> --start MM:SS --end MM:SS --out labels.csv`: converts the excerpt
        to 16 kHz WAV (`convert_to_wav_pcm16k`), runs `_split_speech_stretches`, writes a CSV
        with `start,end,duration,lang` where `lang` is blank, for a person to fill with `bn`,
        `en` or `mixed` while listening.
    *   `score <audio> labels.csv`: for each detector (`bengaliai`, `tiny`, `base`;
        downloading `tiny`/`base` with `ensure_aux_model` if missing) and each English
        threshold 0.5 / 0.6 / 0.7 / 0.8, prints accuracy on `bn`+`en` stretches (`mixed`
        excluded), Bangla-tagged-English count (the G2 risk), English-tagged-Bangla count,
        accuracy by stretch length (<1 s, 1–2 s, 2–4 s, >4 s), and detector seconds per
        minute of audio.
    *   `compare <audio> --start MM:SS --end MM:SS --detector <name>`: transcribes the excerpt
        twice through `transcribe_local_audio` (code switch off, then on), writes both
        transcripts next to the CSV, and prints wall time, peak RSS
        (`resource.getrusage(...).ru_maxrss`), and for each `en`-labelled stretch ≥ 2 s the
        share of Latin letters in the overlapping output lines (G1).

#### 5. `tests/test_code_switch.py` (Create)

*   **Type / Scope**: pytest unit tests with fake models (pattern from
    `tests/test_whisper_language_and_vad.py`), no downloads, no real model.
*   **Proposed Changes**: test cases:
    *   splitter: pauses ≥ 0.6 s split; a 70 s stretch is cut into pieces ≤ 30 s.
    *   detector rule: p(en) 0.55 → `bn`, 0.65 → `en` at threshold 0.6; Hindi probability
        counts as Bangla.
    *   smoothing: a 1 s stretch between two `en` stretches becomes `en`; a slice of only
        short stretches is one `bn` run; runs cover `[0, slice_dur]` with no gap or overlap.
    *   routing: fake Bangla and English models record which runs they decoded; `en` runs
        reach the English fake with the English prompt, `bn` runs reach the Bangla fake with
        no prompt; output lines keep `[MM:SS] Speaker N:` and correct absolute timestamps.
    *   fail soft: English model missing → identical transcript to `code_switch=False`;
        English decode raises → that run re-decoded as `bn`; low-RAM check fails → today's
        path.
    *   live flag: `code_switch=False` never calls `_load_aux_model`.
    *   download: a failed download leaves no final folder and records the reason; a
        `.partial` folder is not treated as installed; an installed folder causes no
        `snapshot_download` call (monkeypatched).

#### 6. `tests/conftest.py` (Modify)

*   **Type / Scope**: pytest configuration.
*   **Proposed Changes**: `os.environ.setdefault("EASD_CODE_SWITCH", "0")` next to the
    existing `EASD_LOCAL_LLM_PRELOAD` line, so existing tests keep today's behaviour on PCs that
    already have the new models; `test_code_switch.py` turns it on per test.

#### 7. `EGM.md` (Modify)

*   **Type / Scope**: architecture contract.
*   **Proposed Changes**: add the `EASD_CODE_SWITCH` and `EASD_CS_*` settings to the
    environment table; add `ensure_aux_model` / `ensure_code_switch_models` to the
    `local_whisper_engine.py` interface line; add an invariant: "Bangla runs always decode on
    `whisper-bengaliai` with `bn` and no prompt; English runs only when p(en) ≥
    `EASD_CS_EN_THRESHOLD`; any failure falls back to Bangla-only"; add the one-time model
    download to Global Side Effects.

#### 8. `CODEMAP.md` (Modify)

*   **Type / Scope**: code and data map.
*   **Proposed Changes**: `models/` row lists `whisper-small.en/` and the chosen detector
    folder; §3 `local_whisper_engine` lists the new functions; §5 notes the one-time
    downloads.

#### 9. `CLAUDE.md` (Modify)

*   **Type / Scope**: project notes.
*   **Proposed Changes**: the "Local models (v8.9 …)" sentence adds `models/whisper-small.en`
    (English stretches) and the chosen detector, and records that switching is controlled
    by `EASD_CODE_SWITCH`.

#### 10. `CHANGELOG_v9.0.md` (Create)

*   **Type / Scope**: release notes (project convention: one changelog per release).
*   **Proposed Changes**: a section "Bangla/English switching in local transcription" with
    the behaviour change, new settings, new model folders, the measured results from Phase 2
    and the rollback setting. The other uncommitted v9.0 work (silence trimmer, Docker
    llama-server, 2 GB uploads) is listed in one line each with a note that it is documented
    elsewhere, so the file is not mistaken for the full v9.0 record.

#### 11. `design_draft.md` → `docs/designs/bilingual_local_transcription.md` (Create at finalization)

*   **Type / Scope**: this design document.
*   **Proposed Changes**: saved at the end of drafting; Phase 2 results are added under
    Decisions (D2 outcome, Q3 and threshold values) during Phase 3.

Files explicitly **not** changed: `app.py` (the warm-up hook and `/api/system_audit` already
call into `local_whisper_engine`), `media_processor.py`, `silence_trimmer.py`,
`speaker_diarization.py`, `transcript_translator.py`, all frontend files, `requirements.txt`
(`faster-whisper` and `huggingface_hub>=0.23.0` are already listed), `.gitignore` (`models/`
is already ignored).

### Verification Plan

*   **Unit tests**: `EASD_WHISPER_BACKEND=ctranslate2 .venv/bin/python -m pytest
    tests/test_code_switch.py tests/test_whisper_language_and_vad.py -q -p no:cacheprovider`
    must pass; then the full suite (`… pytest tests -q -p no:cacheprovider`, about 7 minutes)
    must show no new failures compared with a run before the change (the known environmental
    failures, such as the rejected Gemini test key, are listed in the v8.9 report).
*   **Static check**: `.venv/bin/python -m py_compile local_whisper_engine.py stt_pipeline.py
    ai_providers.py scripts/measure_language_id.py`.
*   **Measurement (Phase 2), pass criteria**, on a 5–10 minute marked excerpt of a real EASD
    meeting with both languages, with nothing else heavy running:
    *   Detector: the winner reaches at least 90% accuracy on `bn`/`en` stretches of 2 s or
        more, and tags at most 3% of Bangla stretches as English at the chosen threshold.
    *   G1: at least 80% of `en`-labelled stretches of 2 s or more come out with mostly Latin
        letters (share ≥ 0.7).
    *   G2: on a Bangla-only excerpt (or the Bangla stretches of the same excerpt), at least
        97% of stretches are tagged `bn`, and the switched transcript of those stretches
        matches the unswitched one except where a stretch was tagged `en`.
    *   G4: `compare` shows wall time with switching ≤ 1.15 × without, and peak RSS
        difference ≤ 0.8 GB.
    *   If any criterion fails, `EASD_CODE_SWITCH` stays `0` by default and the result is
        recorded in the design document before deciding next steps.
*   **One-time download check**: start the app with the models missing and internet on;
    confirm `models/whisper-small.en/` appears once; restart with the network unplugged and
    confirm no download attempt and that a local transcription still uses switching.
*   **Fail-soft check**: rename `models/whisper-small.en/` and run a short local
    transcription; it must succeed Bangla-only with one warning line naming the missing
    model.

--------------------------------------------------------------------------------

<!-- Provenance: Indicates initial structural drafting via EGM. -->

*Drafted with EGM*
