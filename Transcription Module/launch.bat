@echo off
REM Standalone Launcher for Universal Transcription Module (Windows)

set BASE_DIR=%~dp0
set PARENT_DIR=%BASE_DIR%..

if exist "%PARENT_DIR%\.venv\Scripts\activate.bat" (
    echo [Launcher] Activating virtual environment (.venv)...
    call "%PARENT_DIR%\.venv\Scripts\activate.bat"
) else if exist "%BASE_DIR%\.venv\Scripts\activate.bat" (
    call "%BASE_DIR%\.venv\Scripts\activate.bat"
)

cd /d "%BASE_DIR%"

echo ==========================================================
echo  Starting Standalone Universal Transcription Module
echo  Host: http://127.0.0.1:8085
echo ==========================================================

python app.py
pause
