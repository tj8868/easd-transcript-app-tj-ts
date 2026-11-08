#!/usr/bin/env bash
# Standalone Launcher for Universal Transcription Module (Linux / macOS)

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$BASE_DIR")"

# Activate parent virtual environment if present
if [ -f "$PARENT_DIR/.venv/bin/activate" ]; then
    echo "[Launcher] Activating virtual environment (.venv)..."
    source "$PARENT_DIR/.venv/activate"
elif [ -f "$BASE_DIR/.venv/bin/activate" ]; then
    source "$BASE_DIR/.venv/activate"
fi

export PYTHONUNBUFFERED=1
cd "$BASE_DIR"

echo "=========================================================="
echo " Starting Standalone Universal Transcription Module"
echo " Host: http://127.0.0.1:8085"
echo "=========================================================="

python3 app.py
