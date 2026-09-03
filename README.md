# Eminence Transcription & Meeting Minutes AI Hub

An enterprise-grade, privacy-first AI speech transcription and multi-document generation hub. Transforms audio recordings, phone voice memos, videos, transcripts, or meeting notes into official, publication-ready Microsoft Word (`.docx`) documents with 100% fidelity to organizational templates.

---

## 🌟 Key Features

1. **Universal Audio & Media Engine**:
   - Supports all media containers: `.mp3`, `.wav`, `.m4a` (iPhone voice memos), `.aac`, `.ogg`, `.flac`, `.mp4`, `.mov`, `.mkv`, `.webm`, and `.docx`.
   - Automatic FFmpeg audio extraction, 16kHz mono normalization, and smart 24MB audio chunking.
2. **Live Microphone Recording Studio**:
   - Real-time in-browser microphone capture with animated soundwave visualizer and auto-queue buffer.
3. **Multi-Document-Type Registry**:
   - **Meeting minutes**: 4-topic framework (Followup, Action items, Task assignments, Decisions) + 21-member attendance checklist.
   - **Report - Bangladesh government structure**: Official Secretariat Nothi / Memo format (গণপ্রজাতন্ত্রী বাংলাদেশ সরকার, Ministry, Memo No/স্মারক নং, Date, Subject/বিষয়, Background/পটভূমি, Observations/পর্যবেক্ষণ, Decisions, Recommendations, Implementation Matrix, and Signatures).
   - **Journal**: Academic paper structure (Abstract, Introduction, Methodology, Results, Discussion, Conclusion, References).
   - **News**: Press release format (Immediate release badge, Headline, Dateline, Inverted pyramid lead, Quotes, Boilerplate).
   - **Blog**: Thought leadership article (Magnetic title, Hook intro, Core insights, Actionable takeaways, CTA).
   - **Custom Uploaded `.docx`**: Upload any organizational Word template; the app auto-extracts fields, tables, and sections.
4. **3 Core AI Directives System**:
   - **Context (Purpose)**: Defines institutional background, domain, and audience.
   - **Rules (Guidelines)**: Enforces tone, bullet conventions, and language constraints.
   - **Requirements (Mandatory)**: Guarantees essential metadata fields and table extractions are never omitted.
   - Interactive inline `(?)` buttons provide concrete, copyable examples.
5. **Standards-Compliant Font Engine & Settings (⚙️)**:
   - **Bangladesh Government Standard**: `Nikosh`, `NikoshBAN`, `Kalpurush`.
   - **Microsoft & Academic Standard**: `Times New Roman`, `Calibri`, `Arial`, `Inter`.
   - **Accent Colors**: Eminence Cerulean (`#0284c7`), Govt Emerald (`#047857`), Royal Navy (`#004b87`), Sunset Orange (`#ea580c`), Violet (`#7c3aed`), Crimson Red (`#dc2626`).
   - Distinct, visible textbox outlines across both Light and Dark studio themes.
6. **1:1 Authentic Document Preview**:
   - Renders an exact replica of the output document with official logos, headers, table fills (`#E36C0A` Eminence Orange or `#047857` Govt Green), and formatting before downloading.

---

