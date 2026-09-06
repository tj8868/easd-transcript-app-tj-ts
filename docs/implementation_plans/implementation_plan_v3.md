# Implementation Plan (Branch: v3 / Version: v3)
**Status**: Active Execution & Verification  
**Target Branch**: `v3`  
**Standard**: RFC / Docs-as-Code Specification v3

---

## Branch Specification Overview
This plan governs all architectural, AI pipeline, template engine, and UI/UX changes on branch **`v3`**. In accordance with Docs-as-Code standards:
- The major specification number maps directly to the active git branch (`v3`).
- Revisions are tracked as revisions `v3.1` through `v3.9`.
- **v3.9** represents the current active revision: **Gemini 3.7 Flash Interactions API Fix, Template Schema Alignment, and Antigravity / Windows 11 Fluent Dark Mode**.

---

## Revision Changelog (Branch: v3)

| Revision | Scope & Deliverable | Status |
| :--- | :--- | :--- |
| **v3.1** | Decouple STT (Speech-to-Text) and LLM (Summarization) provider pipelines; allow independent key & model assignment. | Completed |
| **v3.2** | Settings multi-key storage & masked key vault with instant connection check (`/api/verify_ai_key`). | Completed |
| **v3.3** | Front-page top active engine indicator button with seamless 1-tap Settings modal opening. | Completed |
| **v3.4** | Official EASD Word template integration (`EASD Meeting minutes - Template.docx`) with 4-row discussions table and 21-member attendance sheet. | Completed |
| **v3.5** | Dynamic multi-document template engine supporting 5 distinct document types (Meeting Minutes, Journal, News, Blog, Bangladesh Govt Report) and custom docx upload. | Completed |
| **v3.6** | Verbatim multi-language STT transcription strictly isolated from AI summary/minutes. | Completed |
| **v3.7** | Zero sideways scrolling layout across mobile, tablet, and desktop with wrapping navigation tabs. | Completed |
| **v3.8** | Windows Unicode terminal reconfiguration (`sys.stdout.reconfigure(encoding='utf-8')`) preventing cp1252 crash on Bengali text. | In Progress |
| **v3.9** | **Current Milestone**: Full migration to **Gemini 3.7 Flash Interactions API**, elimination of deprecated `gemini-2.5-flash`, schema unwrapping preventing JSON sentence-slicing gibberish, and **Antigravity / Windows 11 Fluent Dark Mode** overhaul (obsidian `#090c12`, acrylic card `#131722`, cyan/blue glow `#38bdf8`, no green tint). | In Progress |

---

## Technical Specifications (v3 Canon)

### 1. Antigravity & Windows 11 Fluent Dark Mode
- **Palette**:
  - Background Canvas: Deep neutral obsidian (`#090c12`, `#0d1117`, `#08090d`).
  - Elevated Cards: Acrylic dark slate `rgba(18, 22, 32, 0.85)` with `backdrop-filter: blur(20px)`.
  - Borders: Crisp translucent white `rgba(240, 246, 252, 0.10)`.
  - Accent / Glow: Modern cyan/blue `#38bdf8` / `#2563eb` with glow `rgba(56, 189, 248, 0.35)`.
  - Text: Crisp primary `#f0f6fc`, secondary neutral gray `#8b949e`.
  - Scrollbars: Dark neutral track `rgba(0,0,0,0.35)`, translucent light thumb on hover.
  - Zero green/mossy tint across all components.

### 2. Gemini 3.7 Flash Integration via Interactions API
- **Model Migration**:
  - Replace all deprecated `gemini-2.5-flash`, `gemini-2.0-flash`, and `gemini-1.5-flash` calls with:
    - Primary: **`gemini-3.7-flash`** (with `generation_config={"thinking_level": "low"}` for ~8s fast response).
    - Fallbacks: **`gemini-3.5-flash-lite`** and **`gemini-3.6-flash`**.
- **SDK Method**:
  - Use `client.interactions.create(model=m, input=..., generation_config=...)`.
- **Template Prompt Alignment (`build_template_system_prompt`)**:
  - For `easd_default_minutes`, use `LLM_SYSTEM_PROMPT` directly so Gemini produces the exact required fields: `summary.discussions` (4 rows), `summary.agendas` (list of 4-5 items), and `summary.decisions`.
  - Append custom context, rules, and organizational context.
- **Payload Unwrapping (`process_extracted_payload`)**:
  - Unpack `sections_data` and `tables_data` to top-level `summary` keys so custom and default templates never lose fields.
  - Ensure `summary["discussions"]` and `summary["agendas"]` are always populated.
  - NEVER fall back to `deep_semantic_synthesis` when valid JSON is returned.

### 3. Settings & Key Persistence
- `api_settings.json`:
  - Set `"summarization_model": "gemini-3.7-flash"`.
  - Sync `"gemini_api_key"` and `"summarization_api_key"` from `GeminiAPI.txt`.
- Frontend (`apiKeyStorage.js`, `SettingsModal.jsx`, `App.jsx`, `LiveRecordStudio.jsx`, `MediaInput.jsx`):
  - Set default Gemini model to `gemini-3.7-flash`.

### 4. Windows Unicode Reconfiguration
- Add `sys.stdout.reconfigure(encoding='utf-8')` and `sys.stderr.reconfigure(encoding='utf-8')` in `app.py`.

### 5. Build & Verification
- Compile frontend with `npm run build`.
- Execute end-to-end audio test with `test_slice2.mp3` through `process_ai_request` to verify zero errors and executive-grade meeting minutes output.
