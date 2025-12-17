"""ASQL compiler - transforms ASQL to SQL.

This module implements the ASQL compilation pipeline:
1. Pre-parse: Transform ASQL structural syntax to SQL-like syntax
2. Parse: Use SQLGlot with ASQL dialect to parse the SQL-like syntax
3. Generate: Output SQL in the target dialect

The pre-parser handles ASQL-specific structural transformations that fundamentally
differ from SQL (FROM-first, pipeline operators, aggregate blocks, etc.).

The ASQL dialect handles expression-level ASQL syntax that fits within SQLGlot's
extension model (custom tokens, function parsers, etc.).

Settings can be configured via:
- asql.config.yaml file
- Inline SET statements in the query

Auto-spine feature:
When auto_spine is enabled (default), date truncation functions in GROUP BY
automatically include gap-filling CTEs to ensure all dates appear in results.
"""

from typing import Optional, List, Tuple, Dict, Set
import sqlglot
from sqlglot import exp
from sqlglot.dialects import Dialect
import re

from asql.errors import ASQLCompilationError, ASQLSyntaxError
from asql.preparser import preparse_asql, ASQLPreParser
from asql.dialect import register_asql_dialect
from asql.config import CompileSettings, KNOWN_COMPILE_SETTINGS

# Ensure ASQL dialect is registered
register_asql_dialect()

# Date truncation functions that trigger auto-spine
DATE_TRUNC_FUNCTIONS = {
    'year', 'month', 'week', 'day', 'hour', 'quarter',
    'date_trunc',
}

# Mapping from truncation unit to interval for generate_series
TRUNC_TO_INTERVAL = {
    'year': '1 year',
    'month': '1 month',
    'week': '1 week',
    'day': '1 day',
    'hour': '1 hour',
    'quarter': '3 months',
}


def _detect_rollup_cube(stmt: exp.Expression) -> Tuple[bool, bool, List[str]]:
    """
    Detect if a statement uses ROLLUP or CUBE in GROUP BY.
    
    Returns: (has_rollup, has_cube, rollup_cube_columns)
    - has_rollup: True if ROLLUP is present
    - has_cube: True if CUBE is present
    - rollup_cube_columns: List of column names in the ROLLUP/CUBE (in order for ROLLUP)
    
    Note: ASQL doesn't have native ROLLUP/CUBE syntax - this only handles raw SQL
    passthrough. If SQL passthrough is ever removed, this ROLLUP/CUBE handling
    (and the related NULL spine logic) can be deleted.
    """
    has_rollup = False
    has_cube = False
    columns = []
    
    rollup = stmt.find(exp.Rollup)
    if rollup:
        has_rollup = True
        for expr in rollup.expressions:
            if isinstance(expr, exp.Column):
                columns.append(expr.name)
            elif isinstance(expr, exp.Alias):
                columns.append(expr.alias)
            else:
                columns.append(expr.sql())
    
    cube = stmt.find(exp.Cube)
    if cube:
        has_cube = True
        for expr in cube.expressions:
            if isinstance(expr, exp.Column):
                columns.append(expr.name)
            elif isinstance(expr, exp.Alias):
                columns.append(expr.alias)
            else:
                columns.append(expr.sql())
    
    return has_rollup, has_cube, columns


def _is_guarantee_wrapped(expr: exp.Expression) -> Tuple[bool, Optional[List[str]]]:
    """
    Check if an expression is wrapped in guarantee() for explicit spine.
    
    Returns: (is_guarantee, explicit_values)
    - is_guarantee: True if wrapped in guarantee()
    - explicit_values: List of values if provided, None otherwise
    """
    inner = expr.this if isinstance(expr, exp.Alias) else expr
    
    if isinstance(inner, exp.Anonymous):
        if inner.name and inner.name.lower() == 'guarantee':
            # Check for explicit values (second arg could be array or subquery)
            if len(inner.expressions) > 1:
                values_expr = inner.expressions[1]
                # Handle array literal: ['a', 'b', 'c']
                if isinstance(values_expr, exp.Array):
                    values = [str(e.this).strip("'\"") for e in values_expr.expressions]
                    return True, values
                # For now, return True but no explicit values for other cases
                return True, None
            return True, None
    return False, None


def _unwrap_guarantee(expr: exp.Expression) -> exp.Expression:
    """Unwrap guarantee() wrapper and return the inner expression."""
    if isinstance(expr, exp.Alias):
        inner = expr.this
        if isinstance(inner, exp.Anonymous) and inner.name and inner.name.lower() == 'guarantee':
            # Get the first inner expression (the column/function) and re-wrap with alias
            if inner.expressions:
                return exp.Alias(this=inner.expressions[0], alias=expr.alias)
        return expr
    
    if isinstance(expr, exp.Anonymous) and expr.name and expr.name.lower() == 'guarantee':
        if expr.expressions:
            return expr.expressions[0]
    return expr


def _remove_guarantee_wrappers(stmt: exp.Expression) -> exp.Expression:
    """
    Remove all guarantee() wrappers from a statement before SQL generation.
    
    guarantee(expr) -> expr
    guarantee(expr, values) AS alias -> expr AS alias
    """
    if not isinstance(stmt, exp.Select):
        return stmt
    
    # Process GROUP BY clause
    group = stmt.find(exp.Group)
    if group:
        new_exprs = []
        for expr in group.expressions:
            is_guarantee, _ = _is_guarantee_wrapped(expr)
            if is_guarantee:
                new_exprs.append(_unwrap_guarantee(expr))
            else:
                new_exprs.append(expr)
        group.set("expressions", new_exprs)
    
    # Process SELECT clause (in case guarantee appears there too)
    if stmt.expressions:
        new_exprs = []
        for expr in stmt.expressions:
            is_guarantee, _ = _is_guarantee_wrapped(expr)
            if is_guarantee:
                new_exprs.append(_unwrap_guarantee(expr))
            else:
                new_exprs.append(expr)
        stmt.set("expressions", new_exprs)
    
    return stmt


