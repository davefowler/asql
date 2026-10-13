"""ASQL Dialect Feature Support Registry.

This module tracks which ASQL features are supported by each SQL dialect,
enabling compile-time validation to catch unsupported feature + dialect combinations.
"""

from enum import Enum


class Feature(Enum):
    """ASQL features that have varying dialect support."""

    COLUMN_EXCLUDE = "column_exclude"  # except, rename, replace operators
    AUTO_SPINE = "auto_spine"  # Automatic gap-filling for date GROUP BY
    AUTO_SPINE_ROLLUP = "auto_spine_rollup"  # Auto-spine with ROLLUP/CUBE (edge cases)
    GENERATE_SERIES = "generate_series"  # generate_series() function for spines
    SLICE_SYNTAX = "slice_syntax"  # Python-style slice syntax [1:5]


# Dialect feature support matrix
# Based on: docs/dialect-limitations.md
DIALECT_SUPPORT: dict[str, set[Feature]] = {
    "bigquery": {
        Feature.COLUMN_EXCLUDE,
        Feature.AUTO_SPINE,
        Feature.AUTO_SPINE_ROLLUP,  # ⚠️ Partial support
        Feature.GENERATE_SERIES,
        Feature.SLICE_SYNTAX,  # ✅ Converted to SUBSTRING by preparser
    },
    "snowflake": {
        Feature.COLUMN_EXCLUDE,
        Feature.AUTO_SPINE,
        Feature.AUTO_SPINE_ROLLUP,  # ⚠️ Partial support
        Feature.GENERATE_SERIES,
        Feature.SLICE_SYNTAX,  # ✅ Converted to SUBSTRING by preparser
    },
    "duckdb": {
        Feature.COLUMN_EXCLUDE,
        Feature.AUTO_SPINE,
        Feature.AUTO_SPINE_ROLLUP,  # ⚠️ Partial support
        Feature.GENERATE_SERIES,
        Feature.SLICE_SYNTAX,  # ✅ Fully supported (native + SUBSTRING)
    },
    "postgres": {
        Feature.AUTO_SPINE,
        Feature.AUTO_SPINE_ROLLUP,  # ⚠️ Partial support
        Feature.GENERATE_SERIES,
        Feature.SLICE_SYNTAX,  # ✅ Converted to SUBSTRING by preparser
        # Feature.COLUMN_EXCLUDE - ❌ Not supported
    },
    "postgresql": {  # Alias for postgres
        Feature.AUTO_SPINE,
        Feature.AUTO_SPINE_ROLLUP,  # ⚠️ Partial support
        Feature.GENERATE_SERIES,
        Feature.SLICE_SYNTAX,  # ✅ Converted to SUBSTRING by preparser
    },
    "mysql": {
        Feature.AUTO_SPINE,
        Feature.AUTO_SPINE_ROLLUP,  # ⚠️ Partial support
        Feature.SLICE_SYNTAX,  # ✅ Converted to SUBSTRING by preparser
        # Feature.COLUMN_EXCLUDE - ❌ Not supported
        # Feature.GENERATE_SERIES - ❌ Not supported
    },
    "sqlite": {
        Feature.SLICE_SYNTAX,  # ✅ Converted to SUBSTRING by preparser
        # Feature.AUTO_SPINE - ❌ Not supported
        # Feature.COLUMN_EXCLUDE - ❌ Not supported
        # Feature.GENERATE_SERIES - ❌ Not supported
    },
    "redshift": {
        Feature.AUTO_SPINE,
        Feature.AUTO_SPINE_ROLLUP,  # ⚠️ Partial support
        Feature.GENERATE_SERIES,
        Feature.SLICE_SYNTAX,  # ✅ Converted to SUBSTRING by preparser
        # Feature.COLUMN_EXCLUDE - ❌ Not supported
    },
}


def check_feature(feature: Feature, dialect: str | None) -> bool:
    """Check if a feature is supported by the given dialect.

    Args:
        feature: The feature to check
        dialect: SQL dialect name (e.g., 'postgres', 'bigquery')

    Returns:
        True if feature is supported, False otherwise
    """
    if not dialect:
        return False

    # Normalize dialect name
    dialect_lower = dialect.lower()

    # Handle aliases
    if dialect_lower == "postgresql":
        dialect_lower = "postgres"

    return feature in DIALECT_SUPPORT.get(dialect_lower, set())


def supports_column_exclude(dialect: str | None) -> bool:
    """Check if dialect supports EXCLUDE/EXCEPT column syntax.

    Some dialects (BigQuery, Snowflake, DuckDB) support native column
    exclusion syntax like `SELECT * EXCEPT(col)` or `SELECT * EXCLUDE(col)`.

    For dialects without this support, ASQL can use schema-aware
    column expansion as a fallback.

    Args:
        dialect: SQL dialect name (e.g., 'postgres', 'bigquery')

    Returns:
        True if dialect supports EXCLUDE/EXCEPT, False otherwise
    """
    return check_feature(Feature.COLUMN_EXCLUDE, dialect)
