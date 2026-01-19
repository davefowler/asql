"""ASQL: Analytic SQL - A modern, pipeline-based query language.

ASQL is a human-readable query language that transpiles to SQL via SQLGlot.

Usage:
    >>> import asql
    >>> 
    >>> # ASQL → SQL (recommended way)
    >>> asql.transpile("from users where active", write="postgres")[0]
    'SELECT * FROM users WHERE active'
    >>> 
    >>> # With spine for gap-filling
    >>> asql.transpile("from orders spine by month(date) (sum(amount))", write="snowflake")[0]
    'WITH date_spine AS (...) SELECT ...'
    >>> 
    >>> # With settings
    >>> asql.transpile(query, write="postgres", week_start="sunday")[0]
    >>> 
    >>> # SQL → ASQL
    >>> import sqlglot
    >>> sqlglot.transpile("SELECT * FROM users", read="postgres", write="asql")[0]
    'from users'

For simple passthrough without ASQL transforms, you can use sqlglot.transpile() directly:
    >>> sqlglot.transpile("from users", read="asql", write="postgres")[0]
"""

from asql.dialect import ASQL, register_asql_dialect
from asql.visual_dialect import VisualASQL, register_visual_asql_dialect
from asql.config import ASQLConfig, StyleConfig, CompileSettings
from asql.transpile import transpile, transpile_one
from asql.expressions import Spine, CohortBy

__version__ = "0.1.0"

# Register ASQL dialect on import
register_asql_dialect()

__all__ = [
    # Main entry point
    "transpile",
    "transpile_one",
    
    # Dialects
    "ASQL",
    "register_asql_dialect",
    "VisualASQL",
    "register_visual_asql_dialect",
    
    # Configuration
    "ASQLConfig",
    "StyleConfig",
    "CompileSettings",
    
    # Custom AST nodes
    "Spine",
    "CohortBy",
]
