"""ASQL Dialect package.

This package provides the ASQL dialect for SQLGlot, consisting of:
- Tokenizer: Handles ASQL-specific token mappings
- Parser: Parses ASQL pipeline syntax
- Generator: Converts AST back to ASQL strings
- Dialect: The main dialect class connecting all components

Usage:
    import sqlglot
    import asql  # Registers the dialect
    
    # ASQL → SQL
    result = sqlglot.transpile("from users where id = 1", read="asql", write="postgres")
    
    # SQL → ASQL
    result = sqlglot.transpile("SELECT * FROM users WHERE id = 1", read="postgres", write="asql")
"""

from asql.dialect.dialect import ASQL, register_asql_dialect
from asql.dialect.generator import ASQLGenerator
from asql.dialect.parser import ASQLParser
from asql.dialect.tokenizer import ASQLTokenizer

__all__ = [
    "ASQL",
    "ASQLGenerator",
    "ASQLParser",
    "ASQLTokenizer",
    "register_asql_dialect",
]

# Ensure dialect is registered on package import
register_asql_dialect()
