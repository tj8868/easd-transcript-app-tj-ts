# Implementation Plan (Branch: v2 / Version: v2)
**Status**: Active Development & Verification  
**Target Branch**: `v2`  
**Standard**: RFC / Docs-as-Code Specification v2

---

## Branch Specification Overview
This plan governs all architectural and UI/UX changes on branch **`v2`**. In accordance with modern *Docs-as-Code* standards, the major specification number maps directly to the active git branch (`v2`), with internal iterations tracked as revisions (`v2.0` through `v2.8`).

---

## Revision Changelog (Branch: v2)

| Revision | Scope & Deliverable | Status |
| :--- | :--- | :--- |
| **v2.1** | Menu re-ordering (Live Recording -> Transcription Studio -> Raw Dual Transcripts). All subordinate sections collapsed with persistent preview. | Completed |
| **v2.2** | Responsive layout across Mobile/Tablet with zero horizontal scroll; Firefox security & loopback exception resolution. | Completed |
| **v2.3** | Deep green Antigravity dark mode (`#071913`, `#0d271f`, `#10b981`) with emerald glowing accents. | Completed |
| **v2.4** | Human-friendly one-word headings (`Live`, `Queue`, `Transcripts`, `Generate`, `Preview`) and WCAG AAA colorblind contrast. | Completed |
| **v2.5** | Drag-and-drop compliant file upload shelf with visual dropzone and progress tracking. | Completed |
| **v2.6** | Unified Live Record and Multi-Take studio with 76px circular red record button and take management shelf. | Completed |
| **v2.7** | Zero sideways scrolling (2-row wrapping nav tabs) and mobile-optimized front hero matching user specification. | Completed |
| **v2.8** | Settings-exclusive API Key Vault with Provider dropdown, multi-key storage, masked fields, live testing, and `.env` detection. | Completed |
| **v2.9** | Separate transcript from Template Preview (no raw transcripts appended to preview); fixed API key addition & verification with general options (Google, Anthropic, OpenAI, Custom). | Completed |
| **v2.10** | Effortless Copy-Paste API Key Setup: Single-paste hero card at top of Settings, 1-tap provider selector pills, direct clipboard paste integration, editable key vault, and auto-provider detection. | Completed |
| **v2.11** | Reimplemented Streamlined API Architecture: Front-Page Top API Button displaying active engine name (zero key leakage), Custom Named API option with persistent saving & testing, and Google Gemini set as default system-wide engine. | Completed |

---

## Technical Specifications (v2 Canon)

### 1. Viewport & Responsive Layout Rules
- **Zero Horizontal Scrolling**: Under no circumstance should any screen size (Phone, Tablet, Desktop) produce horizontal overflow.
- **Header Navigation**: Tabs wrap onto a clean second row using `flex-wrap: wrap; justify-content: center;` whenever viewport width is constrained.
- **Containment**: All cards, textareas, and tables are strictly bound to `max-width: 100%; box-sizing: border-box;`.

### 2. Front Screen Architecture (Phone, Tablet, Desktop)
- **Phone Front Screen**:
  - Hero card: *"Live Transcribe — Real-time audio transcription — free, fast, and no account required."*
  - Exactly 2 options above the record button:
    1. **Language Selector** dropdown (`Auto-Detect`, `বাংলা (Bengali)`, `English`).
    2. **Pro Transcription** toggle switch (`[✓]`).
  - Floating speech-bubble tooltip: *"Press and start talking"* with downward pointer.
  - Centered 76px red circular button with microphone icon.
- **Desktop Front Studio**:
  - High-density layout featuring waveform visualizer, multi-take recording shelf, and live dual-language transcription feed.
  - Instant take management (inline rename, notes, audio playback, take deletion, and `⚡ Transcribe All Takes`).
- **Tablet Hybrid**:
  - Adaptive touch targets (minimum 48px), stacked cards in portrait mode, side-by-side split in landscape mode.

### 3. Security & Multi-Key API Vault
- **No Raw Keys in Main UI**: Removed all API key inputs from main recording screens (`MediaInput.jsx`).
- **Settings-Exclusive Vault**:
  - Dedicated `API Keys & Environment` tab in `SettingsModal.jsx`.
  - **System `.env` Detection**: Backend endpoint `/api/env_keys` verifies status of `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, and `ANTHROPIC_API_KEY`.
  - **Provider Dropdown**: Select between `Groq Cloud`, `Google Gemini`, `OpenAI`, `Anthropic`, and `Custom / Local Ollama`.
  - **Multi-Key Features**: Custom label, password-masked field with eye toggle, active radio selector, connection verification (`/api/verify_api_key`), and deletion.

### 4. Build & Production Verification
- Built with Vite + React: `npm run build` exits with code 0.
- Fast, secure client bundle with zero linting or bundle exceptions.

### 5. Streamlined API Architecture & Front-Page Integration (v2.11)
- **Front Page Top API Button**:
  - Prominently integrated into `Header.jsx` (`id="topApiButton"`).
  - Displays **only** the active API name (e.g. `⚡ Gemini API` or user's custom API name such as `⚡ Office Ollama`), strictly preventing raw API key or code leakage.
  - Features an active green status indicator dot (`●`).
  - One-click trigger opens the API settings configuration modal.
- **Default AI Provider**:
  - Google Gemini API (`gemini-2.5-flash`) is established as default provider system-wide (`App.jsx`, `apiKeyStorage.js`, `app.py`, `ai_providers.py`).
- **Custom API Engine with Custom Naming**:
  - Dedicated interface to create, name, configure, test, and save custom endpoints (Ollama, LM Studio, vLLM, DeepSeek).
  - User can assign a custom human-readable name to the API (e.g. `Office Ollama`), which automatically reflects on the front-page button upon activation.
  - Saved Custom APIs Vault allows 1-click activation, verification, editing, and deletion.
