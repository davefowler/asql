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
    2. New FROM at start of line (ASQL natural): A `from` at column 0 starts a new query
    
    Respects strings and parentheses when splitting.
    
    Examples:
        "from users; from orders"  -> ["from users", "from orders"]
        "from users\\nfrom orders" -> ["from users", "from orders"]
        "from users\\n  where x"   -> ["from users\\n  where x"] (indented = same query)
    """
    statements: List[str] = []
    current: List[str] = []
    depth = 0
    in_string: Optional[str] = None
    at_line_start = True  # Track if we're at the start of a line
    
    i = 0
    while i < len(text):
        char = text[i]
        
        # String handling
        if char in ('"', "'") and (i == 0 or text[i-1] != '\\'):
            if in_string == char:
                in_string = None
            elif in_string is None:
                in_string = char
        
        # Track line starts
        if char == '\n':
            at_line_start = True
            current.append(char)
            i += 1
            continue
        
        # Check for 'from' at the start of a line (not indented)
        # This starts a new query if we already have content
        if (at_line_start and 
            in_string is None and 
            depth == 0 and
            text[i:i+4].lower() == 'from' and
            (i + 4 >= len(text) or not text[i+4].isalnum() and text[i+4] != '_')):
            
            # Check if current has meaningful content (not just whitespace)
            current_text = ''.join(current).strip()
            if current_text:
                # This is a new FROM starting a new query
                statements.append(current_text)
                current = []
        
        # Parentheses tracking (only outside strings)
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
                at_line_start = True  # After semicolon, treat as line start
                continue
        
        # Update at_line_start: only whitespace keeps us at line start
        if char not in ' \t':
            at_line_start = False
        
        current.append(char)
        i += 1
    
    # Don't forget the last statement
    if current:
        stmt = ''.join(current).strip()
        if stmt:
            statements.append(stmt)
    
    return statements if statements else [text.strip()]


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
