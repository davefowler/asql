"""Pre-parser transforms: order."""

from __future__ import annotations

import re

class OrderMixin:

    def _transform_order_desc_prefix(self, text: str) -> str:
        """
        Transform -column in ORDER BY to column DESC.
        
        order by -created_at → order by created_at DESC
        order by -amount, name → order by amount DESC, name
        
        Note: Only transforms ORDER BY clauses that are NOT inside parentheses
        (to avoid transforming ORDER BY inside OVER clauses).
        """
        result = text
        
        # Find all ORDER BY clauses and check if they're inside parentheses
        pattern = r'\border\s+by\s+'
        
        # Track parenthesis depth at each position
        paren_depth = 0
        paren_depths = []
        for char in result:
            if char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            paren_depths.append(paren_depth)
        
        # Find ORDER BY that is NOT inside parentheses
        for match in re.finditer(pattern, result, re.IGNORECASE):
            # Check if this ORDER BY is inside parentheses
            if paren_depths[match.start()] > 0:
                # Inside parens (e.g., OVER clause) - transform the -col there too
                # but only within the parenthesis
                continue
            
            start = match.end()
            
            # Find end of ORDER BY clause (before LIMIT, another clause, or end)
            remaining = result[start:]
            clause_end = len(remaining)
            for kw in ['limit', 'offset', 'having', 'union', 'except', 'intersect', 'qualify']:
                kw_match = re.search(rf'\b{kw}\b', remaining, re.IGNORECASE)
                if kw_match and kw_match.start() < clause_end:
                    clause_end = kw_match.start()
            
            order_clause = remaining[:clause_end]
            
            # Transform -col to col DESC (handles dotted identifiers like table.column)
            def transform_col(col_match: re.Match) -> str:
                col = col_match.group(1)
                return f"{col} DESC"
            
            # Pattern for identifiers: simple or dotted (e.g., orders.created_at)
            # Also handles function calls like year(created_at)
            transformed = re.sub(r'-\s*([a-zA-Z_][a-zA-Z0-9_.]*(?:\s*\([^)]*\))?)', transform_col, order_clause)
            
            # Rebuild result
            result = result[:match.start()] + match.group(0) + transformed + remaining[clause_end:]
            
            # Only process one ORDER BY at the top level
            break
        
        # Now handle ORDER BY inside OVER clauses - transform -col to col DESC
        # Pattern: OVER (...ORDER BY -col...)
        def transform_over_order(match: re.Match) -> str:
            over_content = match.group(1)
            # Transform -col to col DESC inside the OVER clause
            transformed = re.sub(r'-\s*([a-zA-Z_][a-zA-Z0-9_]*)', r'\1 DESC', over_content)
            return f"OVER ({transformed})"
        
        result = re.sub(r'\bover\s*\(([^)]+)\)', transform_over_order, result, flags=re.IGNORECASE)
        
        return result
