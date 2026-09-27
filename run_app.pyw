"""
EASD Meeting Minutes Desktop App Launcher (.pyw extension)
Windows natively associates .pyw files with pythonw.exe,
guaranteeing 0 console / command prompt windows.
"""
import os
import sys
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. Automatic Virtual Environment Hand-off:
# If run_app.pyw is executed directly using system Python rather than .venv,
# automatically re-execute inside the project's dedicated virtual environment (.venv)
candidate_venvs = [
    os.path.join(BASE_DIR, ".venv"),
    os.path.join(BASE_DIR, "venv"),
    os.path.join(os.path.dirname(BASE_DIR), "easd-transcript-app-tj-ts-7", ".venv"),
]
known_vp_paths = []
for cv in candidate_venvs:
    known_vp_paths.extend([
        os.path.join(cv, "Scripts", "python.exe"),
        os.path.join(cv, "Scripts", "pythonw.exe")
    ])

current_exe = os.path.abspath(sys.executable).lower()
current_real = os.path.realpath(sys.executable).lower()
is_in_venv = False
for vp in known_vp_paths:
    if os.path.isfile(vp):
        vp_abs = os.path.abspath(vp).lower()
        vp_real = os.path.realpath(vp).lower()
        if current_exe in (vp_abs, vp_real) or current_real in (vp_abs, vp_real):
            is_in_venv = True
            break

if not is_in_venv:
    target_py = None
    for cv in candidate_venvs:
        p_pyw = os.path.join(cv, "Scripts", "pythonw.exe")
        p_py = os.path.join(cv, "Scripts", "python.exe")
        if os.path.isfile(p_pyw):
            target_py = p_pyw
            break
        elif os.path.isfile(p_py):
            target_py = p_py
            break
    if target_py:
        cmd = [target_py, os.path.abspath(__file__)] + sys.argv[1:]
        subprocess.Popen(cmd, cwd=BASE_DIR)
        sys.exit(0)

# Ensure sys.stdout and sys.stderr are valid streams under pythonw (GUI mode)
if sys.stdout is None:
    try:
        sys.stdout = open(os.path.join(BASE_DIR, "app_service.log"), "a", encoding="utf-8", buffering=1)
    except Exception:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")

if sys.stderr is None:
    try:
        sys.stderr = open(os.path.join(BASE_DIR, "app_service.log"), "a", encoding="utf-8", buffering=1)
    except Exception:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Ensure current folder is in Python module path
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import app

if __name__ == "__main__":
    try:
        # If server is already running, focus the application window and exit
        if app.is_server_already_running(8000):
            t = app.open_native_app_window("http://localhost:8000/", delay=0.1)
            if t:
                t.join(timeout=2.0)
            sys.exit(0)

        import uvicorn
        port = app.find_available_port(8000)
        url = f"http://localhost:{port}/"
        app.open_native_app_window(url, delay=0.1)
        uvicorn.run(app.app, host="127.0.0.1", port=port, log_level="warning")
    except Exception as e:
        import traceback
        try:
            with open(os.path.join(BASE_DIR, "app_service.log"), "a", encoding="utf-8") as f:
                f.write(f"\n[FATAL Launcher Error] {e}\n")
                traceback.print_exc(file=f)
        except Exception:
            pass
        sys.exit(1)
