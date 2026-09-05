#!/usr/bin/env bash
# macOS Double-Clickable Launcher
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "Starting Eminence AI Hub for macOS..."
python3 app.py
