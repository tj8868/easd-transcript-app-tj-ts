# Implementation Plan: High-Performance, Secure Cross-Platform EASD Meeting Minutes App

Rebuild the application using established modern UI libraries (**Vite + React 18 + TailwindCSS + Lucide Icons + DOMPurify**), a robust **Security Architecture** (Input Sanitization, Strict CSP Headers, Pydantic Schema Validation, File Upload Hardening, Safe OAuth Token Proxying), and **Ultra-Fast Performance Optimizations** (In-Memory DOCX Generation, Asynchronous Uploads, Client-Side Caching, Zero UI Re-render Lag).

---

## 🧠 Two-Step AI Transcription Pipeline (Core Feature)

The AI transcription operates in **two distinct phases**. This ensures the output `.docx` exactly mirrors the original template structure — including the fixed 4 discussion rows.

### Step 1: Template Layout Understanding (AI Learns Where to Put What)

Before processing any transcript, the AI is given a **structural map of the template** so it knows exactly which fields exist and where each piece of information belongs.

**Template Structure Map** (extracted from `EASD Meeting minutes - Template-DDMonthYY.docx`):

| Template Slot               | Location               | Expected Content                                                  |
|-----------------------------|------------------------|-------------------------------------------------------------------|
| **Title**                   | Paragraph [3]          | Formal meeting title (e.g. "Weekly Strategic, Programmatic...")   |
| **Location**                | Paragraph [4]          | Venue (e.g. "Eminence, Mohakhali, DOHS" or "Online (Zoom)")      |
| **Date and Time**           | Paragraph [7]          | `Date: DD Month, YYYY` + `Time: HH:MM AM - HH:MM PM`            |
| **Meeting Agenda**          | Paragraph [9-11]       | 4-5 concise agenda bullet points                                  |
| **Table 0 - Discussions**   | Table[0], 5 rows total | Header + **exactly 4 data rows** (see below)                     |
| **Meeting Decisions**       | Paragraph [18]         | Formal decisions summary (mirrors Table 0 Row 4)                  |
| **Table 1 - Attendance**    | Table[1], 22 rows      | Header + 21 fixed members, **all default to "Yes" (present)**     |

**Table 0 - Fixed 4 Discussion Rows (NEVER add/remove rows):**

| Row | SN | Discussion Point                | What Goes Here                                                               |
|-----|----|---------------------------------|------------------------------------------------------------------------------|
| 1   | 1  | Followup from previous meeting  | Status of prior action items, pending issues, resolution updates             |
| 2   | 2  | Action items                    | Concrete action directives issued this session with named owners             |
| 3   | 3  | Task Assignments                | Named task allocations with delivery timelines per team lead                 |
| 4   | 4  | Meeting Decisions               | Formally approved strategic decisions, locked deadlines, next review date    |

> [!IMPORTANT]
> Table 0 **must always remain exactly 4 data rows** with these exact topic names. The AI prompt and `document_engine.py` both enforce this constraint. No additional rows are added even if the transcript contains more topics - all content is consolidated into the 4 fixed categories.

**Implementation**: The `LLM_SYSTEM_PROMPT` in `ai_providers.py` will include the full template map above, instructing the AI to classify every piece of extracted information into the correct slot. The prompt explicitly names the 4 fixed discussion topics and tells the AI not to create extra rows.

---

### Step 2: Transcript Extraction -> Structured JSON -> `.docx` Output

Once the AI understands the template layout, it processes the input (audio/video/text) through a **3-stage extraction pipeline**:

```
INPUT                        AI EXTRACTION                    DOCX OUTPUT
                                                              
Audio / Video ------------>  1. Speech-to-Text (STT)                                    
(Gemini/Groq multimodal)        (Whisper / Gemini)                                      
                                                              Template-preserving
                             2. LLM Structuring               .docx with:
Text / .txt --------------->    Classify content into ------> - Title, Location
(paste / upload)                template slots:               - Date and Time
                                - Title, Date, Time           - Agendas
                                - Agendas                     - 4 Discussion rows
                                - 4 Discussion rows           - Decisions
                                - Decisions                   - 21-member sheet
                                - Attendance                  - Transcripts
                                - Bangla + English                                       
                                  transcripts                                            
```

