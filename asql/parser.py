"""ASQL parser - parses ASQL syntax into SQLGlot AST."""

import re
from typing import List, Optional, Tuple, Union
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
            # Check for GROUP BY
            elif self._peek_keyword("group"):
                group_expr, aggregations = self._parse_group_by()
                select_expr.set("group", group_expr)
                # Set aggregations as SELECT expressions if no SELECT was specified
                if not hasattr(select_expr, "expressions") or not select_expr.expressions:
                    # Include grouping columns + aggregations
                    expressions = []
                    # Add grouping columns
                    if group_expr.expressions:
                        expressions.extend(group_expr.expressions)
                    # Add aggregations
                    expressions.extend(aggregations)
                    select_expr.set("expressions", expressions)
            # Check for SORT
            elif self._peek_keyword("sort"):
                order_expr = self._parse_sort()
                select_expr.set("order", order_expr)
            # Check for TAKE
            elif self._peek_keyword("take"):
                limit_expr = self._parse_take()
                select_expr.set("limit", limit_expr)
            # Check for DERIVE
            elif self._peek_keyword("derive"):
                derived_expr = self._parse_derive()
                # Add derived column to SELECT expressions
                if not hasattr(select_expr, "expressions") or not select_expr.expressions:
                    # Start with SELECT *
                    select_expr.set("expressions", [exp.Star(), derived_expr])
                else:
                    # Add to existing expressions
                    expressions = list(select_expr.expressions)
                    # Remove * if present and replace with derived column
                    if any(isinstance(e, exp.Star) for e in expressions):
                        expressions = [e for e in expressions if not isinstance(e, exp.Star)]
                    expressions.append(derived_expr)
                    select_expr.set("expressions", expressions)
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
    
    def _parse_group_by(self) -> Tuple[exp.Group, List[exp.Expression]]:
        """
        Parse GROUP BY clause.
        
        Returns:
            Tuple of (Group expression, list of aggregation expressions)
        """
        # Consume "group by"
        if not self._consume_keyword("group"):
            raise ASQLSyntaxError("Expected 'group' keyword")
        
        if not self._consume_keyword("by"):
            raise ASQLSyntaxError("Expected 'by' after 'group'")
        
        self._skip_whitespace()
        
        # Parse grouping columns (comma-separated)
        grouping_columns = []
        while True:
            col = self._parse_column()
            if col:
                grouping_columns.append(col)
            
            self._skip_whitespace()
            if self._peek() == ",":
                self._consume(",")
                self._skip_whitespace()
            else:
                break
        
        if not grouping_columns:
            raise ASQLSyntaxError("Expected at least one grouping column")
        
        # Parse aggregation block in parentheses
        self._skip_whitespace()
        if self._peek() != "(":
            raise ASQLSyntaxError("Expected '(' after grouping columns")
        
        self._consume("(")
        self._skip_whitespace()
        
        # Parse aggregations
        aggregations = []
        while True:
            agg = self._parse_aggregation()
            if agg:
                aggregations.append(agg)
            
            self._skip_whitespace()
            if self._peek() == ",":
                self._consume(",")
                self._skip_whitespace()
            elif self._peek() == ")":
                self._consume(")")
                break
            else:
                if not self._has_more():
                    raise ASQLSyntaxError("Unclosed aggregation block")
        
        if not aggregations:
            raise ASQLSyntaxError("Expected at least one aggregation")
        
        # Create Group expression
        group_expr = exp.Group(expressions=grouping_columns)
        
        return group_expr, aggregations
    
    def _parse_aggregation(self) -> Optional[exp.Expression]:
        """Parse an aggregation expression."""
        self._skip_whitespace()
        
        if not self._has_more():
            return None
        
        # Check for # (COUNT(*))
        if self._peek() == "#":
            self._consume("#")
            self._skip_whitespace()
            
            # Parse alias if present
            alias = None
            if self._peek_keyword("as"):
                self._consume_keyword("as")
                self._skip_whitespace()
                alias = self._parse_identifier()
            
            # Create COUNT(*) expression
            count_expr = exp.Count(this=exp.Star())
            if alias:
                return exp.Alias(this=count_expr, alias=exp.Identifier(this=alias))
            return count_expr
        
        # Try to parse aggregation function (sum, avg, count, min, max)
        func_name = self._parse_identifier()
        if not func_name:
            return None
        
        func_name_lower = func_name.lower()
        
        # Check if it's an aggregation function
        if func_name_lower in ("sum", "avg", "average", "count", "min", "max"):
            self._skip_whitespace()
            
            # Parse function arguments
            if self._peek() != "(":
                raise ASQLSyntaxError(f"Expected '(' after {func_name}")
            
            self._consume("(")
            self._skip_whitespace()
            
            # Parse argument (column or expression)
            arg = self._parse_column()
            if not arg:
                raise ASQLSyntaxError(f"Expected argument for {func_name}()")
            
            self._skip_whitespace()
            if self._peek() != ")":
                raise ASQLSyntaxError(f"Expected ')' after {func_name} argument")
            
            self._consume(")")
            self._skip_whitespace()
            
            # Create aggregation function
            if func_name_lower == "sum":
                agg_expr = exp.Sum(this=arg)
            elif func_name_lower in ("avg", "average"):
                agg_expr = exp.Avg(this=arg)
            elif func_name_lower == "count":
                agg_expr = exp.Count(this=arg)
            elif func_name_lower == "min":
                agg_expr = exp.Min(this=arg)
            elif func_name_lower == "max":
                agg_expr = exp.Max(this=arg)
            else:
                raise ASQLSyntaxError(f"Unknown aggregation function: {func_name}")
            
            # Parse alias if present
            if self._peek_keyword("as"):
                self._consume_keyword("as")
                self._skip_whitespace()
                alias = self._parse_identifier()
                if alias:
                    return exp.Alias(this=agg_expr, alias=exp.Identifier(this=alias))
            
            return agg_expr
        
        # Not an aggregation, return None
        return None
    
    def _parse_sort(self) -> exp.Order:
        """Parse SORT/ORDER BY clause."""
        if not self._consume_keyword("sort"):
            raise ASQLSyntaxError("Expected 'sort' keyword")
        
        self._skip_whitespace()
        
        # Parse sort columns
        order_expressions = []
        
        while True:
            # Check for descending indicator (-)
            descending = False
            if self._peek() == "-":
                self._consume("-")
                descending = True
                self._skip_whitespace()
            
            # Parse column name
            col = self._parse_column()
            if not col:
                if not order_expressions:
                    raise ASQLSyntaxError("Expected at least one sort column")
                break
            
            # Create Order expression
            if descending:
                order_expr = exp.Ordered(this=col, desc=True)
            else:
                order_expr = exp.Ordered(this=col, desc=False)
            
            order_expressions.append(order_expr)
            
            self._skip_whitespace()
            if self._peek() == ",":
                self._consume(",")
                self._skip_whitespace()
            else:
                break
        
        if not order_expressions:
            raise ASQLSyntaxError("Expected at least one sort column")
        
        return exp.Order(expressions=order_expressions)
    
    def _parse_take(self) -> exp.Limit:
        """Parse TAKE/LIMIT clause."""
        if not self._consume_keyword("take"):
            raise ASQLSyntaxError("Expected 'take' keyword")
        
        self._skip_whitespace()
        
        # Parse number
        number_str = ""
        while self._has_more() and self._peek().isdigit():
            number_str += self._peek()
            self.pos += 1
        
        if not number_str:
            raise ASQLSyntaxError("Expected number after 'take'")
        
        try:
            limit_value = int(number_str)
        except ValueError:
            raise ASQLSyntaxError(f"Invalid number: {number_str}")
        
        return exp.Limit(this=exp.Literal(this=limit_value, is_string=False))
    
    def _parse_derive(self) -> exp.Alias:
        """Parse DERIVE clause (add computed column)."""
        if not self._consume_keyword("derive"):
            raise ASQLSyntaxError("Expected 'derive' keyword")
        
        self._skip_whitespace()
        
        # Parse column name (alias)
        alias_name = self._parse_identifier()
        if not alias_name:
            raise ASQLSyntaxError("Expected column name after 'derive'")
        
        self._skip_whitespace()
        
        # Parse "as"
        if not self._peek_keyword("as"):
            raise ASQLSyntaxError("Expected 'as' after derived column name")
        
        self._consume_keyword("as")
        self._skip_whitespace()
        
        # Parse expression (for now, just handle column reference)
        # TODO: Implement full expression parsing
        expr = self._parse_expression()
        
        return exp.Alias(this=expr, alias=exp.Identifier(this=alias_name))
    
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
        """Parse an expression (handles OR with lowest precedence)."""
        # Parse AND expression (higher precedence)
        left_expr = self._parse_and_expression()
        if not left_expr:
            raise ASQLSyntaxError("Expected expression")
        
        self._skip_whitespace()
        
        # Check for OR operator (lowest precedence)
        while self._peek_keyword("or"):
            self._consume_keyword("or")
            self._skip_whitespace()
            right_expr = self._parse_and_expression()
            if not right_expr:
                raise ASQLSyntaxError("Expected expression after 'or'")
            left_expr = exp.Or(this=left_expr, expression=right_expr)
            self._skip_whitespace()
        
        return left_expr
    
    def _parse_and_expression(self) -> Optional[exp.Expression]:
        """Parse AND expressions (medium precedence)."""
        # Parse comparison expression (higher precedence)
        left_expr = self._parse_comparison_expression()
        if not left_expr:
            return None
        
        self._skip_whitespace()
        
        # Check for AND operator
        while self._peek_keyword("and"):
            self._consume_keyword("and")
            self._skip_whitespace()
            right_expr = self._parse_comparison_expression()
            if not right_expr:
                raise ASQLSyntaxError("Expected expression after 'and'")
            left_expr = exp.And(this=left_expr, expression=right_expr)
            self._skip_whitespace()
        
        return left_expr
    
    def _parse_comparison_expression(self) -> Optional[exp.Expression]:
        """Parse comparison expressions (highest precedence)."""
        self._skip_whitespace()
        
        # Check for NOT operator (unary)
        if self._peek_keyword("not"):
            self._consume_keyword("not")
            self._skip_whitespace()
            expr = self._parse_comparison_expression()
            if not expr:
                raise ASQLSyntaxError("Expected expression after 'not'")
            return exp.Not(this=expr)
        
        # Parse left side
        left_expr = self._parse_primary_expression()
        if not left_expr:
            return None
        
        self._skip_whitespace()
        
        # Check for comparison operators
        if self._peek(2) == "==":
            self._consume("==")
            self._skip_whitespace()
            right_expr = self._parse_primary_expression()
            if not right_expr:
                raise ASQLSyntaxError("Expected value after ==")
            return exp.EQ(this=left_expr, expression=right_expr)
        elif self._peek(2) == "!=":
            self._consume("!=")
            self._skip_whitespace()
            right_expr = self._parse_primary_expression()
            if not right_expr:
                raise ASQLSyntaxError("Expected value after !=")
            return exp.NEQ(this=left_expr, expression=right_expr)
        elif self._peek(2) == "<=":
            self._consume("<=")
            self._skip_whitespace()
            right_expr = self._parse_primary_expression()
            if not right_expr:
                raise ASQLSyntaxError("Expected value after <=")
            return exp.LTE(this=left_expr, expression=right_expr)
        elif self._peek(2) == ">=":
            self._consume(">=")
            self._skip_whitespace()
            right_expr = self._parse_primary_expression()
            if not right_expr:
                raise ASQLSyntaxError("Expected value after >=")
            return exp.GTE(this=left_expr, expression=right_expr)
        elif self._peek() == "<":
            self._consume("<")
            self._skip_whitespace()
            right_expr = self._parse_primary_expression()
            if not right_expr:
                raise ASQLSyntaxError("Expected value after <")
            return exp.LT(this=left_expr, expression=right_expr)
        elif self._peek() == ">":
            self._consume(">")
            self._skip_whitespace()
            right_expr = self._parse_primary_expression()
            if not right_expr:
                raise ASQLSyntaxError("Expected value after >")
            return exp.GT(this=left_expr, expression=right_expr)
        elif self._peek_keyword("is"):
            self._consume_keyword("is")
            self._skip_whitespace()
            if self._peek_keyword("not"):
                self._consume_keyword("not")
                self._skip_whitespace()
                if not self._peek_keyword("null"):
                    raise ASQLSyntaxError("Expected 'null' after 'is not'")
                self._consume_keyword("null")
                return exp.Not(this=exp.Is(this=left_expr, expression=exp.Null()))
            elif self._peek_keyword("null"):
                self._consume_keyword("null")
                return exp.Is(this=left_expr, expression=exp.Null())
            else:
                raise ASQLSyntaxError("Expected 'null' or 'not null' after 'is'")
        
        # Fallback: just return the expression (column reference, etc.)
        return left_expr
    
    def _parse_primary_expression(self) -> Optional[exp.Expression]:
        """Parse a primary expression (literal, identifier, or column)."""
        self._skip_whitespace()
        
        # Try to parse string literal first
        str_literal = self._parse_string_literal()
        if str_literal is not None:
            return exp.Literal(this=str_literal, is_string=True)
        
        # Try to parse numeric literal
        num_literal = self._parse_numeric_literal()
        if num_literal is not None:
            # SQLGlot expects string values for Literal
            return exp.Literal(this=str(num_literal), is_string=False)
        
        # Try to parse identifier/column
        identifier = self._parse_identifier()
        if identifier:
            # Check if it's a keyword that should be handled differently
            identifier_lower = identifier.lower()
            if identifier_lower == "null":
                return exp.Null()
            return exp.Column(this=exp.Identifier(this=identifier))
        
        return None
    
    def _parse_numeric_literal(self) -> Optional[Union[int, float]]:
        """Parse a numeric literal."""
        self._skip_whitespace()
        
        if not self._has_more():
            return None
        
        # Check for negative sign
        negative = False
        if self._peek() == "-":
            negative = True
            self.pos += 1
            self._skip_whitespace()
        
        # Parse digits
        number_str = ""
        has_dot = False
        
        while self._has_more():
            char = self._peek()
            if char.isdigit():
                number_str += char
                self.pos += 1
            elif char == "." and not has_dot:
                number_str += char
                has_dot = True
                self.pos += 1
            else:
                break
        
        if not number_str:
            if negative:
                # Put back the minus sign
                self.pos -= 1
            return None
        
        try:
            if has_dot:
                value = float(number_str)
            else:
                value = int(number_str)
            if negative:
                value = -value
            return value
        except ValueError:
            return None
    
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
