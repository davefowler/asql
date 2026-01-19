"""Spine generation helpers.

This module contains helper functions for generating spine CTEs used for
gap-filling in GROUP BY queries.

Contains:
- Date spine generation (generate_series, etc.)
- Categorical spine generation (DISTINCT values or explicit values)
- Utility functions for extracting bounds and detecting date truncations
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from sqlglot import exp


logger = logging.getLogger(__name__)


# Default spine date bounds (can be made configurable later)
SPINE_MIN_DATE = "'1970-01-01'"
SPINE_MAX_DATE = "CURRENT_DATE"


# Date truncation function names
DATE_TRUNC_FUNCTIONS = {
    "year",
    "month",
    "week",
    "day",
    "hour",
    "quarter",
    "date_trunc",
}


# Map truncation unit to interval for generate_series
TRUNC_TO_INTERVAL = {
    "year": "1 year",
    "month": "1 month",
    "week": "1 week",
    "day": "1 day",
    "hour": "1 hour",
    "quarter": "3 months",
}


def _generate_spine_comment(metadata: dict) -> str:
    """Generate a descriptive comment for a spine CTE.
    
    Args:
        metadata: Dict with keys: alias, is_date, trunc_unit, explicit_values,
                  source_column, source_table, needs_data_bounds
    
    Returns:
        Comment text (without /* */ markers - SQLGlot adds those)
    """
    alias = metadata.get("alias", "column")
    is_date = metadata.get("is_date", False)
    trunc_unit = metadata.get("trunc_unit")
    explicit_values = metadata.get("explicit_values")
    source_column = metadata.get("source_column")
    source_table = metadata.get("source_table", "table")
    needs_data_bounds = metadata.get("needs_data_bounds", False)
    
    if explicit_values:
        # Explicit values from guarantee()
        values_preview = explicit_values[:3]
        if len(explicit_values) > 3:
            values_str = ", ".join(f"'{v}'" for v in values_preview) + ", ..."
        else:
            values_str = ", ".join(f"'{v}'" for v in values_preview)
        return f"Guaranteed values for {alias}: [{values_str}]"
    
    if is_date and trunc_unit:
        # Date spine
        col_ref = source_column or alias
        if needs_data_bounds:
            return f"Date spine for {trunc_unit}({col_ref}) - range from data MIN to MAX"
        else:
            return f"Date spine for {trunc_unit}({col_ref}) - ensures all {trunc_unit}s in range appear"
    
    # Categorical spine (DISTINCT values)
    col_ref = source_column or alias
    return f"All distinct values of '{col_ref}' from {source_table}"


def _detect_rollup_cube(stmt: exp.Expression) -> Tuple[bool, bool, List[str]]:
    """Detect if a statement uses ROLLUP or CUBE in GROUP BY."""
    has_rollup = False
    has_cube = False
    columns: List[str] = []

    rollup = stmt.find(exp.Rollup)
    if rollup:
        has_rollup = True
        for expr_ in rollup.expressions:
            if isinstance(expr_, exp.Column):
                columns.append(expr_.name)
            elif isinstance(expr_, exp.Alias):
                columns.append(expr_.alias)
            else:
                columns.append(expr_.sql())

    cube = stmt.find(exp.Cube)
    if cube:
        has_cube = True
        for expr_ in cube.expressions:
            if isinstance(expr_, exp.Column):
                columns.append(expr_.name)
            elif isinstance(expr_, exp.Alias):
                columns.append(expr_.alias)
            else:
                columns.append(expr_.sql())

    return has_rollup, has_cube, columns


def _get_source_column_from_trunc(trunc_expr: exp.Expression) -> Optional[exp.Expression]:
    """Extract the source column from a date truncation expression."""
    expr_ = trunc_expr
    if isinstance(expr_, exp.Alias):
        expr_ = expr_.this

    if isinstance(expr_, (exp.Anonymous, exp.Func)):
        # Handle date_trunc('unit', column) - column is second argument
        if hasattr(expr_, "name") and expr_.name and expr_.name.lower() == "date_trunc":
            if len(expr_.expressions) > 1:
                return expr_.expressions[1]

        # Handle functions like MONTH(column), YEAR(column) where arg is in expressions
        if expr_.expressions:
            return expr_.expressions[0]

        # Handle SQLGlot's typed date functions (Month, Year, etc.) where arg is in .this
        if hasattr(expr_, "this") and expr_.this is not None:
            return expr_.this

    return None


def _columns_match(expr1: exp.Expression, expr2: exp.Expression) -> bool:
    """Check if two expressions refer to the same column."""
    if isinstance(expr1, exp.Column) and isinstance(expr2, exp.Column):
        return expr1.name == expr2.name
    return expr1.sql() == expr2.sql()


def _extract_date_bounds_from_where(
    stmt: exp.Expression,
    column_expr: exp.Expression,
) -> Tuple[Optional[str], Optional[str]]:
    """Extract date bounds from WHERE clause for a given column expression.
    
    Looks for conditions like:
    - col >= '2024-01-01' (min bound)
    - col <= '2024-12-31' (max bound)
    - col BETWEEN '2024-01-01' AND '2024-12-31' (both bounds)
    """
    where = stmt.find(exp.Where)
    if not where:
        return None, None

    min_date: Optional[str] = None
    max_date: Optional[str] = None

    def check_condition(node: exp.Expression) -> None:
        nonlocal min_date, max_date

        if isinstance(node, (exp.GTE, exp.GT)):
            if _columns_match(node.this, column_expr) and isinstance(node.expression, (exp.Literal, exp.Cast)):
                min_date = node.expression.sql()
        elif isinstance(node, (exp.LTE, exp.LT)):
            if _columns_match(node.this, column_expr) and isinstance(node.expression, (exp.Literal, exp.Cast)):
                max_date = node.expression.sql()
        elif isinstance(node, exp.Between):
            if _columns_match(node.this, column_expr):
                low = node.args.get("low")
                high = node.args.get("high")
                if isinstance(low, (exp.Literal, exp.Cast)):
                    min_date = low.sql()
                if isinstance(high, (exp.Literal, exp.Cast)):
                    max_date = high.sql()
        elif isinstance(node, exp.And):
            check_condition(node.this)
            check_condition(node.expression)

    check_condition(where.this)
    return min_date, max_date


def _build_date_spine_sql(
    alias: str,
    trunc_unit: str,
    min_date: str,
    max_date: str,
    interval: str,
    dialect: Optional[str] = None,
    include_null: bool = False,
) -> str:
    """Build SQL for a date spine with explicit bounds.
    
    Uses generate_series (or equivalent) to create all date values
    between min_date and max_date at the specified interval.
    """
    dialect_lower = dialect.lower() if dialect else ""
    null_union = f" UNION ALL SELECT NULL AS {alias}" if include_null else ""

    if dialect_lower in ("postgres", "postgresql", "redshift"):
        return (
            f"SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias} "
            f"FROM generate_series({min_date}::date, {max_date}::date, INTERVAL '{interval}') AS d"
        ) + null_union
    if dialect_lower == "bigquery":
        return (
            f"SELECT DATE_TRUNC(d, {trunc_unit.upper()}) AS {alias} "
            f"FROM UNNEST(GENERATE_DATE_ARRAY({min_date}, {max_date})) AS d"
        ) + null_union
    if dialect_lower == "snowflake":
        return (
            f"SELECT DISTINCT DATE_TRUNC('{trunc_unit}', DATEADD({trunc_unit}, SEQ4(), {min_date})) AS {alias} "
            f"FROM TABLE(GENERATOR(ROWCOUNT => 10000)) "
            f"WHERE DATE_TRUNC('{trunc_unit}', DATEADD({trunc_unit}, SEQ4(), {min_date})) <= {max_date}"
        ) + null_union
    if dialect_lower == "duckdb":
        return (
            f"SELECT DATE_TRUNC('{trunc_unit}', d) AS {alias} "
            f"FROM generate_series({min_date}::date, {max_date}::date, INTERVAL '{interval}') AS t(d)"
        ) + null_union

    # Default (generic SQL)
    return (
        f"SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias} "
        f"FROM generate_series({min_date}::date, {max_date}::date, INTERVAL '{interval}') AS d"
    ) + null_union


def _build_date_spine_from_data_sql(
    alias: str,
    trunc_unit: str,
    col_expr: str,
    source_table: str,
    where_sql: str,
    interval: str,
    dialect: Optional[str] = None,
    include_null: bool = False,
) -> str:
    """Build SQL for a date spine derived from data MIN/MAX.
    
    Used when explicit bounds aren't specified - determines range
    from the MIN/MAX of the source column in the data.
    """
    dialect_lower = dialect.lower() if dialect else ""
    null_union = f" UNION ALL SELECT NULL AS {alias}" if include_null else ""

    if dialect_lower in ("postgres", "postgresql", "redshift"):
        return (
            f"WITH bounds AS (SELECT MIN({col_expr}) as min_d, MAX({col_expr}) as max_d FROM {source_table} {where_sql}) "
            f"SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias} "
            f"FROM bounds, generate_series(min_d::date, max_d::date, INTERVAL '{interval}') AS d"
        ) + null_union
    if dialect_lower == "duckdb":
        return (
            f"WITH bounds AS (SELECT MIN({col_expr}) as min_d, MAX({col_expr}) as max_d FROM {source_table} {where_sql}) "
            f"SELECT DATE_TRUNC('{trunc_unit}', d) AS {alias} "
            f"FROM bounds, generate_series(min_d::date, max_d::date, INTERVAL '{interval}') AS t(d)"
        ) + null_union

    # Fallback: just get distinct values
    return (
        f"SELECT DISTINCT DATE_TRUNC('{trunc_unit}', {col_expr}) AS {alias} FROM {source_table} {where_sql}"
    ) + null_union


def _build_explicit_values_spine_ast(
    alias: str,
    values: List[str],
    dialect: Optional[str] = None,
    include_null: bool = False,
) -> exp.Expression:
    """Build AST for a categorical spine with explicit values.
    
    Returns an exp.Select or exp.Union representing the spine query.
    SQLGlot handles dialect-specific UNNEST/ARRAY syntax automatically.
    """
    # Build array of literal values
    value_literals = [exp.Literal.string(v) for v in values]
    array_expr = exp.Array(expressions=value_literals)
    
    # UNNEST(array) AS alias - SQLGlot generates correct syntax per dialect
    unnest_expr = exp.Unnest(expressions=[array_expr])
    
    # SELECT alias FROM UNNEST(...) AS alias
    main_select = exp.Select(
        expressions=[exp.to_identifier(alias)],
        from_=exp.From(this=exp.Alias(this=unnest_expr, alias=exp.to_identifier(alias)))
    )
    
    if include_null:
        # UNION ALL SELECT NULL AS alias
        null_select = exp.Select(
            expressions=[exp.Alias(this=exp.Null(), alias=exp.to_identifier(alias))]
        )
        return exp.Union(this=main_select, expression=null_select, distinct=False)
    
    return main_select


def _build_explicit_values_spine_sql(
    alias: str,
    values: List[str],
    dialect: Optional[str] = None,
    include_null: bool = False,
) -> str:
    """Build SQL for a categorical spine with explicit values.
    
    Uses UNNEST(ARRAY[...]) to generate rows from explicit values.
    """
    ast = _build_explicit_values_spine_ast(alias, values, dialect, include_null)
    return ast.sql(dialect=dialect)


def _build_categorical_spine_sql(
    alias: str,
    values: List[str],
    dialect: Optional[str] = None,
    include_null: bool = False,
) -> str:
    """Build SQL for a categorical spine with explicit values.
    
    This is an alias for _build_explicit_values_spine_sql for backwards compatibility.
    """
    return _build_explicit_values_spine_sql(alias, values, dialect, include_null)


def _build_distinct_values_spine_sql(
    alias: str,
    source_table: str,
    col_expr: str,
    where_sql: str = "",
    dialect: Optional[str] = None,
    include_null: bool = False,
) -> str:
    """Build SQL for a categorical spine from distinct values in a table.
    
    Used when no explicit values are provided - gets all distinct values
    from the source column in the table.
    """
    null_union = f" UNION ALL SELECT NULL AS {alias}" if include_null else ""
    
    return f"SELECT DISTINCT {col_expr} AS {alias} FROM {source_table}{' ' + where_sql if where_sql else ''}" + null_union


def _find_select_alias_for_expr(stmt: exp.Select, expr: exp.Expression) -> Optional[str]:
    """Find alias from SELECT for a matching expression.
    
    If the SELECT has an alias for an expression matching expr, return that alias.
    This is used to leverage auto-aliasing when GROUP BY expressions don't have aliases.
    """
    expr_sql = expr.sql()
    
    for sel_expr in stmt.expressions:
        if isinstance(sel_expr, exp.Alias):
            # Compare the inner expression
            if sel_expr.this.sql() == expr_sql:
                return sel_expr.alias
    
    return None


def _find_non_date_group_by_columns(stmt: exp.Expression) -> List[Tuple[str, exp.Expression]]:
    """Find non-date columns in GROUP BY that need cross-join with distinct values."""
    results: List[Tuple[str, exp.Expression]] = []

    if not isinstance(stmt, exp.Select):
        return results

    group_by = stmt.find(exp.Group)
    if not group_by:
        return results

    for group_expr in group_by.expressions:
        if isinstance(group_expr, exp.Alias):
            alias = group_expr.alias
            inner = group_expr.this
        else:
            inner = group_expr
            alias = inner.name if isinstance(inner, exp.Column) else None

        func_name = None
        if isinstance(inner, exp.Anonymous):
            func_name = inner.name.lower() if inner.name else None
        elif isinstance(inner, exp.Func):
            func_name = inner.sql_name().lower() if hasattr(inner, "sql_name") else type(inner).__name__.lower()

        if func_name not in DATE_TRUNC_FUNCTIONS and alias:
            results.append((alias, group_expr))

    return results


def _get_all_group_by_columns(
    stmt: exp.Expression,
) -> List[Tuple[str, exp.Expression, bool, Optional[str], Optional[List[str]], Optional[str]]]:
    """Get all GROUP BY columns with their spine information.
    
    Returns list of tuples:
    - alias: output column alias
    - group_expr: the GROUP BY expression
    - is_date: whether this is a date truncation
    - trunc_unit: the truncation unit (month, day, etc.) if is_date
    - explicit_values: explicit values from guarantee() if any (now deprecated)
    - source_column: the source column name (for predicate extraction)
    """
    results: List[Tuple[str, exp.Expression, bool, Optional[str], Optional[List[str]], Optional[str]]] = []

    if not isinstance(stmt, exp.Select):
        return results

    group_by = stmt.find(exp.Group)
    if not group_by:
        return results

    all_group_exprs: List[exp.Expression] = []

    for group_expr in group_by.expressions:
        if isinstance(group_expr, (exp.Rollup, exp.Cube)):
            all_group_exprs.extend(list(group_expr.expressions))
        else:
            all_group_exprs.append(group_expr)

    rollup_list = group_by.args.get("rollup", [])
    for rollup in rollup_list or []:
        if isinstance(rollup, exp.Rollup):
            all_group_exprs.extend(list(rollup.expressions))

    cube_list = group_by.args.get("cube", [])
    for cube in cube_list or []:
        if isinstance(cube, exp.Cube):
            all_group_exprs.extend(list(cube.expressions))

    for group_expr in all_group_exprs:
        alias: Optional[str] = None
        is_date = False
        trunc_unit: Optional[str] = None
        explicit_values: Optional[List[str]] = None
        source_column: Optional[str] = None

        if isinstance(group_expr, exp.Alias):
            alias = group_expr.alias
            inner = group_expr.this
        else:
            inner = group_expr
            if isinstance(inner, exp.Column):
                alias = inner.name

        # If no alias found, check SELECT for matching auto-generated alias
        if not alias:
            alias = _find_select_alias_for_expr(stmt, group_expr)

        if not alias:
            alias = f"col_{len(results)}"

        # Determine function name and source column
        func_name = None
        if isinstance(inner, exp.Anonymous):
            func_name = inner.name.lower() if inner.name else None
        elif isinstance(inner, exp.Func):
            func_name = inner.sql_name().lower() if hasattr(inner, "sql_name") else type(inner).__name__.lower()

        # Get source column for predicate extraction
        if isinstance(inner, exp.Column):
            source_column = inner.name
        else:
            source_col_expr = _get_source_column_from_trunc(group_expr)
            if source_col_expr and isinstance(source_col_expr, exp.Column):
                source_column = source_col_expr.name

        if func_name in DATE_TRUNC_FUNCTIONS:
            is_date = True
            if func_name == "date_trunc":
                if inner.expressions:
                    unit_arg = inner.expressions[0]
                    if isinstance(unit_arg, exp.Literal):
                        trunc_unit = unit_arg.this.strip("'\"").lower()
            else:
                trunc_unit = func_name

        results.append((alias, group_expr, is_date, trunc_unit, explicit_values, source_column))

    return results


def _find_date_trunc_in_group_by(
    stmt: exp.Expression,
) -> List[Tuple[str, str, exp.Expression, Optional[List[str]]]]:
    """Find date truncation expressions in GROUP BY clause.
    
    Returns list of tuples: (alias, trunc_unit, group_expr, explicit_values)
    """
    results: List[Tuple[str, str, exp.Expression, Optional[List[str]]]] = []

    if not isinstance(stmt, exp.Select):
        return results

    group_by = stmt.find(exp.Group)
    if not group_by:
        return results

    for group_expr in group_by.expressions:
        func_name = None
        trunc_unit = None
        alias = None
        explicit_values = None

        if isinstance(group_expr, exp.Alias):
            alias = group_expr.alias
            inner = group_expr.this
        else:
            inner = group_expr
            if isinstance(inner, exp.Column):
                alias = inner.name
            elif hasattr(inner, "alias") and inner.alias:
                alias = inner.alias

        if isinstance(inner, exp.Anonymous):
            func_name = inner.name.lower() if inner.name else None
        elif isinstance(inner, exp.Func):
            func_name = inner.sql_name().lower() if hasattr(inner, "sql_name") else type(inner).__name__.lower()

        if func_name in DATE_TRUNC_FUNCTIONS:
            if func_name == "date_trunc":
                if inner.expressions:
                    unit_arg = inner.expressions[0]
                    if isinstance(unit_arg, exp.Literal):
                        trunc_unit = unit_arg.this.strip("'\"").lower()
            else:
                trunc_unit = func_name

            if trunc_unit and alias:
                results.append((alias, trunc_unit, group_expr, explicit_values))

    return results
