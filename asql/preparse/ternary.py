"""Pre-parser transforms: ternary conditional expressions."""

from __future__ import annotations

import re
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
        
        # Track parentheses and brackets
        paren_depth = 0
        bracket_depth = 0
        in_string = False
        string_char: Optional[str] = None
        start_pos = pos + 1
        
        while pos >= 0:
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
            
            # Track parentheses and brackets
            if char == ')':
                paren_depth += 1
            elif char == '(':
                paren_depth -= 1
                if paren_depth == 0:
                    # Found matching open paren, check for function name
                    start_pos = pos
                    pos -= 1
                    # Skip whitespace
                    while pos >= 0 and text[pos] in ' \t\n':
                        pos -= 1
                    # Parse identifier
                    while pos >= 0 and (text[pos].isalnum() or text[pos] == '_'):
                        pos -= 1
                    start_pos = pos + 1
                    break
            elif char == ']':
                bracket_depth += 1
            elif char == '[':
                bracket_depth -= 1
            
            # Stop at operators or delimiters at top level
            if paren_depth == 0 and bracket_depth == 0 and not in_string:
                if char in (',', ';', '=', '<', '>', '!', '+', '-', '*', '/', '%', '&', '|', '^'):
                    # Check for multi-character operators
                    if char in ('=', '<', '>', '!', '&', '|') and pos > 0:
                        prev_char = text[pos - 1]
                        if (char == '=' and prev_char in ('=', '<', '>', '!')) or \
                           (char == '&' and prev_char == '&') or \
                           (char == '|' and prev_char == '|'):
                            pos -= 1
                            continue
                    start_pos = pos + 1
                    break
            
            pos -= 1
        
        if start_pos > end_pos:
            return None, end_pos
        
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
        
        # Track parentheses and brackets
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
                    # Check for escaped quote
                    if pos + 1 < max_pos and text[pos + 1] == string_char:
                        pos += 2
                        end_pos = pos
                        continue
                    in_string = False
                    string_char = None
                    pos += 1
                    end_pos = pos
                    continue
                pos += 1
                end_pos = pos
                continue
            
            # Track parentheses and brackets
            if char == '(':
                paren_depth += 1
                pos += 1
                end_pos = pos
                continue
            elif char == ')':
                paren_depth -= 1
                pos += 1
                end_pos = pos
                if paren_depth == 0:
                    # Check if there's more (function call, cast, etc.)
                    # For now, stop here
                    break
                continue
            elif char == '[':
                bracket_depth += 1
                pos += 1
                end_pos = pos
                continue
            elif char == ']':
                bracket_depth -= 1
                pos += 1
                end_pos = pos
                continue
            
            # Stop at operators or delimiters at top level
            if paren_depth == 0 and bracket_depth == 0 and not in_string:
                if char in (',', ';', '=', '<', '>', '!', '+', '-', '*', '/', '%', '&', '|', '^', '?', ':'):
                    # Check for multi-character operators
                    if char in ('=', '<', '>', '!', '&', '|') and pos + 1 < max_pos:
                        next_char = text[pos + 1]
                        if (char == '=' and next_char == '=') or \
                           (char == '<' and next_char == '=') or \
                           (char == '>' and next_char == '=') or \
                           (char == '!' and next_char == '=') or \
                           (char == '&' and next_char == '&') or \
                           (char == '|' and next_char == '|'):
                            # Multi-character operator, but we stop before it
                            break
                    # Stop before this operator
                    break
                elif char == '?':
                    # Nested ternary - stop here, let outer ternary handle it
                    break
                elif char == ':':
                    # This is the matching colon for a nested ternary - stop here
                    break
            
            pos += 1
            end_pos = pos
        
        expr = text[start_pos:end_pos].strip()
        if not expr:
            return None, start_pos
        
        return expr, end_pos
