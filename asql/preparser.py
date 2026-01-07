"""Legacy shim for the ASQL pre-parser.

The implementation moved to `asql.preparse`.
"""

from asql.preparse import ASQLPreParser, PreParseResult, preparse_asql

__all__ = ["ASQLPreParser", "PreParseResult", "preparse_asql"]
