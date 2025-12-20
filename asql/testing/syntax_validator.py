"""Syntax validation for ASQL across all supported dialects using SQLGlot.

This module provides utilities to validate that generated SQL is syntactically
valid for a target dialect, without requiring actual database connections.
"""

from typing import Tuple, List, Dict

import sqlglot

# All dialects we officially support and test against
SUPPORTED_DIALECTS: List[str] = [
    'duckdb',
    'postgres',
    'mysql',
    'snowflake',
    'bigquery',
    'redshift',
    'databricks',
    'trino',
]

# Known dialect limitations that we document and xfail in tests
# Maps dialect -> list of feature tags that don't work
DIALECT_LIMITATIONS: Dict[str, List[str]] = {
    # MySQL doesn't support QUALIFY or slice syntax
    'mysql': ['qualify_clause', 'slice_syntax'],
    # Redshift has limited window function support
    'redshift': ['list_comprehension'],
    # Trino doesn't support QUALIFY natively (though SQLGlot can transpile)
    'trino': ['qualify_clause'],
}


def validate_syntax(sql: str, dialect: str) -> Tuple[bool, str]:
    """Validate SQL syntax for a dialect using SQLGlot.
    
    This parses the SQL using SQLGlot's dialect-specific parser and then
    attempts to regenerate SQL, which catches additional issues.
    
    Args:
        sql: The SQL string to validate
        dialect: Target dialect (e.g., 'postgres', 'snowflake')
    
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if SQL is syntactically valid
        - error_message: Empty string if valid, otherwise the error details
    """
    try:
        # Parse with the target dialect
        ast = sqlglot.parse_one(sql, dialect=dialect)
        
        # Also try to regenerate - catches some additional issues
        # where parsing succeeds but the AST is malformed
        regenerated = ast.sql(dialect=dialect)
        
        # Basic sanity check - output shouldn't be empty
        if not regenerated.strip():
            return False, "Generated SQL is empty"
        
        return True, ""
    except sqlglot.errors.ParseError as e:
        return False, f"Parse error: {e}"
    except Exception as e:
        return False, f"Validation error: {e}"


def validate_syntax_all_dialects(sql_by_dialect: Dict[str, str]) -> Dict[str, Tuple[bool, str]]:
    """Validate SQL syntax across multiple dialects.
    
    Args:
        sql_by_dialect: Dictionary mapping dialect name to generated SQL
    
    Returns:
        Dictionary mapping dialect name to (is_valid, error_message) tuple
    """
    results: Dict[str, Tuple[bool, str]] = {}
    for dialect, sql in sql_by_dialect.items():
        results[dialect] = validate_syntax(sql, dialect)
    return results


def is_feature_supported(dialect: str, feature: str) -> bool:
    """Check if a feature is supported by a dialect.
    
    Args:
        dialect: Target dialect (e.g., 'postgres', 'mysql')
        feature: Feature tag (e.g., 'qualify_clause', 'slice_syntax')
    
    Returns:
        True if the feature is supported (not in the limitations list)
    """
    limitations = DIALECT_LIMITATIONS.get(dialect, [])
    return feature not in limitations
