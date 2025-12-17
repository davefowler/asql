"""ASQL Playground package."""

from .jinja_utils import strip_jinja_templates
from .examples import (
    ASQL_EXAMPLES,
    PIPELINE_EXAMPLES, 
    COHORT_EXAMPLES,
    SAMPLING_EXAMPLES,
    RESHAPING_EXAMPLES,
    COLUMN_OPERATOR_EXAMPLES,
    COUNT_INFERENCE_EXAMPLES,
    SQL_EXAMPLES,
    get_all_examples,
    get_all_examples_flat,
)

# Lazy import app to avoid requiring fastapi for just examples/jinja_utils
def _get_app():
    from .app import app
    return app

__all__ = [
    "strip_jinja_templates",
    "ASQL_EXAMPLES",
    "PIPELINE_EXAMPLES",
    "COHORT_EXAMPLES", 
    "SAMPLING_EXAMPLES",
    "RESHAPING_EXAMPLES",
    "COLUMN_OPERATOR_EXAMPLES",
    "COUNT_INFERENCE_EXAMPLES",
    "SQL_EXAMPLES",
    "get_all_examples",
    "get_all_examples_flat",
]

# For backwards compatibility: `from playground import app`
def __getattr__(name):
    if name == "app":
        return _get_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
