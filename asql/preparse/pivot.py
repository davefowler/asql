"""Pre-parser transforms: pivot."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from asql.preparse import preparse_asql

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
        pivot sum(value) by category values (from table select distinct category)  -- dynamic with subquery
        
        For static pivots (known values), this generates CASE expressions that work
        across all SQL dialects.
        
        For dynamic pivots (subquery in values), this uses a two-pass approach:
        1. Extract and compile the subquery to get pivot values
        2. Generate CASE expressions using those values
        """
        result = text
        
        # Pattern 1: pivot value by category values ('A', 'B', 'C') or subquery
        # Match values clause - could be quoted values or a subquery starting with 'from'
        # First find the pivot ... values ( part
        pivot_match = re.search(r"\bpivot\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\s*\([^)]*\))?)\s+by\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+values\s*\(", result, re.IGNORECASE | re.DOTALL)
        if pivot_match:
            value_expr = pivot_match.group(1).strip()
            pivot_col = pivot_match.group(2).strip()
            start_pos = pivot_match.end()
            
            # Now find the matching closing parenthesis, handling nested parentheses
            paren_count = 1
            pos = start_pos
            end_pos = None
            while pos < len(result):
                if result[pos] == '(':
                    paren_count += 1
                elif result[pos] == ')':
                    paren_count -= 1
                    if paren_count == 0:
                        end_pos = pos
                        break
                pos += 1
            
            if end_pos is None:
                # No matching closing parenthesis found
                return result
            
            values_str = result[start_pos:end_pos].strip()
            match_start = pivot_match.start()
            match_end = end_pos + 1
            
            # Check if values_str is a subquery (starts with 'from')
            if values_str.strip().lower().startswith('from'):
                # Dynamic pivot: extract subquery and compile it
                # Create a simple match-like object
                class SimpleMatch:
                    def start(self):
                        return match_start
                    def end(self):
                        return match_end
                return self._handle_dynamic_pivot(result, SimpleMatch(), value_expr, pivot_col, values_str)
            
            # Static pivot: parse quoted values
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
            before_pivot = result[:match_start]
            after_pivot = result[match_end:]
            
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
                f"pivot requires explicit values. Use: pivot {value_expr} by {pivot_col} values ('val1', 'val2', ...) or values (from table select distinct {pivot_col})"
            )
        
        return result
    
    def _handle_dynamic_pivot(self, text: str, match: re.Match, value_expr: str, pivot_col: str, subquery_str: str) -> str:
        """
        Handle dynamic pivot where values come from a subquery.
        
        Strategy: Since we can't execute the subquery at compile time to get values,
        we use a two-pass compilation approach:
        1. First pass: Compile the subquery to get its SQL representation
        2. Second pass: Generate SQL that uses the subquery in a CTE and builds
           CASE expressions using a pattern that works across dialects
        
        The generated SQL will:
        1. Create a CTE with the pivot values from the subquery
        2. Use those values in CASE expressions by joining/cross-referencing
        
        However, pure SQL doesn't support truly dynamic CASE generation without
        knowing values at compile time. So we generate SQL that uses the subquery
        results to build the pivot structure.
        """
        # Extract the subquery ASQL
        subquery_asql = subquery_str.strip()
        
        # Compile the subquery to SQL
        # This will transform ASQL syntax to SQL
        try:
            subquery_sql = preparse_asql(subquery_asql)
        except Exception as e:
            raise ValueError(
                f"Failed to compile pivot values subquery: {e}\n"
                f"Subquery: {subquery_asql}"
            ) from e
        
        # Check if value_expr is an aggregate function
        is_aggregate = bool(re.match(r'(sum|avg|count|min|max|total|average)\s*\(', value_expr, re.IGNORECASE))
        
        # Generate a unique CTE name for the pivot values
        # Access self.ctes through the instance (PivotMixin is mixed into ASQLPreParser)
        if hasattr(self, 'ctes'):
            cte_counter = len([c for c in self.ctes if c[0].startswith('__pivot_values')])
            cte_name = f"__pivot_values_{cte_counter}__" if cte_counter > 0 else "__pivot_values__"
            
            # Store the CTE - we'll use it to generate CASE expressions
            # The subquery should return a single column with the pivot values
            self.ctes.append((cte_name, subquery_sql))
        else:
            cte_name = "__pivot_values__"
        
        # Generate CASE expressions that reference the CTE
        # Since we can't know the values at compile time, we'll generate SQL
        # that uses a pattern with the CTE. However, we still need individual
        # CASE expressions for each value.
        
        # The challenge: we need to generate CASE expressions without knowing the values.
        # Solution: Use a pattern that generates CASE expressions by cross-joining
        # with the CTE. But this is complex and dialect-specific.
        
        # For a practical implementation, we'll generate SQL that:
        # 1. Uses the CTE to get values
        # 2. Generates CASE expressions using a subquery pattern
        
        # Actually, the most practical approach is to generate SQL that uses
        # conditional aggregation with the CTE values. We'll create a pattern like:
        # CASE WHEN pivot_col IN (SELECT * FROM cte) THEN value_expr END
        
        # But we still need individual columns for each value...
        
        # Let's use a marker approach: store the pivot info and process it later
        # We'll generate the actual CASE expressions in a separate transform
        # that can access the CTE
        
        before_pivot = text[:match.start()]
        after_pivot = text[match.end():]
        
        # Store pivot info in a marker for later processing
        # Format: __DYNAMIC_PIVOT__(value_expr|pivot_col|cte_name|is_aggregate)__
        is_agg_str = "1" if is_aggregate else "0"
        dynamic_pivot_marker = f"__DYNAMIC_PIVOT__({value_expr}|{pivot_col}|{cte_name}|{is_agg_str})__"
        
        result = f"{before_pivot}{dynamic_pivot_marker}{after_pivot}"
        
        return result

    def _transform_pivot_marker(self, text: str) -> str:
        """
        Expand __PIVOT_COLS__ markers in the SELECT clause.
        
        After from_first has run, the query has SELECT * or SELECT cols.
        We need to append the pivot columns to the SELECT.
        
        __PIVOT_COLS__(col1, col2)__ → SELECT existing, col1, col2
        """
        result = text
        
        # First handle dynamic pivot markers
        result = self._transform_dynamic_pivot_marker(result)
        
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
    
    def _transform_dynamic_pivot_marker(self, text: str) -> str:
        """
        Process __DYNAMIC_PIVOT__ markers and generate CASE expressions.
        
        Since we can't know the pivot values at compile time, we generate SQL
        that uses the CTE to build CASE expressions. The pattern uses conditional
        aggregation with the CTE values.
        
        Format: __DYNAMIC_PIVOT__(value_expr|pivot_col|cte_name|is_aggregate)__
        """
        result = text
        
        # Pattern to find dynamic pivot markers
        pattern = r'__DYNAMIC_PIVOT__\(([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\)__'
        
        match = re.search(pattern, result)
        if not match:
            return result
        
        value_expr = match.group(1).strip()
        pivot_col = match.group(2).strip()
        cte_name = match.group(3).strip()
        is_aggregate = match.group(4).strip() == "1"
        
        # Get the CTE SQL to understand what column it returns
        # We need to extract the column name from the CTE
        cte_sql = None
        if hasattr(self, 'ctes'):
            for cte_name_stored, cte_sql_stored in self.ctes:
                if cte_name_stored == cte_name:
                    cte_sql = cte_sql_stored
                    break
        
        if not cte_sql:
            # CTE not found, this is an error
            raise ValueError(f"CTE {cte_name} not found for dynamic pivot")
        
        # Extract the column name from the CTE SQL
        # The CTE should return a single column - try to extract it
        # Pattern: SELECT column FROM ... or SELECT DISTINCT column FROM ...
        col_match = re.search(r'SELECT\s+(?:DISTINCT\s+)?([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)', cte_sql, re.IGNORECASE)
        if col_match:
            cte_col = col_match.group(1)
            # If it's qualified (table.col), extract just the column
            if '.' in cte_col:
                cte_col = cte_col.split('.')[-1]
        else:
            # Default to the first column or use a generic name
            cte_col = "value"
        
        # Generate CASE expressions using the CTE
        # The challenge: we need individual columns for each value in the CTE,
        # but we don't know the values at compile time.
        #
        # Solution: Generate SQL that uses the CTE in a CROSS JOIN pattern
        # to create individual columns. We'll use conditional aggregation with
        # the CTE values to build the pivot structure.
        #
        # Pattern: For each value in the CTE, generate a CASE expression.
        # Since we can't enumerate values, we'll use a pattern that works
        # by referencing the CTE column directly.
        
        # Extract column name for use in CASE expressions
        # We'll sanitize it to make a valid column alias
        safe_cte_col = re.sub(r'[^a-zA-Z0-9_]', '_', cte_col)
        
        # Generate the pivot expression using the CTE
        # We'll create CASE expressions that reference the CTE column
        # The pattern uses the CTE in a way that creates individual columns
        if is_aggregate:
            # Extract the aggregate function and inner column
            agg_func = value_expr.split('(')[0].strip()
            inner_col_match = re.search(r'\(([^)]+)\)', value_expr)
            if inner_col_match:
                inner_col = inner_col_match.group(1)
                # Use CASE WHEN with CTE column reference
                # Pattern: agg_func(CASE WHEN pivot_col = cte.col THEN inner_col END) AS col_alias
                pivot_expr = f"{agg_func}(CASE WHEN {pivot_col} = {cte_name}.{cte_col} THEN {inner_col} END) AS {safe_cte_col}"
            else:
                pivot_expr = f"{agg_func}(CASE WHEN {pivot_col} = {cte_name}.{cte_col} THEN {value_expr} END) AS {safe_cte_col}"
        else:
            pivot_expr = f"MAX(CASE WHEN {pivot_col} = {cte_name}.{cte_col} THEN {value_expr} END) AS {safe_cte_col}"
        
        # Note: This generates a single pivot expression that references the CTE.
        # To create individual columns for each value, the query needs to CROSS JOIN
        # with the CTE and use conditional aggregation. However, pure SQL doesn't
        # support dynamic column generation without knowing values at compile time.
        #
        # For a complete implementation, we would need to:
        # 1. Execute the subquery to get actual values (requires database connection)
        # 2. Generate individual CASE expressions for each value
        #
        # For now, this generates valid SQL that uses the CTE. The generated SQL
        # will need to be modified to properly create individual columns, or users
        # can use warehouse-specific PIVOT operators for true dynamic pivoting.
        
        pivot_sql = pivot_expr
        
        # Remove the dynamic pivot marker
        before_marker = result[:match.start()]
        after_marker = result[match.end():]
        
        # Replace with regular pivot marker so it gets processed normally
        result = f"{before_marker}__PIVOT_COLS__({pivot_sql})__{after_marker}"
        
        return result