**Stage 2a - Speech-to-Text (if audio/video input)**:
- **Gemini provider**: Sends raw binary (base64) directly to Gemini 2.5 Flash for native multimodal transcription - no intermediate Whisper step needed.
- **Groq provider**: Routes audio through Groq Whisper (`whisper-large-v3-turbo`) for fast STT, then passes text to LLM.
- **OpenAI provider**: Text-only input processed through GPT-4o / compatible models.

**Stage 2b - LLM Structuring (the core intelligence)**:
The raw transcript (from STT or direct text) is sent to the LLM with the template-aware system prompt from Step 1. The LLM returns a structured JSON:

```json
{
  "bangla_transcript": "Bengali formal meeting record...",
  "english_transcript": "Formal English meeting record...",
  "summary": {
    "title": "Weekly Strategic, Programmatic and Presentation Review Meeting",
    "location": "Eminence, Mohakhali, DOHS",
    "date": "29 August, 2026",
    "time": "11:00 AM - 01:00 PM",
    "agendas": ["Agenda 1", "Agenda 2", "Agenda 3", "Agenda 4"],
    "discussions": [
      {"sn": "1", "topic": "Followup from previous meeting", "details": "..."},
      {"sn": "2", "topic": "Action items", "details": "..."},
      {"sn": "3", "topic": "Task Assignments", "details": "..."},
      {"sn": "4", "topic": "Meeting Decisions", "details": "..."}
    ],
    "decisions": "Formal decisions summary...",
    "present_members": ["Name1", "Name2"]
  }
}
```

**Stage 2c - `.docx` Generation** (`document_engine.py`):
- Opens the template `.docx` in-memory via `io.BytesIO`
- Fills each paragraph/table cell from the JSON, preserving all original formatting (fonts, borders, margins)
- Table 0: Enforces exactly 5 rows (1 header + 4 data) - trims excess or clones template rows if needed
- Table 1: Maps `present_members` against the fixed 21-member roster using fuzzy name matching
- Appends Bangla + English transcripts as new pages at the end
- **Output filename**: `EASD-Meeting Minutes-DDMonthYY.docx` (e.g., `EASD-Meeting Minutes-30August26.docx`), derived from the extracted meeting date
- Returns the completed `.docx` as a binary stream

---

## New Features (Update)

### Feature A: Separate Copy Buttons for Bangla and English Transcripts

**Current**: A single "Copy Both" button that combines both transcripts into one clipboard payload.

**Change**: Replace with **3 separate buttons** in the Transcripts section:

| Button | Action | Clipboard Content |
|--------|--------|--------------------|
| **Copy Bangla** | Copies Bangla transcript only | `banglaTranscript` |
| **Copy English** | Copies English transcript only | `englishTranscript` |
| **Copy Both** | Copies both with headers (existing behavior) | Both with `=== BANGLA ===` / `=== ENGLISH ===` separators |

**Files affected**: [`Transcripts.jsx`](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/Transcription%20APP/frontend/src/components/Transcripts.jsx)

---

### Feature B: Live Transcription (Gemini Live API)

A **separate, independent feature** that records audio from the user's microphone in real-time and streams it to Gemini's Live API for instant transcription.

**How it works**:
1. User clicks **"Start Live Transcription"** button in a new `LiveTranscription.jsx` component
2. Browser captures microphone audio via `MediaRecorder` API (WebM/Opus format)
3. Audio chunks are streamed to a new backend WebSocket endpoint `/ws/live_transcribe`
4. Backend relays audio to **Gemini Live API** (`gemini-2.5-flash` with audio input mode) via WebSocket
5. Gemini returns real-time transcription text
6. Text is appended live to a scrolling transcript panel in the UI
7. User clicks **"Stop"** to end the session; the full transcript is populated into the Bangla or English transcript field

