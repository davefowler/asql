"""Dialect-specific handling for list comprehensions."""

from __future__ import annotations

import re
from typing import Optional

from asql.errors import ASQLCompilationError


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
