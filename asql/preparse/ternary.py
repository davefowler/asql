"""Pre-parser transforms: ternary conditional expressions."""

from __future__ import annotations

from typing import Optional, Tuple


class TernaryMixin:
    """Mixin for transforming ternary expressions to CASE WHEN."""

    def _transform_ternary_expressions(self, text: str) -> str:
        """
        Transform ternary expressions to SQL CASE WHEN syntax.
        
        condition ? true_value : false_value → CASE WHEN condition THEN true_value ELSE false_value END
        
        Examples:
        amount > 1000 ? 'high' : 'low'
        status == 'active' ? 1 : 0
        (a + b) ? sum(revenue) : 0
        """
        result = text
        
        # Process from right to left to handle nested ternaries correctly
        # Find all ? operators and match them with their corresponding : operators
        while True:
            # Find the rightmost ? that hasn't been processed
            q_pos = result.rfind('?')
            if q_pos == -1:
                break
            
            # Skip if inside a string or comment
            before = result[:q_pos]
            if (before.count("'") % 2 != 0) or (before.count('"') % 2 != 0):
                # Inside a string, skip this one
                result = result[:q_pos] + '\x00' + result[q_pos + 1:]
                continue
            
            # Skip if part of ?? (coalesce operator)
            if q_pos + 1 < len(result) and result[q_pos + 1] == '?':
                result = result[:q_pos] + '\x00' + result[q_pos + 1:]
                continue
            
            # Find the matching : operator
            colon_pos = self._find_matching_colon(result, q_pos)
            if colon_pos == -1:
                # No matching colon, skip this ?
                result = result[:q_pos] + '\x00' + result[q_pos + 1:]
                continue
            
            # Parse the three parts: condition, true_value, false_value
            condition, cond_start = self._parse_expression_backward(result, q_pos)
            true_value, true_end = self._parse_expression_forward(result, q_pos + 1, colon_pos)
            false_value, false_end = self._parse_expression_forward(result, colon_pos + 1, len(result))

            def strip_condition_prefix(expr: str) -> str:
                lowered = expr.lower()
                # If we accidentally captured leading clause text like "from t select ...",
                # keep only the expression after the last SELECT.
                # Handle both " select " and "select " (start of string).
                idx = lowered.rfind(" select ")
                if idx != -1:
                    return expr[idx + len(" select "):].strip()
                idx = lowered.rfind("select ")
                if idx != -1:
                    return expr[idx + len("select "):].strip()
                return expr.strip()

            def strip_trailing_clause(expr: str) -> str:
                lowered = expr.lower()
                # Stop before common clause/alias keywords when the false arm is inside SELECT lists.
                for marker in [" as ", " from ", " where ", " group by ", " order by ", " limit ", " having ", " qualify "]:
                    idx = lowered.find(marker)
                    if idx != -1:
                        return expr[:idx].strip()
                return expr.strip()

            if condition:
                condition = strip_condition_prefix(condition)
            if true_value is not None:
                true_value = strip_trailing_clause(true_value)
            if false_value is not None:
                false_value = strip_trailing_clause(false_value)
            
            if condition and true_value is not None and false_value is not None:
                # Build CASE WHEN expression
                case_expr = f"CASE WHEN {condition} THEN {true_value} ELSE {false_value} END"
                
                # Replace the ternary expression
                result = result[:cond_start] + case_expr + result[false_end:]
            else:
                # Can't parse, skip this ?
                result = result[:q_pos] + '\x00' + result[q_pos + 1:]
        
        # Restore any skipped ? characters
        result = result.replace('\x00', '?')
        
        return result
    
    def _find_matching_colon(self, text: str, q_pos: int) -> int:
        """
        Find the matching : operator for a ? operator.
        
        The matching : is the first : after the ? that is at the same nesting level
        (same number of parentheses, brackets, etc.).
        """
        pos = q_pos + 1
        paren_depth = 0
        bracket_depth = 0
        in_string = False
        string_char: Optional[str] = None
        
        while pos < len(text):
            char = text[pos]
            
            # Handle string literals
            if not in_string and char in ('"', "'"):
                in_string = True
                string_char = char
                pos += 1
                continue
            
            if in_string:
                if char == string_char:
                    # Check for escaped quote
                    if pos + 1 < len(text) and text[pos + 1] == string_char:
                        pos += 2
                        continue
                    in_string = False
                    string_char = None
                pos += 1
                continue
            
            # Track parentheses and brackets
            if char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            elif char == '[':
                bracket_depth += 1
            elif char == ']':
                bracket_depth -= 1
            
            # Check for : operator at same nesting level
            if char == ':' and paren_depth == 0 and bracket_depth == 0:
                # Make sure it's not part of :: (cast operator)
                if pos + 1 < len(text) and text[pos + 1] == ':':
                    pos += 2
                    continue
                return pos
            
            pos += 1
        
        return -1
    
    def _parse_expression_backward(self, text: str, end_pos: int) -> Tuple[Optional[str], int]:
        """
        Parse an expression backward from end_pos.
        
        Returns:
            (expression, start_pos)
        """
        pos = end_pos - 1

        # Skip whitespace
        while pos >= 0 and text[pos] in ' \t\n':
            pos -= 1

        if pos < 0:
            return None, end_pos

        paren_depth = 0
        bracket_depth = 0
        in_string = False
        string_char: Optional[str] = None

        start_pos = 0

        while pos >= 0:
            char = text[pos]

            # Clause boundaries (only meaningful at top level, outside strings).
            if not in_string and paren_depth == 0 and bracket_depth == 0:
                lower_prefix = text[:pos + 1].lower()
                for marker in ("select ", "where ", "having ", "qualify "):
                    if lower_prefix.endswith(marker):
                        start_pos = pos + 1
                        pos = -1
                        break
                if pos == -1:
                    break

            # Handle string literals
            if not in_string and char in ('"', "'"):
                in_string = True
                string_char = char
                pos -= 1
                continue

            if in_string:
                if char == string_char:
                    # Check for escaped quote ('' or "")
                    if pos > 0 and text[pos - 1] == string_char:
                        pos -= 2
                        continue
                    in_string = False
                    string_char = None
                pos -= 1
                continue

            # Track parentheses/brackets
            if char == ')':
                paren_depth += 1
                pos -= 1
                continue
            if char == ']':
                bracket_depth += 1
                pos -= 1
                continue
            if char == '(':
                if paren_depth == 0:
                    start_pos = pos + 1
                    break
                paren_depth -= 1
                pos -= 1
                continue
            if char == '[':
                if bracket_depth == 0:
                    start_pos = pos + 1
                    break
                bracket_depth -= 1
                pos -= 1
                continue

            # Stop at delimiters at top level
            if paren_depth == 0 and bracket_depth == 0:
                if char in (',', ';', '\n'):
                    start_pos = pos + 1
                    break

            pos -= 1

        expr = text[start_pos:end_pos].strip()
        if not expr:
            return None, end_pos
        
        return expr, start_pos
    
    def _parse_expression_forward(self, text: str, start_pos: int, max_pos: int) -> Tuple[Optional[str], int]:
        """
        Parse an expression forward from start_pos up to max_pos.
        
        Returns:
            (expression, end_pos)
        """
        pos = start_pos
        
        # Skip whitespace
        while pos < max_pos and text[pos] in ' \t\n':
            pos += 1
        
        if pos >= max_pos:
            return None, start_pos
        
        paren_depth = 0
        bracket_depth = 0
        in_string = False
        string_char: Optional[str] = None

        end_pos = pos

        while pos < max_pos:
            char = text[pos]

            # Handle string literals
            if not in_string and char in ('"', "'"):
                in_string = True
                string_char = char
                pos += 1
                end_pos = pos
                continue

            if in_string:
                if char == string_char:
                    # Check for escaped quote ('' or "")
                    if pos + 1 < max_pos and text[pos + 1] == string_char:
                        pos += 2
                        end_pos = pos
                        continue
                    in_string = False
                    string_char = None
                pos += 1
                end_pos = pos
                continue

            # Stop at a closing paren/bracket that would end our expression at top level
            if char == ')' and paren_depth == 0 and bracket_depth == 0:
                break
            if char == ']' and bracket_depth == 0 and paren_depth == 0:
                break

            # Track parentheses/brackets
            if char == '(':
                paren_depth += 1
                pos += 1
                end_pos = pos
                continue
            if char == ')':
                paren_depth = max(0, paren_depth - 1)
                pos += 1
                end_pos = pos
                continue
            if char == '[':
                bracket_depth += 1
                pos += 1
                end_pos = pos
                continue
            if char == ']':
                bracket_depth = max(0, bracket_depth - 1)
                pos += 1
                end_pos = pos
                continue

            # Stop at delimiters at top level
            if paren_depth == 0 and bracket_depth == 0:
                remaining = text[pos:max_pos].lower()
                for marker in (" as ", " from ", " where ", " group by ", " order by ", " limit ", " having ", " qualify "):
                    if remaining.startswith(marker):
                        break
                else:
                    remaining = None
                if remaining is not None:
                    break
                if char in (',', ';', '\n'):
                    break
                if char == '?':
                    # Nested ternary - stop here, let outer ternary handle it
                    break
                if char == ':':
                    # This is the matching colon for a nested ternary - stop here
                    break

            pos += 1
            end_pos = pos

        expr = text[start_pos:end_pos].strip()
        if not expr:
            return None, start_pos
        
        return expr, end_pos