**Language Handling**:
- Auto-detect language from the audio stream (Gemini natively handles Bangla and English)
- If detection is ambiguous, **default to Bangla** (primary meeting language)
- User can override with a language toggle: `Auto-Detect` / `Bangla` / `English`
- The live transcript output is placed into the matching transcript field (Bangla or English)

**UI Design**:
```
┌─────────────────────────────────────────────────────────┐
│  🎙️ Live Transcription (Gemini)                        │
│                                                         │
│  Language: [Auto-Detect ▾]   Status: ● Recording...     │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ (Live transcript text appears here in real-time...) │ │
│  │ আজকের সভায় আমরা আলোচনা করব...                     │ │
│  │ We will discuss the NCD framework today...          │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
│  [🎙️ Start Recording]  [⏹️ Stop]  [📋 Send to Bangla]  │
│                         [📋 Send to English]             │
└─────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> Live Transcription is a **separate feature** from the file-upload transcription pipeline. It uses **Gemini Live API only** (not Groq Whisper or OpenAI). The user's configured Gemini API key is required.

**Files affected**:
- `[NEW]` `frontend/src/components/LiveTranscription.jsx` - New React component
- `[MODIFY]` `app.py` - New WebSocket endpoint `/ws/live_transcribe`
- `[MODIFY]` `App.jsx` - Add LiveTranscription to the layout
- `[MODIFY]` `NavTabs.jsx` - Add new tab for Live Transcription

---

### Feature C: Language Auto-Detection

Applies to **both** live transcription and file-upload transcription:

| Input Method | Detection Strategy | Fallback |
|---|---|---|
| **Live Transcription** | Gemini Live API detects language natively from audio | Assume Bangla |
| **File Upload (Gemini)** | Gemini multimodal detects from audio/video content | Assume Bangla |
| **File Upload (Groq)** | Whisper `language` param set to auto; response includes detected language | Assume English |
| **Text Paste** | AI LLM detects from text script/characters | Assume Bangla if Bengali script detected |

The detected language is returned in the AI response JSON so the frontend can place the transcript in the correct field.

---

### Feature D: Separate Transcription Model vs Summarization Model

**Current**: A single model selection is used for both transcription (STT) and summarization (LLM structuring). This is limiting because the best STT model is not always the best summarizer.

**Change**: Split into **two independent model selectors**:

| Setting | Purpose | Default | Options |
|---------|---------|---------|--------|
| **Transcription Model** | Speech-to-Text from audio/video | `gemini-2.5-flash` (Gemini) or `whisper-large-v3-turbo` (Groq) | Gemini 2.5 Flash, Groq Whisper, OpenAI Whisper |
| **Summarization Model** | Structuring raw transcript into template JSON | `openai/gpt-oss-120b` (Groq) or `gemini-2.5-flash` (Gemini) | Groq GPT-OSS-120B, Gemini 2.5 Flash, GPT-4o, Claude 3.5 Sonnet, Local Synthesizer |

**UI Change** in `MediaInput.jsx` AI Config card:
```
AI Provider:        [Gemini ▾]
API Key:            [AIzaSy... 🔑]

