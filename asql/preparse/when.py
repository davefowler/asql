"""Pre-parser transforms: when conditional expressions."""

from __future__ import annotations

import re
from typing import List, Tuple, Optional


class WhenMixin:
    """Mixin for transforming when expressions to CASE WHEN."""

    def _transform_when_expressions(self, text: str) -> str:
        """
        Transform when expressions to SQL CASE WHEN syntax.
        
        Simple case:
        when status is "active" then 1 → CASE WHEN status = 'active' THEN 1 END
        
        Implied equality:
        when status "active" then 1 → CASE WHEN status = 'active' THEN 1 END
        
        Comparison:
        when age < 4 then "infant" → CASE WHEN age < 4 THEN 'infant' END
        
        Searched case:
        when age < 18 then "Minor" → CASE WHEN age < 18 THEN 'Minor' END
        
        Multiple branches:
        when status
          is "active" then 1
          is "pending" then 0
          otherwise -1
        → CASE WHEN status = 'active' THEN 1 WHEN status = 'pending' THEN 0 ELSE -1 END
        """
        result = text
        
        # Find all "when" keywords (case-insensitive, word boundary)
        when_pattern = r'\bwhen\b'
        matches = list(re.finditer(when_pattern, result, re.IGNORECASE))
        
        # Process from end to start to avoid position shifts
        for match in reversed(matches):
            start_pos = match.start()
            
            # Skip if already inside a string or comment
            before = result[:start_pos]
            # Simple check: if odd number of quotes before, we're inside a string
            if (before.count("'") % 2 != 0) or (before.count('"') % 2 != 0):
                continue
            
            # Parse the when expression starting from this position
            case_expr, end_pos = self._parse_when_block(result, start_pos)
            
            if case_expr:
                # Replace the when expression with CASE expression
                result = result[:start_pos] + case_expr + result[end_pos:]
        
        return result
    
    def _parse_when_block(self, text: str, start_pos: int) -> Tuple[Optional[str], int]:
        """
        Parse a complete when block starting at start_pos.
        
        Returns:
            (case_expr, end_pos) or (None, start_pos) if parsing fails
        """
        pos = start_pos + 4  # Skip "when"
        
        # Skip whitespace
        while pos < len(text) and text[pos] in ' \t\n':
            pos += 1
        
        if pos >= len(text):
            return None, start_pos
        
        branches: List[Tuple[str, str]] = []  # (condition, result) pairs
        else_value: Optional[str] = None
        base_expr: Optional[str] = None
        
        # Parse first branch
        first_condition, first_result, new_pos, is_simple = self._parse_when_branch(
            text, pos, None
        )
        if first_condition is None:
            return None, start_pos
        
        branches.append((first_condition, first_result))
        
        # Extract base_expr from first branch if it's a simple case
        if is_simple:
            base_expr = self._extract_base_expr(first_condition)
        
        pos = new_pos
        
        # Parse additional branches (they may be on new lines with indentation)
        while pos < len(text):
            # Skip whitespace and newlines
            while pos < len(text) and text[pos] in ' \t\n':
                pos += 1
            
            if pos >= len(text):
                break
            
            # Check for otherwise/else
            remaining = text[pos:].lower().lstrip()
            if remaining.startswith('otherwise') or remaining.startswith('else'):
                # Parse else value
                if remaining.startswith('otherwise'):
                    pos += text[pos:].lower().find('otherwise') + 9
                else:
                    pos += text[pos:].lower().find('else') + 4
                
                # Skip whitespace
                while pos < len(text) and text[pos] in ' \t\n':
                    pos += 1
                
                # Parse the else value
                else_value, pos = self._parse_expression(text, pos)
                break
            
            # Check if there's another "when" branch (indented or on same line)
            # Look for patterns like: "is", "is not", "<", ">", "in", or a value
            # These indicate another branch
            
            # Try to parse another branch
            condition, result, new_pos, _ = self._parse_when_branch(text, pos, base_expr)
            
            if condition is None:
                # No more branches
                break
            
            branches.append((condition, result))
            pos = new_pos
        
        # Build CASE expression
        if not branches:
            return None, start_pos
        
        case_parts = ["CASE"]
        
        # Add WHEN clauses
        for condition, result in branches:
            case_parts.append(f"WHEN {condition} THEN {result}")
        
        if else_value:
            case_parts.append(f"ELSE {else_value}")
        
        case_parts.append("END")
        
        return " ".join(case_parts), pos
    
    def _parse_when_branch(
        self, text: str, start_pos: int, base_expr: Optional[str]
    ) -> Tuple[Optional[str], Optional[str], int, bool]:
        """
        Parse a single when branch.
        
        Returns:
            (condition, result, end_pos, is_simple_case)
        """
        pos = start_pos
        
        # Skip whitespace
        while pos < len(text) and text[pos] in ' \t\n':
            pos += 1
        
        if pos >= len(text):
            return None, None, start_pos, False
        
        # Parse the condition part
        # It can be:
        # 1. Simple case: expr is value, expr is not value, expr < value, etc.
        # 2. Implied equality: expr value (no operator)
        # 3. Searched case: condition (no expr before it)
        
        # Try to parse an expression first
        expr, pos = self._parse_expression(text, pos)
        if expr is None:
            return None, None, start_pos, False
        
        # Skip whitespace
        while pos < len(text) and text[pos] in ' \t\n':
            pos += 1
        
        if pos >= len(text):
            return None, None, start_pos, False
        
        # Check for operators
        remaining = text[pos:].lower().lstrip()
        
        condition: Optional[str] = None
        is_simple = False
        
        if remaining.startswith('is not'):
            # expr is not value
            pos += text[pos:].lower().find('is not') + 6
            while pos < len(text) and text[pos] in ' \t\n':
                pos += 1
            value, pos = self._parse_expression(text, pos)
            if value:
                condition = f"{expr} != {value}"
                is_simple = True
        elif remaining.startswith('is'):
            # expr is value
            pos += text[pos:].lower().find('is') + 2
            while pos < len(text) and text[pos] in ' \t\n':
                pos += 1
            value, pos = self._parse_expression(text, pos)
            if value:
                condition = f"{expr} = {value}"
                is_simple = True
        elif remaining.startswith('in'):
            # expr in (values)
            pos += text[pos:].lower().find('in') + 2
            while pos < len(text) and text[pos] in ' \t\n':
                pos += 1
            if pos < len(text) and text[pos] == '(':
                values, pos = self._parse_value_list(text, pos)
                condition = f"{expr} IN {values}"
                is_simple = True
        elif remaining.startswith('<='):
            pos += 2
            while pos < len(text) and text[pos] in ' \t\n':
                pos += 1
            value, pos = self._parse_expression(text, pos)
            if value:
                condition = f"{expr} <= {value}"
                is_simple = True
        elif remaining.startswith('>='):
            pos += 2
            while pos < len(text) and text[pos] in ' \t\n':
                pos += 1
            value, pos = self._parse_expression(text, pos)
            if value:
                condition = f"{expr} >= {value}"
                is_simple = True
        elif remaining.startswith('!=') or remaining.startswith('<>'):
            pos += 2
            while pos < len(text) and text[pos] in ' \t\n':
                pos += 1
            value, pos = self._parse_expression(text, pos)
            if value:
                condition = f"{expr} != {value}"
                is_simple = True
        elif remaining.startswith('<'):
            pos += 1
            while pos < len(text) and text[pos] in ' \t\n':
                pos += 1
            value, pos = self._parse_expression(text, pos)
            if value:
                condition = f"{expr} < {value}"
                is_simple = True
        elif remaining.startswith('>'):
            pos += 1
            while pos < len(text) and text[pos] in ' \t\n':
                pos += 1
            value, pos = self._parse_expression(text, pos)
            if value:
                condition = f"{expr} > {value}"
                is_simple = True
        elif remaining.startswith('='):
            pos += 1
            while pos < len(text) and text[pos] in ' \t\n':
                pos += 1
            value, pos = self._parse_expression(text, pos)
            if value:
                condition = f"{expr} = {value}"
                is_simple = True
            else:
                # No operator found - could be implied equality or searched case
                # Check if next token is a value (string/number) followed by "then"
                # This indicates implied equality: when expr value then result
                saved_pos = pos
                while saved_pos < len(text) and text[saved_pos] in ' \t\n':
                    saved_pos += 1
                
                # Try to parse what comes next
                next_expr, next_end = self._parse_expression(text, saved_pos)
                if next_expr:
                    # Check if after next_expr we have "then"
                    check_pos = next_end
                    while check_pos < len(text) and text[check_pos] in ' \t\n':
                        check_pos += 1
                    remaining_check = text[check_pos:].lower().lstrip()
                    
                    if remaining_check.startswith('then'):
                        # This is implied equality: when expr value then result
                        # The first expr is the base, next_expr is the value
                        if base_expr is None:
                            # First branch - expr is the base
                            base_expr = expr
                        condition = f"{base_expr} = {next_expr}"
                        is_simple = True
                        # Update pos to after the value
                        pos = next_end
                    else:
                        # Not implied equality - this is a searched case condition
                        condition = expr
                        is_simple = False
                else:
                    # Can't parse next token - treat as searched case
                    condition = expr
                    is_simple = False
        
        if condition is None:
            return None, None, start_pos, False
        
        # Now parse "then result"
        while pos < len(text) and text[pos] in ' \t\n':
            pos += 1
        
        if pos >= len(text):
            return None, None, start_pos, False
        
        remaining = text[pos:].lower().lstrip()
        if not remaining.startswith('then'):
            return None, None, start_pos, False
        
        pos += text[pos:].lower().find('then') + 4
        
        # Skip whitespace
        while pos < len(text) and text[pos] in ' \t\n':
            pos += 1
        
        # Parse result
        result, pos = self._parse_expression(text, pos)
        if result is None:
            return None, None, start_pos, False
        
        return condition, result, pos, is_simple
    
    def _extract_base_expr(self, condition: str) -> Optional[str]:
        """Extract base expression from a condition like 'status = value'."""
        # Simple extraction: take everything before the first operator
        for op in [' = ', ' != ', ' < ', ' > ', ' <= ', ' >= ', ' IN ']:
            if op in condition:
                return condition.split(op)[0].strip()
        return None
    
    def _parse_expression(self, text: str, start_pos: int) -> Tuple[Optional[str], int]:
        """
        Parse an expression (identifier, string, number, function call, etc.).
        
        Returns:
            (expression, end_pos)
        """
        pos = start_pos
        
        # Skip whitespace
        while pos < len(text) and text[pos] in ' \t\n':
            pos += 1
        
        if pos >= len(text):
            return None, start_pos
        
        # Check for string literal
        if text[pos] in '"\'':
            quote = text[pos]
            pos += 1
            start = pos
            while pos < len(text) and text[pos] != quote:
                if text[pos] == '\\':
                    pos += 1  # Skip escaped character
                pos += 1
            if pos < len(text):
                return text[start_pos:pos+1], pos + 1
            else:
                return None, start_pos
        
        # Check for number
        if text[pos].isdigit() or (text[pos] == '-' and pos + 1 < len(text) and text[pos + 1].isdigit()):
            start = pos
            if text[pos] == '-':
                pos += 1
            while pos < len(text) and (text[pos].isdigit() or text[pos] == '.'):
                pos += 1
            return text[start:pos], pos
        
        # Check for boolean/null
        remaining = text[pos:].lower()
        if remaining.startswith('true'):
            return text[pos:pos+4], pos + 4
        if remaining.startswith('false'):
            return text[pos:pos+5], pos + 5
        if remaining.startswith('null'):
            return text[pos:pos+4], pos + 4
        
        # Parse identifier or function call
        start = pos
        paren_depth = 0
        
        while pos < len(text):
            char = text[pos]
            
            if char == '(':
                paren_depth += 1
                pos += 1
            elif char == ')':
                if paren_depth > 0:
                    paren_depth -= 1
                    pos += 1
                else:
                    break
            elif char in ' \t\n,;':
                if paren_depth == 0:
                    break
                pos += 1
            elif char in '=<>!':
                # Operator - stop if not inside parens
                if paren_depth == 0:
                    break
                pos += 1
            else:
                pos += 1
        
        expr = text[start:pos].strip()
        if not expr:
            return None, start_pos
        
        return expr, pos
    
    def _parse_value_list(self, text: str, start_pos: int) -> Tuple[str, int]:
        """
        Parse a list of values: (value1, value2, ...)
        
        Returns:
            (value_list_string, end_pos)
        """
        pos = start_pos
        
        # Skip whitespace
        while pos < len(text) and text[pos] in ' \t\n':
            pos += 1
        
        if pos >= len(text) or text[pos] != '(':
            return '()', start_pos
        
        pos += 1  # Skip '('
        
        values = []
        paren_depth = 1
        
        while pos < len(text) and paren_depth > 0:
            # Skip whitespace
            while pos < len(text) and text[pos] in ' \t\n':
                pos += 1
            
            if pos >= len(text):
                break
            
            if text[pos] == ')':
                paren_depth -= 1
                if paren_depth == 0:
                    pos += 1
                    break
                pos += 1
            elif text[pos] == '(':
                paren_depth += 1
                pos += 1
            elif text[pos] == ',':
                pos += 1
            else:
                # Parse a value
                value, new_pos = self._parse_expression(text, pos)
                if value:
                    values.append(value)
                    pos = new_pos
                else:
                    pos += 1
        
        return '(' + ', '.join(values) + ')', pos
