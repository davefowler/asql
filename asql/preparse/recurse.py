"""Pre-parser transforms: recurse (recursive CTEs)."""

from __future__ import annotations

import re
from typing import Optional, Tuple


class RecurseMixin:
    """Mixin to handle recursive query syntax.
    
    Transforms:
        from employees
          where id = 1
          recurse(manager_id)
        
        -- or with max depth:
        from employees
          where id = 1
          recurse(manager_id, 5)
    
    Into a recursive CTE that traverses the hierarchy.
    """

    def _transform_recurse(self, text: str) -> str:
        """
        Transform recurse(fk_column [, max_depth]) to a recursive CTE.
        
        The recurse clause must follow a FROM...WHERE pattern.
        The WHERE clause becomes the anchor condition.
        The FK column is used to traverse the hierarchy.
        """
        result = text
        
        # Pattern: recurse(fk_column) or recurse(fk_column, max_depth)
        recurse_pattern = r'\brecurse\s*\(\s*(\w+)(?:\s*,\s*(\d+))?\s*\)'
        match = re.search(recurse_pattern, result, re.IGNORECASE)
        
        if not match:
            return result
        
        fk_column = match.group(1)
        max_depth_str = match.group(2)
        max_depth = int(max_depth_str) if max_depth_str else 100  # Default max depth for safety
        
        recurse_start = match.start()
        recurse_end = match.end()
        
        # Extract the query before recurse
        query_before = result[:recurse_start].strip()
        query_after = result[recurse_end:].strip()
        
        # Parse the query to extract table name and anchor condition
        parsed = self._parse_recurse_query(query_before)
        if not parsed:
            # Can't parse - return unchanged
            return result
        
        table_name, anchor_condition, select_clause = parsed
        
        # Determine the target column (the PK that the FK points to)
        # By convention, FKs like "manager_id" point to "id" on the same table
        target_column = "id"
        
        # Generate the recursive CTE
        cte_name = f"_recurse_{table_name}"
        
        # Build the recursive CTE
        recursive_cte = self._build_recursive_cte(
            cte_name=cte_name,
            table_name=table_name,
            anchor_condition=anchor_condition,
            fk_column=fk_column,
            target_column=target_column,
            max_depth=max_depth,
        )
        
        # Parse continuation clauses (select, order by, limit, etc.)
        final_select, remaining_clauses = self._parse_continuation(query_after)
        
        # Build the final query
        if final_select:
            final_query = f"{recursive_cte} SELECT {final_select} FROM {cte_name}"
        else:
            final_query = f"{recursive_cte} SELECT * FROM {cte_name}"
        
        if remaining_clauses:
            final_query = f"{final_query} {remaining_clauses}"
        
        return final_query

    def _parse_recurse_query(self, query: str) -> Optional[Tuple[str, str, Optional[str]]]:
        """
        Parse the query before recurse to extract table name and anchor condition.
        
        Returns: (table_name, anchor_condition, select_clause) or None if can't parse.
        """
        # Look for FROM table_name [WHERE condition]
        # The query might have SELECT before FROM in transformed state
        
        # First, try to find FROM clause
        from_pattern = r'\bfrom\s+(\w+)'
        from_match = re.search(from_pattern, query, re.IGNORECASE)
        
        if not from_match:
            return None
        
        table_name = from_match.group(1)
        
        # Find WHERE clause
        where_pattern = r'\bwhere\s+(.+?)(?:\s*$)'
        where_match = re.search(where_pattern, query, re.IGNORECASE)
        
        if where_match:
            anchor_condition = where_match.group(1).strip()
        else:
            # No WHERE - use TRUE as anchor (select all as roots)
            anchor_condition = "1=1"
        
        # Check for SELECT clause
        select_pattern = r'\bselect\s+(.+?)\s+from\b'
        select_match = re.search(select_pattern, query, re.IGNORECASE)
        select_clause = select_match.group(1) if select_match else None
        
        return (table_name, anchor_condition, select_clause)

    def _parse_continuation(self, query_after: str) -> Tuple[Optional[str], str]:
        """
        Parse continuation clauses after recurse().
        
        Handles: select X, order by Y, limit Z, etc.
        
        Returns: (select_clause, remaining_clauses)
        """
        if not query_after:
            return (None, "")
        
        query_after = query_after.strip()
        
        # Check if it starts with SELECT
        select_match = re.match(r'\bselect\s+(.+?)(?=\s+(?:order\s+by|limit|having|qualify|where|group\s+by)\b|\s*$)', 
                               query_after, re.IGNORECASE | re.DOTALL)
        
        if select_match:
            select_clause = select_match.group(1).strip()
            remaining = query_after[select_match.end():].strip()
            return (select_clause, remaining)
        
        # No SELECT - everything is remaining clauses (ORDER BY, LIMIT, etc.)
        return (None, query_after)

    def _build_recursive_cte(
        self,
        cte_name: str,
        table_name: str,
        anchor_condition: str,
        fk_column: str,
        target_column: str,
        max_depth: int,
    ) -> str:
        """
        Build the WITH RECURSIVE CTE for hierarchical traversal.
        
        Structure:
            WITH RECURSIVE cte_name AS (
                -- Anchor: rows matching the initial condition
                SELECT *, 1 AS _level FROM table WHERE anchor_condition
                UNION ALL
                -- Recursive: rows whose FK matches a row already in the CTE
                SELECT t.*, cte._level + 1
                FROM table t
                JOIN cte_name ON t.fk_column = cte.target_column
                WHERE cte._level < max_depth
            )
        """
        # Use table alias in recursive part to avoid ambiguity
        table_alias = table_name[0].lower()  # First letter as alias
        
        # Build the CTE - don't use EXCEPT, just include _level in output
        # Users can filter it out with explicit SELECT if needed
        cte = f"""WITH RECURSIVE {cte_name} AS (
    SELECT *, 1 AS _level FROM {table_name} WHERE {anchor_condition}
    UNION ALL
    SELECT {table_alias}.*, {cte_name}._level + 1
    FROM {table_name} {table_alias}
    JOIN {cte_name} ON {table_alias}.{fk_column} = {cte_name}.{target_column}
    WHERE {cte_name}._level < {max_depth}
)"""
        
        return cte

