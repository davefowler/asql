"""Pre-parser transforms: slugify() URL-friendly slug function."""

from __future__ import annotations

import re
from typing import List, Tuple


class SlugifyMixin:
    """Mixin for transforming slugify() URL-friendly slug function calls.
    
    The slugify() function converts strings to URL-friendly slugs by:
    1. Converting to lowercase
    2. Replacing runs of non-alphanumeric characters with hyphens
    3. Trimming leading/trailing hyphens
    4. Handling NULLs (returns NULL)
    
    This is inspired by dbt_utils-style helpers for repeatable transformations.
    
    Example:
        slugify('Hello World!')  →  'hello-world'
        slugify('Foo  --  Bar')  →  'foo-bar'
        slugify('---Test---')    →  'test'
    """

    def _transform_slugify_function(self, text: str) -> str:
        """
        Transform slugify(expr) to cross-dialect regex replacement.
        
        Cross-dialect strategy:
        - Uses LOWER() for lowercasing (universally supported)
        - Uses REGEXP_REPLACE() for character replacement (PostgreSQL, BigQuery, 
          Snowflake, DuckDB, Trino, Spark)
        - Uses TRIM(BOTH '-' FROM ...) to remove leading/trailing hyphens
        
        Pattern generated:
        TRIM(BOTH '-' FROM REGEXP_REPLACE(LOWER(expr), '[^a-z0-9]+', '-'))
        
        Note: For dialects that don't support REGEXP_REPLACE, this may not work.
        However, most modern analytics databases support this pattern.
        SQLGlot will transpile to the appropriate dialect syntax.
        """
        result = text
        
        # Pattern: slugify(expr)
        # Match slugify(...) function calls (case-insensitive)
        # Use word boundary to avoid matching "slugify" inside other identifiers
        pattern = r'\bslugify\s*\('
        
        def find_slugify_calls(text: str) -> List[Tuple[int, int, str]]:
            """Find all slugify(...) calls with their positions and argument strings."""
            matches = []
            i = 0
            while i < len(text):
                # Look for 'slugify(' (case-insensitive)
                match = re.search(pattern, text[i:], re.IGNORECASE)
                if not match:
                    break
                
                start = i + match.start()
                args_start = i + match.end()  # Position after '('
                
                # Find matching closing paren, handling nested parens
                paren_depth = 1
                j = args_start
                in_string = False
                string_char = None
                
                while j < len(text) and paren_depth > 0:
                    char = text[j]
                    
                    # Handle string literals
                    if char in ("'", '"') and not in_string:
                        in_string = True
                        string_char = char
                    elif char == string_char and in_string:
                        # Check for escaped quote
                        if j + 1 < len(text) and text[j + 1] == string_char:
                            j += 1  # Skip escaped quote
                        else:
                            in_string = False
                            string_char = None
                    elif not in_string:
                        if char == '(':
                            paren_depth += 1
                        elif char == ')':
                            paren_depth -= 1
                    j += 1
                
                if paren_depth == 0:
                    # Found matching closing paren
                    args_str = text[args_start:j-1]  # Exclude closing paren
                    matches.append((start, j, args_str))
                    i = j
                else:
                    # No matching paren found, skip this match
                    i = args_start
            
            return matches
        
        # Find all slugify() calls
        matches = find_slugify_calls(result)
        
        # Process matches from right to left to preserve positions
        for start, end, args_str in reversed(matches):
            args_str = args_str.strip()
            
            if not args_str:
                continue  # Skip if no args
            
            # Build the slugify expression:
            # TRIM(BOTH '-' FROM REGEXP_REPLACE(LOWER(expr), '[^a-z0-9]+', '-'))
            #
            # Step 1: LOWER(expr) - convert to lowercase
            # Step 2: REGEXP_REPLACE(..., '[^a-z0-9]+', '-') - replace non-alphanumeric with hyphens
            # Step 3: TRIM(BOTH '-' FROM ...) - remove leading/trailing hyphens
            
            slugify_expr = (
                f"TRIM(BOTH '-' FROM REGEXP_REPLACE(LOWER({args_str}), '[^a-z0-9]+', '-'))"
            )
            
            # Replace the slugify(...) call with the expression
            result = result[:start] + slugify_expr + result[end:]
        
        return result
