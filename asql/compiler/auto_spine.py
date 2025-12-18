"""Auto-spine transformation helpers.

Auto-spine automatically adds gap-filling spines for GROUP BY columns.

This module intentionally exports a number of semi-private helpers that the
test suite imports directly.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import sqlglot
from sqlglot import exp

from asql.config import CompileSettings
from asql.errors import ASQLCompilationError


DATE_TRUNC_FUNCTIONS = {
    "year",
    "month",
    "week",
    "day",
    "hour",
    "quarter",
    "date_trunc",
}


TRUNC_TO_INTERVAL = {
    "year": "1 year",
    "month": "1 month",
    "week": "1 week",
    "day": "1 day",
    "hour": "1 hour",
    "quarter": "3 months",
}


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


def _is_guarantee_wrapped(expr_: exp.Expression) -> Tuple[bool, Optional[List[str]]]:
    """Check if an expression is wrapped in guarantee() for explicit spine."""
    inner = expr_.this if isinstance(expr_, exp.Alias) else expr_

    if isinstance(inner, exp.Anonymous) and inner.name and inner.name.lower() == "guarantee":
        if len(inner.expressions) > 1:
            values_expr = inner.expressions[1]
            if isinstance(values_expr, exp.Array):
                values = [str(e.this).strip("'\"") for e in values_expr.expressions]
                return True, values
            return True, None
        return True, None

    return False, None


def _unwrap_guarantee(expr_: exp.Expression) -> exp.Expression:
    """Unwrap guarantee() wrapper and return the inner expression."""
    if isinstance(expr_, exp.Alias):
        inner = expr_.this
        if isinstance(inner, exp.Anonymous) and inner.name and inner.name.lower() == "guarantee":
            if inner.expressions:
                return exp.Alias(this=inner.expressions[0], alias=expr_.alias)
        return expr_

    if isinstance(expr_, exp.Anonymous) and expr_.name and expr_.name.lower() == "guarantee":
        if expr_.expressions:
            return expr_.expressions[0]

    return expr_


def _remove_guarantee_wrappers(stmt: exp.Expression) -> exp.Expression:
    """Remove all guarantee() wrappers from a statement before SQL generation."""
    if not isinstance(stmt, exp.Select):
        return stmt

    group = stmt.find(exp.Group)
    if group:
        new_exprs = []
        for expr_ in group.expressions:
            is_guarantee, _ = _is_guarantee_wrapped(expr_)
            new_exprs.append(_unwrap_guarantee(expr_) if is_guarantee else expr_)
        group.set("expressions", new_exprs)

    if stmt.expressions:
        new_exprs = []
        for expr_ in stmt.expressions:
            is_guarantee, _ = _is_guarantee_wrapped(expr_)
            new_exprs.append(_unwrap_guarantee(expr_) if is_guarantee else expr_)
        stmt.set("expressions", new_exprs)

    return stmt


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

        is_guarantee, _ = _is_guarantee_wrapped(group_expr)
        if is_guarantee:
            continue

        func_name = None
        if isinstance(inner, exp.Anonymous):
            func_name = inner.name.lower() if inner.name else None
        elif isinstance(inner, exp.Func):
            func_name = inner.sql_name().lower() if hasattr(inner, "sql_name") else type(inner).__name__.lower()

        if func_name not in DATE_TRUNC_FUNCTIONS and alias:
            results.append((alias, group_expr))

    return results


def _find_date_trunc_in_group_by(
    stmt: exp.Expression,
) -> List[Tuple[str, str, exp.Expression, Optional[List[str]]]]:
    """Find date truncation expressions in GROUP BY clause."""
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

        is_guarantee, values = _is_guarantee_wrapped(group_expr)
        if is_guarantee:
            explicit_values = values

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


def _find_guarantee_in_group_by(
    stmt: exp.Expression,
) -> List[Tuple[str, exp.Expression, Optional[List[str]]]]:
    """Find guarantee() expressions in GROUP BY clause for categorical columns."""
    results: List[Tuple[str, exp.Expression, Optional[List[str]]]] = []

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
    column_expr: exp.Expression,
) -> Tuple[Optional[str], Optional[str]]:
    """Extract date bounds from WHERE clause for a given column expression."""
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


def _columns_match(expr1: exp.Expression, expr2: exp.Expression) -> bool:
    """Check if two expressions refer to the same column."""
    if isinstance(expr1, exp.Column) and isinstance(expr2, exp.Column):
        return expr1.name == expr2.name
    return expr1.sql() == expr2.sql()


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


def _get_all_group_by_columns(
    stmt: exp.Expression,
) -> List[Tuple[str, exp.Expression, bool, Optional[str], Optional[List[str]]]]:
    """Get all GROUP BY columns with their spine information."""
    results: List[Tuple[str, exp.Expression, bool, Optional[str], Optional[List[str]]]] = []

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

        is_guarantee, values = _is_guarantee_wrapped(group_expr)
        if is_guarantee:
            explicit_values = values

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

        # If no alias found, check SELECT for matching auto-generated alias
        if not alias:
            alias = _find_select_alias_for_expr(stmt, group_expr)

        if not alias:
            alias = f"col_{len(results)}"

        func_name = None
        if isinstance(inner, exp.Anonymous):
            func_name = inner.name.lower() if inner.name else None
        elif isinstance(inner, exp.Func):
            func_name = inner.sql_name().lower() if hasattr(inner, "sql_name") else type(inner).__name__.lower()

        if func_name in DATE_TRUNC_FUNCTIONS:
            is_date = True
            if func_name == "date_trunc":
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
    dialect: Optional[str] = None,
) -> exp.Expression:
    """Apply auto-spine transformation to ALL GROUP BY columns."""
    if not settings.auto_spine:
        return stmt

    if not isinstance(stmt, exp.Select):
        return stmt

    has_rollup, has_cube, rollup_cube_columns = _detect_rollup_cube(stmt)

    group_cols = _get_all_group_by_columns(stmt)
    if not group_cols:
        return stmt

    from_clause = stmt.find(exp.From)
    if not from_clause:
        return stmt
    source_table = from_clause.this.sql()

    where_clause = stmt.find(exp.Where)
    where_sql = f"WHERE {where_clause.this.sql()}" if where_clause else ""

    spine_ctes: List[Tuple[str, exp.Expression]] = []
    # spine_columns: (alias, cte_name, original_expr_sql)
    spine_columns: List[Tuple[str, str, str]] = []
    rollup_column_order: List[str] = []

    for alias, group_expr, is_date, trunc_unit, explicit_values in group_cols:
        # Get the original expression SQL for matching SELECT expressions
        if isinstance(group_expr, exp.Alias):
            original_expr_sql = group_expr.this.sql()
        else:
            original_expr_sql = group_expr.sql()
        spine_cte_name = f"{alias}_spine"

        is_in_rollup_cube = alias in rollup_cube_columns or alias.lower() in [c.lower() for c in rollup_cube_columns]
        if is_in_rollup_cube and has_rollup:
            rollup_column_order.append(alias)

        if explicit_values:
            spine_sql = _build_categorical_spine_sql(alias, explicit_values, dialect, include_null=is_in_rollup_cube)
        elif is_date and trunc_unit:
            source_col = _get_source_column_from_trunc(group_expr)
            min_date, max_date = _extract_date_bounds_from_where(stmt, source_col) if source_col else (None, None)
            interval = TRUNC_TO_INTERVAL.get(trunc_unit, "1 day")

            if min_date and max_date:
                spine_sql = _build_date_spine_sql(
                    alias,
                    trunc_unit,
                    min_date,
                    max_date,
                    interval,
                    dialect,
                    include_null=is_in_rollup_cube,
                )
            else:
                spine_sql = _build_date_spine_from_data_sql(
                    alias,
                    trunc_unit,
                    source_col.sql() if source_col else alias,
                    source_table,
                    where_sql,
                    interval,
                    dialect,
                    include_null=is_in_rollup_cube,
                )
        else:
            inner_expr = group_expr.this if isinstance(group_expr, exp.Alias) else group_expr
            if _is_guarantee_wrapped(group_expr)[0]:
                inner = inner_expr
                if isinstance(inner, exp.Anonymous):
                    inner = inner.expressions[0] if inner.expressions else inner
                col_expr = inner.sql()
            else:
                col_expr = inner_expr.sql()

            if is_in_rollup_cube:
                spine_sql = (
                    f"SELECT DISTINCT {col_expr} AS {alias} FROM {source_table} {where_sql} "
                    f"UNION ALL SELECT NULL AS {alias}"
                )
            else:
                spine_sql = f"SELECT DISTINCT {col_expr} AS {alias} FROM {source_table} {where_sql}"

        try:
            spine_select = sqlglot.parse_one(spine_sql.strip(), dialect=dialect)
            spine_ctes.append((spine_cte_name, spine_select))
            spine_columns.append((alias, spine_cte_name, original_expr_sql))
        except Exception as e:
            raise ASQLCompilationError(
                f"Failed to generate spine for GROUP BY column '{alias}'. "
                f"Generated SQL: {spine_sql}\nError: {e}"
            ) from e

    if not spine_ctes:
        return stmt

    # For single GROUP BY, use the spine CTE directly instead of creating a redundant combined_spine
    use_combined_spine = len(spine_columns) > 1 or (has_rollup and len(rollup_column_order) > 1)

    if use_combined_spine:
        combined_spine_name = "combined_spine"
        selects = [f"{cte_name}.{alias}" for alias, cte_name, _ in spine_columns]
        froms = [spine_columns[0][1]]
        for _, cte_name, _ in spine_columns[1:]:
            froms.append(f"CROSS JOIN {cte_name}")
        combined_spine_sql = f"SELECT {', '.join(selects)} FROM {' '.join(froms)}"

        if has_rollup and len(rollup_column_order) > 1:
            rollup_filter_conditions: List[str] = []
            for i in range(len(rollup_column_order) - 1):
                col_curr = rollup_column_order[i]
                col_next = rollup_column_order[i + 1]
                curr_cte = next((cte for a, cte, _ in spine_columns if a == col_curr), None)
                next_cte = next((cte for a, cte, _ in spine_columns if a == col_next), None)
                if curr_cte and next_cte:
                    rollup_filter_conditions.append(
                        f"({curr_cte}.{col_curr} IS NOT NULL OR {next_cte}.{col_next} IS NULL)"
                    )

            if rollup_filter_conditions:
                combined_spine_sql += f" WHERE {' AND '.join(rollup_filter_conditions)}"
    else:
        # Single GROUP BY: use the spine CTE name directly
        combined_spine_name = spine_columns[0][1]
        combined_spine_sql = None  # Not needed

    data_cte_name = "spine_data"
    join_conditions = [f"{combined_spine_name}.{alias} = {data_cte_name}.{alias}" for alias, _, _ in spine_columns]

    select_cols: List[str] = []
    for sel_expr in stmt.expressions:
        # Handle SELECT * - just pass through without COALESCE wrapping
        if isinstance(sel_expr, exp.Star):
            select_cols.append(f"{data_cte_name}.*")
            continue

        if isinstance(sel_expr, exp.Alias):
            col_name = sel_expr.alias
            expr_sql = sel_expr.this.sql()
        elif isinstance(sel_expr, exp.Column):
            col_name = sel_expr.name
            expr_sql = sel_expr.sql()
        else:
            col_name = sel_expr.sql()
            expr_sql = col_name

        # Match against both alias and original expression SQL
        matched_alias = None
        for alias, _, orig_expr_sql in spine_columns:
            if col_name == alias or expr_sql == orig_expr_sql:
                matched_alias = alias
                break

        if matched_alias:
            select_cols.append(f"{combined_spine_name}.{matched_alias}")
        else:
            # Check if col_name is a valid SQL identifier (alphanumeric + underscore)
            # If not (e.g., function calls), we need to alias it properly
            safe_alias = col_name
            if not col_name.replace("_", "").isalnum() or col_name[0].isdigit() if col_name else False:
                # Use a sanitized alias for complex expressions
                safe_alias = f"col_{len(select_cols)}"
            select_cols.append(f"COALESCE({data_cte_name}.{col_name}, 0) AS {safe_alias}")

    if not select_cols:
        select_cols = [f"{combined_spine_name}.*"]

    final_sql = (
        f"SELECT {', '.join(select_cols)} "
        f"FROM {combined_spine_name} "
        f"LEFT JOIN {data_cte_name} ON {' AND '.join(join_conditions)}"
    )

    try:
        sqlglot.parse_one(final_sql.strip(), dialect=dialect)
    except Exception as e:
        raise ASQLCompilationError(
            f"Failed to generate spine join query. "
            f"Generated SQL: {final_sql}\nError: {e}"
        ) from e

    # Add aliases to the data CTE's SELECT expressions for GROUP BY columns
    # This ensures the join can reference them by the spine's alias
    data_stmt = stmt.copy()
    expr_to_alias = {orig_sql: alias for alias, _, orig_sql in spine_columns}

    new_expressions = []
    for sel_expr in data_stmt.expressions:
        if isinstance(sel_expr, exp.Alias):
            inner_expr = sel_expr.this
            original_alias = sel_expr.alias
        else:
            inner_expr = sel_expr
            original_alias = None

        # Check if this is a guarantee-wrapped expression
        is_guarantee, _ = _is_guarantee_wrapped(sel_expr)
        unwrapped_expr = inner_expr
        if is_guarantee:
            # Get the inner expression (unwrap guarantee)
            if isinstance(inner_expr, exp.Anonymous) and inner_expr.name and inner_expr.name.lower() == "guarantee":
                unwrapped_expr = inner_expr.expressions[0] if inner_expr.expressions else inner_expr

        unwrapped_sql = unwrapped_expr.sql()

        if unwrapped_sql in expr_to_alias:
            # Use the spine's alias for this expression
            new_expressions.append(exp.Alias(this=unwrapped_expr, alias=exp.to_identifier(expr_to_alias[unwrapped_sql])))
        elif is_guarantee:
            # guarantee expression not in spine - still unwrap and use original alias if present
            if original_alias:
                new_expressions.append(exp.Alias(this=unwrapped_expr, alias=exp.to_identifier(original_alias)))
            else:
                new_expressions.append(unwrapped_expr)
        else:
            new_expressions.append(sel_expr)

    data_stmt.set("expressions", new_expressions)

    cte_parts: List[str] = []

    for cte_name, cte_select in spine_ctes:
        cte_parts.append(f"{cte_name} AS ({cte_select.sql(dialect=dialect)})")

    # Only add combined_spine CTE when we have multiple GROUP BY columns or rollup
    if combined_spine_sql is not None:
        cte_parts.append(f"{combined_spine_name} AS ({combined_spine_sql})")
    cte_parts.append(f"{data_cte_name} AS ({data_stmt.sql(dialect=dialect)})")

    result_sql = "WITH " + ", ".join(cte_parts) + " " + final_sql
    try:
        return sqlglot.parse_one(result_sql.strip(), dialect=dialect)
    except Exception as e:
        raise ASQLCompilationError(
            f"Failed to assemble spine query. "
            f"Generated SQL: {result_sql}\nError: {e}"
        ) from e


def _build_categorical_spine_sql(
    alias: str,
    values: List[str],
    dialect: Optional[str] = None,
    include_null: bool = False,
) -> str:
    """Build SQL for a categorical spine with explicit values."""
    dialect_lower = dialect.lower() if dialect else ""

    values_sql = ", ".join([f"'{v}'" for v in values])
    null_union = f" UNION ALL SELECT NULL AS {alias}" if include_null else ""

    if dialect_lower in ("postgres", "postgresql", "redshift", "duckdb"):
        return f"SELECT unnest(ARRAY[{values_sql}]) AS {alias}{null_union}"
    if dialect_lower == "bigquery":
        return f"SELECT {alias} FROM UNNEST([{values_sql}]) AS {alias}{null_union}"
    if dialect_lower == "snowflake":
        return (
            f"SELECT value AS {alias} FROM TABLE(FLATTEN(INPUT => SPLIT('{','.join(values)}', ',')))"
            f"{null_union}"
        )

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
    include_null: bool = False,
) -> str:
    """Build SQL for a date spine with explicit bounds."""
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
    """Build SQL for a date spine derived from data MIN/MAX."""
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

    return (
        f"SELECT DISTINCT DATE_TRUNC('{trunc_unit}', {col_expr}) AS {alias} FROM {source_table} {where_sql}"
    ) + null_union


def _build_spine_select_with_bounds(
    alias: str,
    trunc_unit: str,
    min_date: str,
    max_date: str,
    interval: str,
    dialect: Optional[str] = None,
) -> exp.Expression:
    """Build a spine SELECT using explicit date bounds."""
    dialect_lower = dialect.lower() if dialect else ""

    if dialect_lower in ("postgres", "postgresql", "redshift"):
        spine_sql = (
            f"SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias} "
            f"FROM generate_series({min_date}::date, {max_date}::date, INTERVAL '{interval}') AS d"
        )
    elif dialect_lower == "bigquery":
        if trunc_unit in ("hour",):
            spine_sql = (
                f"SELECT DATE_TRUNC(TIMESTAMP(d), {trunc_unit.upper()}) AS {alias} "
                f"FROM UNNEST(GENERATE_TIMESTAMP_ARRAY({min_date}, {max_date}, INTERVAL 1 {trunc_unit.upper()})) AS d"
            )
        else:
            unit = trunc_unit.upper() if trunc_unit != "quarter" else "MONTH"
            spine_sql = (
                f"SELECT DATE_TRUNC(d, {trunc_unit.upper()}) AS {alias} "
                f"FROM UNNEST(GENERATE_DATE_ARRAY({min_date}, {max_date}, INTERVAL 1 {unit})) AS d"
            )
    elif dialect_lower == "snowflake":
        spine_sql = (
            f"SELECT DISTINCT DATE_TRUNC('{trunc_unit}', DATEADD({trunc_unit}, ROW_NUMBER() OVER (ORDER BY 1) - 1, {min_date})) AS {alias} "
            f"FROM TABLE(GENERATOR(ROWCOUNT => 10000)) "
            f"WHERE {alias} <= {max_date}"
        )
    elif dialect_lower in ("mysql", "mariadb"):
        spine_sql = (
            "WITH RECURSIVE dates AS ("
            f"SELECT {min_date} AS d UNION ALL SELECT DATE_ADD(d, INTERVAL {interval}) FROM dates WHERE d < {max_date}"
            ") SELECT DATE_FORMAT(d, '%Y-%m-01') AS {alias} FROM dates"
        )
    elif dialect_lower == "duckdb":
        spine_sql = (
            f"SELECT DATE_TRUNC('{trunc_unit}', d) AS {alias} "
            f"FROM generate_series({min_date}::date, {max_date}::date, INTERVAL '{interval}') AS t(d)"
        )
    else:
        spine_sql = (
            f"SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias} "
            f"FROM generate_series({min_date}::date, {max_date}::date, INTERVAL '{interval}') AS d"
        )

    return sqlglot.parse_one(spine_sql.strip(), dialect=dialect)


def _build_spine_select_from_data(
    stmt: exp.Expression,
    alias: str,
    trunc_unit: str,
    source_col: Optional[exp.Expression],
    interval: str,
    dialect: Optional[str] = None,
) -> Optional[exp.Expression]:
    """Build a spine SELECT deriving bounds from the data itself."""
    if not source_col:
        return None

    from_clause = stmt.find(exp.From)
    if not from_clause:
        return None

    col_sql = source_col.sql()
    table_sql = from_clause.this.sql()

    where_clause = stmt.find(exp.Where)
    where_sql = f"WHERE {where_clause.this.sql()}" if where_clause else ""

    dialect_lower = dialect.lower() if dialect else ""

    if dialect_lower in ("postgres", "postgresql", "redshift"):
        spine_sql = (
            f"WITH bounds AS (SELECT MIN({col_sql}) as min_d, MAX({col_sql}) as max_d FROM {table_sql} {where_sql}) "
            f"SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias} "
            f"FROM bounds, generate_series(min_d::date, max_d::date, INTERVAL '{interval}') AS d"
        )
    elif dialect_lower == "snowflake":
        spine_sql = (
            f"WITH bounds AS (SELECT MIN({col_sql}) as min_d, MAX({col_sql}) as max_d FROM {table_sql} {where_sql}) "
            f"SELECT DISTINCT DATE_TRUNC('{trunc_unit}', DATEADD({trunc_unit}, seq4(), min_d)) AS {alias} "
            f"FROM bounds, TABLE(GENERATOR(ROWCOUNT => 10000)) "
            f"WHERE DATE_TRUNC('{trunc_unit}', DATEADD({trunc_unit}, seq4(), min_d)) <= max_d"
        )
    elif dialect_lower == "bigquery":
        spine_sql = (
            f"WITH bounds AS (SELECT MIN({col_sql}) as min_d, MAX({col_sql}) as max_d FROM {table_sql} {where_sql}) "
            f"SELECT DATE_TRUNC(d, {trunc_unit.upper()}) AS {alias} "
            f"FROM bounds, UNNEST(GENERATE_DATE_ARRAY(min_d, max_d)) AS d"
        )
    else:
        spine_sql = (
            f"WITH bounds AS (SELECT MIN({col_sql}) as min_d, MAX({col_sql}) as max_d FROM {table_sql} {where_sql}) "
            f"SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias} "
            f"FROM bounds, generate_series(min_d::date, max_d::date, INTERVAL '{interval}') AS d"
        )

    try:
        return sqlglot.parse_one(spine_sql.strip(), dialect=dialect)
    except Exception as e:
        raise ASQLCompilationError(
            f"Failed to build date spine. "
            f"Generated SQL: {spine_sql}\nError: {e}"
        ) from e


def _build_spine_join_query(
    spine_cte_name: str,
    data_cte_name: str,
    alias: str,
    original_stmt: exp.Expression,
    dialect: Optional[str] = None,
) -> exp.Expression:
    """Build the final query that left-joins spine with data."""
    original_select = original_stmt.find(exp.Select)

    columns: List[str] = []
    for sel_expr in original_select.expressions:
        if isinstance(sel_expr, exp.Alias):
            col_name = sel_expr.alias
        elif isinstance(sel_expr, exp.Column):
            col_name = sel_expr.name
        else:
            col_name = sel_expr.sql()

        if col_name == alias:
            columns.append(f"{spine_cte_name}.{alias}")
        else:
            columns.append(f"COALESCE({data_cte_name}.{col_name}, 0) AS {col_name}")

    if not columns:
        columns = [f"{spine_cte_name}.{alias}", f"{data_cte_name}.*"]

    join_sql = (
        f"SELECT {', '.join(columns)} FROM {spine_cte_name} "
        f"LEFT JOIN {data_cte_name} ON {spine_cte_name}.{alias} = {data_cte_name}.{alias}"
    )

    try:
        return sqlglot.parse_one(join_sql.strip(), dialect=dialect)
    except Exception as e:
        raise ASQLCompilationError(
            f"Failed to build spine join query. "
            f"Generated SQL: {join_sql}\nError: {e}"
        ) from e
