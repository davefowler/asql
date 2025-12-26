"""ASQL pre-parser package."""

from typing import List, Optional, TYPE_CHECKING

from asql.preparse.preparser import ASQLPreParser, PreParseResult

if TYPE_CHECKING:
    from asql.config import CompileSettings

# Dialects that support native PIVOT syntax
NATIVE_PIVOT_DIALECTS = frozenset({"duckdb", "snowflake", "bigquery"})


def _has_multi_statement_cte_pattern(text: str) -> bool:
    """Check if text contains multi-statement CTE patterns that use blank lines.
    
    These patterns indicate that blank-line-separated statements should
    be kept together for the preparser to handle:
    - 'stash as <name>' - stash-based CTEs  
    - 'with <name> = from' - with-equals CTEs
    
    IMPORTANT: Only applies when there are NO semicolons in the text.
    Semicolons are explicit statement separators and take precedence.
    """
    import re
    
    # If there are semicolons, let the normal splitting handle it
    # (semicolons are explicit statement separators)
    if ';' in text:
        return False
    
    # Check for 'stash as name' pattern
    if re.search(r'\bstash\s+as\s+\w+', text, re.IGNORECASE):
        return True
    # Check for 'with name = from' pattern
    if re.search(r'\bwith\s+\w+\s*=\s*from\b', text, re.IGNORECASE):
        return True
    return False


def _split_statements(text: str) -> List[str]:
    """Split text into individual statements.
    
    Query separators:
    1. Semicolons (SQL standard): "from a; from b"
    2. Blank lines (ASQL natural): "from a\\n\\nfrom b"
    
    EXCEPTION: If text contains 'stash as <name>' patterns, we keep it as a
    single statement and let the MultiStatementMixin handle it. This allows
    multi-statement stash-based CTEs to work correctly.
    
    Valid statements can start with:
    - FROM (queries)
    - SET (global configuration)
    - WITH (CTEs, for SQL compatibility)
    
    Respects strings and parentheses when splitting.
    
    Examples:
        "from users; from orders"      -> ["from users", "from orders"]
        "from users\\n\\nfrom orders"  -> ["from users", "from orders"]
        "from users\\n  where x"       -> ["from users\\n  where x"] (no blank line)
        "SET x = 1"                    -> ["SET x = 1"] (standalone SET is valid)
        "from a stash as x\\n\\nfrom x" -> kept as single statement for stash handling
    """
    # If text contains multi-statement CTE patterns, keep it as a single statement
    # so the preparser can handle CTEs and their references together
    if _has_multi_statement_cte_pattern(text):
        return [text.strip()]
    
    depth = 0
    in_string: Optional[str] = None
    
    # First pass: split by semicolons (respecting strings and parens)
    chunks: List[str] = []
    current: List[str] = []
    
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
            chunks.append(chunk)
    
    # Second pass: split each chunk by blank lines
    statements: List[str] = []
    for chunk in chunks:
        lines = chunk.split('\n')
        current_block: List[str] = []
        
        for line in lines:
            stripped = line.strip()
            
            # Blank line = query separator
            if not stripped:
                if current_block:
                    block_text = '\n'.join(current_block).strip()
                    if block_text:
                        statements.append(block_text)
                    current_block = []
            else:
                current_block.append(line)
        
        # Don't forget the last block
        if current_block:
            block_text = '\n'.join(current_block).strip()
            if block_text:
                statements.append(block_text)
    
    return statements if statements else [text.strip()]


def preparse_asql(
    text: str,
    settings: Optional["CompileSettings"] = None,
    dialect: Optional[str] = None,
) -> str:
    """Pre-parse ASQL to SQL-like syntax.
    
    Args:
        text: ASQL query text (can contain multiple statements separated by ; or blank lines)
        settings: Optional compile settings (includes schema for join inference)
        dialect: Optional target SQL dialect (affects dialect-specific transformations like pivot)
        
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
        return ASQLPreParser(statements[0], settings=settings, dialect=dialect).preparse()
    
    # Multiple statements - preparse each independently
    preparsed_statements: List[str] = []
    for stmt in statements:
        preparsed = ASQLPreParser(stmt, settings=settings, dialect=dialect).preparse()
        # Strip trailing semicolons to avoid double semicolons when joining
        preparsed = preparsed.rstrip().rstrip(';').rstrip()
        preparsed_statements.append(preparsed)
    
    return ";\n\n".join(preparsed_statements)


__all__ = ["ASQLPreParser", "PreParseResult", "preparse_asql"]
