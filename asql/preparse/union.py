"""Pre-parser transforms: UNION/INTERSECT/EXCEPT set operations."""

from __future__ import annotations

import re
from typing import List, Tuple, Optional


class UnionMixin:
    """Mixin for transforming UNION/INTERSECT/EXCEPT with ASQL queries."""

    def _transform_union_operations(self, text: str) -> str:
        """
        Transform set operations (UNION, INTERSECT, EXCEPT) between ASQL queries.
        
        Example:
            from orders where status = 'completed' select id, amount
            union all
            from refunds select id, amount
        
        Becomes:
            SELECT id, amount FROM orders WHERE status = 'completed'
            UNION ALL
            SELECT id, amount FROM refunds
        
        Note: This transform must run BEFORE other transformations because
        we need to detect the boundary between queries.
        """
        result = text.strip()
        
        # Pattern to match set operators on their own line or inline
        # This matches: UNION, UNION ALL, INTERSECT, EXCEPT
        set_op_pattern = r'\b(union\s+all|union|intersect|except)\b'
        
        # Find all set operation keywords (case-insensitive)
        matches = list(re.finditer(set_op_pattern, result, re.IGNORECASE))
        
        if not matches:
            return result
        
        # Split the query at set operation boundaries
        parts: List[Tuple[str, Optional[str]]] = []  # (query, set_operator_after)
        last_end = 0
        
        for match in matches:
            query_before = result[last_end:match.start()].strip()
            set_op = match.group(1).upper()
            
            if query_before:
                parts.append((query_before, set_op))
            
            last_end = match.end()
        
        # Add the final query (after the last set operator)
        final_query = result[last_end:].strip()
        if final_query:
            parts.append((final_query, None))
        
        if len(parts) <= 1:
            # No valid split happened
            return result
        
        # Process each query part separately
        processed_parts: List[str] = []
        
        for i, (query, set_op) in enumerate(parts):
            # Preparse this query part
            from asql.preparse.preparser import ASQLPreParser
            sub_parser = ASQLPreParser(query, self.settings, self.dialect)
            
            # Run the preparse (but don't include set operators)
            parsed_query = sub_parser.preparse()
            
            # Merge any CTEs from sub-parser
            self.ctes.extend(sub_parser.ctes)
            
            # Handle ORDER BY/LIMIT on the last query part
            # These should apply to the combined result, not just the last query
            # For now, keep them as-is (they'll be in the parsed output)
            
            processed_parts.append(parsed_query)
            
            if set_op:
                processed_parts.append(set_op)
        
        return ' '.join(processed_parts)

