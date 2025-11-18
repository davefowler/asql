"""ASQL parser - parses ASQL syntax into SQLGlot AST."""

import re
from typing import List, Optional, Tuple, Union
from sqlglot import exp
from sqlglot.errors import ParseError

from asql.errors import ASQLSyntaxError
from asql.pipeline import PipelineStep, build_cte_pipeline


class ASQLParser:
    """Parser for ASQL pipeline syntax."""
    
    def __init__(self, text: str):
        """
        Initialize ASQL parser.
        
        Args:
            text: ASQL query string to parse
        """
        self.text = text.strip()
        self.pos = 0
        self.lines = self.text.split('\n')
        self.current_line = 0
    
    def parse(self) -> exp.Select:
        """
        Parse ASQL query into SQLGlot AST using pipeline CTE approach.
        
        Returns:
            SQLGlot Select expression with CTEs
            
        Raises:
            ASQLSyntaxError: If syntax is invalid
        """
        if not self.text:
            raise ASQLSyntaxError("Empty ASQL query")
        
        # Check if this is a SET/CTE statement: "set variable = query"
        self._skip_whitespace()
        if self._peek_keyword("set"):
            # Parse SET statement - this creates a CTE
            return self._parse_set_statement()
        
        # Parse into pipeline steps
        steps = self.parse_pipeline()
        
        # Build CTE-based pipeline
        return build_cte_pipeline(steps)
    
    def parse_pipeline(self) -> List[PipelineStep]:
        """
        Parse ASQL query into pipeline steps.
        
        Returns:
            List of PipelineStep objects representing the pipeline
            
        Raises:
            ASQLSyntaxError: If syntax is invalid
        """
        if not self.text:
            raise ASQLSyntaxError("Empty ASQL query")
        
        # Check if this is a SET/CTE statement - handle separately
        saved_pos = self.pos
        self._skip_whitespace()
        if self._peek_keyword("set"):
            # For SET statements, parse normally (they create their own CTEs)
            self.pos = saved_pos
            # This will be handled in parse() method
            raise ValueError("SET statements should be handled in parse() method")
        
        self.pos = saved_pos
        
        # Parse FROM clause (required, must be first)
        from_expr = self._parse_from()
        
        # Initialize first step
        steps: List[PipelineStep] = []
        current_step = PipelineStep()
        current_step.from_clause = from_expr
        
        # Parse pipeline operators
        while self._has_more():
            self._skip_whitespace()
            if not self._has_more():
                break
            
            # Check for WHERE
            if self._peek_keyword("where") or self._peek_keyword("if"):
                where_expr = self._parse_where()
                current_step.add_where(where_expr)
            # Check for GROUP BY - starts new step
            elif self._peek_keyword("group"):
                # Save current step if it has content
                if current_step.has_content():
                    steps.append(current_step)
                # Start new step for GROUP BY (will reference previous step)
                current_step = PipelineStep()
                group_expr, aggregations = self._parse_group_by()
                current_step.group_by = group_expr
                current_step.aggregations = aggregations
            # Check for JOIN - starts new step
            elif self._peek_keyword("join"):
                # Save current step if it has content
                if current_step.has_content():
                    steps.append(current_step)
                # Start new step for JOIN (will reference previous step)
                current_step = PipelineStep()
                join_expr = self._parse_join()
                current_step.add_join(join_expr)
            # Check for SORT
            elif self._peek_keyword("sort"):
                order_expr = self._parse_sort()
                current_step.sort = order_expr
            # Check for TAKE
            elif self._peek_keyword("take"):
                limit_expr = self._parse_take()
                current_step.limit = limit_expr
            # Check for SELECT
            elif self._peek_keyword("select") or self._peek_keyword("project"):
                select_list = self._parse_select_list()
                current_step.select = select_list
            else:
                # Unknown operator, stop parsing
                break
        
        # Add final step if it has content
        if current_step.has_content():
            steps.append(current_step)
        
        # If no steps were created (just FROM), create a single step
        if not steps:
            steps.append(current_step)
        
        return steps
    
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
        from_expr = exp.From(this=table)
        from_expr.set("joins", [])  # Initialize joins list
        return from_expr
    
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
        # Can be simple columns or function calls like month(created_at)
        grouping_columns = []
        while True:
            # Parse grouping expression (column or function call)
            col = self._parse_grouping_expression()
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
            start_pos = self.pos  # Position before consuming '#'
            self._consume("#")
            self._skip_whitespace()
            
            # Check for natural language form: "# of users" or "# of distinct column"
            natural_lang_text = None
            
            # Check if there's "of" keyword (natural language form)
            if self._peek_keyword("of"):
                self._consume_keyword("of")
                self._skip_whitespace()
                
                # Parse what comes after "of" - could be "distinct column" or just "column"
                if self._peek_keyword("distinct"):
                    self._consume_keyword("distinct")
                    self._skip_whitespace()
                    column = self._parse_column()
                    if column:
                        # Build natural language text: "# of distinct column"
                        end_pos = self.pos
                        natural_lang_text = self.text[start_pos:end_pos].strip()
                else:
                    # Parse column or identifier
                    column = self._parse_column()
                    if not column:
                        # Try parsing as identifier (for table names like "users")
                        ident = self._parse_identifier()
                        if ident:
                            # Build natural language text: "# of users"
                            end_pos = self.pos
                            natural_lang_text = self.text[start_pos:end_pos].strip()
                    else:
                        # Build natural language text: "# of column"
                        end_pos = self.pos
                        natural_lang_text = self.text[start_pos:end_pos].strip()
            
            # Parse alias if present
            alias = None
            if self._peek_keyword("as"):
                self._consume_keyword("as")
                self._skip_whitespace()
                alias = self._parse_identifier()
            
            # Create COUNT(*) expression
            count_expr = exp.Count(this=exp.Star())
            
            # Use natural language text as alias if no explicit alias provided
            if alias:
                return exp.Alias(this=count_expr, alias=exp.Identifier(this=alias))
            elif natural_lang_text:
                # Use natural language text as column name (will be quoted in SQL)
                return exp.Alias(this=count_expr, alias=exp.Identifier(this=natural_lang_text, quoted=True))
            return count_expr
        
        # Try to parse aggregation function (sum, avg, count, min, max)
        func_name = self._parse_identifier()
        if not func_name:
            return None
        
        func_name_lower = func_name.lower()
        
        # Check if it's an aggregation function
        if func_name_lower in ("sum", "avg", "average", "count", "min", "max", "total"):
            # Capture start position before consuming function name
            start_pos = self.pos - len(func_name)
            self._skip_whitespace()
            
            # Check for natural language form (without parentheses): "avg amount", "sum of amount"
            natural_lang_text = None
            
            # Check if there's "of" keyword (natural language form)
            if self._peek_keyword("of"):
                self._consume_keyword("of")
                self._skip_whitespace()
                # Parse column after "of"
                arg = self._parse_column()
                if not arg:
                    arg = self._parse_additive_expression()
                if arg:
                    end_pos = self.pos
                    natural_lang_text = self.text[start_pos:end_pos].strip()
            elif self._peek() != "(":
                # Natural language form without "of": "avg amount", "sum amount"
                # Parse column name directly
                arg = self._parse_column()
                if not arg:
                    arg = self._parse_additive_expression()
                if arg:
                    end_pos = self.pos
                    natural_lang_text = self.text[start_pos:end_pos].strip()
            
            # If we didn't find natural language form, parse standard function syntax
            if not natural_lang_text:
                # Parse function arguments
                if self._peek() != "(":
                    raise ASQLSyntaxError(f"Expected '(' after {func_name}")
                
                self._consume("(")
                self._skip_whitespace()
                
                # Parse argument (column or expression with arithmetic)
                arg = self._parse_additive_expression()
                if not arg:
                    raise ASQLSyntaxError(f"Expected argument for {func_name}()")
                
                self._skip_whitespace()
                if self._peek() != ")":
                    raise ASQLSyntaxError(f"Expected ')' after {func_name}() argument")
                
                self._consume(")")
                self._skip_whitespace()
            
            # Create aggregation function
            if func_name_lower in ("sum", "total"):
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
            
            # Use natural language text as alias if no explicit alias provided
            if natural_lang_text:
                return exp.Alias(this=agg_expr, alias=exp.Identifier(this=natural_lang_text, quoted=True))
            
            return agg_expr
        
        # Not an aggregation, return None
        return None
    
    def _parse_sort(self) -> exp.Order:
        """Parse SORT/ORDER BY clause."""
        if not self._consume_keyword("sort"):
            raise ASQLSyntaxError("Expected 'sort' keyword")
        
        self._skip_whitespace()
        
        # Parse sort expressions (columns or function calls)
        order_expressions = []
        
        while True:
            # Check for descending indicator (-)
            descending = False
            if self._peek() == "-":
                self._consume("-")
                descending = True
                self._skip_whitespace()
            
            # Parse sort expression (column or function call)
            sort_expr = self._parse_sort_expression()
            if not sort_expr:
                if not order_expressions:
                    raise ASQLSyntaxError("Expected at least one sort expression")
                break
            
            # Create Order expression
            if descending:
                order_expr = exp.Ordered(this=sort_expr, desc=True)
            else:
                order_expr = exp.Ordered(this=sort_expr, desc=False)
            
            order_expressions.append(order_expr)
            
            self._skip_whitespace()
            if self._peek() == ",":
                self._consume(",")
                self._skip_whitespace()
            else:
                break
        
        if not order_expressions:
            raise ASQLSyntaxError("Expected at least one sort expression")
        
        return exp.Order(expressions=order_expressions)
    
    def _parse_grouping_expression(self) -> Optional[exp.Expression]:
        """
        Parse a grouping expression (column reference or function call).
        
        Similar to _parse_sort_expression() but needs to distinguish between
        function calls like month(created_at) and the aggregation block ( # ... ).
        """
        self._skip_whitespace()
        
        # Parse identifier first (could be column name or function name)
        saved_pos = self.pos
        identifier = self._parse_identifier()
        if not identifier:
            return None
        
        self._skip_whitespace()
        
        # Check if next is ( - could be function call or aggregation block
        if self._peek() == "(":
            # Peek ahead to see if it's aggregation block
            peek_pos = self.pos
            self._consume("(")
            self._skip_whitespace()
            peek_char = self._peek()
            
            # Restore to before the (
            self.pos = peek_pos
            
            if peek_char == "#":
                # This is aggregation block - return simple column
                return exp.Column(this=exp.Identifier(this=identifier))
            
            # Check if it's an aggregation keyword
            test_pos = self.pos
            self._consume("(")
            self._skip_whitespace()
            test_id = self._parse_identifier()
            if test_id and test_id.lower() in ("sum", "avg", "average", "count", "min", "max"):
                # This is aggregation block
                self.pos = peek_pos
                return exp.Column(this=exp.Identifier(this=identifier))
            
            # Not aggregation - it's a function call like month(created_at)
            # Parse as function call
            self.pos = peek_pos
            self._consume("(")
            self._skip_whitespace()
            arg = self._parse_column()
            if not arg:
                raise ASQLSyntaxError(f"Expected column argument in function call {identifier}()")
            self._skip_whitespace()
            if self._peek() != ")":
                raise ASQLSyntaxError(f"Expected ')' after function argument in {identifier}()")
            self._consume(")")
            return exp.Anonymous(this=identifier, expressions=[arg])
        else:
            # No ( - could be simple column or qualified column (table.column)
            # Try parsing as qualified column
            if self._peek() == ".":
                # Qualified column: table.column
                self._consume(".")
                self._skip_whitespace()
                column_id = self._parse_identifier()
                if not column_id:
                    raise ASQLSyntaxError("Expected column name after '.'")
                return exp.Column(
                    this=exp.Identifier(this=column_id),
                    table=exp.Identifier(this=identifier)
                )
            else:
                # Simple column reference
                return exp.Column(this=exp.Identifier(this=identifier))
    
    def _parse_sort_expression(self) -> Optional[exp.Expression]:
        """Parse a sort expression (column reference or function call)."""
        self._skip_whitespace()
        
        # Check for quoted string (natural language column name)
        if self._peek() in ('"', "'"):
            quoted_name = self._parse_string_literal()
            if quoted_name:
                # Return column reference with quoted identifier
                return exp.Column(this=exp.Identifier(this=quoted_name, quoted=True))
        
        # Check for numeric positional reference (1, 2, etc.) - SQL standard
        # Positional references are numbers at the start of a sort expression
        if self._peek().isdigit():
            num_str = ""
            start_pos = self.pos
            while self._has_more() and self._peek().isdigit():
                num_str += self._peek()
                self._consume(self._peek())
            # Check if this is followed by comma, end, whitespace, or minus (for descending)
            # This indicates it's a positional reference, not part of a larger expression
            self._skip_whitespace()
            if not self._has_more() or self._peek() in (",", "-") or self._peek().isspace():
                # This is a positional reference (SQL ORDER BY 1, 2, etc.)
                # Store as numeric literal - SQLGlot will handle it as positional reference
                return exp.Literal(this=int(num_str), is_string=False)
            else:
                # Not a positional reference, reset position
                self.pos = start_pos
        
        # Check for # (COUNT(*)) - special case for sorting by count
        if self._peek() == "#":
            self._consume("#")
            # Return COUNT(*) expression for sorting
            return exp.Count(this=exp.Star())
        
        # Parse identifier (function name or column name)
        identifier = self._parse_identifier()
        if not identifier:
            return None
        
        # Check if it's a function call
        self._skip_whitespace()
        if self._peek() == "(":
            # It's a function call: month(updated_at)
            self._consume("(")
            self._skip_whitespace()
            
            # Parse function argument (column reference)
            arg = self._parse_column()
            if not arg:
                raise ASQLSyntaxError(f"Expected column argument in function call {identifier}()")
            
            self._skip_whitespace()
            if self._peek() != ")":
                raise ASQLSyntaxError(f"Expected ')' after function argument in {identifier}()")
            self._consume(")")
            
            # Create function call expression
            return exp.Anonymous(this=identifier, expressions=[arg])
        else:
            # It's a simple column reference
            return exp.Column(this=exp.Identifier(this=identifier))
    
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
    
    def _parse_set_statement(self) -> exp.Select:
        """
        Parse SET statement for CTEs.
        
        Syntax: set variable_name = from table ...
        Example: set active_users = from users where status == "active"
        
        Returns a Select with CTE (WITH clause).
        """
        if not self._consume_keyword("set"):
            raise ASQLSyntaxError("Expected 'set' keyword")
        
        self._skip_whitespace()
        
        # Parse variable name
        var_name = self._parse_identifier()
        if not var_name:
            raise ASQLSyntaxError("Expected variable name after 'set'")
        
        self._skip_whitespace()
        
        # Parse = sign
        if self._peek() != "=":
            raise ASQLSyntaxError("Expected '=' after variable name in SET statement")
        self._consume("=")
        self._skip_whitespace()
        
        # Parse the query (starts with FROM)
        # Save current position and parse the query
        query_start = self.pos
        query_text = self.text[query_start:].strip()
        
        # Create a sub-parser for the query part
        sub_parser = ASQLParser(query_text)
        query_select = sub_parser.parse()
        
        # Update our position to where sub-parser ended
        self.pos = query_start + sub_parser.pos
        
        # Create CTE (WITH ... AS)
        cte = exp.CTE(
            this=query_select,
            alias=exp.TableAlias(this=exp.Identifier(this=var_name))
        )
        
        # Store CTE info in the query_select's meta dict (SQLGlot's way to store custom data)
        # We'll check for this in the compiler
        if not hasattr(query_select, "meta"):
            query_select.meta = {}
        query_select.meta["_cte_name"] = var_name
        query_select.meta["_is_cte"] = True
        
        return query_select
    
    def _parse_join(self) -> exp.Join:
        """
        Parse JOIN clause.
        
        Syntax: join table_name on condition
        Example: join owners on owner_id == owners.id
        """
        if not self._consume_keyword("join"):
            raise ASQLSyntaxError("Expected 'join' keyword")
        
        self._skip_whitespace()
        
        # Parse table name
        table_name = self._parse_identifier()
        if not table_name:
            raise ASQLSyntaxError("Expected table name after 'join'")
        
        self._skip_whitespace()
        
        # Parse ON condition
        if not self._peek_keyword("on"):
            raise ASQLSyntaxError("Expected 'on' after join table name")
        
        self._consume_keyword("on")
        self._skip_whitespace()
        
        # Parse join condition (an expression)
        condition = self._parse_expression()
        if not condition:
            raise ASQLSyntaxError("Expected join condition after 'on'")
        
        # Create JOIN expression
        join_table = exp.Table(this=exp.Identifier(this=table_name))
        join_expr = exp.Join(this=join_table, on=condition, kind="INNER")
        
        return join_expr
    
    def _parse_select_list(self) -> List[exp.Expression]:
        """Parse SELECT column list (supports expressions with arithmetic)."""
        self._consume_keyword("select") or self._consume_keyword("project")
        self._skip_whitespace()
        
        columns = []
        
        # Check for *
        if self._peek() == "*":
            self._consume("*")
            return [exp.Star()]
        
        # Parse expression list (can include arithmetic)
        while True:
            # Parse expression (may include arithmetic, aliases, etc.)
            expr = self._parse_select_expression()
            if expr:
                columns.append(expr)
            
            self._skip_whitespace()
            if self._peek() == ",":
                self._consume(",")
                self._skip_whitespace()
            else:
                break
        
        return columns
    
    def _parse_select_expression(self) -> Optional[exp.Expression]:
        """Parse a SELECT expression (column, arithmetic expression, or alias)."""
        self._skip_whitespace()
        
        # Check for quoted string (natural language column name)
        if self._peek() in ('"', "'"):
            quoted_name = self._parse_string_literal()
            if quoted_name:
                # Return column reference with quoted identifier
                expr = exp.Column(this=exp.Identifier(this=quoted_name, quoted=True))
                self._skip_whitespace()
                # Check for alias
                if self._peek_keyword("as"):
                    self._consume_keyword("as")
                    self._skip_whitespace()
                    alias = self._parse_identifier()
                    if alias:
                        return exp.Alias(this=expr, alias=exp.Identifier(this=alias))
                return expr
        
        # Check for numeric positional reference (1, 2, etc.) - SQL standard
        # In SELECT, positional references refer to column positions
        if self._peek().isdigit():
            num_str = ""
            start_pos = self.pos
            while self._has_more() and self._peek().isdigit():
                num_str += self._peek()
                self._consume(self._peek())
            # Check if this is followed by comma, end, or whitespace (not part of larger expression)
            self._skip_whitespace()
            if not self._has_more() or self._peek() == "," or self._peek().isspace():
                # This is a positional reference
                expr = exp.Literal(this=int(num_str), is_string=False)
                self._skip_whitespace()
                # Check for alias
                if self._peek_keyword("as"):
                    self._consume_keyword("as")
                    self._skip_whitespace()
                    alias = self._parse_identifier()
                    if alias:
                        return exp.Alias(this=expr, alias=exp.Identifier(this=alias))
                return expr
            else:
                # Not a positional reference, reset position
                self.pos = start_pos
        
        # Parse expression (supports arithmetic)
        expr = self._parse_additive_expression()
        if not expr:
            return None
        
        self._skip_whitespace()
        
        # Check for alias: "as name" or just "name"
        if self._peek_keyword("as"):
            self._consume_keyword("as")
            self._skip_whitespace()
            alias = self._parse_identifier()
            if alias:
                return exp.Alias(this=expr, alias=exp.Identifier(this=alias))
        elif self._peek() and self._peek().isalnum() or self._peek() == "_":
            # Check if next token is a comma or end - if so, this might be an alias
            # But we can't reliably detect this without lookahead, so we'll require "as"
            # For now, just return the expression
            pass
        
        return expr
    
    def _parse_column(self) -> Optional[exp.Expression]:
        """Parse a column reference (may be qualified: table.column)."""
        # Parse first identifier (table or column name)
        first_id = self._parse_identifier()
        if not first_id:
            return None
        
        self._skip_whitespace()
        
        # Check if there's a dot (qualified name: table.column)
        if self._peek() == ".":
            self._consume(".")
            self._skip_whitespace()
            
            # Parse column name
            column_id = self._parse_identifier()
            if not column_id:
                raise ASQLSyntaxError("Expected column name after '.'")
            
            # Create qualified column: table.column
            return exp.Column(
                this=exp.Identifier(this=column_id),
                table=exp.Identifier(this=first_id)
            )
        else:
            # Simple column reference
            return exp.Column(this=exp.Identifier(this=first_id))
    
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
        """Parse comparison expressions."""
        self._skip_whitespace()
        
        # Check for NOT operator (unary)
        if self._peek_keyword("not"):
            self._consume_keyword("not")
            self._skip_whitespace()
            expr = self._parse_comparison_expression()
            if not expr:
                raise ASQLSyntaxError("Expected expression after 'not'")
            return exp.Not(this=expr)
        
        # Parse left side (arithmetic expression)
        left_expr = self._parse_additive_expression()
        if not left_expr:
            return None
        
        self._skip_whitespace()
        
        # Check for comparison operators
        if self._peek(2) == "==":
            self._consume("==")
            self._skip_whitespace()
            right_expr = self._parse_additive_expression()
            if not right_expr:
                raise ASQLSyntaxError("Expected value after ==")
            return exp.EQ(this=left_expr, expression=right_expr)
        elif self._peek(2) == "!=":
            self._consume("!=")
            self._skip_whitespace()
            right_expr = self._parse_additive_expression()
            if not right_expr:
                raise ASQLSyntaxError("Expected value after !=")
            return exp.NEQ(this=left_expr, expression=right_expr)
        elif self._peek(2) == "<=":
            self._consume("<=")
            self._skip_whitespace()
            right_expr = self._parse_additive_expression()
            if not right_expr:
                raise ASQLSyntaxError("Expected value after <=")
            return exp.LTE(this=left_expr, expression=right_expr)
        elif self._peek(2) == ">=":
            self._consume(">=")
            self._skip_whitespace()
            right_expr = self._parse_additive_expression()
            if not right_expr:
                raise ASQLSyntaxError("Expected value after >=")
            return exp.GTE(this=left_expr, expression=right_expr)
        elif self._peek() == "<":
            self._consume("<")
            self._skip_whitespace()
            right_expr = self._parse_additive_expression()
            if not right_expr:
                raise ASQLSyntaxError("Expected value after <")
            return exp.LT(this=left_expr, expression=right_expr)
        elif self._peek() == ">":
            self._consume(">")
            self._skip_whitespace()
            right_expr = self._parse_additive_expression()
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
        elif self._peek_keyword("in"):
            # Parse IN (value1, value2, ...)
            self._consume_keyword("in")
            self._skip_whitespace()
            if self._peek() != "(":
                raise ASQLSyntaxError("Expected '(' after 'in'")
            self._consume("(")
            self._skip_whitespace()
            
            # Parse list of values
            values = []
            while True:
                self._skip_whitespace()
                value_expr = self._parse_additive_expression()
                if not value_expr:
                    break
                values.append(value_expr)
                
                self._skip_whitespace()
                if self._peek() == ",":
                    self._consume(",")
                    self._skip_whitespace()
                elif self._peek() == ")":
                    break
                else:
                    raise ASQLSyntaxError("Expected ',' or ')' in IN list")
            
            if self._peek() != ")":
                raise ASQLSyntaxError("Expected ')' after IN list")
            self._consume(")")
            
            if not values:
                raise ASQLSyntaxError("IN list cannot be empty")
            
            # Create IN expression
            return exp.In(this=left_expr, expressions=values)
        elif self._peek_keyword("not"):
            # Check if next keyword is "in"
            saved_pos = self.pos
            self._consume_keyword("not")
            self._skip_whitespace()
            is_in = self._peek_keyword("in")
            self.pos = saved_pos  # Restore position
            
            if is_in:
                # Parse NOT IN (value1, value2, ...)
                self._consume_keyword("not")
                self._skip_whitespace()
                self._consume_keyword("in")
                self._skip_whitespace()
                if self._peek() != "(":
                    raise ASQLSyntaxError("Expected '(' after 'not in'")
                self._consume("(")
                self._skip_whitespace()
                
                # Parse list of values
                values = []
                while True:
                    self._skip_whitespace()
                    value_expr = self._parse_additive_expression()
                    if not value_expr:
                        break
                    values.append(value_expr)
                    
                    self._skip_whitespace()
                    if self._peek() == ",":
                        self._consume(",")
                        self._skip_whitespace()
                    elif self._peek() == ")":
                        break
                    else:
                        raise ASQLSyntaxError("Expected ',' or ')' in NOT IN list")
                
                if self._peek() != ")":
                    raise ASQLSyntaxError("Expected ')' after NOT IN list")
                self._consume(")")
                
                if not values:
                    raise ASQLSyntaxError("NOT IN list cannot be empty")
                
                # Create NOT IN expression
                return exp.Not(this=exp.In(this=left_expr, expressions=values))
        
        # Fallback: just return the expression (column reference, etc.)
        return left_expr
    
    def _parse_additive_expression(self) -> Optional[exp.Expression]:
        """
        Parse additive expressions (+ and -).
        
        Precedence: Additive operators have lower precedence than multiplicative.
        """
        # Parse multiplicative expression (higher precedence)
        left_expr = self._parse_multiplicative_expression()
        if not left_expr:
            return None
        
        self._skip_whitespace()
        
        # Check for additive operators
        while True:
            if self._peek() == "+":
                self._consume("+")
                self._skip_whitespace()
                right_expr = self._parse_multiplicative_expression()
                if not right_expr:
                    raise ASQLSyntaxError("Expected expression after '+'")
                left_expr = exp.Add(this=left_expr, expression=right_expr)
                self._skip_whitespace()
            elif self._peek() == "-":
                # Check if this is a unary minus or binary minus
                # If we're at the start of an expression, it's unary
                # Otherwise, it's binary subtraction
                self._consume("-")
                self._skip_whitespace()
                right_expr = self._parse_multiplicative_expression()
                if not right_expr:
                    raise ASQLSyntaxError("Expected expression after '-'")
                left_expr = exp.Sub(this=left_expr, expression=right_expr)
                self._skip_whitespace()
            else:
                break
        
        return left_expr
    
    def _parse_multiplicative_expression(self) -> Optional[exp.Expression]:
        """
        Parse multiplicative expressions (*, /, %).
        
        Precedence: Multiplicative operators have higher precedence than additive.
        """
        # Parse primary expression (highest precedence)
        left_expr = self._parse_primary_expression()
        if not left_expr:
            return None
        
        self._skip_whitespace()
        
        # Check for multiplicative operators
        while True:
            if self._peek() == "*":
                self._consume("*")
                self._skip_whitespace()
                right_expr = self._parse_primary_expression()
                if not right_expr:
                    raise ASQLSyntaxError("Expected expression after '*'")
                left_expr = exp.Mul(this=left_expr, expression=right_expr)
                self._skip_whitespace()
            elif self._peek() == "/":
                self._consume("/")
                self._skip_whitespace()
                right_expr = self._parse_primary_expression()
                if not right_expr:
                    raise ASQLSyntaxError("Expected expression after '/'")
                left_expr = exp.Div(this=left_expr, expression=right_expr)
                self._skip_whitespace()
            elif self._peek() == "%":
                self._consume("%")
                self._skip_whitespace()
                right_expr = self._parse_primary_expression()
                if not right_expr:
                    raise ASQLSyntaxError("Expected expression after '%'")
                left_expr = exp.Mod(this=left_expr, expression=right_expr)
                self._skip_whitespace()
            else:
                break
        
        return left_expr
    
    def _parse_primary_expression(self) -> Optional[exp.Expression]:
        """Parse a primary expression (literal, identifier, column, or parenthesized expression)."""
        self._skip_whitespace()
        
        # Check for parenthesized expression
        if self._peek() == "(":
            self._consume("(")
            self._skip_whitespace()
            expr = self._parse_expression()
            if not expr:
                raise ASQLSyntaxError("Expected expression inside parentheses")
            self._skip_whitespace()
            if self._peek() != ")":
                raise ASQLSyntaxError("Expected ')' after expression")
            self._consume(")")
            return expr
        
        # Try to parse string literal first
        str_literal = self._parse_string_literal()
        if str_literal is not None:
            return exp.Literal(this=str_literal, is_string=True)
        
        # Try to parse numeric literal
        num_literal = self._parse_numeric_literal()
        if num_literal is not None:
            # SQLGlot expects string values for Literal
            return exp.Literal(this=str(num_literal), is_string=False)
        
        # Try to parse column (supports qualified names: table.column)
        column = self._parse_column()
        if column:
            return column
        
        # Try to parse identifier (for keywords like null)
        identifier = self._parse_identifier()
        if identifier:
            # Check if it's a keyword that should be handled differently
            identifier_lower = identifier.lower()
            if identifier_lower == "null":
                return exp.Null()
            # Fallback to column if not a special keyword
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
                raise ASQLSyntaxError("Unclosed string literal")
            
            value = self.text[self.pos:end_pos]
            self.pos = end_pos + 1
            return value
        
        return None
    
    def _is_string_literal(self, value: str) -> bool:
        """Check if value is a string literal."""
        return value.startswith(('"', "'"))
    
    def _peek(self, length: int = 1) -> str:
        """
        Peek at next character(s) without consuming.
        
        Args:
            length: Number of characters to peek
            
        Returns:
            Next character(s) or empty string if at end
        """
        if self.pos + length > len(self.text):
            return ""
        return self.text[self.pos:self.pos + length]
    
    def _consume(self, expected: str) -> None:
        """
        Consume expected string, raising error if not found.
        
        Args:
            expected: String to consume
            
        Raises:
            ASQLSyntaxError: If expected string not found
        """
        if not self.text[self.pos:].startswith(expected):
            raise ASQLSyntaxError(f"Expected '{expected}' at position {self.pos}")
        self.pos += len(expected)
    
    def _peek_keyword(self, keyword: str) -> bool:
        """
        Check if next token is a keyword (without consuming).
        
        Args:
            keyword: Keyword to check for
            
        Returns:
            True if keyword is next, False otherwise
        """
        saved_pos = self.pos
        self._skip_whitespace()
        result = self.text[self.pos:].lower().startswith(keyword.lower())
        # Check that it's followed by whitespace or end (not part of identifier)
        if result:
            next_char_pos = self.pos + len(keyword)
            if next_char_pos < len(self.text):
                next_char = self.text[next_char_pos]
                if next_char.isalnum() or next_char == "_":
                    result = False
        self.pos = saved_pos
        return result
    
    def _consume_keyword(self, keyword: str) -> bool:
        """
        Consume keyword if present.
        
        Args:
            keyword: Keyword to consume
            
        Returns:
            True if keyword was consumed, False otherwise
        """
        if self._peek_keyword(keyword):
            self._skip_whitespace()
            self.pos += len(keyword)
            self._skip_whitespace()
            return True
        return False
    
    def _skip_whitespace(self) -> None:
        """Skip whitespace characters."""
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1
    
    def _has_more(self) -> bool:
        """
        Check if there's more text to parse.
        
        Returns:
            True if more text remains, False otherwise
        """
        return self.pos < len(self.text)
