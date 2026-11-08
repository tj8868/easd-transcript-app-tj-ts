# src

## Overview
React 19 application source. `main.jsx` mounts `App` in `StrictMode` on `#root`; `App.jsx` holds the application state and orchestrates the backend workflow (transcribe, summarize, translate, generate DOCX, upload to Google Drive).

## Interface
- `main.jsx` - entry point (`createRoot(...).render(<App />)`)
- `App.jsx:App` (default export); module helper `buildActiveSkillPrompts(activeSkills, customSkillsList)`; constants `DEFAULT_AGENDAS`, `DEFAULT_DISCUSSIONS`
- Subdirectories:
  - [components](./components/EGM.md) - UI components
  - [utils](./utils/EGM.md) - provider/key storage and settings helpers

## Invariants
- `App` is the single owner of document state; child components mutate it only through passed setters.
- Provider/key state is initialized from and persisted through `./utils/apiKeyStorage` and `localStorage`.

## Side Effects
- `localStorage` persistence (in `App.jsx`): `theme`, `appSettings`, `customAppLogo`, `documentType`, `activeTemplateId`, `aiProvider`, `apiKey`, `baseUrl`, `transcriptionModel`, `summarizationModel`, `modelName`, `orgContext`, `activeSkills`, `customSkillsList`.
- Backend calls (`axios`, in `App.jsx`): `/api/templates`, `/api/template_members`, `/api/skills`, `/api/default_config`, `/api/settings`, `/api/transcribe_and_summarize` (3 h timeout), `/api/summarize_transcript`, `/api/translate_transcript`, `/api/generate_docx`, `/api/generate_custom_docx`, `/api/upload_gdrive`.

## Verification
- Run: `npm test` (from `frontend/`)
