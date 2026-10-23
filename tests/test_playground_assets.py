"""The playground page's local assets ship inside the installed package.

The Docker image installs the wheel, so an asset outside `asql/` serves in a
checkout and 404s in production.
"""

from __future__ import annotations

import re
from pathlib import Path

from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

import asql
from asql.playground.app import app

PACKAGE_DIR = Path(asql.__file__).parent.resolve()
INDEX_HTML = PACKAGE_DIR / "playground" / "templates" / "index.html"


def _static_mounts() -> dict[str, Path]:
    return {
        route.path: Path(str(route.app.directory)).resolve()
        for route in app.routes
        if isinstance(route, Mount) and isinstance(route.app, StaticFiles)
    }


def test_every_local_asset_the_page_references_ships_in_the_package() -> None:
    urls = re.findall(r'(?:src|href)="(/static/[^"]+)"', INDEX_HTML.read_text())
    assert any(url.endswith("asql-mode.js") for url in urls)
    mounts = _static_mounts()
    for url in urls:
        prefix = next((p for p in mounts if url.startswith(p + "/")), None)
        assert prefix is not None, f"{url} matches no static mount"
        path = mounts[prefix] / url.removeprefix(prefix + "/")
        assert path.is_file(), url
        assert path.is_relative_to(PACKAGE_DIR), f"{url} is served from {path}"
