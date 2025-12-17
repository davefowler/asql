"""Pre-parser transforms: pivot."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

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
        Transform ASQL pivot clause to SQL with CASE/GROUP BY.
        
        Syntax:
        pivot value by category values ('A', 'B', 'C')  -- static with explicit values
        pivot sum(value) by category values ('A', 'B')  -- with aggregation
        
        For static pivots (known values), this generates CASE expressions that work
        across all SQL dialects.
        
        Note: Dynamic pivot (values from subquery) is not supported in pure SQL
        compilation, as it requires knowing all pivot values at compile time to generate
        individual CASE expressions. For dynamic pivoting, use warehouse-specific PIVOT
        operators (e.g., Snowflake's PIVOT) or raw SQL.
        """
        result = text
        
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
            before_pivot = result[:match.start()]
            after_pivot = result[match.end():]
            
            # Store the pivot expressions in a special marker format
            # The from_first transform will pick this up and add to SELECT
            result = f"{before_pivot}__PIVOT_COLS__({pivot_sql})__{after_pivot}"
            
            return result
        
        # Pattern 2: pivot value by category (no values specified)
        # Leave a helpful error message
        pattern_basic = r'\bpivot\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\s*\([^)]*\))?)\s+by\s+([a-zA-Z_][a-zA-Z0-9_]*)\b'
        
        match = re.search(pattern_basic, result, re.IGNORECASE)
        if match:
            # Raise a helpful error
            value_expr = match.group(1).strip()
            pivot_col = match.group(2).strip()
            raise ValueError(
                f"pivot requires explicit values. Use: pivot {value_expr} by {pivot_col} values ('val1', 'val2', ...)"
            )
        
        return result

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
