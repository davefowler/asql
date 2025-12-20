"""Dialect-specific handling for list comprehensions."""

from __future__ import annotations

import re
from typing import Optional

from asql.errors import ASQLCompilationError


def fix_duckdb_list_comprehensions(sql: str, dialect: Optional[str]) -> str:
    """
    Convert ARRAY(SELECT ... FROM UNNEST(...)) to DuckDB's native list comprehension syntax.
    
    DuckDB supports native list comprehensions: [EXPR FOR VAR IN ARR]
    SQLGlot transpiles to ARRAY(SELECT ... FROM UNNEST(...)) which doesn't work in DuckDB.
    """
    if not dialect or dialect.lower() != "duckdb":
        return sql
    
    # Pattern: ARRAY(SELECT expr [AS alias] FROM UNNEST(array_col) AS var [WHERE condition])
    # Need to handle the AS alias that SQLGlot auto-adds
    pattern = r'ARRAY\s*\(\s*SELECT\s+(.+?)\s+(?:AS\s+\w+\s+)?FROM\s+UNNEST\s*\(\s*(\w+)\s*\)\s+AS\s+(\w+)(?:\s+WHERE\s+(.+?))?\s*\)'
    
    def replace_with_duckdb_syntax(match: re.Match) -> str:
        expr_with_alias = match.group(1).strip()
        array_col = match.group(2).strip()
        var_name = match.group(3).strip()
        where_cond = match.group(4).strip() if match.group(4) else None
        
        # Remove any AS alias from the expression (DuckDB doesn't support aliases in list comprehensions)
        # Pattern: expr AS alias -> expr
        expr = re.sub(r'\s+AS\s+\w+$', '', expr_with_alias, flags=re.IGNORECASE).strip()
        
        # Build DuckDB native syntax: [expr FOR var IN array_col [IF condition]]
        if where_cond:
            return f"[{expr} FOR {var_name} IN {array_col} IF {where_cond}]"
        else:
            return f"[{expr} FOR {var_name} IN {array_col}]"
    
    result = re.sub(pattern, replace_with_duckdb_syntax, sql, flags=re.IGNORECASE)
    return result


def check_snowflake_list_comprehensions(sql: str, dialect: Optional[str]) -> None:
    """
    Check for invalid Snowflake list comprehension syntax and raise helpful error.
    
    SQLGlot generates invalid syntax for Snowflake:
    [SELECT ... FROM TABLE(FLATTEN(...))]  ❌ Invalid
    
    This function detects this pattern and raises an error with a helpful message.
    """
    if not dialect or dialect.lower() != "snowflake":
        return
    
    # Pattern to match invalid Snowflake syntax: [SELECT ... FROM TABLE(FLATTEN(...))]
    pattern = r'\[SELECT\s+.+?\s+FROM\s+TABLE\(FLATTEN\([^)]+\)\)'
    
    if re.search(pattern, sql, re.IGNORECASE):
        raise ASQLCompilationError(
            "List comprehensions are not yet fully supported for Snowflake dialect. "
            "SQLGlot generates invalid syntax. "
            "As a workaround, you can use ARRAY_AGG with FLATTEN manually:\n"
            "  SELECT ARRAY_AGG(f.value) FROM table, TABLE(FLATTEN(INPUT => array_col)) AS f"
        )