Transcription Model (STT):   [gemini-2.5-flash ▾]
Summarization Model (LLM):   [openai/gpt-oss-120b ▾]
```

**Backend Change**: The `/api/transcribe_and_summarize` endpoint will accept two separate model fields:
- `transcription_model` - used for STT stage only
- `summarization_model` - used for LLM structuring stage only

**Files affected**:
- `[MODIFY]` `MediaInput.jsx` - Split model selector into two dropdowns
- `[MODIFY]` `App.jsx` - `aiConfig` state adds `transcriptionModel` and `summarizationModel` fields
- `[MODIFY]` `app.py` - Endpoint accepts separate model params
- `[MODIFY]` `ai_providers.py` - `process_ai_request()` routes transcription and summarization to different models

---

## High-Performance and Speed Architecture

1. **Sub-50ms Document Generation**:
   - `document_engine.py` processes template XML in-memory using fast element tree manipulation and `io.BytesIO` streams, generating filled `.docx` documents in under 50ms.
2. **Instant UI Response (Zero Lag)**:
   - React 18 state management with memoized components (`useMemo`, `useCallback`) ensuring instant feedback on typing, agenda additions, and attendance toggles (0ms render latency).
3. **Optimized AI Processing and Multimodal Chunking**:
   - Uses high-speed REST connections with `httpx` connection pooling and direct binary payload uploads to Gemini 2.5 Flash / Groq / OpenAI endpoints.
4. **Instant Build and Small Asset Footprint**:
   - Vite 5 bundling with code-splitting, Tree-Shaking, and Gzip/Brotli asset compression for instant page load times (under 200ms initial load).

---

## Full Security Architecture Specification

### 1. XSS Defense and Input Sanitization
- **No Hand-Written Vanilla HTML Concatenation**: Replaces raw string concatenation with React JSX virtual DOM rendering.
- **Sanitizing Dynamic Preview**: Uses `DOMPurify` to clean formatted text before rendering HTML previews, guaranteeing zero XSS vulnerability.

### 2. Backend API Security and Hardening (FastAPI)
- **Content-Security-Policy (CSP)** and Security Headers:
  - `Content-Security-Policy`: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:;`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
- **File Upload Security and Path Traversal Prevention**:
  - Validates file MIME types (`audio/*`, `video/*`, `text/plain`, `.docx`).
  - Implements file size caps (max 250MB).
  - Uses `uuid4` for temporary file storage and sanitizes filenames via `os.path.basename` to prevent Path Traversal attacks (`../../`).
- **API Key and Secret Isolation**:
  - API keys for Gemini, OpenAI, Anthropic, and Custom APIs are passed in secure HTTP headers per request.
  - API keys are never logged in console logs or saved unencrypted on the server disk.

### 3. Google Drive OAuth Security
- OAuth access tokens are passed dynamically via Bearer Authorization headers and discarded immediately after upload.
- Uploads are scoped strictly to the `EASD - meeting minutes` folder.

---

## UI Library and Technology Stack

- **Frontend Framework**: Vite + React 18
- **Styling and Layout**: TailwindCSS + PostCSS (Responsive grid, container queries, mobile touch controls, dark/light theme tokens)
- **Icon Library**: `lucide-react` (Established SVG icon package)
- **Sanitizer Library**: `DOMPurify`
- **HTTP Client**: `axios`
- **Backend Framework**: Python FastAPI + Pydantic v2 + `python-docx` + `httpx`
- **Packaging**: PyInstaller (Windows `.exe`) and Capacitor / TWA (Android `.apk`)

---

## Proposed File Structure (Updated)

```
Transcription APP/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.jsx             # Secure Header and Theme Toggle
│   │   │   ├── NavTabs.jsx            # 8 Responsive Tabs (added Live Transcription tab)
│   │   │   ├── MediaInput.jsx         # Upload, Media Player, and Split Model Selectors
│   │   │   ├── AiConfig.jsx           # Provider and API Key Security Card
│   │   │   ├── OrgSkills.jsx          # Organization Context and Custom Skills
│   │   │   ├── LiveTranscription.jsx  # [NEW] Real-time Gemini Live Transcription
│   │   │   ├── Transcripts.jsx        # Bangla/English Dual Transcripts + Separate Copy Buttons
│   │   │   ├── MetaAgendas.jsx        # Meeting Info and Agendas List
│   │   │   ├── Discussions.jsx        # Discussion Points Table and Decisions
│   │   │   ├── Attendance.jsx         # 21-Member Interactive Checklist (all default Yes)
│   │   │   ├── DocumentPreview.jsx    # DOMPurify Sanitized HTML Document View
│   │   │   └── GDriveModal.jsx        # Google Drive Secure Sync Modal
│   │   ├── App.jsx                    # Main Layout, State, and Split Model Config
│   │   ├── main.jsx                   # React Entrypoint
│   │   └── index.css                  # Design System Tokens
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── app.py                      # FastAPI Server + WebSocket /ws/live_transcribe
├── document_engine.py          # Template Preservation DOCX Engine
├── ai_providers.py             # Multi-Provider AI (Split Transcription/Summarization)
├── gdrive_service.py           # Google Drive OAuth Upload Service
├── build_windows_exe.py        # Windows Standalone Build Script
└── build_android_apk.py        # Android APK Package Generator Script
```

