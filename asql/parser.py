"""ASQL parser - parses ASQL syntax into SQLGlot AST."""

import re
from typing import List, Optional
from sqlglot import exp
from sqlglot.errors import ParseError

from asql.errors import ASQLSyntaxError


class ASQLParser:
    """Parser for ASQL pipeline syntax."""
    
    def __init__(self, text: str):
        self.text = text.strip()
        self.pos = 0
        self.lines = self.text.split('\n')
        self.current_line = 0
    
    def parse(self) -> exp.Select:
        """
        Parse ASQL query into SQLGlot AST.
        
        Returns:
            SQLGlot Select expression
            
        Raises:
            ASQLSyntaxError: If syntax is invalid
        """
        if not self.text:
            raise ASQLSyntaxError("Empty ASQL query")
        
        # Parse FROM clause (required, must be first)
        from_expr = self._parse_from()
        
        # Build SELECT statement
        select_expr = exp.Select()
        select_expr.set("from", from_expr)
        
        # Parse pipeline operators
        while self._has_more():
            self._skip_whitespace()
            if not self._has_more():
                break
            
            # Check for WHERE
            if self._peek_keyword("where") or self._peek_keyword("if"):
                where_expr = self._parse_where()
                select_expr.set("where", where_expr)
            # Check for SELECT
            elif self._peek_keyword("select") or self._peek_keyword("project"):
                select_list = self._parse_select_list()
                select_expr.set("expressions", select_list)
            else:
                # Unknown operator, stop parsing
                break
        
        # If no SELECT was specified, default to SELECT *
        if not hasattr(select_expr, "expressions") or not select_expr.expressions:
            select_expr.set("expressions", [exp.Star()])
        
        return select_expr
    
    def _parse_from(self) -> exp.From:
        """Parse FROM clause."""
        if not self._peek_keyword("from"):
            raise ASQLSyntaxError("ASQL query must start with 'from'")
        
        self._consume_keyword("from")
        self._skip_whitespace()
        
        # Parse table name
        table_name = self._parse_identifier()
        if not table_name:
            raise ASQLSyntaxError("Expected table name after 'from'")
        
        table = exp.Table(this=exp.Identifier(this=table_name))
        return exp.From(this=table)
    
    def _parse_where(self) -> exp.Where:
        """Parse WHERE clause."""
        self._consume_keyword("where") or self._consume_keyword("if")
        self._skip_whitespace()
        
        # Parse condition (simplified for now)
        # TODO: Implement full expression parsing
        condition = self._parse_expression()
        
        return exp.Where(this=condition)
    
    def _parse_select_list(self) -> List[exp.Expression]:
        """Parse SELECT column list."""
        self._consume_keyword("select") or self._consume_keyword("project")
        self._skip_whitespace()
        
        columns = []
        
        # Check for *
        if self._peek() == "*":
            self._consume("*")
            return [exp.Star()]
        
        # Parse column list
        while True:
            col = self._parse_column()
            if col:
                columns.append(col)
            
            self._skip_whitespace()
            if self._peek() == ",":
                self._consume(",")
                self._skip_whitespace()
            else:
                break
        
        return columns
    
    def _parse_column(self) -> Optional[exp.Expression]:
        """Parse a column reference."""
        identifier = self._parse_identifier()
        if identifier:
            return exp.Column(this=exp.Identifier(this=identifier))
        return None
    
    def _parse_expression(self) -> exp.Expression:
        """Parse an expression (simplified - just handles == for now)."""
        # TODO: Implement full expression parsing
        # For now, handle simple comparisons: column == value
        
        left = self._parse_identifier()
        if not left:
            raise ASQLSyntaxError("Expected expression")
        
        self._skip_whitespace()
        
        # Check for ==
        if self._peek(2) == "==":
            self._consume("==")
            self._skip_whitespace()
            
            # Parse right side (string or identifier)
            # Try to parse string literal first
            right_str = self._parse_string_literal()
            if right_str:
                # It's a string literal
                right = exp.Literal(this=right_str, is_string=True)
            else:
                # Try identifier
                right_str = self._parse_identifier()
                if not right_str:
                    raise ASQLSyntaxError("Expected value after ==")
                right = exp.Column(this=exp.Identifier(this=right_str))
            
            return exp.EQ(this=exp.Column(this=exp.Identifier(this=left)), expression=right)
        
        # Fallback: just return column reference
        return exp.Column(this=exp.Identifier(this=left))
    
    def _parse_identifier(self) -> Optional[str]:
        """Parse an identifier."""
        self._skip_whitespace()
        
        if not self._has_more():
            return None
        
        # Simple identifier parsing (alphanumeric + underscore)
        match = re.match(r'[a-zA-Z_][a-zA-Z0-9_]*', self.text[self.pos:])
        if match:
            ident = match.group(0)
            self.pos += len(ident)
            return ident
        
        return None
    
    def _parse_string_literal(self) -> Optional[str]:
        """Parse a string literal."""
        self._skip_whitespace()
        
        if not self._has_more():
            return None
        
        if self._peek() in ('"', "'"):
            quote = self._peek()
            self._consume(quote)
            
            # Find closing quote
            end_pos = self.pos
            escaped = False
            while end_pos < len(self.text):
                if self.text[end_pos] == "\\" and not escaped:
                    escaped = True
                    end_pos += 1
                    continue
                if self.text[end_pos] == quote and not escaped:
                    break
                escaped = False
                end_pos += 1
            
            if end_pos >= len(self.text):
                raise ASQLSyntaxError(f"Unclosed string literal")
            
            value = self.text[self.pos:end_pos]
            self.pos = end_pos + 1
            return value
        
        return None
    
    def _is_string_literal(self, value: str) -> bool:
        """Check if value is a string literal."""
        return value.startswith(('"', "'"))
    
    def _peek(self, length: int = 1) -> str:
        """Peek at next character(s)."""
        if self.pos + length > len(self.text):
            return ""
        return self.text[self.pos:self.pos + length]
    
    def _consume(self, expected: str) -> None:
        """Consume expected string."""
        if not self.text[self.pos:].startswith(expected):
            raise ASQLSyntaxError(f"Expected '{expected}'")
        self.pos += len(expected)
    
    def _peek_keyword(self, keyword: str) -> bool:
        """Check if next token is a keyword."""
        saved_pos = self.pos
        self._skip_whitespace()
        result = self.text[self.pos:].lower().startswith(keyword.lower())
        # Check that it's followed by whitespace or end
        if result:
            next_char_pos = self.pos + len(keyword)
            if next_char_pos < len(self.text):
                next_char = self.text[next_char_pos]
                if next_char.isalnum() or next_char == "_":
                    result = False
        self.pos = saved_pos
        return result
    
    def _consume_keyword(self, keyword: str) -> bool:
        """Consume keyword if present."""
        if self._peek_keyword(keyword):
            self._skip_whitespace()
            self.pos += len(keyword)
            self._skip_whitespace()
            return True
        return False
    
    def _skip_whitespace(self) -> None:
        """Skip whitespace."""
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1
    
    def _has_more(self) -> bool:
        """Check if there's more text to parse."""
        return self.pos < len(self.text)
