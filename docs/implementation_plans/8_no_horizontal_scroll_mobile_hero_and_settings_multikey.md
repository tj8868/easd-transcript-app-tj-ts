# Implementation Plan (Version 8): No Sideway Scroll, Screenshot-Matching Mobile Hero & Settings Multi-Key Architecture

## Version History
- **Plan 1 (Initial Core)**: [`1_initial_core_implementation.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/1_initial_core_implementation.md) - Foundational two-step AI pipeline & template engine.
- **Plan 2 (Order & Collapsible Sections)**: [`2_menu_reorder_and_collapsible_sections.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/2_menu_reorder_and_collapsible_sections.md) - Menu reordering, live transcription, auto-queue, raw transcripts, collapsible sections, visible preview.
- **Plan 3 (Responsive & Firefox Security)**: [`3_responsive_mobile_tablet_and_firefox_security.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/3_responsive_mobile_tablet_and_firefox_security.md) - Mobile/tablet responsive de-cluttering, overflow prevention, and Firefox localhost security.
- **Plan 4 (Theme & Visuals)**: [`4_deep_green_dark_mode_and_antigravity_theme.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/4_deep_green_dark_mode_and_antigravity_theme.md) - Deep green Antigravity-inspired aesthetic overhaul.
- **Plan 5 (One-Word Headings & Accessibility)**: [`5_one_word_headings_and_colorblind_accessibility.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/5_one_word_headings_and_colorblind_accessibility.md) - Simple headings & colorblind accessibility.
- **Plan 6 (Drag-and-Drop Upload)**: [`6_live_record_and_drag_drop_upload.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/6_live_record_and_drag_drop_upload.md) - Drag-and-drop compliant upload section.
- **Plan 7 (Unified Live Record & Multi-Take Studio)**: [`7_unified_live_record_and_multitake_studio.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/7_unified_live_record_and_multitake_studio.md) - Combined Live and Multi-Take in one single block with big red record button.
- **Plan 8 (Current - No Sideway Scroll, Screenshot-Matching Mobile Hero & Settings Multi-Key)**: [`8_no_horizontal_scroll_mobile_hero_and_settings_multikey.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/8_no_horizontal_scroll_mobile_hero_and_settings_multikey.md) - Zero horizontal scrolling with 2-row wrapping nav, mobile Live Transcribe hero matching the user's reference image, and multi-key API architecture configured exclusively in Settings.

---

## Deliverables in Version 8

### 1. Zero Sideway Scrolling (Fit Entire Width Nicely)
- Update `.nav-tabs` in `index.css` to `flex-wrap: wrap; justify-content: center; overflow-x: hidden; width: 100%;`.
- Automatically wrap tabs onto a second row when viewport width is constrained.
- Guarantee zero horizontal scroll on mobile, tablet, and desktop screens.

### 2. Live Transcribe Mobile Hero (Matching Provided Screenshot)
- In `LiveRecordStudio.jsx`:
  - **Title**: `Live Transcribe`
  - **Subtitle**: `Real-time audio transcription — free, fast, and no account required.`
  - **Option 1**: `Language` label on left, clean dropdown on right (`Detect...`, `বাংলা (Bengali)`, `English (US/UK)`).
  - **Option 2**: `Pro transcription` label on left, modern toggle switch on right (`[✓]`).
  - **Floating Tooltip**: `Press and start talking` with a pointer pointing to the button.
  - **Big Circular Red Record Button**: 76px circular button with glowing red aura and white microphone icon.
  - Clicking starts live speech streaming into the Live Transcribe Box and records takes.
  - Full multi-take editing, playing, deleting, and downloading.

### 3. Settings Multi-Key Architecture & Environment Variables
- **API Keys Hidden from Main View**:
  - Remove all API key inputs from `MediaInput.jsx`.
  - Main view only shows "🔐 API Keys: Configured in Settings" with a direct button to open Settings.
- **Settings Modal API Keys Tab**:
  - Add **`API Keys & Environment`** tab in `SettingsModal.jsx`.
  - Display Environment Variables detected from `.env` / system (`GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`).
  - **Multiple API Keys Manager**:
    - Each key has:
      - **Type of API as a dropdown**: `Groq`, `Google Gemini`, `OpenAI`, `Anthropic`, `Custom / Ollama`.
      - **Title / Name**: e.g., "Main Groq Key", "Gemini 2.5 Pro".
      - **Key Value**: masked with eye show/hide toggle.
      - **Active Status**: toggle/select which key is active for that provider.
      - **Delete**: remove key.
    - **`+ Add API Key`** button to add multiple keys dynamically.
    - Persisted in `localStorage` and synchronized with `aiConfig`.
