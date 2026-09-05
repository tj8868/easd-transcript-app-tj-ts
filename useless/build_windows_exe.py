import os
import sys
import shutil
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_EXE = r"C:\Users\Emenance-T1\AppData\Local\Python\pythoncore-3.14-64\python.exe"

def build_windows_executable():
    print("=== Building Secure & High-Performance Windows Standalone Executable ===")
    
    # Ensure frontend/dist is copied to static directory for launcher compatibility
    frontend_dist = os.path.join(BASE_DIR, "frontend", "dist")
    static_dir = os.path.join(BASE_DIR, "static")
    
    if os.path.exists(frontend_dist):
        if os.path.exists(static_dir):
            shutil.rmtree(static_dir)
        shutil.copytree(frontend_dist, static_dir)
        print("[SUCCESS] Copied React production bundle to static directory.")

    # 1. Create Launch_App.bat for double-click startup
    bat_content = f"""@echo off
title EASD Meeting Assistant
echo Starting High-Performance EASD Meeting Assistant...
cd /d "%~dp0"
"{PYTHON_EXE}" app.py
pause
"""
    bat_path = os.path.join(BASE_DIR, "Launch_App.bat")
    with open(bat_path, "w") as f:
        f.write(bat_content)
    print(f"[SUCCESS] Created Windows launcher script: {bat_path}")

    # 2. PyInstaller build command
    pyinstaller_cmd = [
        PYTHON_EXE, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "EASD_Meeting_Minutes",
        "--add-data", f"{os.path.join(BASE_DIR, 'frontend', 'dist')};frontend/dist",
        "--add-data", f"{os.path.join(BASE_DIR, 'static')};static",
        "--add-data", f"{os.path.join(BASE_DIR, 'EASD Meeting minutes - Template-DDMonthYY.docx')};.",
        os.path.join(BASE_DIR, "app.py")
    ]
    
    print("Executing PyInstaller build process...")
    try:
        res = subprocess.run(pyinstaller_cmd, cwd=BASE_DIR, capture_output=True, text=True)
        print("PyInstaller stdout:\n", res.stdout[-1000:])
        if res.returncode == 0:
            print("[SUCCESS] Windows executable build completed in 'dist/EASD_Meeting_Minutes'")
        else:
            print("[WARNING] PyInstaller exited with code:", res.returncode)
            print("PyInstaller stderr:\n", res.stderr[-1000:])
    except Exception as e:
        print("[ERROR] PyInstaller build failed:", str(e))

if __name__ == "__main__":
    build_windows_executable()
