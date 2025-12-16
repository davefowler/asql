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

from asql.compiler import compile, compile_to_ast, get_preparsed
from asql.dialect import ASQL, ASQLDialect, register_asql_dialect
from asql.preparser import preparse_asql, ASQLPreParser
from asql.reverse_compiler import reverse_compile, detect_dialect

__version__ = "0.1.0"

__all__ = [
    # Main compilation functions
    "compile",
    "compile_to_ast",
    "get_preparsed",
    
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
]
