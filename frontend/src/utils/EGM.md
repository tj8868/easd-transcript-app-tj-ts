# utils

## Overview
Shared, non-UI helpers: AI provider definitions, API key / base URL storage in `localStorage`, and backend settings/engine-test calls.

## Interface
- `aiModelConstants.js:MODEL_OPTIONS_BY_PROVIDER` - STT/LLM model options for `gemini` and `local_whisper`
- `apiKeyStorage.js`: `PROVIDERS` (`gemini`, `local_whisper`, `openai_compatible`), `CUSTOM_API_PRESETS`, `QUICK_STT_MODELS`, `QUICK_LLM_MODELS`
- `apiKeyStorage.js` functions: `getSavedKeyForProvider(providerId)`, `getSavedBaseUrlForProvider(providerId)`, `saveKeyForProvider(providerId, keyVal, baseUrl)`, `getActiveApiDisplayName(aiConfig)`, `activateProvider(providerId, setAiConfig)`, `saveServerSettings(settings)`, `testAiEngine({...})`
- Module-private: `loadServerSettings`

## Invariants
- Key lookup order in `getSavedKeyForProvider`: `apiKey_<id>`, then `easd_api_keys_list` entry, then `apiKey` only when `aiProvider` equals the requested provider; returns `''` on miss or error.
- Storage helpers swallow exceptions (try/catch) and never throw.
- `activateProvider` falls back to `PROVIDERS[0]` (Gemini) for unknown ids and clears `activeCustomApiId` / `activeCustomApiName`.

## Side Effects
- Reads/writes `localStorage` keys: `apiKey_<id>`, `baseUrl_<id>`, `easd_api_keys_list`, `aiProvider`, `apiKey`, `baseUrl`, `transcriptionModel`, `summarizationModel`, `modelName`, `activeCustomApiId`, `activeCustomApiName`. API keys are stored in plaintext.
- Network: `GET`/`POST /api/settings`, `POST /api/test_engine` (sends API keys in the body).

## Verification
- Run: `npm test` (from `frontend/`)
