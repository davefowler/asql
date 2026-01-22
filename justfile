# ASQL Development Commands
# Run `just --list` to see all available commands

# Default recipe - show help
default:
    @just --list

# ============================================================================
# SETUP
# ============================================================================

# Create virtual environment and install all dependencies
install:
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
    ./venv/bin/pip install -r requirements-test.txt
    ./venv/bin/pip install -r requirements-docs.txt
    ./venv/bin/pip install -e .
    @echo "✓ Virtual environment created and dependencies installed"

# ============================================================================
# TESTING & LINTING
# ============================================================================

# Run tests (pass any pytest args: just test tests/test_basic.py -v -k "pattern")
test *args:
    ./venv/bin/pytest {{ if args == "" { "tests/" } else { args } }}

# Run ruff linter (--fix to auto-fix)
lint *args:
    ./venv/bin/ruff check . {{args}}

# ============================================================================
# DEVELOPMENT SERVERS
# ============================================================================

# Start both documentation and playground servers (with hot reload)
serve: _kill-servers
    #!/usr/bin/env bash
    set -e
    
    # Load env files
    [[ -f asql.env ]] && set -a && source asql.env && set +a
    [[ -f .env ]] && set -a && source .env && set +a
    
    # Local dev URLs
    export DOCS_URL="http://localhost:8000"
    export PLAYGROUND_URL="http://localhost:5001"
    
    echo ""
    echo "=================================================="
    echo "  ASQL Development Servers"
    echo "=================================================="
    echo "  Documentation: http://localhost:8000"
    echo "  Playground:    http://localhost:5001"
    echo "  Press Ctrl+C to stop"
    echo "=================================================="
    echo ""
    
    # Start both servers (watch static files for CSS/JS changes)
    ./venv/bin/uvicorn playground:app --reload --reload-dir playground/static --reload-dir playground/templates --host 0.0.0.0 --port 5001 &
    PLAYGROUND_PID=$!
    ./venv/bin/python -m mkdocs serve --livereload &
    MKDOCS_PID=$!
    
    trap "kill $PLAYGROUND_PID $MKDOCS_PID 2>/dev/null; exit 0" SIGINT SIGTERM
    wait $PLAYGROUND_PID $MKDOCS_PID

# Start documentation server only
docs:
    ./venv/bin/python -m mkdocs serve --livereload

# Build documentation for production
docs-build:
    ./venv/bin/python -m mkdocs build

# ============================================================================
# UTILITIES
# ============================================================================

# Generate visual ASQL examples from ASQL source queries (edit the script to update examples)
gen-visual-examples:
    ./venv/bin/python scripts/generate_visual_examples.py

# Kill development servers on ports 8000 and 5001
kill:
    #!/usr/bin/env bash
    for port in 8000 5001; do
        pids=$(lsof -nP -iTCP:$port -sTCP:LISTEN -t 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            echo "Killing process(es) on port $port: $pids"
            kill -9 $pids 2>/dev/null || true
        fi
    done
    pkill -9 -f "uvicorn .*playground:app" 2>/dev/null || true
    pkill -9 -f "mkdocs serve" 2>/dev/null || true
    sleep 1
    echo "✓ Development servers stopped"

# ============================================================================
# INTERNAL
# ============================================================================

[private]
_kill-servers:
    #!/usr/bin/env bash
    for port in 8000 5001; do
        pids=$(lsof -nP -iTCP:$port -sTCP:LISTEN -t 2>/dev/null || true)
        [[ -n "$pids" ]] && kill -9 $pids 2>/dev/null || true
    done
    pkill -9 -f "uvicorn .*playground:app" 2>/dev/null || true
    pkill -9 -f "mkdocs serve" 2>/dev/null || true
    sleep 1
