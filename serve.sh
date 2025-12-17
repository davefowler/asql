#!/bin/bash
# Start ASQL documentation server (MkDocs) and playground

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✓ Activated virtual environment"
else
    echo "⚠ Warning: venv directory not found. Using system Python."
fi

# Kill any existing processes on our ports
echo "Cleaning up existing processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:5001 | xargs kill -9 2>/dev/null
sleep 1

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "Shutting down servers..."
    kill $MKDOCS_PID $PLAYGROUND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

echo ""
echo "=================================================="
echo "  ASQL Development Servers"
echo "=================================================="
echo ""

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
