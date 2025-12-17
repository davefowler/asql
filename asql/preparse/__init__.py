"""ASQL pre-parser package."""

from asql.preparse.preparser import ASQLPreParser, PreParseResult

def preparse_asql(text: str) -> str:
    """Pre-parse ASQL to SQL-like syntax."""
    return ASQLPreParser(text).preparse()

__all__ = ["ASQLPreParser", "PreParseResult", "preparse_asql"]
