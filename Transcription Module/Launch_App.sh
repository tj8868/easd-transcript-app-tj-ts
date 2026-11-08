#!/usr/bin/env bash
# Linux 1-Click Launcher for Universal Transcription Module
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT="$(dirname "$DIR")"

# Activate virtual environment if present
if [ -f "$PARENT/.venv/bin/activate" ]; then
    source "$PARENT/.venv/bin/activate"
elif [ -f "$DIR/.venv/bin/activate" ]; then
    source "$DIR/.venv/bin/activate"
fi

cd "$DIR"
python3 run_app.py