def _find_non_date_group_by_columns(stmt: exp.Expression) -> List[Tuple[str, exp.Expression]]:
    """
    Find non-date columns in GROUP BY that need cross-join with distinct values.
    
    For mixed GROUP BY (date + non-date), we cross-join the date spine
    with all distinct values of non-date columns to get complete combinations.
    
    Returns list of tuples: (alias, expression)
    """
    results = []
    
    if not isinstance(stmt, exp.Select):
        return results
    
    group_by = stmt.find(exp.Group)
    if not group_by:
        return results
    
    for group_expr in group_by.expressions:
        # Get the inner expression
        if isinstance(group_expr, exp.Alias):
            alias = group_expr.alias
            inner = group_expr.this
        else:
            inner = group_expr
            alias = inner.name if isinstance(inner, exp.Column) else None
        
        # Check if wrapped in guarantee() - handled separately
        is_guarantee, _ = _is_guarantee_wrapped(group_expr)
        if is_guarantee:
            continue
        
        # Check for date truncation functions
        func_name = None
        if isinstance(inner, exp.Anonymous):
            func_name = inner.name.lower() if inner.name else None
        elif isinstance(inner, exp.Func):
            func_name = inner.sql_name().lower() if hasattr(inner, 'sql_name') else type(inner).__name__.lower()
        
        # If it's NOT a date truncation function, it's a non-date column
        if func_name not in DATE_TRUNC_FUNCTIONS and alias:
            results.append((alias, group_expr))
    
    return results


def _find_date_trunc_in_group_by(
    stmt: exp.Expression
) -> List[Tuple[str, str, exp.Expression, Optional[List[str]]]]:
    """
    Find date truncation expressions in GROUP BY clause.
    
    Returns list of tuples: (alias, trunc_unit, original_expression, explicit_values)
    - explicit_values is set when guarantee() is used with an array
    """
    results = []
    
    if not isinstance(stmt, exp.Select):
        return results
    
    group_by = stmt.find(exp.Group)
    if not group_by:
        return results
    
    for group_expr in group_by.expressions:
        # Check if this is a date truncation function
        func_name = None
        trunc_unit = None
        alias = None
        explicit_values = None
        
        # Check for guarantee() wrapper
        is_guarantee, values = _is_guarantee_wrapped(group_expr)
        if is_guarantee:
            explicit_values = values
        
        # Handle aliased expressions: month(created_at) as month
        if isinstance(group_expr, exp.Alias):
            alias = group_expr.alias
            inner = group_expr.this
            # If guarantee-wrapped, unwrap to get the actual function
            if is_guarantee and isinstance(inner, exp.Anonymous):
                inner = inner.expressions[0] if inner.expressions else inner
        else:
            inner = group_expr
            # If guarantee-wrapped, unwrap
            if is_guarantee and isinstance(inner, exp.Anonymous):
                inner = inner.expressions[0] if inner.expressions else inner
            # Try to derive alias from expression
            if isinstance(inner, exp.Column):
                alias = inner.name
            elif hasattr(inner, 'alias') and inner.alias:
                alias = inner.alias
        
        # Check for date truncation functions
        if isinstance(inner, exp.Anonymous):
            func_name = inner.name.lower() if inner.name else None
        elif isinstance(inner, exp.Func):
            func_name = inner.sql_name().lower() if hasattr(inner, 'sql_name') else type(inner).__name__.lower()
        
        if func_name in DATE_TRUNC_FUNCTIONS:
            # Determine the truncation unit
            if func_name == 'date_trunc':
                # date_trunc('month', col) - first arg is unit
                if inner.expressions:
                    unit_arg = inner.expressions[0]
                    if isinstance(unit_arg, exp.Literal):
                        trunc_unit = unit_arg.this.strip("'\"").lower()
            else:
                # year(col), month(col), etc. - function name is unit
                trunc_unit = func_name
            
            if trunc_unit and alias:
                results.append((alias, trunc_unit, group_expr, explicit_values))
    
    return results


def _find_guarantee_in_group_by(
    stmt: exp.Expression
) -> List[Tuple[str, exp.Expression, Optional[List[str]]]]:
    """
    Find guarantee() expressions in GROUP BY clause for categorical columns.
    
    Returns list of tuples: (alias, original_expression, explicit_values)
    """
    results = []
    
    if not isinstance(stmt, exp.Select):
        return results
    
    group_by = stmt.find(exp.Group)
    if not group_by:
        return results
    
    for group_expr in group_by.expressions:
        is_guarantee, explicit_values = _is_guarantee_wrapped(group_expr)
        if not is_guarantee:
            continue
        
        alias = None
        if isinstance(group_expr, exp.Alias):
            alias = group_expr.alias
        else:
            # Try to derive alias from inner expression
            inner = group_expr
            if isinstance(inner, exp.Anonymous) and inner.expressions:
                first_arg = inner.expressions[0]
                if isinstance(first_arg, exp.Column):
                    alias = first_arg.name
        
        if alias:
            results.append((alias, group_expr, explicit_values))
    
    return results


