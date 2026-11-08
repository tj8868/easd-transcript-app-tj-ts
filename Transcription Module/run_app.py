#!/usr/bin/env python3
"""
Universal Cross-Platform 1-Click Launcher for Universal Transcription Module.
Works seamlessly on Windows, Linux, and macOS.
- Auto-detects virtual environment (.venv)
- Automatically checks if server is already running (focuses/opens browser if running)
- Starts backend server
- Automatically opens default web browser to the app
"""

import os
import sys
import time
import socket
import subprocess
import threading
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)

# 1. Virtual Environment Auto-Handoff
def find_python_executable():
    """Finds the best Python executable (prioritizing project's .venv)."""
    candidates = [
        # In parent directory
        os.path.join(PARENT_DIR, ".venv", "bin", "python"),
        os.path.join(PARENT_DIR, ".venv", "bin", "python3"),
        os.path.join(PARENT_DIR, ".venv", "Scripts", "pythonw.exe"),
        os.path.join(PARENT_DIR, ".venv", "Scripts", "python.exe"),
        # In local directory
        os.path.join(BASE_DIR, ".venv", "bin", "python"),
        os.path.join(BASE_DIR, ".venv", "bin", "python3"),
        os.path.join(BASE_DIR, ".venv", "Scripts", "pythonw.exe"),
        os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK if os.name != 'nt' else os.R_OK):
            return c
    return sys.executable

def is_port_open(host="127.0.0.1", port=8085):
    """Checks if the port is responding."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False

def open_browser_delayed(url, host="127.0.0.1", port=8085):
    """Waits for server to become active and opens browser."""
    for _ in range(30):
        if is_port_open(host, port):
            time.sleep(0.3)
            webbrowser.open(url)
            return
        time.sleep(0.2)
    webbrowser.open(url)

def main():
    target_py = find_python_executable()
    current_exe = os.path.abspath(sys.executable)

    # Re-execute in venv if not already inside it
    if os.path.abspath(target_py) != current_exe:
        cmd = [target_py, os.path.abspath(__file__)] + sys.argv[1:]
        try:
            sys.exit(subprocess.call(cmd, cwd=BASE_DIR))
        except Exception:
            pass

    # Ensure BASE_DIR is on sys.path
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)

    from config import load_settings
    cfg = load_settings()
    host = cfg.get("server_host", "127.0.0.1")
    port = int(cfg.get("server_port", 8085))
    url = f"http://{host}:{port}"

    # If server is already running, simply open browser and exit
    if is_port_open(host, port):
        print(f"[Launcher] Transcription Module is already running at {url}. Opening browser...")
        webbrowser.open(url)
        sys.exit(0)

    # Launch browser in background thread
    threading.Thread(target=open_browser_delayed, args=(url, host, port), daemon=True).start()

    # Start FastAPI server via Uvicorn
    import uvicorn
    from app import app
    print("=" * 60)
    print(" Universal Transcription Module [1-Click Launcher]")
    print(f" URL: {url}")
    print(" Opening browser automatically...")
    print("=" * 60)

    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()
