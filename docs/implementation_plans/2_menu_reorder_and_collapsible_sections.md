# Implementation Plan Version 2: Menu Reordering & Collapsible Sections

## Overview
Restructure the application layout and menu navigation:
1. **Live Recording**: Instant real-time transcription in the speaker's language as they speak.
2. **🎙️ Auto-Queue Recording & Transcription Studio**: Multi-take recording queue and 1-click batch transcription.
3. **Dual Transcripts**: Raw transcripts only (summarizer widget removed).
4. **All headings below collapsed**: Collapsible accordion cards by default.
5. **Document Preview kept visible**: Fully visible at all times.

## Changes:
- Order of menu in NavTabs and App.jsx:
  1. Live Recording (`section-live`)
  2. Auto-Queue Studio (`section-queue`)
  3. Dual Transcripts (`section-transcripts`)
  4. Media & AI Input (`section-input`) (collapsed)
  5. Templates & Directives (`section-templates`) (collapsed)
  6. Agendas & Venue (`section-meta`) (collapsed)
  7. Discussions (`section-discussions`) (collapsed)
  8. Attendance (`section-attendance`) (collapsed)
  9. Document Preview (`section-export`) (visible)
- Separate Live Recording component and Auto-Queue component.
- Remove AI Summarizer toolbar from Dual Transcripts.
- Wrap all intermediate sections in CollapsibleCard wrappers.
