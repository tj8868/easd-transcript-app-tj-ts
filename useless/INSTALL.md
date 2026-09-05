# Installation & Setup Guide

This guide explains how to install, build, and run the **Eminence AI Transcription & Meeting Minutes Hub**.

---

## 📋 Prerequisites

Before running the application, ensure you have the following installed on your system:

1. **Python 3.10+** (Python 3.11 or 3.12 recommended)
   - [Download Python](https://www.python.org/downloads/) (Make sure to check *"Add python.exe to PATH"* during installation).
2. **Node.js (v18 or higher) & npm**
   - [Download Node.js](https://nodejs.org/)
3. **FFmpeg** *(Required for universal audio/video extraction — HEVC/H.265, iPhone MOV/M4A/CAF, MP4, MKV)*
   - **Windows (via Winget)**:
     ```powershell
     winget install Gyan.FFmpeg
     ```
   - **Windows (via Chocolatey)**:
     ```powershell
     choco install ffmpeg
     ```
   - *Or download binary from [ffmpeg.org](https://ffmpeg.org/download.html) and add to system PATH.*

---

## 🚀 Quick Start (Automated)

If you already have Python and Node.js installed:

1. **Double-click** `Launch_App.bat` in the root folder.
2. The script will start the application server on `https://127.0.0.1:8000` (or `http://localhost:8000`).
3. Open your browser and navigate to:
   ```
   https://localhost:8000
   ```

---

## 🛠️ Step-by-Step Manual Installation

### Step 1: Clone or Open the Project Directory
Open PowerShell or Command Prompt in the project folder:
```powershell
cd "e:\ESAD -Taseen-Workspace-2026\EASD-TJ-Admin\EASD Meeting Minutes\Transcription APP"
```

### Step 2: Set Up Python Virtual Environment
```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
.\venv\Scripts\activate
```

### Step 3: Install Python Dependencies
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Install Frontend Dependencies & Build
```powershell
cd frontend
npm install
npm run build
cd ..
```
*(The build output will be placed in `frontend/dist/` and automatically served by FastAPI).*

### Step 5: Start the Backend Server
```powershell
python app.py
```

Output:
```
INFO: Uvicorn running on https://127.0.0.1:8000 (Press CTRL+C to quit)
```

---

## 🔑 API Keys & Configuration

- You can configure your **Groq API Key**, **Gemini API Key**, or **OpenAI / Claude Endpoint** directly in the Web UI under the **"1. Audio / Video / Text Input & AI Provider"** card.
- Alternatively, you can save your default Groq key in `GroqAPI.txt` in the root folder, and the application will auto-load it on startup.

---

## 🧪 Testing Your Installation

To verify that all components, media extractors, templates, and AI routes are functioning 100%:

```powershell
# Run Media Format & FFmpeg Test
python test_media_formats.py

# Run Complete End-to-End Test Suite
python test_e2e.py
```
