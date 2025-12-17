#!/bin/bash
# Start ASQL documentation server (MkDocs) and playground

# More robust cleanup on macOS (uvicorn --reload spawns multiple processes)
kill_port() {
    local port="$1"
    local pids

    # Only kill LISTENers to avoid killing random clients
    pids="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | tr '\n' ' ')"
    if [ -z "$pids" ]; then
        return 0
    fi

    echo "Killing processes on port $port: $pids"
    # Try graceful first
    kill $pids 2>/dev/null || true
    sleep 0.5

    # Anything still listening? Force kill.
    pids="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | tr '\n' ' ')"
    if [ -n "$pids" ]; then
        kill -9 $pids 2>/dev/null || true
    fi
}

kill_patterns() {
    # Kill orphaned reloaders that might not be holding the port yet/anymore
    pkill -f "uvicorn .*playground:app .*--port 5001" 2>/dev/null || true
    pkill -f "python -m mkdocs serve" 2>/dev/null || true
    pkill -f "mkdocs serve" 2>/dev/null || true
}

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Load default env vars (production defaults live in asql.env)
if [ -f "asql.env" ]; then
    set -a
    source "asql.env"
    set +a
fi

# Optional: support local, untracked .env overrides (if present)
if [ -f ".env" ]; then
    set -a
    source ".env"
    set +a
fi

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✓ Activated virtual environment"
else
    echo "⚠ Warning: venv directory not found. Using system Python."
fi

# Kill any existing processes on our ports
echo "Cleaning up existing processes..."
kill_patterns
kill_port 8000
kill_port 5001
sleep 1

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "Shutting down servers..."
    # Kill the process groups (helps with uvicorn --reload)
    kill -- -$MKDOCS_PID 2>/dev/null || true
    kill -- -$PLAYGROUND_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

echo ""
echo "=================================================="
echo "  ASQL Development Servers"
echo "=================================================="
echo ""

# Local dev should point buttons/links at localhost servers
export DOCS_URL="http://localhost:8000"
export PLAYGROUND_URL="http://localhost:5001"

# Start playground in background with hot reload
echo "Starting Playground on http://localhost:5001..."
uvicorn playground:app --reload --host 0.0.0.0 --port 5001 &
PLAYGROUND_PID=$!

# Start MkDocs in background
echo "Starting Documentation on http://localhost:8000..."
python -m mkdocs serve &
MKDOCS_PID=$!

echo ""
echo "=================================================="
echo "  Documentation: http://localhost:8000"
echo "  Playground:    http://localhost:5001"
echo ""
echo "  Hot reload enabled - edit files and refresh!"
echo "=================================================="
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for both processes
wait $MKDOCS_PID $PLAYGROUND_PID
