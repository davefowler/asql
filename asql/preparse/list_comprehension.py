"""Pre-parser transforms: Python-style list comprehensions."""

from __future__ import annotations

import re
from typing import Optional, Tuple

import sqlglot
from sqlglot import exp


class ListComprehensionMixin:
    """Mixin for transforming list comprehensions to SQL ARRAY expressions."""

    def _transform_list_comprehensions(self, text: str) -> str:
        """
        Transform Python-style list comprehensions to SQL ARRAY expressions.
        
        Examples:
        [lower(tag) for tag in tags] → ARRAY(SELECT LOWER(tag) FROM UNNEST(tags) AS tag)
        [x * 2 for x in numbers if x > 0] → ARRAY(SELECT x * 2 FROM UNNEST(numbers) AS x WHERE x > 0)
        """
        result = text
        
        # Find all list comprehensions by scanning for [ ... for ... in ... ]
        # Process from right to left to avoid position shifts
        pos = len(result) - 1
        
        while pos >= 0:
            # Look for closing bracket
            if result[pos] != ']':
                pos -= 1
                continue
            
            # Skip if inside a string
            before = result[:pos]
            if (before.count("'") % 2 != 0) or (before.count('"') % 2 != 0):
                pos -= 1
                continue
            
            # Try to parse a list comprehension starting from this position
            comp_start, expr_str, var_name, array_col, condition_str = self._parse_list_comprehension(
                result, pos
            )
            
            if comp_start is not None:
                # Build SQLGlot AST
                sql_expr = self._build_list_comprehension_ast(
                    expr_str, var_name, array_col, condition_str
                )
                
                if sql_expr:
                    # Convert AST to SQL string (use postgres as base, SQLGlot will transpile later)
                    try:
                        sql_str = sql_expr.sql(dialect="postgres")
                        result = result[:comp_start] + sql_str + result[pos + 1:]
                        pos = comp_start - 1
                        continue
                    except Exception:
                        # If AST conversion fails, skip this match
                        pass
            
            pos -= 1
        
        return result
    
    def _parse_list_comprehension(
        self, text: str, end_pos: int
    ) -> Tuple[Optional[int], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Parse a list comprehension ending at end_pos.
        
        Returns:
            (start_pos, expr_str, var_name, array_col, condition_str) or (None, ...) if not found
        """
        # Work backwards from the closing bracket
        pos = end_pos - 1
        bracket_depth = 1
        paren_depth = 0
        in_string = False
        string_char: Optional[str] = None
        
        # Find the matching opening bracket
        while pos >= 0 and bracket_depth > 0:
            char = text[pos]
            
            # Handle string literals
            if not in_string and char in ('"', "'"):
                in_string = True
                string_char = char
                pos -= 1
                continue
            
            if in_string:
                if char == string_char:
                    # Check for escaped quote
                    if pos > 0 and text[pos - 1] == string_char:
                        pos -= 2
                        continue
                    in_string = False
                    string_char = None
                pos -= 1
                continue
            
            # Track brackets and parentheses
            if char == ']':
                bracket_depth += 1
            elif char == '[':
                bracket_depth -= 1
            elif char == ')':
                paren_depth += 1
            elif char == '(':
                paren_depth -= 1
            
            pos -= 1
        
        if bracket_depth != 0:
            return None, None, None, None, None
        
        start_pos = pos + 1
        content = text[start_pos + 1:end_pos]  # Skip the opening bracket
        
        # Parse: expr for var in arr [if condition]
        # Use case-insensitive matching for keywords
        pattern = r'(.+?)\s+for\s+(\w+)\s+in\s+(\w+)(?:\s+if\s+(.+))?$'
        match = re.match(pattern, content.strip(), re.IGNORECASE)
        
        if not match:
            return None, None, None, None, None
        
        expr_str = match.group(1).strip()
        var_name = match.group(2).strip()
        array_col = match.group(3).strip()
        condition_str = match.group(4).strip() if match.group(4) else None
        
        return start_pos, expr_str, var_name, array_col, condition_str
    
    def _build_list_comprehension_ast(
        self,
        expr_str: str,
        var_name: str,
        array_col: str,
        condition_str: Optional[str],
    ) -> Optional[exp.Expression]:
        """
        Build SQLGlot AST for list comprehension.
        
        Args:
            expr_str: Expression to apply to each element (e.g., "lower(tag)")
            var_name: Variable name in the comprehension (e.g., "tag")
            array_col: Array column name (e.g., "tags")
            condition_str: Optional filter condition (e.g., "x > 0")
        
        Returns:
            SQLGlot AST expression or None if parsing fails
        """
        try:
            # Parse the expression string - it may reference var_name as a column
            expr_ast = sqlglot.parse_one(expr_str)
            
            # Note: The expression may reference var_name as a column.
            # In the UNNEST context, var_name will be available as a column.
            # SQLGlot should handle the column resolution correctly.
            
            # Build UNNEST expression
            # For Postgres/BigQuery/DuckDB: UNNEST(array_col) AS var_name
            unnest = exp.Unnest(
                expressions=[exp.Column(this=exp.Identifier(this=array_col))],
                alias=exp.TableAlias(this=exp.Identifier(this=var_name))
            )
            
            # Build SELECT expression
            select_expressions = [expr_ast]
            
            # Add WHERE clause if condition is present
            where_clause = None
            if condition_str:
                condition_ast = sqlglot.parse_one(condition_str)
                where_clause = exp.Where(this=condition_ast)
            
            select = exp.Select(
                expressions=select_expressions,
                from_=exp.From(this=unnest),
                where=where_clause,
            )
            
            # Wrap in ARRAY
            array_expr = exp.Array(expressions=[select])
            
            return array_expr
            
        except Exception:
            # If parsing fails, return None
            return None