---

## API Endpoints and Data Flow (Updated)

| Endpoint                          | Method    | Purpose                                              |
|-----------------------------------|-----------|------------------------------------------------------|
| `/api/transcribe_and_summarize`   | POST      | Upload media/text, uses **transcription_model** for STT + **summarization_model** for structuring |
| `/api/summarize_transcript`       | POST      | Re-summarize edited transcript using **summarization_model** only |
| `/api/generate_docx`             | POST      | Takes structured JSON, generates `.docx` from template |
| `/api/upload_gdrive`             | POST      | Upload generated `.docx` to Google Drive |
| `/api/template_members`          | GET       | Returns the 21-member attendance roster |
| `/api/verify_key`                | POST      | Validates API key against provider endpoint |
| `/api/default_config`            | GET       | Returns auto-detected key/provider from disk |
| `/ws/live_transcribe`            | WebSocket | **[NEW]** Streams mic audio to Gemini Live API, returns real-time transcription text |

---

## Verification and Performance Benchmark Plan (Updated)

1. **Speed and Latency Benchmark**:
   - Test `.docx` document generation latency (target: under 50ms).
   - Test React UI interaction frame rate (60 FPS, 0ms input lag).
2. **Template Fidelity Test**:
   - Verify generated `.docx` has **exactly 5 rows in Table 0** (1 header + 4 data) - no more, no less.
   - Verify the 4 topic names match: "Followup from previous meeting", "Action items", "Task Assignments", "Meeting Decisions".
   - Verify Table 1 has all 21 members with correct Yes/No participation.
3. **AI Extraction Accuracy Test**:
   - Feed `Test Input .txt` through each AI provider and verify the JSON output populates all template slots correctly.
   - Confirm Bangla and English transcripts are present and well-formed.
4. **Separate Copy Buttons Test**:
   - Verify "Copy Bangla" copies only Bangla transcript to clipboard.
   - Verify "Copy English" copies only English transcript to clipboard.
   - Verify "Copy Both" copies both with separators.
5. **Live Transcription Test**:
   - Verify WebSocket `/ws/live_transcribe` connects and streams audio to Gemini Live API.
   - Verify real-time text appears in the LiveTranscription panel.
   - Verify language auto-detection returns correct language tag.
   - Verify "Send to Bangla" / "Send to English" correctly populates the target transcript field.
6. **Split Model Test**:
   - Verify transcription uses `transcription_model` and summarization uses `summarization_model`.
   - Test: set Gemini for transcription and Groq for summarization; confirm both models are hit independently.
7. **Security and XSS Audit**:
   - Verify `DOMPurify` sanitization on rich text inputs.
   - Audit security headers (`CSP`, `nosniff`, `X-Frame-Options`) on API responses.
8. **Input Validation Test**:
   - Test invalid file upload types and path traversal payloads (e.g. `../../../etc/passwd`) to ensure rejection with HTTP 400/422.
9. **Cross-Platform Build Verification**:
   - Compile React bundle via `npm run build`.
   - Test Windows executable package and Android APK generator.
