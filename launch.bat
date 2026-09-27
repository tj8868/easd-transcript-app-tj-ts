@echo off
setlocal enabledelayedexpansion
title eCommunicator - EASD Meeting Minutes AI
cd /d "%~dp0"

:: 1. Detect Python from active virtual environment or system
set "PY="
set "PYW="

if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY=%~dp0.venv\Scripts\python.exe"
    set "PYW=%~dp0.venv\Scripts\pythonw.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PY=%~dp0venv\Scripts\python.exe"
    set "PYW=%~dp0venv\Scripts\pythonw.exe"
) else if exist "%~dp0..\easd-transcript-app-tj-ts-7\.venv\Scripts\python.exe" (
    set "PY=%~dp0..\easd-transcript-app-tj-ts-7\.venv\Scripts\python.exe"
    set "PYW=%~dp0..\easd-transcript-app-tj-ts-7\.venv\Scripts\pythonw.exe"
) else if exist "%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe" (
    set "PY=%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe"
    set "PYW=%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\pythonw.exe"
) else (
    set "PY=python"
    set "PYW=pythonw"
)

:: 2. Target runner script
if exist "%~dp0run_app.pyw" (
    set "TARGET=%~dp0run_app.pyw"
) else (
    set "TARGET=%~dp0app.py"
)

:: 3. Debug / Console Mode (pass 'debug' or 'console' to see terminal output)
if /i "%~1"=="debug" (
    echo [EASD Meeting Minutes AI] Running in debug console mode...
    "%PY%" "%TARGET%"
    pause
    exit /b 0
)
if /i "%~1"=="console" (
    echo [EASD Meeting Minutes AI] Running in console mode...
    "%PY%" "%TARGET%"
    pause
    exit /b 0
)

:: 4. Background / Silent Desktop Launch
if exist "%PYW%" (
    start "" "%PYW%" "%TARGET%"
    exit /b 0
)

start "" "%PY%" "%TARGET%"
exit /b 0
