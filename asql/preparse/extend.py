"""Pre-parser transforms: extend (add computed columns)."""

from __future__ import annotations

import re
from typing import List, Tuple


class ExtendMixin:
    """Mixin for transforming extend statements to add computed columns."""

    def _transform_extend(self, text: str) -> str:
        """
        Transform extend clauses to add computed columns without SELECT *.

        extend age > 15 as is_adult
        → SELECT *, age > 15 AS is_adult FROM ...

        extend when age > 18 then "adult" otherwise "minor" as category
        → SELECT *, CASE WHEN age > 18 THEN "adult" ELSE "minor" END AS category FROM ...

        Multiple extends can be chained:
        extend age > 15 as is_adult
        extend days_since(created_at) as account_age
        → SELECT *, age > 15 AS is_adult, days_since(created_at) AS account_age FROM ...

        This must run before _transform_from_first so it can modify the SELECT clause.
        """
        result = text

        # Track expressions to add: (expression, alias)
        extend_exprs: List[Tuple[str, str]] = []

        # Pattern: extend <expression> as <alias>
        # The expression can span multiple lines (for when expressions)
        # Look for 'extend' followed by content ending with 'as <identifier>'
        # Stop at the next clause keyword
        extend_pattern = r'\bextend\s+(.*?)\s+as\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\s*(?:extend|from|where|group|order|limit|join|left|right|inner|outer|select|except|rename|replace|$)|\s*$)'

        # Process all extend clauses
        while True:
            match = re.search(extend_pattern, result, re.IGNORECASE | re.DOTALL)
            if not match:
                break

            expr = match.group(1).strip()
            alias = match.group(2).strip()

            # Store the expression and alias
            extend_exprs.append((expr, alias))

            # Remove this extend clause from the result
            result = result[:match.start()] + result[match.end():]

        # If no extend clauses found, return unchanged
        if not extend_exprs:
            return result

        # Now add the expressions to the SELECT clause
        # Check if there's already a SELECT clause
        select_match = re.search(r'\bselect\s+', result, re.IGNORECASE)

        if select_match:
            # There's already a SELECT - need to append our expressions
            select_pos = select_match.end()

            # Find what follows SELECT until FROM or other clause
            rest = result[select_pos:]
            from_match = re.search(r'\bfrom\b', rest, re.IGNORECASE)
            if from_match:
                select_clause = rest[:from_match.start()].strip()
                after_select = rest[from_match.start():]
            else:
                select_clause = rest.strip()
                after_select = ""

            # Build the new expressions to add
            new_exprs = [f"{expr} AS {alias}" for expr, alias in extend_exprs]

            # Append to existing SELECT clause
            if select_clause:
                new_select_clause = select_clause + ", " + ", ".join(new_exprs)
            else:
                new_select_clause = ", ".join(new_exprs)

            result = result[:select_match.start()] + f"SELECT {new_select_clause} " + after_select
        else:
            # No SELECT yet - we're in from-first mode
            # Add SELECT with * and our new expressions
            select_parts = ["*"]

            for expr, alias in extend_exprs:
                select_parts.append(f"{expr} AS {alias}")

            # Insert SELECT clause before FROM
            from_match = re.search(r'\bfrom\b', result, re.IGNORECASE)
            if from_match:
                select_clause = ', '.join(select_parts)
                result = f"SELECT {select_clause} " + result[from_match.start():]

        return result
