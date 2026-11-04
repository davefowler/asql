"""
Pytest configuration for E2E tests using Playwright.

`just install` brings pytest-playwright in with the dev extra; the browser is
a one-off download: `uv run --all-extras --locked playwright install chromium`.
Run them with `just e2e`.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import suppress
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Page


def is_port_in_use(port: int) -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def check_playwright_browsers_installed() -> bool:
    """Check if Playwright browsers are installed."""
    executable = os.environ.get("ASQL_E2E_CHROMIUM")
    if executable:
        return os.path.exists(executable)
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            # Try to get the executable path - this will fail if not installed
            browser_path = p.chromium.executable_path
            return os.path.exists(browser_path) if browser_path else False
    except Exception:  # noqa: BLE001
        return False


# Skip all E2E tests if Playwright browsers aren't installed
def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Mark every test here `e2e` (so `just test` deselects them) and skip
    them when no Playwright browser is available."""
    browsers = check_playwright_browsers_installed()
    skip_marker = pytest.mark.skip(
        reason="Playwright browsers not installed. Run 'playwright install' to enable E2E tests."
    )
    for item in items:
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
            if not browsers:
                item.add_marker(skip_marker)


@pytest.fixture(scope="session")
def server_url() -> str:
    """Return the playground server URL. Override via PLAYGROUND_URL env var."""
    return os.environ.get("PLAYGROUND_URL", "http://localhost:5001")


@pytest.fixture(scope="session")
def playwright_server(server_url: str) -> Iterator[str]:
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

    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )

    # The interpreter running the tests has the playground's dependencies.
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "asql.playground.app:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
        ],
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid,  # Create new process group for clean shutdown
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
    with suppress(ProcessLookupError):
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict) -> dict:
    """Let ASQL_E2E_CHROMIUM point at a Chromium binary outside Playwright's
    cache (a preinstalled browser) instead of downloading one."""
    executable = os.environ.get("ASQL_E2E_CHROMIUM")
    if executable:
        return {**browser_type_launch_args, "executable_path": executable}
    return browser_type_launch_args


@pytest.fixture
def page(playwright_server: str, browser: Browser) -> Iterator[Page]:
    """Create a new page for each test."""
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


# Configure pytest-playwright
def pytest_configure(config: pytest.Config) -> None:
    """Add custom markers for E2E tests."""
    config.addinivalue_line("markers", "e2e: mark test as end-to-end test")
