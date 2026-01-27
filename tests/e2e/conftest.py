"""
Pytest configuration for E2E tests using Playwright.
"""
import pytest
import subprocess
import time
import socket
import os
import signal


def is_port_in_use(port: int) -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


def check_playwright_browsers_installed() -> bool:
    """Check if Playwright browsers are installed."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Try to get the executable path - this will fail if not installed
            browser_path = p.chromium.executable_path
            return os.path.exists(browser_path) if browser_path else False
    except Exception:
        return False


# Skip all E2E tests if Playwright browsers aren't installed
def pytest_collection_modifyitems(config, items):
    """Skip E2E tests if Playwright browsers are not installed."""
    if not check_playwright_browsers_installed():
        skip_marker = pytest.mark.skip(
            reason="Playwright browsers not installed. Run 'playwright install' to enable E2E tests."
        )
        for item in items:
            if "e2e" in str(item.fspath):
                item.add_marker(skip_marker)


@pytest.fixture(scope="session")
def server_url():
    """Return the playground server URL. Override via PLAYGROUND_URL env var."""
    return os.environ.get("PLAYGROUND_URL", "http://localhost:5001")


@pytest.fixture(scope="session")
def playwright_server(server_url):
    """
    Start the playground server if not already running.
    This fixture is session-scoped so it runs once per test session.
    """
    port = int(server_url.split(":")[-1].split("/")[0])

    # Check if server is already running
    if is_port_in_use(port):
        print(f"\nPlayground server already running on port {port}")
        yield server_url
        return

    # Start the server
    print(f"\nStarting playground server on port {port}...")

    # Find the project root (where venv is)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    venv_python = os.path.join(project_root, "venv", "bin", "python")

    if not os.path.exists(venv_python):
        pytest.skip("Virtual environment not found. Run 'just install' first.")

    # Start uvicorn server
    process = subprocess.Popen(
        [venv_python, "-m", "uvicorn", "playground:app", "--host", "0.0.0.0", "--port", str(port)],
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid  # Create new process group for clean shutdown
    )

    # Wait for server to start
    max_wait = 30  # seconds
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if is_port_in_use(port):
            print(f"Server started successfully on port {port}")
            break
        time.sleep(0.5)
    else:
        process.terminate()
        pytest.fail(f"Server failed to start within {max_wait} seconds")

    yield server_url

    # Cleanup: kill the server process group
    print("\nShutting down playground server...")
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except ProcessLookupError:
        pass  # Already terminated


@pytest.fixture
def page(playwright_server, browser):
    """Create a new page for each test."""
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


# Configure pytest-playwright
def pytest_configure(config):
    """Add custom markers for E2E tests."""
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )
