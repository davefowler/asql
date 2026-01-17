"""ASQL Dialect definition and registration.

This is the main dialect class that connects the tokenizer, parser, and generator.
"""

from sqlglot.dialects.dialect import Dialect

from asql.dialect.generator import ASQLGenerator
from asql.dialect.parser import ASQLParser
from asql.dialect.tokenizer import ASQLTokenizer


class ASQL(Dialect):
    """ASQL (Analytic SQL) dialect for SQLGlot.
    
    ASQL is a human-readable, pipeline-based query language that transpiles to SQL.
    This dialect uses SQLGlot's TRANSFORM_PARSERS pattern (like PRQL) for proper
    pipeline semantics.
    
    Key features handled:
    - FROM-first syntax: `from users where status = 'active'`
    - Pipeline operators: `from users | where x | group by y`
    - Proper CTE wrapping: `group by X | where Y` → CTE + WHERE
    - Descending order shorthand: `-column` → `column DESC`
    - NULL equality: `== null` → `IS NULL`
    - Ternary operator: `x ? y : z` → `CASE WHEN x THEN y ELSE z END`
    - Relative dates: `7 days ago` → `CURRENT_TIMESTAMP - INTERVAL '7 days'`
    - Date arithmetic: `col + 7 days` → `col + INTERVAL '7 days'`
    
    Features still handled by preparser (syntactic sugar):
    - `#` → COUNT(*)
    - `@date` → DATE literal
    - Natural aggregates: `sum amount` → `sum(amount)`
    - Join operators (`&`, `<&`, `&>`)
    - etc.
    """
    
    # Dialect configuration constants (following ClickHouse pattern)
    DPIPE_IS_STRING_CONCAT = True  # || is string concatenation, not OR
    NORMALIZE_FUNCTIONS: bool | str = False  # Preserve function name casing
    
    class Tokenizer(ASQLTokenizer):
        pass
    
    class Parser(ASQLParser):
        pass
    
    class Generator(ASQLGenerator):
        pass


# Register the dialect with SQLGlot
def register_asql_dialect() -> None:
    """Register the ASQL dialect with SQLGlot."""
    if "asql" not in Dialect._classes:
        Dialect["asql"] = ASQL


# Auto-register on import
register_asql_dialect()
