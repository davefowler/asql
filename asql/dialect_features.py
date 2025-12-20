"""ASQL Dialect Feature Support Registry.

This module tracks which ASQL features are supported by each SQL dialect,
enabling compile-time validation to catch unsupported feature + dialect combinations.
"""

from enum import Enum
from typing import Dict, Set, Optional
import re


class Feature(Enum):
    """ASQL features that have varying dialect support."""
    
    COLUMN_EXCLUDE = 'column_exclude'      # except, rename, replace operators
    AUTO_SPINE = 'auto_spine'              # Automatic gap-filling for date GROUP BY
    AUTO_SPINE_ROLLUP = 'auto_spine_rollup'  # Auto-spine with ROLLUP/CUBE (edge cases)
    GENERATE_SERIES = 'generate_series'    # generate_series() function for spines
    SLICE_SYNTAX = 'slice_syntax'          # Python-style slice syntax [1:5]


# Dialect feature support matrix
# Based on: docs/dialect-limitations.md
DIALECT_SUPPORT: Dict[str, Set[Feature]] = {
    'bigquery': {
        Feature.COLUMN_EXCLUDE,
        Feature.AUTO_SPINE,
        Feature.AUTO_SPINE_ROLLUP,  # ⚠️ Partial support
        Feature.GENERATE_SERIES,
        # Feature.SLICE_SYNTAX - 🐛 Buggy (Issue #77)
    },
    'snowflake': {
        Feature.COLUMN_EXCLUDE,
        Feature.AUTO_SPINE,
        Feature.AUTO_SPINE_ROLLUP,  # ⚠️ Partial support
        Feature.GENERATE_SERIES,
        # Feature.SLICE_SYNTAX - 🐛 Buggy (Issue #77)
    },
    'duckdb': {
        Feature.COLUMN_EXCLUDE,
        Feature.AUTO_SPINE,
        Feature.AUTO_SPINE_ROLLUP,  # ⚠️ Partial support
        Feature.GENERATE_SERIES,
        Feature.SLICE_SYNTAX,  # ✅ Fully supported
    },
    'postgres': {
        Feature.AUTO_SPINE,
        Feature.AUTO_SPINE_ROLLUP,  # ⚠️ Partial support
        Feature.GENERATE_SERIES,
        # Feature.COLUMN_EXCLUDE - ❌ Not supported
        # Feature.SLICE_SYNTAX - 🐛 Buggy (Issue #77)
    },
    'postgresql': {  # Alias for postgres
        Feature.AUTO_SPINE,
        Feature.AUTO_SPINE_ROLLUP,  # ⚠️ Partial support
        Feature.GENERATE_SERIES,
    },
    'mysql': {
        Feature.AUTO_SPINE,
        Feature.AUTO_SPINE_ROLLUP,  # ⚠️ Partial support
        # Feature.COLUMN_EXCLUDE - ❌ Not supported
        # Feature.GENERATE_SERIES - ❌ Not supported
        # Feature.SLICE_SYNTAX - 🐛 Buggy (Issue #77)
    },
    'sqlite': {
        # Very limited support
        # Feature.AUTO_SPINE - ❌ Not supported
        # Feature.COLUMN_EXCLUDE - ❌ Not supported
        # Feature.GENERATE_SERIES - ❌ Not supported
        # Feature.SLICE_SYNTAX - 🐛 Buggy (Issue #77)
    },
    'redshift': {
        Feature.AUTO_SPINE,
        Feature.AUTO_SPINE_ROLLUP,  # ⚠️ Partial support
        Feature.GENERATE_SERIES,
        # Feature.COLUMN_EXCLUDE - ❌ Not supported
        # Feature.SLICE_SYNTAX - 🐛 Buggy (Issue #77)
    },
}


def check_feature(feature: Feature, dialect: Optional[str]) -> bool:
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
    if dialect_lower == 'postgresql':
        dialect_lower = 'postgres'
    
    return feature in DIALECT_SUPPORT.get(dialect_lower, set())


def has_column_operators(preparsed_query: str) -> bool:
    """Detect if query uses column operators (except, rename, replace).
    
    This checks the preparsed SQL-like query for EXCEPT/EXCLUDE syntax
    that indicates column operators were used.
    
    Args:
        preparsed_query: The preparsed query string (after column operator transformation)
        
    Returns:
        True if column operators are detected, False otherwise
    """
    # Column operators transform to * EXCEPT(...) or * EXCLUDE(...)
    # Check for this pattern in SELECT clauses
    pattern = r'\*\s+(?:EXCEPT|EXCLUDE)\s*\('
    return bool(re.search(pattern, preparsed_query, re.IGNORECASE))


def has_slice_syntax(original_query: str) -> bool:
    """Detect if query uses slice syntax [start:end].
    
    Args:
        original_query: The original ASQL query string
        
    Returns:
        True if slice syntax is detected, False otherwise
    """
    # Look for Python-style slice syntax: [number:number] or [number:]
    # This is a simple pattern - actual parsing happens in preparser
    pattern = r'\[\s*\d+\s*:\s*\d*\s*\]'
    return bool(re.search(pattern, original_query))


def get_dialect_display_name(dialect: Optional[str]) -> str:
    """Get a user-friendly display name for a dialect.
    
    Args:
        dialect: SQL dialect name
        
    Returns:
        Display name (e.g., 'PostgreSQL' instead of 'postgres')
    """
    if not dialect:
        return 'Unknown'
    
    dialect_lower = dialect.lower()
    
    display_names = {
        'postgres': 'PostgreSQL',
        'postgresql': 'PostgreSQL',
        'bigquery': 'BigQuery',
        'snowflake': 'Snowflake',
        'duckdb': 'DuckDB',
        'mysql': 'MySQL',
        'sqlite': 'SQLite',
        'redshift': 'Redshift',
    }
    
    return display_names.get(dialect_lower, dialect.capitalize())
