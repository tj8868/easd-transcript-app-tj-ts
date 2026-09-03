#!/usr/bin/env bash
# Universal GitHub Codespaces & Linux Launcher
set -e
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "  Starting EASD Meeting Minutes AI Hub in Codespaces"
echo "=========================================================="

export HOST="0.0.0.0"
export PORT="8000"

# Install backend dependencies if not present
if ! python3 -c "import fastapi" &> /dev/null; then
    echo "Installing Python requirements..."
    pip install -q -r requirements.txt
fi

# Ensure frontend dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    (cd frontend && npm install)
fi

# Start FastAPI backend in background
echo "Starting FastAPI Backend on 0.0.0.0:8000..."
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Function to gracefully stop on exit
cleanup() {
    echo "Stopping servers..."
    kill $BACKEND_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Start Vite frontend
echo "Starting Vite Frontend on 0.0.0.0:5173..."
(cd frontend && npm run dev -- --host 0.0.0.0 --port 5173)
