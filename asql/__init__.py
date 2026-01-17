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

For SQL → ASQL conversion, use sqlglot.transpile:
    >>> import sqlglot
    >>> sqlglot.transpile("SELECT * FROM users", write="asql")[0]
    'from users'

The compilation pipeline:
1. SQLGlot ASQL Dialect: Parses ASQL syntax directly into an AST
2. Compiler transforms: Apply ASQL-specific transformations to the AST
3. Generator: Outputs SQL in the target dialect
"""

from asql.compiler import compile, compile_to_ast, get_settings_from_query
from asql.dialect import ASQL, register_asql_dialect
from asql.config import ASQLConfig, StyleConfig, CompileSettings

__version__ = "0.1.0"


__all__ = [
    # Main compilation functions
    "compile",
    "compile_to_ast",
    "get_settings_from_query",
    
    # Dialect
    "ASQL",
    "register_asql_dialect",
    
    # Configuration
    "ASQLConfig",
    "StyleConfig",
    "CompileSettings",
]
