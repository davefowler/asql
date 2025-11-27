#!/bin/bash
# Start ASQL documentation server using MkDocs

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

# Start MkDocs documentation server
echo "Starting ASQL Documentation Server..."
echo "Open http://127.0.0.1:8000 in your browser"
echo ""
python -m mkdocs serve
