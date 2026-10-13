"""ASQL Playground examples.

These examples are loaded from JSON files in the examples/ directory.
Each example includes tutorial-style comments explaining the feature being showcased.

Style Guide: Examples follow docs/style_guide.md unless explicitly demonstrating alternatives.
"""

import json
from pathlib import Path
from typing import Any, TypedDict, cast


class Example(TypedDict):
    title: str
    desc: str
    query: str


# Base path for example files
EXAMPLES_DIR = Path(__file__).parent / "examples"


def _load_json(filename: str) -> list[dict[str, Any]]:
    """Load examples from a JSON file."""
    filepath = EXAMPLES_DIR / filename
    if filepath.exists():
        with open(filepath) as f:
            return json.load(f)
    return []


def _load_asql_examples(category: str) -> list[Example]:
    """Load ASQL examples from the asql/ subdirectory."""
    return cast(list[Example], _load_json(f"asql/{category}.json"))


# =============================================================================
# ASQL EXAMPLES (loaded from JSON files)
# =============================================================================

PIPE_EXAMPLES: list[Example] = _load_asql_examples("pipe")
SAMPLING_EXAMPLES: list[Example] = _load_asql_examples("sampling")
RESHAPING_EXAMPLES: list[Example] = _load_asql_examples("reshaping")
COLUMN_OPERATOR_EXAMPLES: list[Example] = _load_asql_examples("column_operators")
SPINE_EXAMPLES: list[Example] = _load_asql_examples("spine")
COHORT_EXAMPLES: list[Example] = _load_asql_examples("cohort")
COUNT_INFERENCE_EXAMPLES: list[Example] = _load_asql_examples("count_inference")
SYNTAX_STYLES_EXAMPLES: list[Example] = _load_asql_examples("syntax_styles")

# =============================================================================
# VISUAL ASQL EXAMPLES
# =============================================================================
# These have "query" as JSON objects (not strings) for the visual editor


def _load_visual_asql_examples() -> list[dict[str, Any]]:
    """Load Visual ASQL examples, converting query objects to JSON strings.

    Note: This loads fresh from disk each time to support hot-reloading
    when examples are regenerated via `just gen-visual-examples`.
    """
    examples = _load_json("visual_asql.json")
    # Convert query objects to JSON strings for the frontend
    for ex in examples:
        if isinstance(ex.get("query"), (dict, list)):
            ex["query"] = json.dumps(ex["query"], indent=2)
    return examples


def get_visual_asql_examples() -> list[dict[str, Any]]:
    """Get Visual ASQL examples (loads fresh from disk each call)."""
    return _load_visual_asql_examples()


# For backwards compatibility - but prefer get_visual_asql_examples() for fresh data
VISUAL_ASQL_EXAMPLES: list[dict[str, Any]] = _load_visual_asql_examples()

# =============================================================================
# SQL EXAMPLES (for reverse compilation demos)
# =============================================================================

SQL_EXAMPLES: list[dict[str, Any]] = _load_json("sql.json")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_all_examples() -> dict[str, list[Example]]:
    """Get all examples organized by category."""
    return {
        "pipe": PIPE_EXAMPLES,
        "cohort": COHORT_EXAMPLES,
        "sampling": SAMPLING_EXAMPLES,
        "reshaping": RESHAPING_EXAMPLES,
        "column_operators": COLUMN_OPERATOR_EXAMPLES,
        "count_inference": COUNT_INFERENCE_EXAMPLES,
        "spine": SPINE_EXAMPLES,
        "syntax_styles": SYNTAX_STYLES_EXAMPLES,
    }


def get_all_examples_flat() -> list[tuple[str, str, str]]:
    """Get all examples as flat list of (category, title, query) tuples for testing."""
    result = []
    for category, examples in get_all_examples().items():
        for ex in examples:
            result.append((category, ex["title"], ex["query"]))
    return result
