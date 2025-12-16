"""Start both documentation server and playground."""

import subprocess
import sys
import signal
import os
from pathlib import Path

def signal_handler(sig, frame):
    """Handle shutdown signals."""
    print("\nShutting down servers...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Start docs server
print("Starting ASQL Documentation Server on http://0.0.0.0:73137...")
docs_process = subprocess.Popen(
    [sys.executable, "docs_server.py"],
    cwd=Path(__file__).parent,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

# Start playground
print("Starting ASQL Playground on http://0.0.0.0:5001...")
playground_process = subprocess.Popen(
    [sys.executable, "playground.py"],
    cwd=Path(__file__).parent,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

print("\n" + "="*60)
print("ASQL Services Running:")
print("  Documentation: http://localhost:73137 (SELECT-ish on phone keypad!)")
print("  Playground:    http://localhost:5001")
print("="*60)
print("\nPress Ctrl+C to stop both servers\n")

import threading

def print_output(process, name):
    """Print output from a process."""
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                print(f"[{name}] {line.rstrip()}")
    except:
        pass

# Start threads to print output from both processes
docs_thread = threading.Thread(target=print_output, args=(docs_process, "DOCS"), daemon=True)
playground_thread = threading.Thread(target=print_output, args=(playground_process, "PLAYGROUND"), daemon=True)
docs_thread.start()
playground_thread.start()

try:
    # Wait for both processes
    docs_process.wait()
    playground_process.wait()
except KeyboardInterrupt:
    print("\nShutting down...")
    docs_process.terminate()
    playground_process.terminate()
    docs_process.wait()
    playground_process.wait()
