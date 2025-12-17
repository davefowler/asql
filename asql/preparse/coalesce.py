"""Pre-parser transforms: coalesce."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

class CoalesceMixin:

    def _transform_coalesce_operator(self, text: str) -> str:
        """
        Transform ?? coalesce operator to COALESCE function.
        
        a ?? b → COALESCE(a, b)
        a ?? b ?? c → COALESCE(a, b, c)
        """
        result = text
        
        # Process ?? chains from right to left to handle nesting correctly
        # Pattern: simple_expr ?? simple_expr (where simple_expr is identifier, string, number, or function call)
        # Note: function calls can have nested parens, so we need to handle those
        
        # First, find all ?? occurrences and process them
        while '??' in result:
            # Find the rightmost ?? first (so inner coalesces are built first)
            pos = result.rfind('??')
            if pos == -1:
                break
            
            # Find the left expression
            # Go backward from ?? to find the start of the left operand
            left_end = pos
            while left_end > 0 and result[left_end - 1] in ' \t':
                left_end -= 1
            
            left_start = left_end - 1
            if left_start >= 0:
                # Handle parenthesized expressions
                if result[left_start] == ')':
                    # Find matching open paren
                    paren_depth = 1
                    left_start -= 1
                    while left_start >= 0 and paren_depth > 0:
                        if result[left_start] == ')':
                            paren_depth += 1
                        elif result[left_start] == '(':
                            paren_depth -= 1
                        left_start -= 1
                    left_start += 1
                    # Check for function name before the paren
                    if left_start > 0:
                        func_start = left_start - 1
                        while func_start >= 0 and result[func_start] in ' \t':
                            func_start -= 1
                        while func_start >= 0 and (result[func_start].isalnum() or result[func_start] == '_'):
                            func_start -= 1
                        if func_start >= 0:
                            left_start = func_start + 1
                # Handle string literals
                elif result[left_start] in '"\'':
                    quote = result[left_start]
                    left_start -= 1
                    while left_start >= 0 and result[left_start] != quote:
                        left_start -= 1
                # Handle identifiers and numbers
                else:
                    while left_start >= 0 and (result[left_start].isalnum() or result[left_start] in '_.:'):
                        left_start -= 1
                    left_start += 1
            else:
                left_start = 0
            
            left_expr = result[left_start:left_end].strip()
            
            # Find the right expression
            right_start = pos + 2
            while right_start < len(result) and result[right_start] in ' \t':
                right_start += 1
            
            right_end = right_start
            if right_end < len(result):
                # Handle string literals
                if result[right_end] in '"\'':
                    quote = result[right_end]
                    right_end += 1
                    while right_end < len(result) and result[right_end] != quote:
                        right_end += 1
                    if right_end < len(result):
                        right_end += 1
                # Handle identifiers, numbers, and function calls
                else:
                    while right_end < len(result) and (result[right_end].isalnum() or result[right_end] in '_.:'):
                        right_end += 1
                    # Check for function call
                    if right_end < len(result) and result[right_end] == '(':
                        paren_depth = 1
                        right_end += 1
                        while right_end < len(result) and paren_depth > 0:
                            if result[right_end] == '(':
                                paren_depth += 1
                            elif result[right_end] == ')':
                                paren_depth -= 1
                            right_end += 1
            
            right_expr = result[right_start:right_end].strip()
            
            if left_expr and right_expr:
                # Build COALESCE expression
                coalesce_expr = f"COALESCE({left_expr}, {right_expr})"
                
                # Replace in result
                result = result[:left_start] + coalesce_expr + result[right_end:]
            else:
                # Can't parse - break to avoid infinite loop
                break
        
        return result
