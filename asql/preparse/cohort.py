"""Pre-parser transforms: cohort analysis."""

from __future__ import annotations

import re
from typing import Optional, TYPE_CHECKING

from asql.errors import ASQLSyntaxError

if TYPE_CHECKING:
    from asql.schema import Schema

class CohortMixin:
    
    def _infer_cohort_join_key(self, activity_table: str, cohort_table: str) -> str:
        """
        Infer the join key between activity and cohort tables.
        
        Priority:
        1. Schema lookup (explicit relationships)
        2. Convention-based inference ({singular_table}_id)
        
        Args:
            activity_table: The activity table (FROM clause)
            cohort_table: The cohort table (e.g., users)
            
        Returns:
            The join key column name (e.g., user_id)
        """
        # Try schema-based lookup first
        settings = getattr(self, 'settings', None)
        if settings:
            schema: Optional["Schema"] = getattr(settings, 'schema', None)
            if schema:
                # Look for relationship from activity_table to cohort_table
                rel = schema.find_relationship(activity_table, cohort_table)
                if rel:
                    return rel.from_column
        
        # Fall back to convention-based inference
        # e.g., users → user_id, customers → customer_id
        singular = cohort_table.rstrip('s') if cohort_table.endswith('s') else cohort_table
        return f"{singular}_id"

    def _transform_cohort_by(self, text: str) -> str:
        """
        Transform cohort by clause to SQL with CTEs and joins.
        
        from events
          group by month(event_date) (count(distinct user_id) as active)
          cohort by month(users.signup_date)
        
        Transforms to SQL with cohort CTEs and proper joins.
        """
        result = text
        
        # Pattern: cohort by [segment,]* <func>(<table.column>) [on <join_key>] [( <derivations> )]
        # Find cohort by clause - must be at end of query or before ORDER BY/LIMIT
        cohort_pattern = r'\bcohort\s+by\s+((?:[a-zA-Z_][a-zA-Z0-9_.]*\s*,\s*)*)(month|week|day)\s*\(\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\)(?:\s+on\s+([a-zA-Z_][a-zA-Z0-9_]*))?(?:\s*\(([^)]*)\))?'
        
        match = re.search(cohort_pattern, result, re.IGNORECASE)
        if not match:
            return result
        
        # Extract components
        granularity = match.group(2).lower()  # month, week, or day
        cohort_col_ref = match.group(3)  # e.g., users.signup_date
        explicit_join_key = match.group(4)  # optional: on user_id
        derivations = match.group(5)  # optional: (pct(active, cohort_size) as retention)
        
        # Store the position where cohort by clause starts (before we modify result)
        cohort_by_start = match.start()
        cohort_by_end = match.end()
        
        # Parse cohort column reference to get table and column
        if '.' in cohort_col_ref:
            cohort_table, cohort_col = cohort_col_ref.rsplit('.', 1)
        else:
            cohort_table = None
            cohort_col = cohort_col_ref
        
        # Find the activity table (the FROM clause) - search before cohort by clause
        from_match = re.search(r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', result[:cohort_by_start], re.IGNORECASE)
        if not from_match:
            return result  # Can't process without FROM
        
        activity_table = from_match.group(1)
        
        # Determine join key: explicit > schema lookup > convention inference
        if explicit_join_key:
            join_key = explicit_join_key
        elif cohort_table:
            join_key = self._infer_cohort_join_key(activity_table, cohort_table)
        else:
            raise ASQLSyntaxError(
                "Cohort analysis requires a cohort table reference or explicit join key. "
                "Use 'cohort by month(users.signup_date)' or 'cohort by month(signup_date) on user_id'."
            )
        
        # Determine period calculation - use EXTRACT with AGE for PostgreSQL-style
        period_expr_map = {
            'month': "EXTRACT(YEAR FROM AGE({date_col}, cb.cohort_month)) * 12 + EXTRACT(MONTH FROM AGE({date_col}, cb.cohort_month))",
            'week': "EXTRACT(EPOCH FROM ({date_col} - cb.cohort_month)) / 604800",
            'day': "EXTRACT(DAY FROM ({date_col} - cb.cohort_month))"
        }
        
        # Determine date trunc function
        trunc_func_map = {
            'month': "DATE_TRUNC('month'",
            'week': "DATE_TRUNC('week'",
            'day': "DATE_TRUNC('day'"
        }
        trunc_func = trunc_func_map.get(granularity, "DATE_TRUNC('month'")
        
        # Find the activity date column from GROUP BY (before cohort by clause)
        group_by_match = re.search(r'\bGROUP\s+BY\s+([^\n]+?)(?=\s+(?:ORDER|LIMIT|HAVING|cohort|$))', result[:cohort_by_start], re.IGNORECASE | re.DOTALL)
        activity_date_col = None
        if group_by_match:
            group_by_clause = group_by_match.group(1).strip()
            # Look for month(...), week(...), or day(...) pattern
            date_func_match = re.search(r'\b(month|week|day)\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)', group_by_clause, re.IGNORECASE)
            if date_func_match:
                activity_date_col = date_func_match.group(2)
        
        # Try to find activity date column if not found in GROUP BY
        if not activity_date_col:
            common_dates = ['event_date', 'created_at', 'timestamp', 'date', 'order_date']
            for col in common_dates:
                if re.search(rf'\b{col}\b', result[:cohort_by_start], re.IGNORECASE):
                    activity_date_col = col
                    break
        
        if not activity_date_col:
            raise ASQLSyntaxError(
                "Cannot determine activity date column for cohort analysis. "
                "Use a date function in GROUP BY (e.g., 'group by month(event_date)') "
                "or ensure your query references a recognizable date column "
                "(event_date, created_at, timestamp, date, order_date)."
            )
        
        # Build period expression - use alias for activity table
        period_template = period_expr_map.get(granularity, period_expr_map['month'])
        activity_alias = 'e'
        period_expr = period_template.format(date_col=f"{activity_alias}.{activity_date_col}")
        
        # Build cohort CTE
        if cohort_table:
            cohort_from = f"FROM {cohort_table}"
        else:
            cohort_from = f"FROM {activity_table}"
            cohort_table = activity_table
        
        # Use proper column reference in CTE
        cohort_col_full = f"{cohort_table}.{cohort_col}" if cohort_table else cohort_col
        
        cohort_cte = f"""WITH cohort_base AS (
  SELECT {join_key}, {trunc_func}, {cohort_col_full}) AS cohort_month
  {cohort_from}
  WHERE {cohort_col_full} IS NOT NULL
),
cohort_sizes AS (
  SELECT cohort_month, COUNT(DISTINCT {join_key}) AS cohort_size
  FROM cohort_base
  GROUP BY cohort_month
)"""
        
        # Remove the cohort by clause first (before other modifications)
        result = result[:cohort_by_start] + result[cohort_by_end:]
        
        # Now find positions in the modified result
        # Find SELECT clause
        select_match = re.search(r'\bSELECT\s+', result, re.IGNORECASE)
        if not select_match:
            return result  # Can't process without SELECT
        
        # Find FROM clause position
        from_match = re.search(r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', result, re.IGNORECASE)
        if not from_match:
            return result
        
        from_pos = from_match.end()
        
        # Add alias to activity table if not present
        from_with_alias = re.search(rf'\bFROM\s+{activity_table}\s+([a-zA-Z_][a-zA-Z0-9_]*)', result, re.IGNORECASE)
        if not from_with_alias:
            # Add alias after table name
            result = result[:from_match.end()] + f" {activity_alias}" + result[from_match.end():]
            from_pos = from_match.end() + len(activity_alias) + 1
            # Re-find FROM after modification
            from_match = re.search(r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', result, re.IGNORECASE)
            from_pos = from_match.end() if from_match else from_pos
        
        # Insert JOINs after FROM clause
        join_clause = f" JOIN cohort_base cb ON {activity_alias}.{join_key} = cb.{join_key} JOIN cohort_sizes cs ON cb.cohort_month = cs.cohort_month "
        
        # Find where to insert (after FROM, before WHERE/GROUP BY)
        insert_pos = from_pos
        next_clause_match = re.search(r'\b(WHERE|GROUP\s+BY|ORDER\s+BY|LIMIT)\b', result[from_pos:], re.IGNORECASE)
        if next_clause_match:
            insert_pos = from_pos + next_clause_match.start()
        
        result = result[:insert_pos] + join_clause + result[insert_pos:]
        
        # Modify GROUP BY to include cohort_month and period
        # Re-find GROUP BY after modifications (cohort by clause removed, JOINs added)
        group_by_match_after = re.search(r'\bGROUP\s+BY\s+[^\n]+?(?=\s+(?:ORDER|LIMIT|HAVING|$))', result, re.IGNORECASE | re.DOTALL)
        if group_by_match_after:
            group_by_start = group_by_match_after.start()
            group_by_end = group_by_match_after.end()
            
            # Replace GROUP BY with cohort-aware version
            # Note: Can't use AS alias in GROUP BY, so repeat the expression
            new_group_by = f"GROUP BY cb.cohort_month, {period_expr}"
            result = result[:group_by_start] + new_group_by + result[group_by_end:]
        
        # Add cohort columns to SELECT - insert at start of SELECT list
        select_match = re.search(r'\bSELECT\s+', result, re.IGNORECASE)
        if select_match:
            select_pos = select_match.end()
            # Find end of SELECT clause (before FROM)
            select_end_match = re.search(r'\bFROM\b', result[select_pos:], re.IGNORECASE)
            if select_end_match:
                select_end = select_pos + select_end_match.start()
                select_clause = result[select_pos:select_end].strip()
                
                # Prepend cohort columns with proper spacing
                new_select_clause = f"cb.cohort_month, {period_expr} AS period, cs.cohort_size, {select_clause}"
                result = result[:select_pos] + new_select_clause + " " + result[select_end:]
        
        # Add ORDER BY if not present
        order_by_match = re.search(r'\bORDER\s+BY\b', result, re.IGNORECASE)
        if not order_by_match:
            limit_match = re.search(r'\bLIMIT\b', result, re.IGNORECASE)
            if limit_match:
                result = result[:limit_match.start()] + " ORDER BY cb.cohort_month, period " + result[limit_match.start():]
            else:
                result = result + " ORDER BY cb.cohort_month, period"
        else:
            # Prepend cohort ordering to existing ORDER BY
            order_by_pos = order_by_match.end()
            result = result[:order_by_match.start()] + "ORDER BY cb.cohort_month, period, " + result[order_by_pos:]
        
        # Process derivations if present
        if derivations:
            derivations_clean = derivations.strip()
            if derivations_clean:
                # Add derivations to SELECT
                select_match = re.search(r'\bSELECT\s+', result, re.IGNORECASE)
                if select_match:
                    # Find end of SELECT clause
                    select_end_match = re.search(r'\bFROM\b', result[select_match.end():], re.IGNORECASE)
                    if select_end_match:
                        select_end = select_match.end() + select_end_match.start()
                        # Add derivations before FROM
                        result = result[:select_end] + f", {derivations_clean}" + result[select_end:]
        
        # Prepend cohort CTEs - check if there's already a WITH clause
        with_match = re.search(r'^\s*WITH\s+', result, re.IGNORECASE)
        if with_match:
            # Insert cohort CTEs into existing WITH clause
            # Find the end of the first CTE name
            first_cte_end = re.search(r'AS\s*\(', result[with_match.end():], re.IGNORECASE)
            if first_cte_end:
                insert_pos = with_match.end() + first_cte_end.start()
                # Insert before first CTE
                result = result[:with_match.end()] + cohort_cte[5:] + ", " + result[with_match.end():]  # Remove "WITH " prefix
        else:
            # Prepend WITH clause
            result = cohort_cte + " " + result
        
        return result
