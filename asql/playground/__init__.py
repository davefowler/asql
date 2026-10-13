"""ASQL Playground package."""

# Import app directly for uvicorn compatibility
# Don't catch ImportError - let real errors surface so we can debug them
from .app import app
from .examples import (
    COHORT_EXAMPLES,
    COLUMN_OPERATOR_EXAMPLES,
    COUNT_INFERENCE_EXAMPLES,
    PIPE_EXAMPLES,
    RESHAPING_EXAMPLES,
    SAMPLING_EXAMPLES,
    SQL_EXAMPLES,
    get_all_examples,
    get_all_examples_flat,
)
from .jinja_utils import strip_jinja_templates
from .schema import (
    PLAYGROUND_SCHEMA,
    SCHEMA_METADATA,
    get_column_names_for_table,
    get_columns_for_table,
    get_playground_schema,
    get_schema_for_sqlglot,
    get_schema_with_metadata,
    get_table_names,
)

__all__ = [
    "strip_jinja_templates",
    "PIPE_EXAMPLES",
    "COHORT_EXAMPLES",
    "SAMPLING_EXAMPLES",
    "RESHAPING_EXAMPLES",
    "COLUMN_OPERATOR_EXAMPLES",
    "COUNT_INFERENCE_EXAMPLES",
    "SQL_EXAMPLES",
    "get_all_examples",
    "get_all_examples_flat",
    "PLAYGROUND_SCHEMA",
    "get_playground_schema",
    "get_schema_for_sqlglot",
    "get_table_names",
    "get_columns_for_table",
    "get_column_names_for_table",
    "get_schema_with_metadata",
    "SCHEMA_METADATA",
    "app",
]
