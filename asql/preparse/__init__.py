"""ASQL pre-parser package."""

import re
from typing import List, Optional, TYPE_CHECKING

from asql.preparse.preparser import ASQLPreParser, PreParseResult

if TYPE_CHECKING:
    from asql.config import CompileSettings


def _split_statements(text: str) -> List[str]:
    """Split text into individual statements by semicolons or new FROM clauses.
    
    Supports two ways to separate queries:
    1. Semicolons (SQL standard): "from a; from b"
    2. New FROM at start of line (ASQL natural): "from a\\n\\nfrom b"
    
    Respects strings and parentheses when splitting.
    """
    statements: List[str] = []
    current: List[str] = []
    depth = 0
    in_string: Optional[str] = None
    
    # First, split by semicolons (respecting strings and parens)
    i = 0
    while i < len(text):
        char = text[i]
        
        # String handling
        if char in ('"', "'") and (i == 0 or text[i-1] != '\\'):
            if in_string == char:
                in_string = None
            elif in_string is None:
                in_string = char
        
        # Parentheses
        if in_string is None:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            elif char == ';' and depth == 0:
                stmt = ''.join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
                i += 1
                continue
        
        current.append(char)
        i += 1
    
    # Don't forget the last statement
    if current:
        stmt = ''.join(current).strip()
        if stmt:
            statements.append(stmt)
    
    # Now, for each statement, check if it contains multiple queries
    # separated by blank lines followed by FROM at column 0
    final_statements: List[str] = []
    
    for stmt in statements:
        # Pattern: blank line(s) followed by 'from' at the start of a line (case-insensitive)
        # This indicates a new query without explicit semicolon
        parts = re.split(r'\n\s*\n(?=\s*(?:from|FROM|From)\s)', stmt)
        for part in parts:
            part = part.strip()
            if part:
                final_statements.append(part)
    
    return final_statements if final_statements else [text.strip()]


def preparse_asql(text: str, settings: Optional["CompileSettings"] = None) -> str:
    """Pre-parse ASQL to SQL-like syntax.
    
    Args:
        text: ASQL query text (can contain multiple statements separated by ; or blank lines)
        settings: Optional compile settings (includes schema for join inference)
        
    Returns:
        SQL-like text ready for SQLGlot parsing
    
    Multiple statements are supported:
    - Separated by semicolons: "from users; from orders"
    - Separated by blank lines with new FROM: "from users\\n\\nfrom orders"
    
    Each statement is pre-parsed independently, then joined with semicolons.
    """
    statements = _split_statements(text)
    
    if len(statements) == 1:
        # Single statement - use original behavior
        return ASQLPreParser(statements[0], settings=settings).preparse()
    
    # Multiple statements - preparse each independently
    preparsed_statements: List[str] = []
    for stmt in statements:
        preparsed = ASQLPreParser(stmt, settings=settings).preparse()
        preparsed_statements.append(preparsed)
    
    return ";\n\n".join(preparsed_statements)


__all__ = ["ASQLPreParser", "PreParseResult", "preparse_asql"]
