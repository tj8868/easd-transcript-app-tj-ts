# Comprehensive Multi-Platform Build & Installation Guide

This guide provides complete, step-by-step instructions on how to build, install, and run the **Eminence Transcription & Meeting Minutes AI Hub** across all 5 major platforms:
- 🪟 **[Windows](#1-windows-installation--build-guide)** (Standalone `.exe` & Source Launch)
- 🍎 **[macOS](#2-macos-installation--launch-guide)** (Apple Silicon M1/M2/M3 & Intel)
- 🐧 **[Linux](#3-linux-installation--server-deployment-guide)** (Ubuntu/Debian, Fedora, Arch, & systemd Service)
- 🤖 **[Android](#4-android-installation-guide-apk--pwa)** (PWA One-Tap Install & Standalone `.apk`)
- 📱 **[iOS / iPhone & iPad](#5-ios-iphone--ipad-installation-guide)** (Safari PWA & Voice Memo Workflow)
- 🐳 **[Docker & GitHub Codespaces](#6-docker--github-codespaces-cloud-environment)**

---

## 1. Windows Installation & Build Guide

### Method 1.1: Instant Zero-Install Launch (Recommended for End Users)
If you received the pre-built application folder or want to run directly:
1. Double-click:
   ```cmd
   Launch_App.bat
   ```
2. The batch script automatically checks Python dependencies, launches the secure FastAPI server, and opens your default browser at `http://127.0.0.1:8000/`.

---

### Method 1.2: Building the Standalone `.exe` Package
You can package the entire app into a standalone Windows executable (`.exe`) that runs on any 64-bit Windows PC without requiring Python, Node.js, or any external installations.

1. **Prerequisites**: Install Python 3.10+ and Node.js 20.
2. **Install PyInstaller & Requirements**:
   ```powershell
   pip install pyinstaller
   pip install -r requirements.txt
   ```
3. **Compile the React/Vite Frontend**:
   ```powershell
   cd frontend
   npm install
   npm run build
   cd ..
   ```
4. **Run the Automated Windows Packager**:
   ```powershell
   python build_windows_exe.py
   ```
5. **Output Executable**:
   The self-contained app is generated in:
   ```
   dist\EASD_Meeting_Minutes\
   ├── EASD_Meeting_Minutes.exe   <-- Double-click to run (~12 MB)
   └── _internal\                 <-- Bundled engine libraries & assets
   ```
   *To distribute to team members, zip the `EASD_Meeting_Minutes` folder and share it.*

---

## 2. macOS Installation & Launch Guide

Supports both **Apple Silicon (M1/M2/M3/M4)** and **Intel-based Macs**.

### Step 2.1: Install Prerequisites via Homebrew
Open Terminal on your Mac:
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.11, Node.js, and FFmpeg (essential for audio processing)
brew install python@3.11 node ffmpeg
```

### Step 2.2: Clone & Install Dependencies
```bash
git clone https://github.com/your-org/easd-transcriptionapp-tj-ts.git
cd easd-transcriptionapp-tj-ts

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install --upgrade pip
pip install -r requirements.txt

# Build frontend
cd frontend
npm install
npm run build
cd ..
```

### Step 2.3: Launching on macOS
- **One-Click Launch**: Double-click [launch_mac.command](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/launch_mac.command) in Finder.
- **Terminal Launch**:
  ```bash
  source venv/bin/activate
  python3 app.py
  ```
- The app starts on `http://127.0.0.1:8000/`. When prompted in Safari or Chrome, allow **Microphone Access** to use the live recording studio.

---

## 3. Linux Installation & Server Deployment Guide

Works on Ubuntu 20.04/22.04/24.04 LTS, Debian, Fedora, Arch, and headless cloud servers.

### Step 3.1: Install System Dependencies
```bash
# On Ubuntu / Debian:
sudo apt update
sudo apt install -y python3 python3-pip python3-venv ffmpeg nodejs npm curl git

# On Fedora / RHEL:
sudo dnf install -y python3 python3-pip ffmpeg nodejs npm curl git
```

### Step 3.2: Build Frontend and Backend
```bash
git clone https://github.com/your-org/easd-transcriptionapp-tj-ts.git
cd easd-transcriptionapp-tj-ts

# Setup Python Virtual Environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Build Frontend
cd frontend
npm install
npm run build
cd ..
```

### Step 3.3: Run as a Production Background Service (systemd)
The repository includes a ready-to-use systemd service file: [easd-ai.service](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/easd-ai.service).

1. Edit `easd-ai.service` with your server's username and project path:
   ```ini
   [Unit]
   Description=EASD Meeting Minutes & Transcription AI Hub
   After=network.target

   [Service]
   Type=simple
   User=www-data
   WorkingDirectory=/var/www/easd-transcriptionapp-tj-ts
   ExecStart=/var/www/easd-transcriptionapp-tj-ts/venv/bin/python3 app.py
   Restart=always
   RestartSec=5
   Environment=HOST=0.0.0.0
   Environment=PORT=8000

   [Install]
   WantedBy=multi-user.target
   ```
2. Enable and start the service:
   ```bash
   sudo cp easd-ai.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable easd-ai
   sudo systemctl start easd-ai
   ```
3. Check status: `sudo systemctl status easd-ai`

---

## 4. Android Installation Guide (APK & PWA)

The application is built as a **Progressive Web App (PWA)** with a mobile-responsive interface, touch gesture support, and offline audio recording.

### Option 4.1: Instant Direct Installation (Recommended — No APK needed)
1. Ensure the app is running on your network, cloud server, or GitHub Codespaces (e.g. `http://192.168.1.50:8000` or `https://your-codespace.app.github.dev`).
2. Open **Google Chrome** on your Android smartphone or tablet.
3. Open the application URL.
4. Tap the **three vertical dots (⋮)** in the top-right corner of Chrome.
5. Tap **"Install app"** (or **"Add to Home screen"**).
6. **Done!** The app installs with its official EASD logo icon in your Android app drawer and home screen. When launched, it opens full-screen without any browser address bar.

---

### Option 4.2: Building a Standalone Android `.apk` File
If you want to produce a physical `.apk` installer file:

#### Method A: Google Bubblewrap CLI (TWA)
```bash
# 1. Install Bubblewrap CLI
npm install -g @bubblewrap/cli

# 2. Generate and build the Android APK package
npx @bubblewrap/cli init --manifest=http://localhost:8000/manifest.json
npx @bubblewrap/cli build
```
*Output*: A signed `app-release-signed.apk` ready for sideloading or sharing.

#### Method B: Online PWABuilder (Zero SDK Setup)
1. Host the app or start GitHub Codespaces.
2. Go to [PWABuilder.com](https://www.pwabuilder.com).
3. Paste your public URL -> Click **Package for Stores** -> Select **Android**.
4. Download the generated `.apk` package directly and install it on any Android device.

---

## 5. iOS (iPhone & iPad) Installation Guide

Apple iOS does not allow direct sideloading of third-party binaries, but natively supports **Standalone Home Screen Web Apps (Apple Webclips)** with full hardware microphone capture.

### Step 5.1: Install to iPhone / iPad Home Screen
1. Open **Safari** on your iPhone or iPad. *(Note: Must use Safari for iOS Home Screen installation).*
2. Navigate to your app URL (your Codespaces preview URL or server domain).
3. Tap the **Share button** (square icon with an upward arrow at the bottom of the screen).
4. Scroll down and tap **"Add to Home Screen"** (`+`).
5. Tap **Add** in the top-right corner.
6. The EASD Minutes app appears on your iPhone home screen with the official app icon. Tap it to launch in dedicated full-screen mode.

### Step 5.2: iPhone Voice Memo Upload Workflow
1. Record any meeting or discussion on your iPhone using the built-in **Voice Memos** app.
2. In Voice Memos, tap the three dots (`...`) on your recording -> tap **Save to Files**.
3. Open the EASD Meeting Minutes app -> tap **Choose File** in the Media Input section.
4. Select the recorded `.m4a` file from your iPhone **Files** app.
5. The backend will automatically convert the Apple M4A/AAC recording, normalize it with FFmpeg, and produce your meeting minutes.

### Step 5.3: Microphone Permissions on iOS
- When you use the **Live Microphone Studio** for the first time, Safari will prompt: *"Allow easd-minutes to use your microphone?"* -> Tap **Allow**.

---

## 6. Docker & GitHub Codespaces (Cloud Environment)

### 6.1: Docker & Docker Compose
The project features a production multi-stage [Dockerfile](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/Dockerfile) and [docker-compose.yml](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/docker-compose.yml):
```bash
# Build and run the self-contained container
docker compose up --build
```
- Frontend (Node 20), Backend (Python 3.11), and FFmpeg are automatically built and packaged.
- Mounts persistent storage for templates and output documents.
- Access at `http://localhost:8000`.

### 6.2: GitHub Codespaces
1. Click **Code** -> **Codespaces** -> **Create codespace on main** on GitHub.
2. Inside the cloud terminal, start the servers:
   ```bash
   bash launch_codespaces.sh
   ```
3. Click **"Open in Browser"** on port `5173`.
4. Test responsiveness across devices using the top toolbar button: **`📱 3-Device View`** (Mobile 375px, Tablet 768px, and Desktop 1200px side-by-side).

---

## 7. Platform Feature Support Matrix

| Feature | Windows (.exe / Source) | macOS | Linux Server | Android (PWA / APK) | iOS / iPhone (Safari PWA) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Standalone App Launcher** | ✅ (`.exe`) | ✅ (`.command`) | ✅ (`systemd`) | ✅ (PWA / APK) | ✅ (Home Screen App) |
| **Microphone Live Capture** | ✅ | ✅ | ✅ | ✅ | ✅ (Safari MediaDevices) |
| **Universal Media Extraction (FFmpeg)** | ✅ | ✅ | ✅ | ✅ (via backend) | ✅ (via backend) |
| **Apple M4A / Voice Memo Upload** | ✅ | ✅ | ✅ | ✅ | ✅ (Direct Files upload) |
| **Offline Studio UI** | ✅ | ✅ | ✅ | ✅ (ServiceWorker) | ✅ (ServiceWorker) |
| **Official .docx Generation** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **3-Device Responsive Visualizer** | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 8. Verification & Troubleshooting

### Check Audio Processing (FFmpeg)
Run the automated multimedia test:
```bash
python test_media_formats.py
```
*Validates audio extraction across MP3, WAV, Apple M4A, MOV, and MP4.*

### Check Template Engine & Protection
```bash
python -c "from template_engine import load_saved_templates; print('Loaded templates:', len(load_saved_templates()))"
```
*Verifies both official built-in templates and custom saved templates are intact.*

### Need Additional Help?
- Check [INSTALL.md](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/INSTALL.md) for environment configuration tips.
- Read [README.md](file:///e:/ESAD%20-Taseen-Workspace-2026/EASD-TJ-Admin/EASD%20Meeting%20Minutes/easd-transcriptionapp-tj-ts/README.md) for full application documentation.
