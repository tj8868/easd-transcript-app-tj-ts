@echo off
setlocal enabledelayedexpansion
title eCommunicator - EASD Meeting Minutes AI
cd /d "%~dp0"

:: 1. Detect Python from active virtual environment or system
set "PY="
set "PYW="

if exist "C:\Users\Emenance-T1\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" (
    set "PY=C:\Users\Emenance-T1\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
    set "PYW=C:\Users\Emenance-T1\AppData\Local\hermes\hermes-agent\venv\Scripts\pythonw.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PY=%~dp0venv\Scripts\python.exe"
    set "PYW=%~dp0venv\Scripts\pythonw.exe"
) else if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY=%~dp0.venv\Scripts\python.exe"
    set "PYW=%~dp0.venv\Scripts\pythonw.exe"
) else (
    set "PY=python"
    set "PYW=pythonw"
)

:: 2. Launch silently without lingering black terminal window
if exist "%PYW%" (
    start "" "%PYW%" "%~dp0app.py"
    exit /b 0
)

start "" "%PY%" "%~dp0app.py"
exit /b 0
