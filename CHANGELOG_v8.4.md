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
