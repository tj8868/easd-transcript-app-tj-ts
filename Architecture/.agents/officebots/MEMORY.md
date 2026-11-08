# OfficeBots — App Task

Agent: officebots (app instance)
Task: single-sheet Excel app layout map of the EASD transcript app, for management approval.

Output: /home/eminence-t1/Tj-p/Transcript-App-Layout-Map.xlsx
Sheet: "App Layout Map" — 42 rows, 8 cols.
Structure: single-page React SPA, sticky navbar + collapsible sections (not separate login pages), Header bar, 3 modals (Settings, Google Drive, Device Viewer).
9 sections with real code IDs: section-live (Record & Upload), section-transcripts, section-templates, section-skills, section-meta (Agendas), section-discussions, section-attendance, section-govt-form/section-article-form, section-export (Preview).
Conditional form logic (Meeting Minutes vs Bangladesh Govt Report vs Journal/News/Blog), each module's inputs/outputs, flow arrows, matching FastAPI backend endpoints.

Source: /home/eminence-t1/Tj-p/Admin/easd-transcript-app-tj-ts-5 (the populated version).
Note: excluded legacy AutoQueueStudio.jsx — present in folder but not imported by App.jsx, so not part of the live app.

Method: scan real code → build → critique vs code → revise until exact. Re-opened and verified after save.

Status: completed and verified 2026-10-15.
