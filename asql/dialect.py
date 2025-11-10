"""ASQL dialect implementation for SQLGlot."""

from typing import Optional
import sqlglot
from sqlglot import exp, tokens
from sqlglot.dialects.dialect import Dialect
from sqlglot.parser import Parser
from sqlglot.generator import Generator
from sqlglot.tokens import Tokenizer, TokenType


class ASQLDialect(Dialect):
    """ASQL dialect - a pipeline-based query language."""
    
    class Tokenizer(Tokenizer):
        """Tokenizer for ASQL syntax."""
        
        # Only override keywords that need special handling
        # Most keywords are already in the base Tokenizer.KEYWORDS
        KEYWORDS = {
            **Tokenizer.KEYWORDS,
            # ASQL-specific keywords that map to existing token types
            "IF": TokenType.WHERE,  # IF is alias for WHERE
            "PROJECT": TokenType.SELECT,  # PROJECT is alias for SELECT
            "SORT": TokenType.ORDER_BY,  # SORT maps to ORDER BY
            "TAKE": TokenType.LIMIT,
            "DERIVE": TokenType.ALIAS,  # Temporary, will need custom handling
            "SET": TokenType.WITH,
            "LET": TokenType.WITH,  # LET is alias for SET
        }
        
        # Add # token for ASQL count syntax
        # Check if HASH exists, otherwise use a generic identifier
        SINGLE_TOKENS = {
            **Tokenizer.SINGLE_TOKENS,
        }
        
        # Handle # token separately if needed
        # For now, we'll parse it as part of expressions
        
        # ASQL uses == instead of = for equality
        def _parse_string(self) -> Optional[tokens.Token]:
            """Override to handle ASQL-specific string parsing."""
            return super()._parse_string()
        
        def _parse_identifier(self) -> Optional[tokens.Token]:
            """Override to handle ASQL-specific identifier parsing."""
            return super()._parse_identifier()
    
    class Parser(Parser):
        """Parser for ASQL pipeline syntax."""
        
        def _parse_select(self) -> exp.Select:
            """Parse SELECT statement - ASQL starts with FROM, not SELECT."""
            # ASQL queries start with FROM, so we need custom parsing
            # For now, delegate to parent but we'll override parse() method
            return super()._parse_select()
        
        def parse(self, raw: str) -> list[exp.Expression]:
            """Parse ASQL query - starts with FROM, not SELECT."""
            # ASQL syntax: "from users where status == 'active'"
            # Need to transform to SQL AST
            
            # For now, try to detect if it's ASQL syntax
            raw_lower = raw.strip().lower()
            if raw_lower.startswith("from "):
                # This is ASQL syntax, need custom parsing
                return self._parse_asql_query(raw)
            else:
                # Fall back to standard SQL parsing
                return super().parse(raw)
        
        def _parse_asql_query(self, raw: str) -> list[exp.Expression]:
            """Parse ASQL query starting with FROM."""
            # TODO: Implement ASQL parsing
            # For now, return empty list
            raise NotImplementedError("ASQL parsing not yet implemented")
    
    class Generator(Generator):
        """Generator for ASQL dialect."""
        
        TRANSFORMS = {
            **Generator.TRANSFORMS,
            # Transform == to = for SQL
            exp.EQ: lambda self, e: self.binary(e, "="),
        }
        
        def eq_sql(self, expression: exp.EQ) -> str:
            """Generate SQL for == operator (ASQL uses ==, SQL uses =)."""
            return self.binary(expression, "=")

