"""Pre-parser transforms: pivot."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

# Dialects that support native PIVOT syntax
NATIVE_PIVOT_DIALECTS = frozenset({"duckdb", "snowflake", "bigquery"})

# Dialects that support dynamic PIVOT (without explicit values)
DYNAMIC_PIVOT_DIALECTS = frozenset({"duckdb", "snowflake"})

class PivotMixin:

    def _transform_explode(self, text: str) -> str:
        """
        Transform ASQL explode clause to a marker for the compiler.
        
        explode array_col as alias → __ASQL_EXPLODE_START__array_col__ASQL_EXPLODE_SEP__alias__ASQL_EXPLODE_END__
        
        The compiler will then generate dialect-specific UNNEST/FLATTEN syntax.
        We use a marker approach because:
        1. UNNEST syntax varies significantly across dialects
        2. SQLGlot's translation of UNNEST aliases differs between read dialects
        3. The compiler knows the target dialect and can generate correct syntax
        """
        result = text
        
        # Pattern: explode column as alias
        # Handles: explode tags as tag
        #          explode split(tags_csv, ',') as tag
        pattern = r'\bexplode\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\s*\([^)]*\))?)\s+as\s+([a-zA-Z_][a-zA-Z0-9_]*)\b'
        
        def replace_explode(match: re.Match) -> str:
            array_expr = match.group(1).strip()
            alias = match.group(2).strip()
            # Use a marker that the compiler will process
            return f"__ASQL_EXPLODE_START__{array_expr}__ASQL_EXPLODE_SEP__{alias}__ASQL_EXPLODE_END__"
        
        result = re.sub(pattern, replace_explode, result, flags=re.IGNORECASE)
        
        return result

    def _transform_unpivot(self, text: str) -> str:
        """
        Transform ASQL unpivot clause to SQL UNION ALL.
        
        unpivot col1, col2, col3 into name, value 
        → UNION ALL approach that works across all dialects
        
        This uses a portable UNION ALL approach rather than native UNPIVOT
        because native UNPIVOT has varying syntax across dialects.
        """
        result = text
        
        # Pattern: unpivot col1, col2, ... into name_col, value_col
        pattern = r'\bunpivot\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\s*,\s*[a-zA-Z_][a-zA-Z0-9_]*)+)\s+into\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*,\s*([a-zA-Z_][a-zA-Z0-9_]*)\b'
        
        match = re.search(pattern, result, re.IGNORECASE)
        if not match:
            return result
        
        cols_str = match.group(1)
        name_col = match.group(2)
        value_col = match.group(3)
        
        # Parse the column list
        cols = [c.strip() for c in cols_str.split(',')]
        
        # Find the table source - look backwards for FROM clause
        before_unpivot = result[:match.start()]
        after_unpivot = result[match.end():]
        
        # Extract FROM table - simple pattern for common case
        from_match = re.search(r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\s+(?:AS\s+)?[a-zA-Z_][a-zA-Z0-9_]*)?)\s*$', 
                               before_unpivot, re.IGNORECASE)
        
        if not from_match:
            # Can't parse the source, return unchanged
            return result
        
        table_ref = from_match.group(1).strip()
        before_from = before_unpivot[:from_match.start()].strip()
        
        # Build UNION ALL query for unpivot
        # Each column becomes a row with (column_name, column_value)
        union_parts = []
        for col in cols:
            union_parts.append(
                f"SELECT *, '{col}' AS {name_col}, {col} AS {value_col} FROM {table_ref}"
            )
        
        unpivot_sql = " UNION ALL ".join(union_parts)
        
        # Generate a complete SELECT * FROM (unpivot_sql) AS __unpivot__ query
        # This way from_first won't add another SELECT *
        result = f"SELECT * FROM ({unpivot_sql}) AS __unpivot__{after_unpivot}"
        
        return result

    def _transform_pivot(self, text: str) -> str:
        """
        Transform ASQL pivot clause to SQL.
        
        Syntax:
        pivot value by category values ('A', 'B', 'C')  -- static with explicit values
        pivot sum(value) by category values ('A', 'B')  -- with aggregation
        pivot sum(value) by category                    -- dynamic (native PIVOT dialects only)
        
        For dialects with native PIVOT support (DuckDB, Snowflake, BigQuery):
        - Emits native PIVOT syntax for both static and dynamic pivots
        - Dynamic pivots (without explicit values) let the database determine columns at runtime
        
        For dialects without native PIVOT (PostgreSQL, MySQL, SQLite):
        - Emits CASE/WHEN expressions for static pivots
        - Raises helpful error for dynamic pivots (values are required)
        """
        result = text
        dialect = getattr(self, 'dialect', None)
        dialect_lower = (dialect or "").lower()
        supports_native_pivot = dialect_lower in NATIVE_PIVOT_DIALECTS
        
        # Pattern 1: pivot value by category values ('A', 'B', 'C')
        # With explicit values list
        pattern_values = r"\bpivot\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\s*\([^)]*\))?)\s+by\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+values\s*\(([^)]+)\)"
        
        match = re.search(pattern_values, result, re.IGNORECASE)
        if match:
            value_expr = match.group(1).strip()
            pivot_col = match.group(2).strip()
            values_str = match.group(3).strip()
            
            # Parse the values - they should be quoted strings
            # Handle both 'value' and "value" formats
            values = re.findall(r"'([^']*)'|\"([^\"]*)\"", values_str)
            values = [v[0] or v[1] for v in values]  # Get the non-empty capture group
            
            if not values:
                # Couldn't parse values, return unchanged
                return result
            
            if supports_native_pivot:
                # Generate native PIVOT syntax
                return self._generate_native_pivot(
                    result, match, value_expr, pivot_col, values, dialect_lower
                )
            else:
                # Generate CASE/WHEN expressions (fallback for unsupported dialects)
                return self._generate_case_when_pivot(
                    result, match, value_expr, pivot_col, values
                )
        
        # Pattern 2: pivot value by category (no values specified - dynamic pivot)
        pattern_basic = r'\bpivot\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\s*\([^)]*\))?)\s+by\s+([a-zA-Z_][a-zA-Z0-9_]*)\b'
        
        match = re.search(pattern_basic, result, re.IGNORECASE)
        if match:
            value_expr = match.group(1).strip()
            pivot_col = match.group(2).strip()
            
            supports_dynamic_pivot = dialect_lower in DYNAMIC_PIVOT_DIALECTS
            
            if supports_dynamic_pivot:
                # Dynamic pivot - use native PIVOT without explicit values
                return self._generate_native_pivot(
                    result, match, value_expr, pivot_col, None, dialect_lower
                )
            else:
                # Raise a helpful error for dialects that don't support dynamic pivot
                dialect_name = dialect_lower if dialect_lower else "this dialect"
                raise ValueError(
                    f"Dynamic pivot (without explicit values) is not supported for {dialect_name}. "
                    f"Please specify values explicitly:\n"
                    f"  pivot {value_expr} by {pivot_col} values ('val1', 'val2', ...)"
                )
        
        return result

    def _generate_native_pivot(
        self,
        text: str,
        match: re.Match,
        value_expr: str,
        pivot_col: str,
        values: Optional[List[str]],
        dialect: str,
    ) -> str:
        """Generate native PIVOT syntax for supported dialects.
        
        Args:
            text: Full query text
            match: Regex match object for the pivot clause
            value_expr: Value expression (e.g., 'amount' or 'sum(amount)')
            pivot_col: Column to pivot on
            values: List of explicit values, or None for dynamic pivot
            dialect: Target dialect (duckdb, snowflake, bigquery)
            
        Returns:
            Query with native PIVOT syntax
        """
        before_pivot = text[:match.start()].strip()
        after_pivot = text[match.end():].strip()
        
        # Check if value_expr is an aggregate function
        agg_match = re.match(r'(sum|avg|count|min|max|total|average)\s*\(([^)]+)\)', value_expr, re.IGNORECASE)
        if agg_match:
            agg_func = agg_match.group(1).upper()
            inner_col = agg_match.group(2).strip()
            agg_expr = f"{agg_func}({inner_col})"
        else:
            # Default to SUM for non-aggregate expressions
            agg_expr = f"SUM({value_expr})"
        
        # Build the values IN clause if explicit values provided
        if values:
            values_in = ", ".join(f"'{v}'" for v in values)
            in_clause = f" IN ({values_in})"
        else:
            in_clause = ""  # Dynamic pivot - no explicit values
        
        if dialect == "duckdb":
            # DuckDB uses: PIVOT ... ON col [IN values] USING agg
            # We need to find the source table and wrap appropriately
            # DuckDB PIVOT is a table expression, so we wrap the query
            
            # Extract table from "from <table>"
            from_match = re.search(r'\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)', before_pivot, re.IGNORECASE)
            if from_match:
                table_name = from_match.group(1)
                # Remove the FROM clause from before_pivot as PIVOT replaces it
                before_from = before_pivot[:from_match.start()].strip()
                
                # DuckDB PIVOT syntax: PIVOT table ON col [IN (values)] USING agg
                pivot_clause = f"PIVOT {table_name} ON {pivot_col}{in_clause} USING {agg_expr}"
                
                # If there's a SELECT before, we need to wrap
                if before_from:
                    result = f"{before_from} FROM ({pivot_clause}) AS __pivot__ {after_pivot}"
                else:
                    # Handle GROUP BY if present
                    group_match = re.search(r'\bgroup\s+by\s+([a-zA-Z_][a-zA-Z0-9_,\s]*)', after_pivot, re.IGNORECASE)
                    if group_match:
                        group_cols = group_match.group(1).strip()
                        after_group = after_pivot[group_match.end():].strip()
                        result = f"SELECT * FROM (PIVOT {table_name} ON {pivot_col}{in_clause} USING {agg_expr} GROUP BY {group_cols}) AS __pivot__ {after_group}"
                    else:
                        result = f"SELECT * FROM ({pivot_clause}) AS __pivot__ {after_pivot}"
                return result
            
        elif dialect in ("snowflake", "bigquery"):
            # Snowflake/BigQuery use: SELECT * FROM table PIVOT (agg FOR col IN (values))
            # For dynamic pivot (no values), use: PIVOT (agg FOR col IN (SELECT DISTINCT col FROM table))
            from_match = re.search(r'\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)', before_pivot, re.IGNORECASE)
            if from_match:
                table_name = from_match.group(1)
                before_from = before_pivot[:from_match.start()].strip()
                
                if values:
                    pivot_clause = f"PIVOT ({agg_expr} FOR {pivot_col} IN ({values_in}))"
                else:
                    # Dynamic pivot - Snowflake/BigQuery can handle this
                    # For Snowflake: PIVOT (agg FOR col IN (ANY ORDER BY col))
                    # For BigQuery: No built-in dynamic pivot, but we try standard syntax
                    if dialect == "snowflake":
                        pivot_clause = f"PIVOT ({agg_expr} FOR {pivot_col} IN (ANY ORDER BY {pivot_col}))"
                    else:  # bigquery
                        # BigQuery doesn't support dynamic PIVOT directly
                        # We'll still emit the syntax and let SQLGlot handle it
                        pivot_clause = f"PIVOT ({agg_expr} FOR {pivot_col})"
                
                # Build the full query
                if before_from:
                    result = f"{before_from} FROM {table_name} {pivot_clause} {after_pivot}"
                else:
                    result = f"SELECT * FROM {table_name} {pivot_clause} {after_pivot}"
                return result
        
        # Fallback: return unchanged
        return text

    def _generate_case_when_pivot(
        self,
        text: str,
        match: re.Match,
        value_expr: str,
        pivot_col: str,
        values: List[str],
    ) -> str:
        """Generate CASE/WHEN expressions for dialects without native PIVOT.
        
        Args:
            text: Full query text
            match: Regex match object for the pivot clause
            value_expr: Value expression (e.g., 'amount' or 'sum(amount)')
            pivot_col: Column to pivot on
            values: List of explicit values to pivot
            
        Returns:
            Query with CASE/WHEN expressions
        """
        # Check if value_expr is an aggregate function
        is_aggregate = bool(re.match(r'(sum|avg|count|min|max|total|average)\s*\(', value_expr, re.IGNORECASE))
        
        # Generate CASE expressions for each pivot value
        case_exprs = []
        for val in values:
            # Sanitize the value to make it a valid column name
            col_name = re.sub(r'[^a-zA-Z0-9_]', '_', val)
            if is_aggregate:
                # Wrap aggregate around CASE
                agg_func = value_expr.split('(')[0].strip()
                inner_col = re.search(r'\(([^)]+)\)', value_expr).group(1)
                case_exprs.append(
                    f"{agg_func}(CASE WHEN {pivot_col} = '{val}' THEN {inner_col} END) AS {col_name}"
                )
            else:
                case_exprs.append(
                    f"MAX(CASE WHEN {pivot_col} = '{val}' THEN {value_expr} END) AS {col_name}"
                )
        
        pivot_sql = ", ".join(case_exprs)
        
        # Replace pivot clause with marker - the CASE expressions will be added
        # We use a marker that _transform_from_first will handle
        before_pivot = text[:match.start()]
        after_pivot = text[match.end():]
        
        # Store the pivot expressions in a special marker format
        # The from_first transform will pick this up and add to SELECT
        return f"{before_pivot}__PIVOT_COLS__({pivot_sql})__{after_pivot}"

    def _transform_pivot_marker(self, text: str) -> str:
        """
        Expand __PIVOT_COLS__ markers in the SELECT clause.
        
        After from_first has run, the query has SELECT * or SELECT cols.
        We need to append the pivot columns to the SELECT.
        
        __PIVOT_COLS__(col1, col2)__ → SELECT existing, col1, col2
        """
        result = text
        
        # Pattern to find pivot markers
        pattern = r'__PIVOT_COLS__\((.+?)\)__'
        
        match = re.search(pattern, result)
        if not match:
            return result
        
        pivot_cols = match.group(1)
        
        # Remove the marker from its current position
        before_marker = result[:match.start()]
        after_marker = result[match.end():]
        result_no_marker = before_marker.strip() + " " + after_marker.strip()
        
        # Find SELECT clause and append pivot columns
        select_match = re.match(r'^(.*?\bSELECT\s+)(.*?)(\s+FROM\b.*)$', result_no_marker, re.IGNORECASE | re.DOTALL)
        
        if select_match:
            before_select = select_match.group(1)
            select_clause = select_match.group(2).strip()
            after_select = select_match.group(3)
            
            # Append pivot columns to the select clause
            if select_clause == '*':
                # Replace * with pivot columns only (pivot implies aggregation)
                new_select = pivot_cols
            else:
                # Append to existing columns
                new_select = f"{select_clause}, {pivot_cols}"
            
            result = f"{before_select}{new_select}{after_select}"
        else:
            # Couldn't find SELECT, leave marker in place (will cause error)
            pass
        
        return result
