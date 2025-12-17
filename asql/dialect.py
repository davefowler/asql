"""ASQL dialect implementation for SQLGlot.

ASQL (Analytic SQL) is a human-readable query language that transpiles to SQL.
This dialect handles ASQL-specific syntax that can be tokenized and parsed
within SQLGlot's framework.

Note: Some ASQL features require pre-parsing (see preparser.py).
"""

from typing import Optional, List, Dict, Any
import sqlglot
from sqlglot import exp
from sqlglot.dialects.dialect import Dialect
from sqlglot.parser import Parser
from sqlglot.generator import Generator
from sqlglot.tokens import Tokenizer, TokenType


class ASQLTokenizer(Tokenizer):
    """Tokenizer for ASQL syntax."""
    
    # ASQL-specific keywords that map to existing token types
    KEYWORDS = {
        **Tokenizer.KEYWORDS,
        # ASQL aliases for SQL keywords
        "PROJECT": TokenType.SELECT,  # project is alias for SELECT
        "STASH": TokenType.VAR,  # for stash as
        "PER": TokenType.VAR,  # for per ... first/last by
        
        # String matching keywords (ASQL-specific)
        "CONTAINS": TokenType.VAR,
        "STARTS": TokenType.VAR,
        "ENDS": TokenType.VAR,
        
        # Window operation keywords
        "PRIOR": TokenType.VAR,
        "NEXT": TokenType.VAR,
        
        # Conditional expression keywords
        "OTHERWISE": TokenType.ELSE,  # alias for ELSE in when expressions
        
        # Natural language aggregation helpers
        "TOTAL": TokenType.VAR,  # alias for SUM
        "AVERAGE": TokenType.VAR,  # alias for AVG
    }
    
    # Single character tokens
    SINGLE_TOKENS = {
        **Tokenizer.SINGLE_TOKENS,
        # Note: # is already handled by preparser
    }
    
    def _scan(self) -> None:
        """Override to handle ASQL-specific token scanning."""
        if self._end:
            return
        
        # Handle ?? as COALESCE (nullish coalescing)
        # Note: This is mostly handled by preparser, but we keep it here for robustness
        if self._char == "?" and self._peek == "?":
            self._advance()
            self._advance()
            self._add(TokenType.COALESCE, "??")
            return
        
        # Handle @ date literals (mostly handled by preparser)
        if self._char == "@" and self._peek and self._peek.isdigit():
            self._scan_date_literal()
            return
        
        # Fall back to standard scanning
        super()._scan()
    
    def _scan_date_literal(self) -> None:
        """Scan @YYYY-MM-DD as a date literal."""
        self._advance()  # skip @
        text = ""
        
        # Collect date characters (digits and dashes)
        while not self._end and (self._char.isdigit() or self._char == "-"):
            text += self._char
            self._advance()
        
        # Check for time component (T or space followed by time)
        if not self._end and self._char in ("T", " "):
            time_sep = self._char
            self._advance()
            
            # Check if this is actually a time
            if not self._end and self._char.isdigit():
                text += time_sep
                while not self._end and (self._char.isdigit() or self._char == ":"):
                    text += self._char
                    self._advance()
        
        # Add as string literal (will be parsed as date/timestamp)
        self._add(TokenType.STRING, text)


class ASQLParser(Parser):
    """Parser for ASQL pipeline syntax."""
    
    # Custom function parsers for ASQL-specific functions
    FUNCTIONS = {
        **Parser.FUNCTIONS,
        # Aggregate aliases
        "TOTAL": exp.Sum.from_arg_list,
        "AVERAGE": exp.Avg.from_arg_list,
        
        # Window utility functions
        "PRIOR": exp.Lag.from_arg_list,  # prior(col) -> LAG(col, 1)
        "NEXT": exp.Lead.from_arg_list,  # next(col) -> LEAD(col, 1)
        
        # Running aggregates
        "RUNNING_SUM": lambda args: exp.Sum(this=args[0]),
        "RUNNING_AVG": lambda args: exp.Avg(this=args[0]),
        "RUNNING_COUNT": lambda args: exp.Count(this=args[0] if args else exp.Star()),
        
        # Rolling aggregates (with window size)
        "ROLLING_SUM": lambda args: exp.Sum(this=args[0]),
        "ROLLING_AVG": lambda args: exp.Avg(this=args[0]),
        
        # Ordered aggregates
        "ARG_MAX": lambda args: exp.ArgMax(this=args[0], expression=args[1] if len(args) > 1 else None),
        "ARG_MIN": lambda args: exp.ArgMin(this=args[0], expression=args[1] if len(args) > 1 else None),
    }
    
    def _parse_order(
        self,
        this: Optional[exp.Expression] = None,
        skip_order_token: bool = False,
    ) -> Optional[exp.Order]:
        """
        Override ORDER BY parsing to handle ASQL's -column for DESC.
        
        Note: The preparser already handles -col → col DESC transformation,
        but this is here for robustness if parsing happens without preparsing.
        """
        return super()._parse_order(this, skip_order_token)
    
    def _parse_unary(self) -> Optional[exp.Expression]:
        """Parse unary expressions, including ASQL's natural aggregate shorthand."""
        return super()._parse_unary()


class ASQLGenerator(Generator):
    """Generator for outputting SQL from ASQL AST.
    
    Note: We typically use target dialect generators (postgres, bigquery, etc.)
    for final output. This is mainly for debugging/introspection.
    """
    
    TRANSFORMS = {
        **Generator.TRANSFORMS,
    }
    
    # Map ASQL-specific expression types to SQL output
    TYPE_MAPPING = {
        **Generator.TYPE_MAPPING,
    }


class ASQL(Dialect):
    """
    ASQL (Analytic SQL) dialect for SQLGlot.
    
    ASQL is a human-readable query language that transpiles to SQL.
    This dialect handles ASQL-specific syntax that can be tokenized
    and parsed within SQLGlot's framework.
    
    Features handled in this dialect:
    - # as COUNT(*) (after preparser transformation)
    - == as equality (after preparser transformation to =)
    - Natural aggregate functions (total, average)
    - Window utility functions (prior, next, running_*, rolling_*)
    
    Features handled by preparser (before this dialect):
    - FROM-first syntax
    - Pipeline operators (|)
    - Aggregate blocks: group by x (agg1, agg2)
    - Stash as (CTEs)
    - Natural aggregates: sum amount → sum(amount)
    - Date expressions: 7 days ago
    - Underscore/space normalization
    
    Usage:
        from asql.preparser import preparse_asql
        
        # Pre-parse ASQL to SQL-like syntax
        sql_like = preparse_asql(asql_text)
        
        # Parse with ASQL dialect (for any remaining ASQL-specific syntax)
        ast = sqlglot.parse_one(sql_like, dialect="asql")
        
        # Generate target SQL
        sql = ast.sql(dialect="postgres")  # or bigquery, snowflake, etc.
    """
    
    class Tokenizer(ASQLTokenizer):
        pass
    
    class Parser(ASQLParser):
        pass
    
    class Generator(ASQLGenerator):
        pass


# Register the dialect with SQLGlot
# This allows using dialect="asql" in parse_one() and sql() methods
def register_asql_dialect() -> None:
    """Register the ASQL dialect with SQLGlot."""
    # Check if already registered
    try:
        Dialect.get_or_raise("asql")
    except ValueError:
        # Not registered, register it
        Dialect["asql"] = ASQL


# Auto-register on import
register_asql_dialect()


# Also keep the old name for backwards compatibility
ASQLDialect = ASQL
