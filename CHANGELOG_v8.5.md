# v8.5 – Universal custom API provider (OpenRouter / DeepSeek / Ollama / LM Studio)

One new provider, `openai_compatible`, handles the **template-fill (Generate) step** against any OpenAI Chat-Completions-compatible endpoint. Transcription is unchanged: it still uses Gemini or Local Whisper.

## Backend
| Area | Change |
|---|---|
| `ai_providers.summarize_text_openai_compatible()` | Sends `POST {base_url}/chat/completions` with `httpx` (no `openai` package). It uses the same `build_template_system_prompt()` as the Gemini and local paths and asks for `response_format=json_object` first. On HTTP 400/415/422 it retries **once** without that field and salvages the JSON with `extract_and_repair_json()`. Output goes through `process_extracted_payload()`. The timeout is 120s (10s to connect). Failures raise `OpenAICompatibleError`, whose short `user_message` covers: bad key (401/403), wrong URL or model (404), rate limit (429), other HTTP errors, connection refused, timeout, and output that isn't JSON. |
| `process_ai_request()` | The provider whitelist now accepts `openai_compatible` (aliases: `custom`, `openai`, `openrouter`). Unknown providers log a warning before being coerced to Gemini. The custom path uses only its own key, base URL and model; **the Gemini key is never sent to a third-party endpoint, and the custom key is never sent to Gemini STT.** If the custom call fails, the app falls back to offline extraction with a plain-language `warning` plus a `(reference <job>)`. It never falls back to Gemini silently. |
| Settings | `custom_api_base_url`, `custom_api_key` and `custom_api_model` are added to `ApiSettingsPayload`, `load_api_settings_from_disk()` and `api_settings.json`. **Fix:** `POST /api/settings` now saves only the fields that were sent (`exclude_unset`). Before, activating Local Whisper also overwrote the saved Gemini key with `""`. |
| Connection test | `ping_openai_compatible()` sends `GET {base_url}/models`, which works on OpenRouter, DeepSeek, Ollama and LM Studio. It is used by `verify_ai_api_key()` (`/api/verify_key`) and `test_summarization_engine()` (`/api/test_engine`, which now accepts `base_url`), and it reports whether the Model ID is in the endpoint's model list. |
| `/api/system_audit` | New `custom_api` block: base URL, model, whether a key is present, whether it is active, reachability, HTTP status, whether the model is listed, and latency. |
| User-facing errors | These no longer include raw exception text: the `/api/summarize_transcript` fallback (it used to show `Cloud AI error ({e})`), the local-LLM fallback warning, and the 500 responses. All carry a `log_id` / `(reference <id>)` you can grep for in `app_service.log`. |

## Frontend
- `apiKeyStorage.js`: new `openai_compatible` entry in `PROVIDERS`, plus `CUSTOM_API_PRESETS`.
- `SettingsModal.jsx`: new third section with Base URL, Model ID (free text) and an optional API key.
  - Five preset chips only prefill the fields: OpenRouter, DeepSeek (direct), Ollama (local), LM Studio (local), Other / custom.
  - A Test Connection button and a **Use for Generate** button.
  - The inaccurate Gemini line was replaced with *"Cloud engine using your configured Gemini transcription and summarization models."*
- `App.jsx`:
  - When the custom provider is active, **Generate** ("☁ Cloud") sends `provider=openai_compatible`, the free-text model ID, `base_url` and the custom key.
  - The upload-and-process flow keeps the Gemini key for transcription.
  - Settings hydration restores the custom fields after a restart.
- `LiveRecordStudio.jsx`: the custom key is never used as a Gemini transcription key.
- `frontend/dist` was rebuilt from this source. The provider strings and preset URLs were checked in the built JS.

## Out of scope (as specified)
Custom STT endpoints, OpenRouter attribution headers, and streaming.
