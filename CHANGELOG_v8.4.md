# v8.4 – Generate button now actually calls a model (local or cloud)

## What was wrong
The Generate button always called `/api/summarize_transcript`, which was wired
correctly on the backend — but:
1. There was **no real local model**. The "local" path was
   `deep_semantic_synthesis`, pure regex/keyword extraction with no model
   involved at all, even though it was being offered as a "local" AI option.
2. The frontend had **no way to choose** local vs cloud from the Generate
   button — it always used whatever `aiConfig.provider` happened to be, with
   no visible control, so if the saved settings pointed at an empty-key cloud
   provider, you'd silently get the offline regex fallback with no obvious
   way to know why, or to switch to something that would actually run.

## What changed

| Area | Change |
|---|---|
| `local_llm_engine.py` *(new)* | A real on-device LLM: **Qwen2.5-1.5B-Instruct** (GGUF, Q4_K_M, ~1.0GB, via `llama-cpp-python`), CPU-only by default so it runs on a phone or a weak laptop. A lighter `qwen2.5-0.5b` (~0.4GB) and `gemma-2-2b` are also selectable via `EASD_LOCAL_LLM_MODEL`. Reuses the existing `build_template_system_prompt` (which embeds the active template's JSON schema) and `process_extracted_payload`, so the local model is fed exactly the same schema-as-context prompt the cloud model gets. Model weights aren't bundled (they're gigabytes); the module auto-downloads them from Hugging Face on first use, or you can copy the `.gguf` file into `models/` manually — see the module docstring for the exact filename/URL. |
| `ai_providers.py` | `process_ai_request`'s local branch now calls `local_llm_engine.generate_template_fill()` first. Only if that raises (dependency missing, weights missing, inference error, unparseable output) does it fall back to `deep_semantic_synthesis` — and now says so explicitly in `result["warning"]`, so a fallback is always visible, never silent. |
| `Transcripts.jsx` | Added a **☁ Cloud / 📱 Local** toggle right next to the Generate button, so the choice is explicit and visible instead of buried in settings. Selecting a mode is passed through to the backend on click. |
| `App.jsx` | `local` model name updated from the old placeholder `local_synthesis` to `local_qwen2.5` to reflect that it's a real model now. |
| `requirements.txt` | Added `llama-cpp-python` and `huggingface_hub`. |
| `test_local_and_cloud_generate.py` *(new)* | Proves the Generate button's backend call reaches a real model call-site in both modes, with the schema passed as context in both, plus that a genuinely unavailable local model falls back honestly rather than silently. |

## Verification performed here
This sandbox has no internet access to Hugging Face (where the GGUF weights
live) and no live Gemini API access, so neither model could be run for real
end to end. Both call paths were proven with the actual production code
(`process_ai_request` → `summarize_text_gemini` / `local_llm_engine.generate_template_fill`)
by substituting only the outermost network/inference call:
- **Cloud**: `stt_pipeline._gemini_client()` replaced with a fake client;
  confirmed `client.models.generate_content(...)` is actually invoked, the
  JSON schema is present in the prompt sent, and the returned JSON is parsed
  into `result["summary"]` correctly.
- **Local**: `llama_cpp.Llama` replaced with a fake class; confirmed
  `create_chat_completion(...)` is actually invoked, the JSON schema is
  present in the system prompt, the transcript reaches the user prompt, and
  the returned JSON is parsed the same way as the cloud path.
- **Fallback**: with `llama_cpp` unimportable and no model file, confirmed
  the app falls back to offline extraction with an explicit warning message
  rather than pretending an LLM ran.

Run `python3 test_local_and_cloud_generate.py` to re-run these checks.

## To actually run local inference on your machine
```
pip install llama-cpp-python huggingface_hub
```
Then click **📱 Local** and hit **Generate** — on first use it downloads
Qwen2.5-1.5B-Instruct (~1.0GB) into `models/` automatically (needs internet
once), then runs fully offline after that. For a phone or very low-RAM
device, set `EASD_LOCAL_LLM_MODEL=qwen2.5-0.5b` before launching for the
~0.4GB variant.

---

# v8.4 (part 2) – Local Whisper: language misdetection & script hallucinations

**Symptom:** transcribing an English recording offline (small or medium, CPU) produced Bangla, Telugu/Kannada and Devanagari gibberish mixed in with the occasional correct English line.

## Root causes and fixes (`local_whisper_engine.py`)

| # | Cause | Fix |
|---|---|---|
| 1 | `detect_audio_language()` forced `bn` whenever Bengali reached **10%** (or **5%** with hi/ne/ur on top). That is easy to reach on noisy English audio, and the whole file was then decoded as Bangla. | New `detect_audio_language_detail()`: the top-ranked language wins. It switches to Bengali only when a confusable language (hi/ne/ur/as) is on top **and** Bengali has at least 60% of its probability. It scores only speech (Silero VAD), and logs the full probability distribution on every call. If detection fails it returns `auto` (Whisper decides) instead of guessing `bn`. |
| 2 | Language was detected once per file and forced on every 180s slice. | Detection now runs **per slice**. The whole-file result is only a prior used to pick `initial_prompt`. When the top two languages in a slice are close (code-switching), the slice is split into 30s windows. Each window is limited to the slice's top two candidates, and neighbouring windows in the same language are transcribed as one run. |
| 3 | `vad_filter=False`, so Whisper decoded silence and noise and hallucinated on it. | `vad_filter=True` with explicit `WHISPER_VAD_PARAMETERS` (threshold 0.5, min_speech 250ms, min_silence 1000ms, pad 400ms). **Validation found a real Silero failure:** after about 150s of silence plus noise, the whole-slice VAD pass dropped *all* of the speech that followed. So each slice is now cross-checked against independent 30s-block VAD, and VAD is turned off for that one slice if the whole-slice pass loses speech. On the real 64-minute meeting this cross-check flagged 0 of 22 slices. |
| 4 | The sanitizer only stripped Tibetan and CJK. | It now also strips Devanagari, Gurmukhi, Gujarati, Odia, Tamil, Telugu, Kannada and Malayalam unless the target language uses that script. Bengali is never stripped, and the danda marks shared with Bengali are kept. A segment that was mostly foreign script is dropped whole. Before the sanitizer runs, segments are also gated on Whisper's own confidence (`no_speech_prob`, `avg_logprob < -1.5`, `compression_ratio > 2.4`). |
| 5 | `select_optimal_model_name()` needed 5GB *available* RAM for medium, so an 8GB box quietly used small. The fallback paths ignored an explicitly chosen model. Asking for medium when its weights were missing downloaded **tiny**. | Medium now needs total ≥7.5GB and ≥2.5GB free; skipping it logs a warning with the numbers. New `resolve_whisper_model_choice()` honours an explicit size and only auto-selects for `auto`/empty. It is used by `ai_providers` (live chunks, Whisper fallback), `stt_pipeline` and `/api/detect_language`. The download size mapping is fixed. The model actually loaded is reported in `result["model"]` and in the log. |

Also:

- `condition_on_previous_text=False` is unchanged.
- The GPU is used automatically when CTranslate2 detects CUDA (`float16` first, then CPU). CPU-only machines are unaffected. Force a device with `EASD_WHISPER_DEVICE=cpu|cuda|auto`.

## Cross-cutting
- `diag_logging`: `bind_job_id()` stamps every log line with `[job=<id>]`. The transcribe endpoints return that id as `log_id` (an internal field, not shown in the UI). `redact_key()` makes sure log lines never contain full API keys.
- User-facing STT errors no longer include exception class names, paths or raw bodies. The detail is in `app_service.log` under the same `job=` id.
- `/api/system_audit` now includes a `local_whisper` block: requested and resolved model, weights, device, CUDA count, VAD settings and RAM.

## Tests
- New `whisper_hallucination_fixtures.py` holds reusable sanitizer samples and detector distributions.
- New `test_whisper_language_and_vad.py` (43 checks) runs the real engine code with a fake acoustic model, plus the real Silero VAD on a real recording.
- `test_anti_hallucination_whisper.py` Case 5 uses the fixtures. Its model-dependent sections now skip with a clear message when no weights or test audio are present.
- **The frontend bundle was stale.** The `frontend/dist` committed in v8.3 predated the v8.3 source; for example, it had no `local_qwen2.5` Generate toggle. `dist` has now been rebuilt from source and the four orphaned bundles removed. The Local Whisper settings text now describes the actual sizing rules instead of the old "≥16GB for medium".
