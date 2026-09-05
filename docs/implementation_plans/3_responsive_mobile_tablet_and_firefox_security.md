# Implementation Plan Version 3: Menu Reordering, Responsive Mobile/Tablet, & Firefox Security

## Version History
- **Plan 1 (Core)**: [`1_initial_core_implementation.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/1_initial_core_implementation.md) - Two-step AI pipeline & template engine.
- **Plan 2 (Order & Collapse)**: [`2_menu_reorder_and_collapsible_sections.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/2_menu_reorder_and_collapsible_sections.md) - Live recording -> Auto-Queue -> Dual Transcripts -> Collapsed sections -> Visible preview.
- **Plan 3 (Current)**: [`3_responsive_mobile_tablet_and_firefox_security.md`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docs/implementation_plans/3_responsive_mobile_tablet_and_firefox_security.md) - Plan 2 + Mobile/Tablet de-cluttering & overflow fixes + Firefox secure localhost launch.

---

## 1. Firefox Security Fix: "This app is risky"
### Root Cause:
`app.py` previously generated a self-signed certificate on localhost and forced `https://localhost:8000`. Firefox marks all self-signed certificates with a full-screen warning: *"Potential Security Risk Ahead / SEC_ERROR_UNKNOWN_ISSUER"*, alarming users.
### Fix:
1. **W3C Secure Context Standard**: Browsers (Firefox, Chrome, Edge) treat `http://localhost` and `http://127.0.0.1` as **Potentially Trustworthy / Secure Contexts**. Microphones (`navigator.mediaDevices.getUserMedia`), Web Speech API, and WebSockets function securely on `http://localhost` without triggering browser certificate warnings.
2. **Server Launch Configuration**:
   - Default to `http://localhost:8000` for seamless, instant, warning-free loading in Firefox, Chrome, and Edge.
   - Support `ENABLE_HTTPS=true` or `--https` argument when HTTPS is specifically required (e.g. accessing over remote local network / LAN).
   - Generate Subject Alternative Names (SAN) for `localhost`, `127.0.0.1`, and machine hostname when HTTPS is explicitly enabled.
   - Dynamic WebSocket URL detection: `window.location.protocol === 'https:' ? 'wss:' : 'ws:'`.

---

## 2. Mobile & Tablet Responsive Design & De-Cluttering
### Objectives:
- Zero horizontal overflow (`overflow-x: hidden` enforced on page).
- Drastically reduced clutter on mobile/tablet viewports (< 1024px and < 640px).
- Clean touch targets, responsive card padding, and horizontal scroll wrappers for tables.

### Key Enhancements:
1. **Header**:
   - Logo and title gracefully scale down on mobile screens.
   - Action buttons (Dark Mode, Settings, GDrive Sync) wrap or switch to compact icon+short-label badges on mobile.
2. **Sticky Navigation Tabs (`NavTabs`)**:
   - Touch-scrollable horizontally with custom hidden scrollbars.
   - Compact button sizing for mobile without truncating labels awkwardly.
3. **Collapsible Sections Below Dual Transcripts**:
   - Sections 4–9 collapsed by default, drastically saving mobile vertical space.
   - When collapsed, display a sleek summary bar with expand toggle.
   - Clicking a nav tab auto-expands and scrolls smoothly to the target section.
4. **Card Padding & Spacing**:
   - Desktop: `padding: 28px;`
   - Tablet (≤ 1024px): `padding: 20px 18px;`
   - Mobile (≤ 640px): `padding: 16px 12px;`
5. **Document Preview Paper**:
   - Wrap `.paper-table` in `.table-responsive` with smooth horizontal touch-scrolling.
   - Reduce paper preview margins and padding on mobile (`padding: 16px 12px;`) so it fits phone screens without stretching.
6. **Grids & Layouts**:
   - `grid-2col` automatically collapses to 1 column below 850px.
   - Attendance cards and Auto-Queue takes adapt to 1 column on narrow devices (< 640px).
   - Audio controls wrap properly and don't push container boundaries.

---

## 3. Order of Menu & Features
1. **Live Recording**:
   - Dedicated component showing real-time streaming speech in speaker's language instantly as they speak.
   - Web Speech API with `interimResults: true`.
   - Real-time language identification badge (`🇧🇩 বাংলা` / `🇬🇧 English`).
   - Sound meter, copy, clear, and send to transcripts buttons.
2. **🎙️ Auto-Queue Recording & Transcription Studio**:
   - Dedicated multi-take audio recording queue.
   - Take playback, duration tracker, take deletion, and 1-click batch transcription to document minutes.
3. **Dual Transcripts**:
   - Raw transcripts only (Bangla & English side-by-side textareas).
   - Summarizer toolbar removed from this card.
   - Download .txt and Copy buttons.
4. **Collapsible Headings Below**:
   - 4. Media & AI Input (Collapsed)
   - 5. Templates & Directives (Collapsed)
   - 6. AI Skills & Directives (Collapsed)
   - 7. Agendas & Venue (Collapsed)
   - 8. 4-Topic Discussions (Collapsed)
   - 9. Attendance (21 Members) (Collapsed)
5. **Document Preview & Export**:
   - Kept **open and visible** at the bottom.
