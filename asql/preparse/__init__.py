"""ASQL pre-parser package."""

import re
from typing import List, Optional, TYPE_CHECKING

from asql.preparse.preparser import ASQLPreParser, PreParseResult

if TYPE_CHECKING:
    from asql.config import CompileSettings


def _is_set_statement(text: str) -> bool:
    """Check if text is a SET statement (configuration, not a query)."""
    stripped = text.strip().upper()
    return stripped.startswith('SET ') and '=' in stripped


def _split_statements(text: str) -> List[str]:
    """Split text into individual statements.
    
    Query separators:
    1. Semicolons (SQL standard): "from a; from b"
    2. Blank lines (ASQL natural): "from a\\n\\nfrom b"
    
    SET statements are kept with the query they configure (not split separately).
    
    Respects strings and parentheses when splitting.
    
    Examples:
        "from users; from orders"      -> ["from users", "from orders"]
        "from users\\n\\nfrom orders"  -> ["from users", "from orders"]
        "from users\\n  where x"       -> ["from users\\n  where x"] (no blank line)
        "SET x = 1; from users"        -> ["SET x = 1; from users"] (SET stays with query)
    """
    depth = 0
    in_string: Optional[str] = None
    
    # First pass: split by semicolons (respecting strings and parens)
    # BUT keep SET statements attached to the next query
    chunks: List[str] = []
    current: List[str] = []
    pending_sets: List[str] = []  # SET statements waiting for a query
    
    i = 0
    while i < len(text):
        char = text[i]
        
        # String handling
        if char in ('"', "'") and (i == 0 or text[i-1] != '\\'):
            if in_string == char:
                in_string = None
            elif in_string is None:
                in_string = char
        
        # Parentheses tracking (only outside strings)
        if in_string is None:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            elif char == ';' and depth == 0:
                chunk = ''.join(current).strip()
                if chunk:
                    if _is_set_statement(chunk):
                        # Keep SET statements pending until we find a real query
                        pending_sets.append(chunk)
                    else:
                        # Prepend any pending SET statements
                        if pending_sets:
                            chunk = '; '.join(pending_sets) + '; ' + chunk
                            pending_sets = []
                        chunks.append(chunk)
                current = []
                i += 1
                continue
        
        current.append(char)
        i += 1
    
    # Don't forget the last chunk
    if current:
        chunk = ''.join(current).strip()
        if chunk:
            if _is_set_statement(chunk):
                pending_sets.append(chunk)
            else:
                if pending_sets:
                    chunk = '; '.join(pending_sets) + '; ' + chunk
                    pending_sets = []
                chunks.append(chunk)
    
    # If only SET statements remain, add them as a chunk (rare edge case)
    if pending_sets and not chunks:
        chunks.append('; '.join(pending_sets))
    elif pending_sets:
        # Attach remaining SETs to the last chunk
        chunks[-1] = '; '.join(pending_sets) + '; ' + chunks[-1]
    
    # Second pass: split each chunk by blank lines
    statements: List[str] = []
    for chunk in chunks:
        lines = chunk.split('\n')
        current_block: List[str] = []
        
        for line in lines:
            stripped = line.strip()
            
            # Blank line = query separator (but not if we only have SET statements so far)
            if not stripped:
                if current_block:
                    block_text = '\n'.join(current_block).strip()
                    # Only split if the block is a real query (not just SET statements)
                    if block_text and not all(_is_set_statement(s.strip()) for s in block_text.split(';') if s.strip()):
                        statements.append(block_text)
                        current_block = []
                    # If it's just SETs, keep them in current_block for the next query
            else:
                current_block.append(line)
        
        # Don't forget the last block
        if current_block:
            block_text = '\n'.join(current_block).strip()
            if block_text:
                statements.append(block_text)
    
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
