"""ASQL: Analytic SQL - A modern, pipeline-based query language.

ASQL is a human-readable query language that transpiles to SQL.
It features:
- FROM-first syntax (more natural reading order)
- Pipeline operators for data transformation
- Natural language aggregations
- Clean date/time handling
- Underscore/space flexibility in function names

Example:
    >>> from asql import compile
    >>> compile("from users where status = 'active' limit 10")
    "SELECT * FROM users WHERE status = 'active' LIMIT 10"
    
    >>> compile("from sales group by region (sum(amount) as revenue)")
    "SELECT region, SUM(amount) AS revenue FROM sales GROUP BY region"

The compilation pipeline:
1. Pre-parser: Transforms ASQL structural syntax to SQL-like syntax
2. SQLGlot: Parses the SQL-like syntax into an AST
3. Generator: Outputs SQL in the target dialect
"""

from asql.compiler import compile, compile_to_ast, get_preparsed, get_settings_from_query
from asql.dialect import ASQL, ASQLDialect, register_asql_dialect
from asql.preparser import preparse_asql, ASQLPreParser
from asql.reverse_compiler import reverse_compile, detect_dialect
from asql.config import ASQLConfig, StyleConfig, CompileSettings

# Version is read from pyproject.toml via importlib.metadata
# This ensures a single source of truth for the version
try:
    from importlib.metadata import version as _get_version
    __version__ = _get_version("asql")
except Exception:
    # Fallback for when package is not installed (e.g., running from source without pip install -e)
    __version__ = "0.1.0"


def normalize(asql_query: str, config: ASQLConfig = None) -> str:
    """
    Normalize ASQL to a consistent style based on config.
    
    This is ASQL → SQL → ASQL transpilation that applies
    the configured style preferences.
    
    Args:
        asql_query: Input ASQL query (any style)
        config: Style configuration (uses defaults if None)
    
    Returns:
        ASQL query in the configured style
    """
    if config is None:
        config = ASQLConfig()
    
    # Step 1: ASQL → SQL
    sql = compile(asql_query, dialect=config.dialect)
    
    # Step 2: SQL → ASQL (with config)
    normalized = reverse_compile(sql, source_dialect=config.dialect, config=config)
    
    return normalized


__all__ = [
    # Version
    "__version__",
    
    # Main compilation functions
    "compile",
    "compile_to_ast",
    "get_preparsed",
    "get_settings_from_query",
    "normalize",
    
    # Pre-parser
    "preparse_asql",
    "ASQLPreParser",
    
    # Dialect
    "ASQL",
    "ASQLDialect",
    "register_asql_dialect",
    
    # Reverse compilation
    "reverse_compile",
    "detect_dialect",
    
    # Configuration
    "ASQLConfig",
    "StyleConfig",
    "CompileSettings",
]
