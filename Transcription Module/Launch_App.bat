@echo off
REM Windows 1-Click Launcher for Universal Transcription Module
set BASE_DIR=%~dp0
set PARENT_DIR=%BASE_DIR%..

cd /d "%BASE_DIR%"

if exist "%PARENT_DIR%\.venv\Scripts\python.exe" (
    "%PARENT_DIR%\.venv\Scripts\python.exe" run_app.py
) else if exist "%BASE_DIR%\.venv\Scripts\python.exe" (
    "%BASE_DIR%\.venv\Scripts\python.exe" run_app.py
) else (
    python run_app.py
)
