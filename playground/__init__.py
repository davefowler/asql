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

# Import app directly for Railway/uvicorn compatibility
# Don't catch ImportError - let real errors surface so we can debug them
from .app import app

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
    "app",
]
