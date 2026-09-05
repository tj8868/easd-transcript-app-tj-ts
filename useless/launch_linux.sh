#!/usr/bin/env bash
# Linux Universal Launcher
set -e
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "Starting Eminence AI Hub on http://localhost:8000..."
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
