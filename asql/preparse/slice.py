"""Pre-parser transforms: slice syntax for substring extraction."""

from __future__ import annotations

import re
from typing import Optional


class SliceMixin:
    """Mixin for transforming Python-style slice syntax to SQL functions.
    
    Transforms:
    - expr[start:end] → SUBSTRING(expr, start, end - start + 1)
    - expr[start:]    → SUBSTRING(expr, start)
    - expr[:end]      → LEFT(expr, end)
    - expr[-n:]       → RIGHT(expr, n)
    
    SQLGlot then handles dialect-specific transpilation:
    - DuckDB: SUBSTRING(x, 1, 5)
    - Postgres: SUBSTRING(x FROM 1 FOR 5)
    - Snowflake: SUBSTRING(x, 1, 5)
    - etc.
    """

    # Pattern to match slice syntax: identifier[start:end]
    # Captures:
    #   1: The expression before the bracket (identifier, function call, etc.)
    #   2: The start index (optional, can be negative)
    #   3: The end index (optional)
    #
    # Examples:
    #   email[1:5]      → expr="email", start="1", end="5"
    #   email[1:]       → expr="email", start="1", end=""
    #   email[:5]       → expr="email", start="", end="5"
    #   email[-5:]      → expr="email", start="-5", end=""
    #   func(x)[1:3]    → expr="func(x)", start="1", end="3"
    
    # Match an expression followed by [start:end]
    # Expression can be: identifier, table.column, or function call
    _SLICE_PATTERN = re.compile(
        r'''
        (                               # Group 1: The expression
            (?:                         # Non-capturing group for expression alternatives
                [a-zA-Z_][a-zA-Z0-9_]*  # Simple identifier
                (?:\.[a-zA-Z_][a-zA-Z0-9_]*)*  # Optional dot-separated parts (table.column)
                (?:\([^)]*\))?          # Optional function call with simple args
            |
                \([^)]+\)               # Or a parenthesized expression
            )
        )
        \[                              # Opening bracket
        (-?\d*)                         # Group 2: Start index (optional, can be negative)
        :                               # The colon separator
        (-?\d*)                         # Group 3: End index (optional)
        \]                              # Closing bracket
        ''',
        re.VERBOSE
    )

    def _transform_slice_syntax(self, text: str) -> str:
        """
        Transform Python-style slice syntax to SQL SUBSTRING/LEFT/RIGHT functions.
        
        Examples:
            email[1:5]   → SUBSTRING(email, 1, 5)
            email[1:]    → SUBSTRING(email, 1)
            email[:5]    → LEFT(email, 5)
            email[-5:]   → RIGHT(email, 5)
        """
        result = text
        
        # Track skipped matches (inside strings) with unique placeholders
        skipped_matches: dict[str, str] = {}
        skip_counter = 0
        
        # Keep replacing until no more matches (handles nested/multiple slices)
        max_iterations = 100  # Safety limit
        iterations = 0
        
        while iterations < max_iterations:
            match = self._SLICE_PATTERN.search(result)
            if not match:
                break
            
            # Check if we're inside a string literal
            before_match = result[:match.start()]
            if self._is_inside_string(before_match):
                # Skip this match by replacing temporarily with a unique placeholder
                original_text = match.group(0)
                placeholder = f'\x00SLICE_SKIP_{skip_counter}\x00'
                skipped_matches[placeholder] = original_text
                skip_counter += 1
                result = result[:match.start()] + placeholder + result[match.end():]
                iterations += 1
                continue
            
            expr = match.group(1)
            start_str = match.group(2)
            end_str = match.group(3)
            
            # Determine the replacement
            replacement = self._build_slice_replacement(expr, start_str, end_str)
            
            # Replace the match
            result = result[:match.start()] + replacement + result[match.end():]
            iterations += 1
        
        # Restore skipped slices (these were inside strings)
        for placeholder, original_text in skipped_matches.items():
            result = result.replace(placeholder, original_text)
        
        return result
    
    def _build_slice_replacement(self, expr: str, start_str: str, end_str: str) -> str:
        """Build the SQL function replacement for a slice expression."""
        has_start = bool(start_str)
        has_end = bool(end_str)
        
        if has_start and has_end:
            # expr[start:end] → SUBSTRING(expr, start, end - start + 1)
            start = int(start_str)
            end = int(end_str)
            length = end - start + 1
            return f"SUBSTRING({expr}, {start}, {length})"
        
        elif has_start and not has_end:
            # Check for negative start (last N characters)
            start = int(start_str)
            if start < 0:
                # expr[-n:] → RIGHT(expr, n)
                return f"RIGHT({expr}, {-start})"
            else:
                # expr[start:] → SUBSTRING(expr, start)
                return f"SUBSTRING({expr}, {start})"
        
        elif not has_start and has_end:
            # expr[:end] → LEFT(expr, end)
            end = int(end_str)
            return f"LEFT({expr}, {end})"
        
        else:
            # expr[:] → just return the expression (no-op)
            return expr
    
    def _is_inside_string(self, text_before: str) -> bool:
        """Check if we're inside a string literal based on quote counts."""
        single_quotes = text_before.count("'") - text_before.count("\\'")
        double_quotes = text_before.count('"') - text_before.count('\\"')
        return (single_quotes % 2 != 0) or (double_quotes % 2 != 0)