## 📖 Complete Build & Platform Deployment Guides
For full step-by-step instructions on building, compiling, and deploying across all platforms, see the dedicated **[Build Guide (BUILD_GUIDE.md)](./BUILD_GUIDE.md)**:
- 💻 **[Source Build (Local Development)](./BUILD_GUIDE.md#2-building-the-app-from-source-local-machine)**
- 🪟 **[Windows Standalone Executable (.exe)](./BUILD_GUIDE.md#3-building-the-windows-standalone-executable-exe)** (`dist/EASD_Meeting_Minutes/EASD_Meeting_Minutes.exe`)
- 🐳 **[Docker & Docker Compose Container](./BUILD_GUIDE.md#4-building-and-running-with-docker)** (`docker compose up --build`)
- ☁️ **[GitHub Codespaces Cloud Environment](./BUILD_GUIDE.md#5-running-in-github-codespaces)** (`bash launch_codespaces.sh`)
- 📱 **[Android Installation (PWA & APK)](./BUILD_GUIDE.md#6-building-and-installing-on-android-apk--pwa)**
- 🐧 **[Linux Server & macOS Daemon](./BUILD_GUIDE.md#7-deploying-on-linux-server--macos)**

---

## 🚀 Quick Start Guide (Windows)

### Option 1: Instant Zero-Install Launch (Recommended)
Simply double-click:
```
Launch_App.bat
```
- Starts the secure local server.
- Opens your default web browser automatically at `http://127.0.0.1:8000/`.

### Option 2: Run via Terminal
```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start application
python app.py
```

---

## 🔑 How to Obtain & Add API Keys

The app supports multiple AI providers. You only need **one** API key to get started (both Google Gemini and Groq offer generous **free** tiers):

### 1. Google Gemini (Recommended - Free & Fast)
- **Get Key**: Go to [Google AI Studio](https://aistudio.google.com/app/apikey) and click **"Create API Key"**.
- **In the App**:
  - Select **AI Provider**: `Google Gemini`.
  - Paste your key (starts with `AIzaSy...`).
  - STT Model: `gemini-2.5-flash` or `gemini-3.5-flash-lite`.
  - LLM Model: `gemini-3.5-flash-lite` or `gemini-3.7-flash`.
  - Click **"Test Key"** to verify connection.

### 2. Groq Cloud (Ultra-Fast 216x Whisper STT - Free)
- **Get Key**: Go to [Groq Console](https://console.groq.com/keys) and click **"Create API Key"**.
- **In the App**:
  - Select **AI Provider**: `Groq Cloud`.
  - Paste your key (starts with `gsk_...`).
  - STT Model: `whisper-large-v3-turbo`.
  - LLM Model: `openai/gpt-oss-120b` or `llama-3.3-70b-versatile`.
  - Click **"Test Key"**.

### 3. OpenAI / Anthropic / Custom (Ollama)
- **OpenAI**: Paste your `sk-...` key to use `whisper-1` and `gpt-4o`.
- **Anthropic Claude**: Paste your `sk-ant-...` key to use `claude-3-5-sonnet`.
- **100% Offline / Local (Zero Internet)**: Select `Custom OpenAI-Compatible`, set Base URL to `http://localhost:11434/v1` (Ollama), and enter your local model name (e.g., `llama3.3:70b`).

> **Privacy Note**: Your API keys are stored solely in your local browser's encrypted `localStorage`. They are never sent to external servers or logged.

---

## 📖 How to Use the Application

### Step 1: Input Audio, Video, or Text
- **Upload File**: Drag and drop any media file (`.mp3`, `.m4a`, `.mp4`, `.wav`, etc.) or existing document into the drop zone.
- **Or Record Live**: Scroll to the Live Transcription section and click **"Start Recording"** to dictate speech.
- **Or Paste Notes**: Paste meeting rough notes or transcript directly into the text box.

### Step 2: Choose Document Type
In the **Template & Document Type** section, select your output format:
- `Meeting minutes`
- `Report-Bangladesh government structure`
- `Journal`
- `News`
- `Blog`

### Step 3: Review Directives
Verify or customize the 3 AI Directives:
- Click the inline **`(?)`** button next to **Context**, **Rules**, or **Requirements** to view practical examples.

### Step 4: Generate Document
Click **"⚡ Generate Document"**:
- The AI extracts speech, aligns the discussions, structures the sections, and fits the data into the chosen schema.

### Step 5: Live Preview & Export
- Scroll to the **Document Preview** section at the bottom.
- Review the formatted document matching the exact template layout, typography, and colors.
- Click **"Download Word .docx"** for an official Microsoft Word file or **"Send to Google Drive"** for cloud sync.

---

## ⚙️ Settings Menu & Customization

Click the **`⚙️ Settings`** button in the top header to configure:
- **Bangla Font Engine**: Choose `Nikosh`, `NikoshBAN`, or `Kalpurush`.
- **English Font Engine**: Choose `Times New Roman`, `Calibri`, or `Arial`.
- **Typography Scale**: Switch between Compact (9.5pt), Standard (10.5pt), and Large (12pt).
- **Accent Color**: Choose Cerulean Blue, Govt Emerald, Royal Navy, Sunset Orange, Violet, or Red.
- **Theme**: Toggle Dark Studio Theme or Light Executive Theme.

---

## 📦 Cross-Platform Distribution & Packaging

This single codebase packages natively across all platforms:

| Platform | Setup / Build File | Instructions |
| :--- | :--- | :--- |
| **Windows** | `Launch_App.bat` / `build_windows_exe.py` | Double-click `Launch_App.bat` for instant launch, or run `python build_windows_exe.py` to create a standalone `dist/EASD_Meeting_Minutes.exe`. |
| **Linux** | `launch_linux.sh` / `easd-ai.service` | Run `./launch_linux.sh` or install `easd-ai.service` into `/etc/systemd/system/`. |
| **macOS** | `launch_mac.command` | Double-click `launch_mac.command` to run on macOS. |
| **Android** | `Build_Android_APK.bat` | Run `Build_Android_APK.bat` to build an installable Android APK using Capacitor or Bubblewrap CLI. |
| **iOS** | Progressive Web App (PWA) | Open in Safari and tap **"Add to Home Screen"** to install as a native iOS app. |

To prepare and refresh all packaging assets at once:
```bash
python package_all_platforms.py
```

---

## 🔒 Private GitHub Collaboration Workflow

To collaborate privately with colleagues without exposing the project to the public:

### 1. Create a Private GitHub Repository
1. Log in to [GitHub](https://github.com/new).
2. Set Repository Name to: `easd-transcription-app`.
3. Select **"Private"** (only invited people can access).
4. Do **not** initialize with a README (we already have one).
5. Click **"Create repository"**.

### 2. Push Your Local Code to GitHub
Open terminal in this project folder and run:
```bash
git add .
git commit -m "Initial commit: EASD Transcription & Document AI Hub"
git remote add origin https://github.com/YOUR_USERNAME/easd-transcription-app.git
git push -u origin main
```

### 3. Invite Collaborators
1. In your GitHub repository, go to **Settings > Collaborators > Add people**.
2. Type your collaborator's GitHub username or email address and send the invite.
3. Once accepted, they can clone, pull, and contribute securely.

---

## 🛡️ License & Confidentiality

Internal and Proprietary. Developed for Eminence Associates for Social Development (EASD). All rights reserved.
