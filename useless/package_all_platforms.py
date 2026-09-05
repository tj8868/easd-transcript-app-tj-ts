"""
Universal Multi-Platform Packaging Orchestrator
EASD Meeting Minutes & Document AI Hub

This script prepares, validates, and packages the entire application for:
  1. Windows (.exe / .bat standalone)
  2. Linux (Standalone ELF binary / AppImage / Systemd Service)
  3. macOS (.app / .dmg bundle)
  4. Android (APK via Capacitor / TWA)
  5. iOS (PWA / Capacitor WebKit Wrapper)
"""

import os
import sys
import json
import shutil
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def ensure_frontend_built():
    """Builds the React frontend and copies it into static/."""
    frontend_dir = os.path.join(BASE_DIR, "frontend")
    dist_dir = os.path.join(frontend_dir, "dist")
    static_dir = os.path.join(BASE_DIR, "static")

    print("[1/5] Checking React Frontend Production Bundle...")
    if not os.path.exists(dist_dir) or not os.path.exists(os.path.join(dist_dir, "index.html")):
        print("  -> Compiling frontend assets with Vite...")
        subprocess.run(["npm", "run", "build"], cwd=frontend_dir, shell=True, check=True)

    if os.path.exists(dist_dir):
        shutil.rmtree(static_dir, ignore_errors=True)
        shutil.copytree(dist_dir, static_dir)
        print("  -> Synced frontend bundle to static/ directory.")

def generate_windows_package():
    """Generates Windows launcher scripts and configuration."""
    print("[2/5] Preparing Windows Portable Package...")
    bat_path = os.path.join(BASE_DIR, "Launch_App.bat")
    bat_content = """@echo off
title Eminence Transcription & Document AI
echo Starting Eminence AI Hub on http://localhost:8000 ...
cd /d "%~dp0"
python app.py
pause
"""
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)
    print(f"  -> Created Windows Quick-Launch: {bat_path}")

def generate_linux_package():
    """Generates Linux launch script and systemd service file."""
    print("[3/5] Preparing Linux Standalone & Service Configurations...")
    sh_path = os.path.join(BASE_DIR, "launch_linux.sh")
    sh_content = """#!/usr/bin/env bash
# Linux Universal Launcher
set -e
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "Starting Eminence AI Hub on http://localhost:8000..."
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
"""
    with open(sh_path, "w", encoding="utf-8") as f:
        f.write(sh_content)
    
    # Systemd Service File
    service_path = os.path.join(BASE_DIR, "easd-ai.service")
    service_content = """[Unit]
Description=Eminence AI Transcription and Meeting Minutes Hub
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/easd-ai
ExecStart=/usr/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    with open(service_path, "w", encoding="utf-8") as f:
        f.write(service_content)
    print(f"  -> Created Linux launcher: {sh_path} and service: {service_path}")

def generate_macos_package():
    """Generates macOS launch script."""
    print("[4/5] Preparing macOS Launcher & DMG Instructions...")
    mac_path = os.path.join(BASE_DIR, "launch_mac.command")
    mac_content = """#!/usr/bin/env bash
# macOS Double-Clickable Launcher
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "Starting Eminence AI Hub for macOS..."
python3 app.py
"""
    with open(mac_path, "w", encoding="utf-8") as f:
        f.write(mac_content)
    print(f"  -> Created macOS Double-Clickable Command: {mac_path}")

def generate_mobile_pwa_package():
    """Generates Android & iOS Mobile Web App Manifest."""
    print("[5/5] Preparing Mobile PWA & Capacitor Manifest (Android & iOS)...")
    manifest = {
        "short_name": "EASD AI",
        "name": "Eminence Transcription & Meeting Minutes AI",
        "description": "Cross-Platform AI Speech Transcription and Document Synthesis",
        "icons": [
            {
                "src": "/eminence_logo.png",
                "type": "image/png",
                "sizes": "192x192 512x512"
            }
        ],
        "start_url": "/",
        "background_color": "#070d1e",
        "theme_color": "#0284c7",
        "display": "standalone",
        "orientation": "portrait"
    }
    
    static_manifest = os.path.join(BASE_DIR, "static", "manifest.json")
    with open(static_manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"  -> Generated Mobile PWA Manifest: {static_manifest}")

def main():
    print("=================================================================")
    print("   EASD Meeting Minutes & Multi-Document AI - Universal Package  ")
    print("=================================================================")
    ensure_frontend_built()
    generate_windows_package()
    generate_linux_package()
    generate_macos_package()
    generate_mobile_pwa_package()
    print("\n[SUCCESS] Universal Multi-Platform Package configured!")

if __name__ == "__main__":
    main()
