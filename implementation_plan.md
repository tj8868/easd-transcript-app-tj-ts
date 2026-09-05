# Implementation Plan (Version 5): Simple One-Word Headings, Colorblind Accessibility & Deep-Green Theme

## Version History
- **Plan 1 (Initial Core)**: [`docs/implementation_plans/1_initial_core_implementation.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/1_initial_core_implementation.md) - Foundational two-step AI pipeline & template engine.
- **Plan 2 (Order & Collapsible Sections)**: [`docs/implementation_plans/2_menu_reorder_and_collapsible_sections.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/2_menu_reorder_and_collapsible_sections.md) - Menu reordering, live transcription, auto-queue, raw transcripts, collapsible sections, visible preview.
- **Plan 3 (Responsive & Firefox Security)**: [`docs/implementation_plans/3_responsive_mobile_tablet_and_firefox_security.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/3_responsive_mobile_tablet_and_firefox_security.md) - Mobile/tablet responsive de-cluttering, overflow prevention, and Firefox localhost security.
- **Plan 4 (Theme & Visuals)**: [`docs/implementation_plans/4_deep_green_dark_mode_and_antigravity_theme.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/4_deep_green_dark_mode_and_antigravity_theme.md) - Deep green Antigravity-inspired aesthetic overhaul.
- **Plan 5 (Current - One-Word Headings & Accessibility)**: [`docs/implementation_plans/5_one_word_headings_and_colorblind_accessibility.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/5_one_word_headings_and_colorblind_accessibility.md) - Simple one-word headings & comprehensive colorblind accessibility.

---

## User Review Required

> [!IMPORTANT]
> - **Simple One-Word Headings**: All headings and menu tabs are simplified to punchy, human-friendly single words:
>   `1. Live` → `2. Studio` → `3. Transcripts` → `4. Media` → `5. Templates` → `6. Skills` → `7. Agendas` → `8. Discussions` → `9. Attendance` → `10. Preview`.
> - **Colorblind Accessibility**:
>   - All statuses and toggles (such as Attendance Yes/No, Recording states, and Mic indicators) now use distinct shapes, icons, and text labels (`[✓ Present]`, `[✕ Absent]`, `[● REC]`, `[⏸ PAUSED]`) so information is never conveyed by color alone.
>   - Palettes are verified for protanopia, deuteranopia, and tritanopia with high-contrast luminance (WCAG AA/AAA compliant).
> - **Deep-Green Dark Mode**: The app uses a deep obsidian-emerald green dark theme (`#041411` / `#08221c`) with radiant mint/cyan accents.
> - **Firefox Security**: Defaulting to `http://localhost:8000` eliminates Firefox's "This app is risky" warning while fully preserving microphone and live transcription access via W3C Secure Context standards.

---

## Proposed Changes

### 1. One-Word Headings & Navigation (`NavTabs.jsx` & Section Headers)

#### [MODIFY] [NavTabs.jsx](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/frontend/src/components/NavTabs.jsx)
Simplify all menu items to one word with their respective icon:
1. `Live` (`#section-live`)
2. `Studio` (`#section-queue`)
3. `Transcripts` (`#section-transcripts`)
4. `Media` (`#section-input`)
5. `Templates` (`#section-templates`)
6. `Skills` (`#section-skills`)
7. `Agendas` (`#section-meta`)
8. `Discussions` (`#section-discussions`)
9. `Attendance` (`#section-attendance`)
10. `Preview` (`#section-export`)

---

### 2. Colorblind Accessibility & Deep-Green Theme (`index.css`)

#### [MODIFY] [frontend/src/index.css](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/frontend/src/index.css)
- **Deep-Green Obsidian Dark Theme**:
  - `--bg-gradient`: `radial-gradient(circle at 50% 0%, #0a2621 0%, #051814 45%, #020c0a 100%)`
  - `--bg-primary`: `#041411`
  - `--bg-secondary`: `#08221c`
  - `--bg-card`: `rgba(8, 34, 28, 0.78)`
  - `--border-color`: `rgba(45, 212, 191, 0.18)`
  - `--text-primary`: `#f2fbf7`
  - `--text-secondary`: `#93ada3`
  - `--accent-color`: `#10b981` (Radiant Emerald)
- **Colorblind-Safe Cues & Contrast**:
  - Attendance: `[✓ Yes]` with blue/cyan fill and white text; `[✕ No]` with striped dark border and cross icon.
  - Recording indicators: `● REC` (blinking dot + text), `⏸ PAUSE` (pause icon + text).
  - High-contrast focus outlines: `:focus-visible { outline: 2.5px solid #34d399; outline-offset: 2px; }`.
  - Contrast ratios > 7:1 for body copy against cards.

---

### 3. Feature Components & Order

#### [NEW] [LiveRecording.jsx](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/frontend/src/components/LiveRecording.jsx)
- **Heading**: `Live`
- Subtitle: `Instant speech transcription in your language as you speak`
- Web Speech API (`interimResults: true`) for instant live streaming.
- Language pills with icons: `Auto`, `বাংলা`, `English`.
- Mic audio meter, `Copy`, `Clear`, `Send to Bangla`, `Send to English`.

#### [NEW] [AutoQueueStudio.jsx](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/frontend/src/components/AutoQueueStudio.jsx)
- **Heading**: `Studio`
- Subtitle: `Multi-take recording studio & batch AI transcription`
- Multi-take queue shelf; stops never overwrite previous takes.
- 1-Click batch button: `⚡ Transcribe All`.

#### [MODIFY] [Transcripts.jsx](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/frontend/src/components/Transcripts.jsx)
- **Heading**: `Transcripts`
- Subtitle: `Raw editable transcripts in Bangla and English`
- Side-by-side editable textareas, copy and download (.txt) buttons.
- Summarizer widget completely removed.

#### [NEW] [CollapsibleCard.jsx](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/frontend/src/components/CollapsibleCard.jsx)
- Accordion wrapper for sections below Transcripts (`Media`, `Templates`, `Skills`, `Agendas`, `Discussions`, `Attendance`).
- One-word headings, collapsed by default with clear expand/collapse chevrons and helper summaries.

#### [MODIFY] [App.jsx](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/frontend/src/App.jsx)
- Sequence: `Live` -> `Studio` -> `Transcripts` -> Collapsible sections (`Media`, `Templates`, `Skills`, `Agendas`, `Discussions`, `Attendance`) -> `Preview` (**Kept Visible**).
- Clicking any tab in `NavTabs` auto-expands and scrolls to the section.

---

### 4. Security & Server Launch (`app.py` & `Launch_App.bat`)

#### [MODIFY] [app.py](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/app.py)
- Default to `http://localhost:8000` (W3C Secure Context).
- Zero "This app is risky" warnings in Firefox or Chrome.
- Optional `--https` flag supported for remote network deployment.

---

## Verification Plan

### Automated Tests
- Run `npm run build` in `frontend/` to confirm zero build errors or style conflicts.

### Manual Verification
1. **One-Word Headings**:
   - Verify every tab and section heading uses a simple, intuitive single word (`Live`, `Studio`, `Transcripts`, `Media`, `Templates`, `Skills`, `Agendas`, `Discussions`, `Attendance`, `Preview`).
2. **Colorblind Accessibility**:
   - Verify all status indicators and attendance toggles use distinct icons/text alongside color (`[✓ Yes]`, `[✕ No]`, `[● REC]`, `[⏸ PAUSE]`).
   - Check focus ring visibility using keyboard navigation (`Tab` key).
3. **Deep Green Theme**:
   - Verify the deep obsidian-emerald dark background looks stunning and easy on the eyes.
4. **Firefox Security**:
   - Launch on `http://localhost:8000` in Firefox and confirm zero security warnings.
5. **Mobile & Tablet Responsiveness**:
   - Test viewport widths from 360px to 1024px, confirming no horizontal overflow.
