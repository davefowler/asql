#!/bin/bash
# Start ASQL documentation and playground servers using venv

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

# Start the servers
echo "Starting ASQL servers..."
python3 start_servers.py

