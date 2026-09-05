# Implementation Plan (Version 6): Live Record & Drag-and-Drop Compliant Upload

## Version History
- **Plan 1 (Initial Core)**: [`1_initial_core_implementation.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/1_initial_core_implementation.md) - Foundational two-step AI pipeline & template engine.
- **Plan 2 (Order & Collapsible Sections)**: [`2_menu_reorder_and_collapsible_sections.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/2_menu_reorder_and_collapsible_sections.md) - Menu reordering, live transcription, auto-queue, raw transcripts, collapsible sections, visible preview.
- **Plan 3 (Responsive & Firefox Security)**: [`3_responsive_mobile_tablet_and_firefox_security.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/3_responsive_mobile_tablet_and_firefox_security.md) - Mobile/tablet responsive de-cluttering, overflow prevention, and Firefox localhost security.
- **Plan 4 (Theme & Visuals)**: [`4_deep_green_dark_mode_and_antigravity_theme.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/4_deep_green_dark_mode_and_antigravity_theme.md) - Deep green Antigravity-inspired aesthetic overhaul.
- **Plan 5 (One-Word Headings & Accessibility)**: [`5_one_word_headings_and_colorblind_accessibility.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/5_one_word_headings_and_colorblind_accessibility.md) - Simple headings & colorblind accessibility.
- **Plan 6 (Current - Live Record & Drag-and-Drop Upload)**: [`6_live_record_and_drag_drop_upload.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/6_live_record_and_drag_drop_upload.md) - Renamed Section 1 to `Live Record`, Section 2 to `Upload` (with upload sign and full drag-and-drop compliance for files + recording takes), Section 4 to `Engine`.

---

## Deliverables in Version 6

1. **`Live Record` (Section 1)**:
   - Header renamed to `Live Record` with live broadcast radio/mic sign.
   - Subtitle: `Instant speech transcription in your language as you speak`.
   - Streaming Web Speech API in Bangla, English, and Auto-Detect.

2. **`Upload` (Section 2 - Drag-and-Drop Compliant)**:
   - Header renamed to `Upload` with `UploadCloud` icon.
   - Subtitle: `Upload audio & video files (Drag & Drop) or record takes for batch AI transcription`.
   - **HTML5 Drag & Drop Compliance**:
     - `onDragOver`, `onDragEnter`, `onDragLeave`, `onDrop` events.
     - Emerald glow and dashed highlight when files are dragged over.
     - Multi-file drop support: automatically adds dropped audio/video files directly into the queue shelf.
     - Audio preview, duration, file size, download, and delete controls for each item.
     - Full compatibility with mic recording takes in the same queue.
     - 1-Click `⚡ Transcribe All` handles both uploaded files and recorded takes.

3. **`Engine` (Section 4)**:
   - Header renamed to `Engine` with `Cpu` icon to distinguish from Section 2's `Upload`.
   - Full HTML5 drag & drop compliance added to its universal document/media dropzone.
