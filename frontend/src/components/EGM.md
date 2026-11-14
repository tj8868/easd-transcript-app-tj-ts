# components

## Overview
React function components (default exports) that make up the meeting-minutes UI: recording/upload, transcript editing, minutes form sections, template and AI-skill management, document preview, and settings.

## Interface
- Default-exported components: `Attendance`, `AiDirectivesEditor`, `AiSkillsSelector`, `ArticleReportForm`, `CircularProgressSpinner`, `CloudImportModal`, `CollapsibleCard`, `Discussions`, `DocumentPreview`, `GDriveModal`, `GovtReportForm`, `Header`, `LiveRecordStudio`, `MetaAgendas`, `NavTabs`, `ResponsiveDeviceViewer`, `SettingsModal`, `TemplateGenerator`, `Transcripts`
- Named export: `SettingsModal.jsx:ACCENT_PALETTES` (imported by `../App.jsx`)
- Module constants: `LiveRecordStudio.jsx:MAX_UPLOAD_BYTES` (2 GB), `AiSkillsSelector.jsx:PRESET_SKILLS`, `CloudImportModal.jsx:PROVIDERS`, `SettingsModal.jsx:BANGLA_FONTS` / `ENGLISH_FONTS` / `PLATFORM_TARGETS`

## Invariants
- State is owned by the parent (`App`); form components receive value/setter prop pairs, e.g. `MetaAgendas({ meta, setMeta, agendas, setAgendas })`, `Discussions({ discussions, setDiscussions, decisions, setDecisions })`, `Attendance({ attendance, setAttendance })`.
- `DocumentPreview.jsx` passes HTML through `DOMPurify.sanitize` before every `dangerouslySetInnerHTML` render.
- `LiveRecordStudio.jsx:MAX_UPLOAD_BYTES` must match the server upload limit (per the source comment).

## Side Effects
- HTTP calls to the backend via `axios` / `fetch`:
  - `LiveRecordStudio`: `/api/transcribe_take`, `/api/transcribe_progress/{jobId}`, `/api/live_transcribe_chunk`, `/api/verify_key`
  - `SettingsModal`: `/api/settings`, `/api/env_keys`, `/api/verify_key`, `/api/test_engine`, `/api/system_audit`
  - `TemplateGenerator`: `/api/save_template`, `/api/delete_template`, `/api/generalize_template`
  - `AiSkillsSelector`: `/api/save_skill`, `/api/delete_skill`
  - `CloudImportModal`: `/api/import_cloud_file`
- `LiveRecordStudio` opens the microphone with `navigator.mediaDevices.getUserMedia` and records with `MediaRecorder`.
- `LiveRecordStudio` writes `transcriptionModel`, `summarizationModel`, `modelName` to `localStorage`.

## Verification
- Run: `npm test` (from `frontend/`)
