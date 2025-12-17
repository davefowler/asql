"""Pre-parser transforms: key() surrogate key function."""

from __future__ import annotations

import re
from typing import List, Tuple


class KeyMixin:
    """Mixin for transforming key() surrogate key function calls."""

    def _transform_key_function(self, text: str) -> str:
        """
        Transform key(col1, col2, ...) to dialect-appropriate hash function.
        
        The key() function generates deterministic surrogate keys by:
        1. Concatenating values with a delimiter ('||')
        2. Handling NULLs consistently (converting to empty string via COALESCE)
        3. Hashing the result
        
        Cross-dialect strategy:
        - Uses MD5() for hashing (supported in PostgreSQL, MySQL, SQL Server, SQLite)
        - Uses CONCAT() for concatenation (broadly supported)
        - Converts all values to VARCHAR before concatenation for type consistency
        - Uses '||' as delimiter (standard SQL string concatenation operator)
        
        Pattern generated:
        MD5(CONCAT(COALESCE(CAST(col1 AS VARCHAR), ''), '||', COALESCE(CAST(col2 AS VARCHAR), ''), ...))
        
        Note: For dialects that don't support MD5 (like BigQuery), SQLGlot's dialect
        transpiler automatically handles the conversion to SHA256 or other hash functions
        during SQL generation. The preparser generates MD5() as a standard pattern that
        SQLGlot can then transpile appropriately for each target dialect.
        """
        result = text
        
        # Pattern: key(expr1, expr2, ...)
        # Match key(...) function calls (case-insensitive)
        # Use word boundary to avoid matching "key" inside other identifiers
        # Need to handle nested parentheses, so we'll find matches manually
        pattern = r'\bkey\s*\('
        
        def find_key_calls(text: str) -> List[Tuple[int, int, str]]:
            """Find all key(...) calls with their positions and argument strings."""
            matches = []
            i = 0
            while i < len(text):
                # Look for 'key(' (case-insensitive)
                match = re.search(pattern, text[i:], re.IGNORECASE)
                if not match:
                    break
                
                start = i + match.start()
                args_start = i + match.end()  # Position after '('
                
                # Find matching closing paren, handling nested parens
                paren_depth = 1
                j = args_start
                while j < len(text) and paren_depth > 0:
                    if text[j] == '(':
                        paren_depth += 1
                    elif text[j] == ')':
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
        
        # Find all key() calls
        matches = find_key_calls(result)
        
        # Process matches from right to left to preserve positions
        for start, end, args_str in reversed(matches):
            # Parse arguments (handle nested parentheses, function calls, etc.)
            args = self._parse_function_args(args_str)
            
            if not args:
                continue  # Skip if no args
            
            # Build COALESCE expressions for each arg to handle NULLs deterministically
            # Cast to VARCHAR for type consistency, then COALESCE to empty string
            coalesced_args = []
            for arg in args:
                arg = arg.strip()
                # Wrap in COALESCE with CAST to handle NULLs and type normalization
                coalesced_arg = f"COALESCE(CAST({arg} AS VARCHAR), '')"
                coalesced_args.append(coalesced_arg)
            
            # Build CONCAT expression with delimiter '||' between values
            # This ensures consistent delimiter injection even with NULLs (which become '')
            concat_parts = []
            for i, arg in enumerate(coalesced_args):
                if i > 0:
                    concat_parts.append("'||'")
                concat_parts.append(arg)
            
            # Use CONCAT() which is broadly supported
            concat_expr = "CONCAT(" + ", ".join(concat_parts) + ")"
            
            # Hash the concatenated string using MD5
            # MD5 is supported in PostgreSQL, MySQL, SQL Server, SQLite
            # For BigQuery/Snowflake, SQLGlot's dialect transpiler automatically handles conversion
            hash_expr = f"MD5({concat_expr})"
            
            # Replace the key(...) call with hash expression
            result = result[:start] + hash_expr + result[end:]
        
        return result
    
    def _parse_function_args(self, args_str: str) -> List[str]:
        """
        Parse function arguments, handling nested parentheses, string literals, and quoted identifiers.
        
        Args:
            args_str: String containing function arguments
            
        Returns:
            List of argument strings
        """
        args = []
        current_arg = []
        paren_depth = 0
        in_string = False
        string_char = None
        i = 0
        
        while i < len(args_str):
            char = args_str[i]
            
            # Handle string literals (single or double quotes)
            if char in ("'", '"') and not in_string:
                in_string = True
                string_char = char
                current_arg.append(char)
            elif char == string_char and in_string:
                # Check if it's an escaped quote
                if i + 1 < len(args_str) and args_str[i + 1] == string_char:
                    # Escaped quote (e.g., 'don''t')
                    current_arg.append(char)
                    current_arg.append(char)
                    i += 1
                else:
                    # End of string
                    in_string = False
                    string_char = None
                    current_arg.append(char)
            elif in_string:
                # Inside string literal - include everything
                current_arg.append(char)
            elif char == '(':
                paren_depth += 1
                current_arg.append(char)
            elif char == ')':
                paren_depth -= 1
                current_arg.append(char)
            elif char == ',' and paren_depth == 0:
                # Top-level comma - argument separator
                if current_arg:
                    args.append(''.join(current_arg).strip())
                    current_arg = []
            else:
                current_arg.append(char)
            
            i += 1
        
        # Add last argument
        if current_arg:
            args.append(''.join(current_arg).strip())
        
        return args
