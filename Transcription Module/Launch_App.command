#!/usr/bin/env bash
# macOS 1-Click Launcher for Universal Transcription Module
DIR="$(cd "$(dirname "$0")" && pwd)"
PARENT="$(dirname "$DIR")"

if [ -f "$PARENT/.venv/bin/activate" ]; then
    source "$PARENT/.venv/bin/activate"
elif [ -f "$DIR/.venv/bin/activate" ]; then
    source "$DIR/.venv/bin/activate"
fi

cd "$DIR"
python3 run_app.py
