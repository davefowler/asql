"""ASQL pre-parser package."""

from typing import Optional, TYPE_CHECKING

from asql.preparse.preparser import ASQLPreParser, PreParseResult

if TYPE_CHECKING:
    from asql.config import CompileSettings

def preparse_asql(text: str, settings: Optional["CompileSettings"] = None) -> str:
    """Pre-parse ASQL to SQL-like syntax.
    
    Args:
        text: ASQL query text
        settings: Optional compile settings (includes schema for join inference)
        
    Returns:
        SQL-like text ready for SQLGlot parsing
    """
    return ASQLPreParser(text, settings=settings).preparse()

__all__ = ["ASQLPreParser", "PreParseResult", "preparse_asql"]
