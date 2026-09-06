# Implementation Plan (Version 9): Gemini 3.7 Flash Interactions API Fix, Template Schema Alignment & Antigravity/Windows 11 Fluent Dark Mode

## Version History
- **Plan 1 (Initial Core)**: [`1_initial_core_implementation.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/1_initial_core_implementation.md) - Foundational two-step AI pipeline & template engine.
- **Plan 2 (Order & Collapsible Sections)**: [`2_menu_reorder_and_collapsible_sections.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/2_menu_reorder_and_collapsible_sections.md) - Menu reordering, live transcription, auto-queue, raw transcripts, collapsible sections, visible preview.
- **Plan 3 (Responsive & Firefox Security)**: [`3_responsive_mobile_tablet_and_firefox_security.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/3_responsive_mobile_tablet_and_firefox_security.md) - Mobile/tablet responsive de-cluttering, overflow prevention, and Firefox localhost security.
- **Plan 4 (Theme & Visuals)**: [`4_deep_green_dark_mode_and_antigravity_theme.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/4_deep_green_dark_mode_and_antigravity_theme.md) - Deep green Antigravity-inspired aesthetic overhaul.
- **Plan 5 (One-Word Headings & Accessibility)**: [`5_one_word_headings_and_colorblind_accessibility.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/5_one_word_headings_and_colorblind_accessibility.md) - Simple headings & colorblind accessibility.
- **Plan 6 (Drag-and-Drop Upload)**: [`6_live_record_and_drag_drop_upload.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/6_live_record_and_drag_drop_upload.md) - Drag-and-drop compliant upload section.
- **Plan 7 (Unified Live Record & Multi-Take Studio)**: [`7_unified_live_record_and_multitake_studio.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/7_unified_live_record_and_multitake_studio.md) - Combined Live and Multi-Take in one single block with big red record button.
- **Plan 8 (No Sideway Scroll, Mobile Hero & Settings Multi-Key)**: [`8_no_horizontal_scroll_mobile_hero_and_settings_multikey.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/8_no_horizontal_scroll_mobile_hero_and_settings_multikey.md) - Zero horizontal scrolling, mobile hero, and multi-key API architecture.
- **Plan 9 (Current - Gemini 3.7 Flash Interactions API, Template Schema Alignment & Antigravity/Windows 11 Dark Mode)**: [`9_gemini_interactions_fix_and_antigravity_windows_dark_mode.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/9_gemini_interactions_fix_and_antigravity_windows_dark_mode.md) - Migration to Gemini 3.7 Flash via Interactions API, schema unwrapping to eliminate sentence-chopping gibberish, and complete visual overhaul to Antigravity / Windows 11 Fluent Dark mode.

---

## Deliverables in Version 9

### 1. Antigravity & Windows 11 Fluent Dark Mode (Clean, Deep Obsidian/Slate)
- **Problem**: The previous dark theme had an excessive swamp/pine green tint (`#04140f`, `#020805`, green borders, sage text) instead of a true neutral dark aesthetic.
- **Solution in `index.css`**:
  - Replace greenish tokens with authentic **Antigravity / Windows 11 Fluent Dark**:
    - `--bg-gradient`: `radial-gradient(circle at 50% -10%, #161b26 0%, #0d1117 55%, #08090d 100%)`
    - `--bg-primary`: `#090c12` (deep obsidian dark)
    - `--bg-secondary`: `#131722` (acrylic elevated surface)
    - `--bg-card`: `rgba(18, 22, 32, 0.85)` with `backdrop-filter: blur(20px)`
    - `--bg-card-hover`: `rgba(24, 29, 42, 0.95)`
    - `--border-color`: `rgba(240, 246, 252, 0.1)` (crisp, subtle light border)
    - `--border-glow`: `rgba(56, 189, 248, 0.35)` (modern fluent cyan/blue glow)
    - `--text-primary`: `#f0f6fc` (crisp white)
    - `--text-secondary`: `#8b949e` (neutral slate gray, high legibility)
    - `--accent-gradient`: `linear-gradient(135deg, #0284c7 0%, #2563eb 50%, #4f46e5 100%)`
    - `--accent-blue-gradient`: `linear-gradient(135deg, #0284c7 0%, #2563eb 100%)`
    - `--accent-color`: `#38bdf8`
    - `--accent-hover`: `#0ea5e9`
    - `--accent-border`: `rgba(56, 189, 248, 0.35)`
    - `--accent-glow`: `rgba(56, 189, 248, 0.25)`
    - `--card-shadow`: `0 20px 40px -15px rgba(0, 0, 0, 0.9), 0 0 1px 1px rgba(255, 255, 255, 0.08)`
  - Neutral dark scrollbars: dark track with translucent light thumb on hover.

### 2. Gemini 3.7 Flash Integration via Interactions API
- **Model Migration**:
  - Replace all deprecated `gemini-2.5-flash` / `gemini-2.0-flash` calls with current models:
    - Primary: **`gemini-3.7-flash`** (with `generation_config={"thinking_level": "low"}` for fast ~8s responses).
    - Fallback: **`gemini-3.5-flash-lite`** and **`gemini-3.6-flash`**.
- **SDK Call Pattern**:
  - Use `client.interactions.create()` for all text, multimodal vision/OCR, and audio operations.
- **Fix Template Prompt Construction (`build_template_system_prompt`)**:
  - For `easd_default_minutes`, use `LLM_SYSTEM_PROMPT` directly so Gemini returns the exact 4-row discussions table (`summary.discussions`), agendas (`summary.agendas`), and decisions (`summary.decisions`).
- **Fix Payload Unwrapping (`process_extracted_payload`)**:
  - Automatically unwrap `sections_data` and `tables_data` to root keys if present so extraction never fails.
  - Eliminate the fallback that sliced raw JSON strings into the discussion table.

### 3. Settings & Key Persistence
- In `api_settings.json`:
  - Set `"summarization_model": "gemini-3.7-flash"`.
  - Sync `"gemini_api_key"` and `"summarization_api_key"` from `GeminiAPI.txt`.
- In `frontend/src/utils/apiKeyStorage.js`, `SettingsModal.jsx`, `App.jsx`, `LiveRecordStudio.jsx`, and `MediaInput.jsx`:
  - Default model options to `gemini-3.7-flash` and `gemini-3.5-flash-lite`.

### 4. Windows Unicode Reconfiguration
- Add `sys.stdout.reconfigure(encoding='utf-8')` and `sys.stderr.reconfigure(encoding='utf-8')` in `app.py` to prevent `UnicodeEncodeError` on Bengali text in Windows terminal.

### 5. Frontend Production Rebuild
- Run `npm run build` to compile the updated dark theme and model configurations into `frontend/dist/`.
