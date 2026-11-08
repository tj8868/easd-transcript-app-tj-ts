# static

## Overview
Hand-written single-page frontend served by `../app.py` via `StaticFiles(directory=STATIC_DIR, html=True)` at `/`. Legacy/standalone module; not used by the main app.

## Interface
- `index.html` - page markup.
- `app.js` - UI controller: hardware status/engine sync, live mic recording with chunk upload, batch drag-and-drop with status polling, custom API configuration/test, and TXT/SRT/VTT exports.
- `styles.css` - styling.
- Backend calls (`app.js` `fetch`): `GET /api/status`, `POST /api/settings`, `POST /api/live/start|chunk|stop`, `POST /api/batch/upload`, `GET /api/batch/status/{jobId}`, `GET|POST /api/custom_api`, `POST /api/custom_api/test`.

## Invariants
- Relative URLs only; must be served from the same origin as `app.py`.

## Side Effects
- Browser microphone capture; HTTP requests to the backend; client-side file downloads.

## Verification
- No automated tests. Manual: open `http://127.0.0.1:8085/` with `app.py` running.
