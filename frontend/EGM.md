# frontend

## Overview
Vite + React 19 single-page client for the EASD transcription / meeting-minutes app. It talks only to the backend through relative `/api` and `/ws` paths, which the dev server proxies to `127.0.0.1:8000`.

## Interface
- [src](./src/EGM.md) - application source ([components](./src/components/EGM.md), [utils](./src/utils/EGM.md))
- `package.json` scripts: `dev`, `build`, `test`, `lint` (`oxlint`), `preview`
- `vite.config.js` - dev server on `0.0.0.0:5173` (`strictPort`), proxy `/api` -> `http://127.0.0.1:8000`, `/ws` -> `ws://127.0.0.1:8000`
- `index.html` - SPA shell; `public/` - static icons/logos
- Dependencies: `react`, `react-dom`, `axios`, `dompurify`, `lucide-react`

## Invariants
- All backend URLs are relative (`/api/...`); the backend must be reachable at the proxy target in development.
- Port 5173 is fixed (`strictPort: true`).

## Side Effects
- Dev server binds all interfaces and allows any host (`allowedHosts: true`).
- Browser `localStorage` holds settings and API keys (see [utils](./src/utils/EGM.md)).

## Verification
- Run: `npm test` (runs `test_api_button_and_vault.js`, `test_raw_transcript_speaker_time.js`, `test_audio_upload_to_transcript_flow.js`)
- Lint: `npm run lint`