def _extract_date_bounds_from_where(
    stmt: exp.Expression,
    column_expr: exp.Expression
) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract date bounds from WHERE clause for a given column expression.
    
    Returns: (min_date, max_date) as string literals or None
    """
    where = stmt.find(exp.Where)
    if not where:
        return None, None
    
    min_date = None
    max_date = None
    
    # Walk the WHERE clause looking for date comparisons
    def check_condition(node):
        nonlocal min_date, max_date
        
        if isinstance(node, (exp.GTE, exp.GT)):
            # col >= date or col > date
            if _columns_match(node.this, column_expr):
                if isinstance(node.expression, (exp.Literal, exp.Cast)):
                    min_date = node.expression.sql()
        elif isinstance(node, (exp.LTE, exp.LT)):
            # col <= date or col < date
            if _columns_match(node.this, column_expr):
                if isinstance(node.expression, (exp.Literal, exp.Cast)):
                    max_date = node.expression.sql()
        elif isinstance(node, exp.Between):
            # col BETWEEN date1 AND date2
            if _columns_match(node.this, column_expr):
                if isinstance(node.args.get('low'), (exp.Literal, exp.Cast)):
                    min_date = node.args['low'].sql()
                if isinstance(node.args.get('high'), (exp.Literal, exp.Cast)):
                    max_date = node.args['high'].sql()
        elif isinstance(node, exp.And):
            check_condition(node.this)
            check_condition(node.expression)
    
    check_condition(where.this)
    return min_date, max_date


def _columns_match(expr1: exp.Expression, expr2: exp.Expression) -> bool:
    """Check if two expressions refer to the same column."""
    # Simple name matching for now
    if isinstance(expr1, exp.Column) and isinstance(expr2, exp.Column):
        return expr1.name == expr2.name
    return expr1.sql() == expr2.sql()


def _get_source_column_from_trunc(trunc_expr: exp.Expression) -> Optional[exp.Expression]:
    """Extract the source column from a date truncation expression."""
    if isinstance(trunc_expr, exp.Alias):
        trunc_expr = trunc_expr.this
    
    # Get the column argument from the function
    if isinstance(trunc_expr, (exp.Anonymous, exp.Func)):
        if trunc_expr.expressions:
            # For date_trunc('unit', col), column is second arg
            if hasattr(trunc_expr, 'name') and trunc_expr.name and trunc_expr.name.lower() == 'date_trunc':
                if len(trunc_expr.expressions) > 1:
                    return trunc_expr.expressions[1]
            else:
                # For year(col), month(col), etc., column is first arg
                return trunc_expr.expressions[0]
    return None


def _get_all_group_by_columns(stmt: exp.Expression) -> List[Tuple[str, exp.Expression, bool, Optional[str], Optional[List[str]]]]:
    """
    Get all GROUP BY columns with their spine information.
    
    Returns list of tuples: (alias, expression, is_date, trunc_unit, explicit_values)
    - is_date: True if this is a date truncation function
    - trunc_unit: The truncation unit (month, year, etc.) if is_date
    - explicit_values: Values from guarantee() if provided
    
    Handles ROLLUP and CUBE by extracting their inner columns.
    """
    results = []
    
    if not isinstance(stmt, exp.Select):
        return results
    
    group_by = stmt.find(exp.Group)
    if not group_by:
        return results
    
    # Collect all GROUP BY expressions, expanding ROLLUP/CUBE
    all_group_exprs = []
    
    # Regular GROUP BY expressions
    for group_expr in group_by.expressions:
        if isinstance(group_expr, (exp.Rollup, exp.Cube)):
            # Extract columns from ROLLUP/CUBE in expressions
            for inner_expr in group_expr.expressions:
                all_group_exprs.append(inner_expr)
        else:
            all_group_exprs.append(group_expr)
    
    # Check for ROLLUP in args (SQLGlot stores it separately)
    rollup_list = group_by.args.get('rollup', [])
    if rollup_list:
        for rollup in rollup_list:
            if isinstance(rollup, exp.Rollup):
                for inner_expr in rollup.expressions:
                    all_group_exprs.append(inner_expr)
    
    # Check for CUBE in args
    cube_list = group_by.args.get('cube', [])
    if cube_list:
        for cube in cube_list:
            if isinstance(cube, exp.Cube):
                for inner_expr in cube.expressions:
                    all_group_exprs.append(inner_expr)
    
    for group_expr in all_group_exprs:
        alias = None
        is_date = False
        trunc_unit = None
        explicit_values = None
        
        # Check for guarantee() wrapper
        is_guarantee, values = _is_guarantee_wrapped(group_expr)
        if is_guarantee:
            explicit_values = values
        
        # Handle aliased expressions
        if isinstance(group_expr, exp.Alias):
            alias = group_expr.alias
            inner = group_expr.this
            if is_guarantee and isinstance(inner, exp.Anonymous):
                inner = inner.expressions[0] if inner.expressions else inner
        else:
            inner = group_expr
            if is_guarantee and isinstance(inner, exp.Anonymous):
                inner = inner.expressions[0] if inner.expressions else inner
            if isinstance(inner, exp.Column):
                alias = inner.name
        
        if not alias:
            # Generate alias from expression
            alias = f"col_{len(results)}"
        
        # Check if this is a date truncation function
        func_name = None
        if isinstance(inner, exp.Anonymous):
            func_name = inner.name.lower() if inner.name else None
        elif isinstance(inner, exp.Func):
            func_name = inner.sql_name().lower() if hasattr(inner, 'sql_name') else type(inner).__name__.lower()
        
        if func_name in DATE_TRUNC_FUNCTIONS:
            is_date = True
            if func_name == 'date_trunc':
                if inner.expressions:
                    unit_arg = inner.expressions[0]
                    if isinstance(unit_arg, exp.Literal):
                        trunc_unit = unit_arg.this.strip("'\"").lower()
            else:
                trunc_unit = func_name
        
        results.append((alias, group_expr, is_date, trunc_unit, explicit_values))
    
    return results


def _apply_auto_spine(
    stmt: exp.Expression,
    settings: CompileSettings,
    dialect: Optional[str] = None
) -> exp.Expression:
    """
    Apply auto-spine transformation to ALL GROUP BY columns.
    
    Every GROUP BY column gets a spine:
    - Date columns: spine from date range (inferred from WHERE or MIN/MAX)
    - Non-date columns: spine from DISTINCT values in data
    - guarantee() columns: spine from explicit values provided
    
    All spines are cross-joined to create complete (col1 × col2 × ...) combinations.
    The data is then left-joined to fill in actual values.
    
    For ROLLUP: spines include NULL and are filtered to valid hierarchical patterns.
    For CUBE: spines include NULL (all combinations are valid).
    
    This ensures all expected dimension values appear in results, which is
    what analysts typically want for charts and reports.
    """
    if not settings.auto_spine:
        return stmt
    
    if not isinstance(stmt, exp.Select):
        return stmt
    
    # Detect ROLLUP/CUBE (only applies to SQL passthrough - ASQL has no native ROLLUP syntax)
    # If SQL passthrough is removed, this block and related NULL handling can be deleted.
    has_rollup, has_cube, rollup_cube_columns = _detect_rollup_cube(stmt)
    
    # Get all GROUP BY columns
    group_cols = _get_all_group_by_columns(stmt)
    
    if not group_cols:
        return stmt
    
    # Get source table for DISTINCT queries
    from_clause = stmt.find(exp.From)
    if not from_clause:
        return stmt
    source_table = from_clause.this.sql()
    
    # Get WHERE clause for date bounds and for filtering DISTINCT
    where_clause = stmt.find(exp.Where)
    where_sql = f"WHERE {where_clause.this.sql()}" if where_clause else ""
    
    # Build spine CTEs for each column
    spine_ctes = []
    spine_columns = []
    # Track which columns are in ROLLUP (in order) for hierarchical filter
    rollup_column_order = []
    
    for alias, group_expr, is_date, trunc_unit, explicit_values in group_cols:
        spine_cte_name = f"{alias}_spine"
        
        # Check if this column is in ROLLUP/CUBE
        is_in_rollup_cube = alias in rollup_cube_columns or alias.lower() in [c.lower() for c in rollup_cube_columns]
        if is_in_rollup_cube and has_rollup:
            rollup_column_order.append(alias)
        
        if explicit_values:
            # Use explicit values from guarantee()
            spine_sql = _build_categorical_spine_sql(alias, explicit_values, dialect, include_null=is_in_rollup_cube)
        elif is_date and trunc_unit:
            # Use date range
            source_col = _get_source_column_from_trunc(group_expr)
            min_date, max_date = _extract_date_bounds_from_where(stmt, source_col) if source_col else (None, None)
            interval = TRUNC_TO_INTERVAL.get(trunc_unit, '1 day')
            
            if min_date and max_date:
                spine_sql = _build_date_spine_sql(alias, trunc_unit, min_date, max_date, interval, dialect, include_null=is_in_rollup_cube)
            else:
                # Fall back to MIN/MAX from data
                spine_sql = _build_date_spine_from_data_sql(
                    alias, trunc_unit, source_col.sql() if source_col else alias, 
                    source_table, where_sql, interval, dialect, include_null=is_in_rollup_cube
                )
        else:
            # Use DISTINCT from data (this is a no-op but maintains consistency)
            inner_expr = group_expr.this if isinstance(group_expr, exp.Alias) else group_expr
            if _is_guarantee_wrapped(group_expr)[0]:
                # Unwrap guarantee to get the actual expression
                inner = inner_expr
                if isinstance(inner, exp.Anonymous):
                    inner = inner.expressions[0] if inner.expressions else inner
                col_expr = inner.sql()
            else:
                col_expr = inner_expr.sql()
            
            if is_in_rollup_cube:
                # Include NULL for ROLLUP/CUBE subtotals
                spine_sql = f"SELECT DISTINCT {col_expr} AS {alias} FROM {source_table} {where_sql} UNION ALL SELECT NULL AS {alias}"
            else:
                spine_sql = f"SELECT DISTINCT {col_expr} AS {alias} FROM {source_table} {where_sql}"
        
        try:
            spine_select = sqlglot.parse_one(spine_sql.strip(), dialect=dialect)
            spine_ctes.append((spine_cte_name, spine_select))
            spine_columns.append((alias, spine_cte_name))
        except Exception:
            # If parsing fails, skip this column
            continue
    
    if not spine_ctes:
        return stmt
    
    # Build the combined spine (cross-join all spines)
    combined_spine_name = "combined_spine"
    if len(spine_columns) == 1:
        combined_spine_sql = f"SELECT * FROM {spine_columns[0][1]}"
    else:
        # Cross-join all spines
        selects = [f"{cte_name}.{alias}" for alias, cte_name in spine_columns]
        froms = [spine_columns[0][1]]
        for alias, cte_name in spine_columns[1:]:
            froms.append(f"CROSS JOIN {cte_name}")
        combined_spine_sql = f"SELECT {', '.join(selects)} FROM {' '.join(froms)}"
    
    # For ROLLUP, add filter for valid hierarchical NULL patterns
    # Rule: if column N is NULL, all subsequent columns must also be NULL
    # Expressed as: (col_i IS NOT NULL OR col_{i+1} IS NULL) for each adjacent pair
    if has_rollup and len(rollup_column_order) > 1:
        rollup_filter_conditions = []
        for i in range(len(rollup_column_order) - 1):
            col_curr = rollup_column_order[i]
            col_next = rollup_column_order[i + 1]
            # Find the CTE name for each column
            curr_cte = next((cte for alias, cte in spine_columns if alias == col_curr), None)
            next_cte = next((cte for alias, cte in spine_columns if alias == col_next), None)
            if curr_cte and next_cte:
                rollup_filter_conditions.append(f"({curr_cte}.{col_curr} IS NOT NULL OR {next_cte}.{col_next} IS NULL)")
        
        if rollup_filter_conditions:
            combined_spine_sql += f" WHERE {' AND '.join(rollup_filter_conditions)}"
    
    # Build the data CTE (original query)
    data_cte_name = "spine_data"
    
    # Build the final join
    join_conditions = [f"{combined_spine_name}.{alias} = {data_cte_name}.{alias}" for alias, _ in spine_columns]
    
    # Get all SELECT columns from original query
    select_cols = []
    for sel_expr in stmt.expressions:
        if isinstance(sel_expr, exp.Alias):
            col_name = sel_expr.alias
        elif isinstance(sel_expr, exp.Column):
            col_name = sel_expr.name
        else:
            col_name = sel_expr.sql()
        
        # Use spine column for group-by columns, coalesce for aggregates
        if col_name in [alias for alias, _ in spine_columns]:
            select_cols.append(f"{combined_spine_name}.{col_name}")
        else:
            select_cols.append(f"COALESCE({data_cte_name}.{col_name}, 0) AS {col_name}")
    
    if not select_cols:
        select_cols = [f"{combined_spine_name}.*"]
    
    final_sql = f"""
        SELECT {', '.join(select_cols)}
        FROM {combined_spine_name}
        LEFT JOIN {data_cte_name} ON {' AND '.join(join_conditions)}
    """
    
    try:
        final_select = sqlglot.parse_one(final_sql.strip(), dialect=dialect)
    except Exception:
        return stmt
    
    # Build the complete WITH clause
    try:
        # Start building the result
        result_sql_parts = ["WITH"]
        cte_parts = []
        
        # Add individual spine CTEs
        for cte_name, cte_select in spine_ctes:
            cte_parts.append(f"{cte_name} AS ({cte_select.sql(dialect=dialect)})")
        
        # Add combined spine CTE
        cte_parts.append(f"{combined_spine_name} AS ({combined_spine_sql})")
        
        # Add data CTE
        cte_parts.append(f"{data_cte_name} AS ({stmt.sql(dialect=dialect)})")
        
        result_sql = "WITH " + ", ".join(cte_parts) + " " + final_sql
        
        return sqlglot.parse_one(result_sql.strip(), dialect=dialect)
    except Exception:
        return stmt


def _build_categorical_spine_sql(alias: str, values: List[str], dialect: Optional[str] = None, include_null: bool = False) -> str:
    """Build SQL for a categorical spine with explicit values.
    
    Args:
        alias: Column alias for the spine
        values: List of values to include
        dialect: SQL dialect
        include_null: If True, include NULL for ROLLUP/CUBE subtotals
    """
    dialect_lower = dialect.lower() if dialect else ""
    
    values_sql = ", ".join([f"'{v}'" for v in values])
    null_union = f" UNION ALL SELECT NULL AS {alias}" if include_null else ""
    
    if dialect_lower in ('postgres', 'postgresql', 'redshift', 'duckdb'):
        return f"SELECT unnest(ARRAY[{values_sql}]) AS {alias}{null_union}"
    elif dialect_lower == 'bigquery':
        return f"SELECT {alias} FROM UNNEST([{values_sql}]) AS {alias}{null_union}"
    elif dialect_lower == 'snowflake':
        # Snowflake uses FLATTEN with SPLIT
        return f"SELECT value AS {alias} FROM TABLE(FLATTEN(INPUT => SPLIT('{','.join(values)}', ','))){null_union}"
    else:
        # Default: UNION ALL approach (works everywhere)
        unions = [f"SELECT '{v}' AS {alias}" for v in values]
        if include_null:
            unions.append(f"SELECT NULL AS {alias}")
        return " UNION ALL ".join(unions)


def _build_date_spine_sql(
    alias: str,
    trunc_unit: str,
    min_date: str,
    max_date: str,
    interval: str,
    dialect: Optional[str] = None,
    include_null: bool = False
) -> str:
    """Build SQL for a date spine with explicit bounds.
    
    Args:
        include_null: If True, include NULL for ROLLUP/CUBE subtotals
    """
    dialect_lower = dialect.lower() if dialect else ""
    null_union = f" UNION ALL SELECT NULL AS {alias}" if include_null else ""
    
    if dialect_lower in ('postgres', 'postgresql', 'redshift'):
        return f"""
            SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias}
            FROM generate_series({min_date}::date, {max_date}::date, INTERVAL '{interval}') AS d
        """ + null_union
    elif dialect_lower == 'bigquery':
        return f"""
            SELECT DATE_TRUNC(d, {trunc_unit.upper()}) AS {alias}
            FROM UNNEST(GENERATE_DATE_ARRAY({min_date}, {max_date})) AS d
        """ + null_union
    elif dialect_lower == 'snowflake':
        return f"""
            SELECT DISTINCT DATE_TRUNC('{trunc_unit}', DATEADD({trunc_unit}, SEQ4(), {min_date})) AS {alias}
            FROM TABLE(GENERATOR(ROWCOUNT => 10000))
            WHERE DATE_TRUNC('{trunc_unit}', DATEADD({trunc_unit}, SEQ4(), {min_date})) <= {max_date}
        """ + null_union
    elif dialect_lower == 'duckdb':
        return f"""
            SELECT DATE_TRUNC('{trunc_unit}', d) AS {alias}
            FROM generate_series({min_date}::date, {max_date}::date, INTERVAL '{interval}') AS t(d)
        """ + null_union
    else:
        return f"""
            SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias}
            FROM generate_series({min_date}::date, {max_date}::date, INTERVAL '{interval}') AS d
        """ + null_union


def _build_date_spine_from_data_sql(
    alias: str,
    trunc_unit: str,
    col_expr: str,
    source_table: str,
    where_sql: str,
    interval: str,
    dialect: Optional[str] = None,
    include_null: bool = False
) -> str:
    """Build SQL for a date spine derived from data MIN/MAX.
    
    Args:
        include_null: If True, include NULL for ROLLUP/CUBE subtotals
    """
    dialect_lower = dialect.lower() if dialect else ""
    null_union = f" UNION ALL SELECT NULL AS {alias}" if include_null else ""
    
    if dialect_lower in ('postgres', 'postgresql', 'redshift'):
        return f"""
            WITH bounds AS (
                SELECT MIN({col_expr}) as min_d, MAX({col_expr}) as max_d
                FROM {source_table}
                {where_sql}
            )
            SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias}
            FROM bounds, generate_series(min_d::date, max_d::date, INTERVAL '{interval}') AS d
        """ + null_union
    elif dialect_lower == 'duckdb':
        return f"""
            WITH bounds AS (
                SELECT MIN({col_expr}) as min_d, MAX({col_expr}) as max_d
                FROM {source_table}
                {where_sql}
            )
            SELECT DATE_TRUNC('{trunc_unit}', d) AS {alias}
            FROM bounds, generate_series(min_d::date, max_d::date, INTERVAL '{interval}') AS t(d)
        """ + null_union
    else:
        # Fallback: just use DISTINCT (no gap filling, but at least works)
        return f"SELECT DISTINCT DATE_TRUNC('{trunc_unit}', {col_expr}) AS {alias} FROM {source_table} {where_sql}" + null_union


def _build_spine_select_with_bounds(
    alias: str,
    trunc_unit: str,
    min_date: str,
    max_date: str,
    interval: str,
    dialect: Optional[str] = None
) -> exp.Expression:
    """Build a spine SELECT using explicit date bounds."""
    # Generate SQL for the spine CTE
    # Different dialects have different date generation functions
    
    dialect_lower = dialect.lower() if dialect else ""
    
    if dialect_lower in ('postgres', 'postgresql', 'redshift'):
        # PostgreSQL/Redshift: generate_series
        spine_sql = f"""
            SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias}
            FROM generate_series({min_date}::date, {max_date}::date, INTERVAL '{interval}') AS d
        """
    elif dialect_lower == 'bigquery':
        # BigQuery: GENERATE_DATE_ARRAY
        if trunc_unit in ('hour',):
            spine_sql = f"""
                SELECT DATE_TRUNC(TIMESTAMP(d), {trunc_unit.upper()}) AS {alias}
                FROM UNNEST(GENERATE_TIMESTAMP_ARRAY({min_date}, {max_date}, INTERVAL 1 {trunc_unit.upper()})) AS d
            """
        else:
            spine_sql = f"""
                SELECT DATE_TRUNC(d, {trunc_unit.upper()}) AS {alias}
                FROM UNNEST(GENERATE_DATE_ARRAY({min_date}, {max_date}, INTERVAL 1 {trunc_unit.upper() if trunc_unit != 'quarter' else 'MONTH'})) AS d
            """
    elif dialect_lower == 'snowflake':
        # Snowflake: TABLE(GENERATOR()) + DATEADD
        # Calculate approximate row count for generator
        spine_sql = f"""
            SELECT DISTINCT DATE_TRUNC('{trunc_unit}', DATEADD({trunc_unit}, ROW_NUMBER() OVER (ORDER BY 1) - 1, {min_date})) AS {alias}
            FROM TABLE(GENERATOR(ROWCOUNT => 10000))
            WHERE {alias} <= {max_date}
        """
    elif dialect_lower in ('mysql', 'mariadb'):
        # MySQL: recursive CTE
        spine_sql = f"""
            WITH RECURSIVE dates AS (
                SELECT {min_date} AS d
                UNION ALL
                SELECT DATE_ADD(d, INTERVAL {interval}) FROM dates WHERE d < {max_date}
            )
            SELECT DATE_FORMAT(d, '%Y-%m-01') AS {alias} FROM dates
        """
    elif dialect_lower in ('duckdb',):
        # DuckDB: generate_series
        spine_sql = f"""
            SELECT DATE_TRUNC('{trunc_unit}', d) AS {alias}
            FROM generate_series({min_date}::date, {max_date}::date, INTERVAL '{interval}') AS t(d)
        """
    else:
        # Default: PostgreSQL-style
        spine_sql = f"""
            SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias}
            FROM generate_series({min_date}::date, {max_date}::date, INTERVAL '{interval}') AS d
        """
    
    return sqlglot.parse_one(spine_sql.strip(), dialect=dialect)


def _build_spine_select_from_data(
    stmt: exp.Expression,
    alias: str,
    trunc_unit: str,
    source_col: Optional[exp.Expression],
    interval: str,
    dialect: Optional[str] = None
) -> Optional[exp.Expression]:
    """Build a spine SELECT deriving bounds from the data itself."""
    if not source_col:
        return None
    
    # Get the FROM clause to know what table to query
    from_clause = stmt.find(exp.From)
    if not from_clause:
        return None
    
    col_sql = source_col.sql()
    table_sql = from_clause.this.sql()
    
    # Get the WHERE clause if any
    where_clause = stmt.find(exp.Where)
    where_sql = f"WHERE {where_clause.this.sql()}" if where_clause else ""
    
    dialect_lower = dialect.lower() if dialect else ""
    
    if dialect_lower in ('postgres', 'postgresql', 'redshift'):
        spine_sql = f"""
            WITH bounds AS (
                SELECT MIN({col_sql}) as min_d, MAX({col_sql}) as max_d
                FROM {table_sql}
                {where_sql}
            )
            SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias}
            FROM bounds, generate_series(min_d::date, max_d::date, INTERVAL '{interval}') AS d
        """
    elif dialect_lower == 'snowflake':
        spine_sql = f"""
            WITH bounds AS (
                SELECT MIN({col_sql}) as min_d, MAX({col_sql}) as max_d
                FROM {table_sql}
                {where_sql}
            )
            SELECT DISTINCT DATE_TRUNC('{trunc_unit}', DATEADD({trunc_unit}, seq4(), min_d)) AS {alias}
            FROM bounds, TABLE(GENERATOR(ROWCOUNT => 10000))
            WHERE DATE_TRUNC('{trunc_unit}', DATEADD({trunc_unit}, seq4(), min_d)) <= max_d
        """
    elif dialect_lower == 'bigquery':
        spine_sql = f"""
            WITH bounds AS (
                SELECT MIN({col_sql}) as min_d, MAX({col_sql}) as max_d
                FROM {table_sql}
                {where_sql}
            )
            SELECT DATE_TRUNC(d, {trunc_unit.upper()}) AS {alias}
            FROM bounds, UNNEST(GENERATE_DATE_ARRAY(min_d, max_d)) AS d
        """
    else:
        # Default PostgreSQL-style
        spine_sql = f"""
            WITH bounds AS (
                SELECT MIN({col_sql}) as min_d, MAX({col_sql}) as max_d
                FROM {table_sql}
                {where_sql}
            )
            SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias}
            FROM bounds, generate_series(min_d::date, max_d::date, INTERVAL '{interval}') AS d
        """
    
    try:
        return sqlglot.parse_one(spine_sql.strip(), dialect=dialect)
    except Exception:
        return None


def _build_spine_join_query(
    spine_cte_name: str,
    data_cte_name: str,
    alias: str,
    original_stmt: exp.Expression,
    dialect: Optional[str] = None
) -> exp.Expression:
    """Build the final query that left-joins spine with data."""
    # Get all columns from the original SELECT except the group-by column
    original_select = original_stmt.find(exp.Select)
    
    # Build column list for final select
    columns = []
    for sel_expr in original_select.expressions:
        if isinstance(sel_expr, exp.Alias):
            col_name = sel_expr.alias
        elif isinstance(sel_expr, exp.Column):
            col_name = sel_expr.name
        else:
            col_name = sel_expr.sql()
        
        if col_name == alias:
            # Use spine column for the date
            columns.append(f"{spine_cte_name}.{alias}")
        else:
            # Use data column (with COALESCE for aggregates)
            columns.append(f"COALESCE({data_cte_name}.{col_name}, 0) AS {col_name}")
    
    if not columns:
        columns = [f"{spine_cte_name}.{alias}", f"{data_cte_name}.*"]
    
    join_sql = f"""
        SELECT {', '.join(columns)}
        FROM {spine_cte_name}
        LEFT JOIN {data_cte_name} ON {spine_cte_name}.{alias} = {data_cte_name}.{alias}
    """
    
    try:
        return sqlglot.parse_one(join_sql.strip(), dialect=dialect)
    except Exception:
        # Fallback to simple join
        return sqlglot.parse_one(f"""
            SELECT *
            FROM {spine_cte_name}
            LEFT JOIN {data_cte_name} USING ({alias})
        """, dialect=dialect)


def extract_inline_settings(
    statements: List[exp.Expression]
) -> Tuple[CompileSettings, Optional[str], List[exp.Expression]]:
    """
    Extract SET statements from parsed statements and return settings.
    
    SET statements at the beginning of a query can configure compilation behavior.
    
    Example:
        SET auto_spine = false;
        SET dialect = 'postgres';
        SELECT * FROM orders
    
    Args:
        statements: List of parsed SQLGlot expressions
        
    Returns:
        Tuple of (settings, dialect_override, remaining_statements)
        - settings: CompileSettings with values from SET statements
        - dialect_override: dialect if SET dialect = 'xxx' was found
        - remaining_statements: statements with SET removed
    """
    settings = CompileSettings()
    dialect_override: Optional[str] = None
    queries: List[exp.Expression] = []
    
    for stmt in statements:
        if isinstance(stmt, exp.Set):
            # Extract key/value pairs from SET statement
            for item in stmt.expressions:
                if hasattr(item, 'this') and isinstance(item.this, exp.EQ):
                    eq = item.this
                    key = eq.this.sql().lower().strip('"\'`')
                    value_expr = eq.expression
                    
                    # Get the value as Python type
                    if isinstance(value_expr, exp.Boolean):
                        value = value_expr.this
                    elif isinstance(value_expr, exp.Literal):
                        value = value_expr.this.strip('"\'')
                        # Try to parse as boolean
                        if value.lower() == 'true':
                            value = True
                        elif value.lower() == 'false':
                            value = False
                    elif isinstance(value_expr, exp.Var):
                        value = value_expr.this
                    else:
                        value = value_expr.sql().strip('"\'')
                    
                    # Apply to settings or dialect
                    if key == 'dialect':
                        dialect_override = str(value).lower()
                    elif key == 'auto_spine':
                        settings.auto_spine = bool(value)
                    elif key == 'week_start':
                        if value in ('monday', 'sunday'):
                            settings.week_start = value
                    elif key == 'relative_date_type':
                        if value in ('timestamp', 'date'):
                            settings.relative_date_type = value
                    # Unknown settings are silently ignored for forward compatibility
        else:
            queries.append(stmt)
    
    return settings, dialect_override, queries


def _extract_dialect_from_comment(asql_query: str) -> Optional[str]:
    """
    Extract dialect from comment directive in ASQL query.
    
    Looks for patterns like:
    - -- dialect: snowflake
    - -- Dialect: snowflake
    - # dialect: snowflake
    
    Can appear at the beginning, middle, or end of the query.
    
    Args:
        asql_query: ASQL query string
        
    Returns:
        Dialect name if found, None otherwise
    """
    # Check for -- dialect: or # dialect: patterns
    patterns = [
        r'--\s*dialect\s*:\s*(\w+)',  # -- dialect: snowflake
        r'#\s*dialect\s*:\s*(\w+)',    # # dialect: snowflake
    ]
    
    for pattern in patterns:
        match = re.search(pattern, asql_query, re.IGNORECASE)
        if match:
            return match.group(1).lower()
    
    return None


def compile(
    asql_query: str,
    dialect: Optional[str] = None,
    pretty: bool = False,
    settings: Optional[CompileSettings] = None,
) -> str:
    """
    Compile ASQL query to SQL.
    
    This is the main compilation function that implements the three-stage pipeline:
    1. Pre-parse: Transform ASQL to SQL-like syntax
    2. Parse: Use SQLGlot to parse the SQL-like syntax
    3. Extract inline SET statements for settings
    4. Generate: Output SQL in the target dialect
    
    Args:
        asql_query: ASQL query string (can contain multiple queries separated by semicolons)
        dialect: Target SQL dialect (e.g., 'postgres', 'mysql', 'bigquery', 'snowflake')
                 If None, will try to extract from SET dialect or -- dialect: comment
        pretty: Whether to format SQL output
        settings: Compilation settings. If None, uses defaults.
                  Inline SET statements override these settings.
    
    Returns:
        SQL query string
    
    Raises:
        ASQLSyntaxError: If ASQL syntax is invalid
        ASQLCompilationError: If compilation fails
    
    Example:
        >>> compile("from users where status = 'active' limit 10", dialect="postgres")
        "SELECT * FROM users WHERE status = 'active' LIMIT 10"
        
        >>> compile("from sales group by region (sum(amount) as revenue)")
        "SELECT region, SUM(amount) AS revenue FROM sales GROUP BY region"
        
        >>> compile("SET auto_spine = true; from orders group by month(created_at) (...)")
        # Will include gap-filling CTEs for the date column
    """
    try:
        if not asql_query.strip():
            raise ASQLSyntaxError("Empty ASQL query")
        
        # Start with provided settings or defaults
        base_settings = settings or CompileSettings()
        
        # Extract dialect from comment if not provided
        if not dialect:
            dialect = _extract_dialect_from_comment(asql_query)
        
        # Pre-parse the entire query first (handles CTEs, FROM-first, etc.)
        preparsed = preparse_asql(asql_query)
        
        # Parse with SQLGlot to get statement list
        try:
            statements = sqlglot.parse(preparsed, dialect=dialect)
        except sqlglot.errors.ParseError as e:
            raise ASQLSyntaxError(
                f"Failed to parse ASQL query.\n"
                f"Original: {asql_query}\n"
                f"Pre-parsed: {preparsed}\n"
                f"Error: {e}"
            ) from e
        
        # Extract inline SET statements
        inline_settings, dialect_override, query_statements = extract_inline_settings(statements)
        
        # Merge settings: inline overrides base
        final_settings = base_settings.merge_with(inline_settings)
        
        # Use dialect from SET statement if provided and no explicit dialect
        if dialect_override and not dialect:
            dialect = dialect_override
        
        if not query_statements:
            raise ASQLSyntaxError("No valid queries found (only SET statements)")
        
        # Generate SQL for each query statement
        sql_dialect = Dialect.get_or_raise(dialect) if dialect else None
        sql_parts = []
        
        for stmt in query_statements:
            # Apply settings-based transformations
            transformed_stmt = stmt
            
            # Apply auto-spine for date truncations in GROUP BY
            if final_settings.auto_spine:
                try:
                    transformed_stmt = _apply_auto_spine(stmt, final_settings, dialect)
                except Exception:
                    # If spine transformation fails, use original statement
                    transformed_stmt = stmt
            
            # Remove guarantee() wrappers before SQL generation
            transformed_stmt = _remove_guarantee_wrappers(transformed_stmt)
            
            sql = transformed_stmt.sql(dialect=sql_dialect, pretty=pretty)
            sql_parts.append(sql)
        
        return ";\n\n".join(sql_parts)
        
    except ASQLSyntaxError:
        raise
    except sqlglot.errors.ParseError as e:
        raise ASQLSyntaxError(f"ASQL syntax error: {e}") from e
    except Exception as e:
        raise ASQLCompilationError(f"Compilation error: {e}") from e


def _compile_single_query(
    asql_query: str,
    dialect: Optional[str] = None,
    pretty: bool = False,
    settings: Optional[CompileSettings] = None,
) -> str:
    """
    Compile a single ASQL query to SQL.
    
    This implements the three-stage pipeline for a single query:
    1. Pre-parse ASQL to SQL-like syntax
    2. Parse with SQLGlot
    3. Generate target SQL
    
    Note: This is a legacy function. The main compile() function now handles
    settings extraction and multi-statement parsing more efficiently.
    
    Args:
        asql_query: Single ASQL query string
        dialect: Target SQL dialect
        pretty: Whether to format SQL output
        settings: Compilation settings (currently unused, for future features)
        
    Returns:
        SQL query string
    """
    # Stage 1: Pre-parse ASQL to SQL-like syntax
    sql_like = preparse_asql(asql_query)
    
    # Stage 2: Parse with SQLGlot
    # We use the default dialect for parsing since pre-parser has already
    # transformed ASQL-specific syntax to SQL-like syntax
    try:
        ast = sqlglot.parse_one(sql_like, dialect=dialect)
    except sqlglot.errors.ParseError as e:
        # Try to provide a more helpful error message
        raise ASQLSyntaxError(
            f"Failed to parse ASQL query.\n"
            f"Original: {asql_query}\n"
            f"Pre-parsed: {sql_like}\n"
            f"Error: {e}"
        ) from e
    
    # Stage 3: Generate target SQL
    sql_dialect = Dialect.get_or_raise(dialect) if dialect else None
    sql = ast.sql(dialect=sql_dialect, pretty=pretty)
    
    return sql


def compile_to_ast(asql_query: str) -> exp.Expression:
    """
    Compile ASQL query to SQLGlot AST (without generating SQL).
    
    This is useful for programmatic manipulation of the parsed query.
    
    Args:
        asql_query: ASQL query string
        
    Returns:
        SQLGlot expression tree
        
    Raises:
        ASQLSyntaxError: If ASQL syntax is invalid
        ASQLCompilationError: If compilation fails
    """
    try:
        if not asql_query.strip():
            raise ASQLSyntaxError("Empty ASQL query")
        
        # Pre-parse ASQL to SQL-like syntax
        sql_like = preparse_asql(asql_query)
        
        # Parse with SQLGlot
        ast = sqlglot.parse_one(sql_like)
        
        return ast
        
    except ASQLSyntaxError:
        raise
    except sqlglot.errors.ParseError as e:
        raise ASQLSyntaxError(f"ASQL syntax error: {e}") from e
    except Exception as e:
        raise ASQLCompilationError(f"Compilation error: {e}") from e


def get_preparsed(asql_query: str) -> str:
    """
    Get the pre-parsed SQL-like representation of an ASQL query.
    
    This is useful for debugging and understanding how ASQL syntax
    is transformed before SQLGlot parsing.
    
    Args:
        asql_query: ASQL query string
        
    Returns:
        SQL-like string (intermediate representation)
    """
    return preparse_asql(asql_query)


def get_settings_from_query(
    asql_query: str,
    base_settings: Optional[CompileSettings] = None,
) -> Tuple[CompileSettings, Optional[str]]:
    """
    Extract settings from a query's inline SET statements.
    
    Useful for tooling that needs to know what settings a query uses
    without fully compiling it.
    
    Args:
        asql_query: ASQL query string
        base_settings: Base settings to merge with (uses defaults if None)
        
    Returns:
        Tuple of (merged_settings, dialect_override)
        - merged_settings: CompileSettings with inline settings applied
        - dialect_override: dialect from SET statement, or None
    
    Example:
        >>> settings, dialect = get_settings_from_query('''
        ...     SET auto_spine = true;
        ...     SET dialect = 'postgres';
        ...     from orders ...
        ... ''')
        >>> settings.auto_spine
        True
        >>> dialect
        'postgres'
    """
    base = base_settings or CompileSettings()
    
    try:
        preparsed = preparse_asql(asql_query)
        statements = sqlglot.parse(preparsed)
        inline_settings, dialect_override, _ = extract_inline_settings(statements)
        merged = base.merge_with(inline_settings)
        return merged, dialect_override
    except Exception:
        # If parsing fails, return base settings unchanged
        return base, None
