"""Compile every runnable docs example so docs can't drift from the language.

The docs mini-playground (``docs/macros.py``) compiles each ```asql-play`` block to
every supported dialect when a page renders, raising if any dialect fails. That
check only runs during ``mkdocs build`` (and only when split panes are enabled), so
it never gated CI — docs examples could silently fall behind syntax changes.

This test runs the same contract (``precompile_asql_query``) over every ```asql-play``
block in ``docs/`` as part of the normal suite, so ``just asql test`` catches drift.

Only ```asql-play`` fences are runnable queries; plain ```asql`` fences are
syntax-highlight-only snippets (templates, partial examples) and are not compiled —
see the fence convention documented in ``docs/macros.py::process_asql_blocks``.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"
_MACROS_PATH = DOCS_DIR / "macros.py"

# Same pattern the docs build uses to find runnable blocks.
_ASQL_PLAY = re.compile(r"```asql-play\s*\n(.*?)```", re.DOTALL)


def _load_macros():
    """Import docs/macros.py directly — it lives outside the asql package."""
    spec = importlib.util.spec_from_file_location("asql_docs_macros", _MACROS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_macros = _load_macros()


def _collect_examples() -> list[tuple[str, str]]:
    examples: list[tuple[str, str]] = []
    for md in sorted(DOCS_DIR.rglob("*.md")):
        for index, block in enumerate(
            _ASQL_PLAY.findall(md.read_text(encoding="utf-8"))
        ):
            query = block.strip()
            if not query:
                continue
            example_id = f"{md.relative_to(DOCS_DIR)}#{index}"
            examples.append((example_id, query))
    return examples


DOCS_EXAMPLES = _collect_examples()


def test_docs_examples_found() -> None:
    """Guard against a silently empty parametrization (bad glob / fence rename)."""
    assert len(DOCS_EXAMPLES) > 100, (
        f"Expected many asql-play blocks in {DOCS_DIR}, found {len(DOCS_EXAMPLES)}"
    )


@pytest.mark.parametrize(
    ("example_id", "query"),
    DOCS_EXAMPLES,
    ids=[example_id for example_id, _ in DOCS_EXAMPLES],
)
def test_docs_example_compiles_all_dialects(example_id: str, query: str) -> None:
    """Each asql-play block must compile to every dialect the docs advertise.

    ``precompile_asql_query`` raises RuntimeError listing the offending dialect(s)
    if any compilation fails — the same failure the docs build would surface.
    """
    _macros.precompile_asql_query(query)
