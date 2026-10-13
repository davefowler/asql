"""Spine transformation for explicit spine() expressions.

This module processes exp.Spine nodes in GROUP BY clauses and generates
gap-filling CTEs. It replaces the auto-detection approach with explicit
spine marking.

Usage:
    from orders spine by month(created_at) (sum(amount))
    from orders group by spine(month(created_at)), region (sum(amount))

Both syntaxes create Spine() wrapped columns in GROUP BY, which this
module processes to generate gap-filling CTEs.
"""

from __future__ import annotations

import logging

import sqlglot
from sqlglot import exp

from asql.compiler.date_parts import retarget_spine_weeks, week_start_of

# Import helpers from spine_helpers
from asql.compiler.spine_helpers import (
    DATE_TRUNC_FUNCTIONS,
    TRUNC_TO_INTERVAL,
    _get_source_column_from_trunc,
    build_date_spine_from_data_sql,
    build_date_spine_sql,
    build_distinct_values_spine_sql,
    detect_rollup_cube,
    extract_date_bounds_from_where,
    generate_spine_comment,
)
from asql.config import CompileSettings
from asql.errors import ASQLCompilationError
from asql.expressions import Spine

logger = logging.getLogger(__name__)

_WHERE_PLACEHOLDER = "__asql_spine_where__"


def transform_spine_expressions(
    stmt: exp.Expr,
    dialect: str,
    settings: CompileSettings,
) -> exp.Expr:
    """Transform Spine() expressions into gap-filling CTEs.

    Finds Spine(column) expressions in GROUP BY and generates:
    1. Date spine CTE (for date truncation columns)
    2. Categorical spine CTE (for other columns)
    3. LEFT JOIN to ensure all values appear in output

    Args:
        stmt: SQLGlot expression (typically a SELECT)
        dialect: Target SQL dialect (for generate_series syntax)
        settings: Compile settings (for comments, etc.)

    Returns:
        Transformed expression with spine CTEs
    """
    # A pipeline step after the aggregate block moves the block into a CTE, so the
    # Spine can sit in a nested SELECT rather than the root.
    for select in list(stmt.find_all(exp.Select)):
        group = select.args.get("group")
        if group is None or not any(isinstance(g, Spine) for g in group.expressions):
            continue
        has_rollup, has_cube, _ = detect_rollup_cube(select)
        if has_rollup or has_cube:
            logger.warning("Spine not supported with ROLLUP/CUBE - skipping")
            _unwrap_spine_expressions(select)
            continue
        _apply_spine_transform(select, _find_spine_columns(select), dialect, settings)
    return stmt


def _find_spine_columns(
    stmt: exp.Expr,
) -> list[tuple[str, exp.Expr, str | None, bool]]:
    """Find Spine() expressions in GROUP BY.

    Returns list of tuples: (alias, inner_expr, trunc_unit, is_date)
    """
    results: list[tuple[str, exp.Expr, str | None, bool]] = []

    group_by = stmt.args.get("group")
    if not group_by:
        return results

    for i, group_expr in enumerate(group_by.expressions):
        spine_node = None
        alias = None

        # Handle Spine directly or wrapped in Alias
        if isinstance(group_expr, Spine):
            spine_node = group_expr
            alias = f"spine_col_{i}"
        elif isinstance(group_expr, exp.Alias):
            if isinstance(group_expr.this, Spine):
                spine_node = group_expr.this
                alias = group_expr.alias

        if spine_node is None:
            continue

        # Extract the inner expression from Spine
        inner_expr = spine_node.this

        # Determine if this is a date truncation
        trunc_unit = _get_trunc_unit(inner_expr)
        is_date = trunc_unit is not None

        if alias is None:
            # Generate alias from inner expression
            if isinstance(inner_expr, exp.Column):
                alias = inner_expr.name
            elif isinstance(inner_expr, exp.Alias):
                alias = inner_expr.alias
            else:
                alias = f"spine_col_{i}"

        results.append((alias, inner_expr, trunc_unit, is_date))

    return results


def _get_trunc_unit(expr: exp.Expr) -> str | None:
    """Get the truncation unit if expr is a date truncation function."""
    if isinstance(expr, exp.Paren) and week_start_of(expr):
        return "week"

    # Hour gets a date spine; minute/second have no spine interval, so they fall
    # through to a categorical spine
    if isinstance(expr, exp.TimestampTrunc):
        ts_unit = expr.args.get("unit")
        if (
            isinstance(ts_unit, exp.Literal)
            and ts_unit.this.lower() in TRUNC_TO_INTERVAL
        ):
            return ts_unit.this.lower()
        return None

    # Check for Anonymous function calls
    if isinstance(expr, exp.Anonymous):
        func_name = expr.name.lower() if expr.name else ""
        if func_name in DATE_TRUNC_FUNCTIONS:
            if func_name == "date_trunc":
                # DATE_TRUNC('month', col) - get unit from first arg
                if expr.expressions:
                    first_arg = expr.expressions[0]
                    if isinstance(first_arg, exp.Literal):
                        return first_arg.this.lower()
            else:
                return func_name

    # Check for DateTrunc expression
    if isinstance(expr, exp.DateTrunc):
        dt_unit = expr.args.get("unit")
        if isinstance(dt_unit, exp.WeekStart):
            return "week"
        if isinstance(dt_unit, exp.Literal):
            return dt_unit.this.lower()

    return None


def _unwrap_spine_expressions(stmt: exp.Expr) -> exp.Expr:
    """Remove Spine wrappers from GROUP BY, keeping inner expressions."""
    if not isinstance(stmt, exp.Select):
        return stmt

    group = stmt.args.get("group")
    if not group:
        return stmt

    new_exprs = []
    for expr in group.expressions:
        if isinstance(expr, Spine):
            new_exprs.append(expr.this)
        elif isinstance(expr, exp.Alias) and isinstance(expr.this, Spine):
            # Preserve alias but unwrap Spine
            new_exprs.append(exp.Alias(this=expr.this.this, alias=expr.alias))
        else:
            new_exprs.append(expr)

    group.set("expressions", new_exprs)
    return stmt


def _apply_spine_transform(
    stmt: exp.Select,
    spine_columns: list[tuple[str, exp.Expr, str | None, bool]],
    dialect: str,
    settings: CompileSettings,
) -> exp.Expr:
    """Apply spine transformation to the statement.

    This is a simplified version that handles the most common cases.
    For complex queries, we delegate to the existing auto_spine machinery.
    """

    # Get existing CTEs
    existing_ctes = []
    with_clause = stmt.args.get("with_")
    if with_clause:
        existing_ctes = list(with_clause.expressions)

    spine_ctes = []
    spine_keys: list[tuple[str, str, exp.Expr, exp.Expr]] = []

    # Get the source table for categorical spines
    from_clause = stmt.args.get("from_")
    source_table = ""
    if from_clause and isinstance(from_clause.this, exp.Table):
        source_table = from_clause.this.name

    # Extract WHERE bounds for date spines
    where_clause = stmt.args.get("where")

    for alias, inner_expr, trunc_unit, is_date in spine_columns:
        spine_alias = f"{alias}_spine"
        # Distinct from any source column so the join/ON conditions stay unambiguous.
        spine_col = f"{alias}_key"
        key_expr = inner_expr

        if is_date and trunc_unit:
            # Generate date spine CTE
            source_col = _get_source_column_from_trunc(inner_expr)
            if source_col is not None:
                # Explicit truncation, so the join key matches the spine's DATE_TRUNC
                # whatever month()/week() themselves compile to.
                key_expr = exp.func(
                    "DATE_TRUNC", exp.Literal.string(trunc_unit), source_col.copy()
                )
            source_col_name = (
                source_col.name if isinstance(source_col, exp.Column) else None
            )

            # Get interval for this truncation unit
            interval = TRUNC_TO_INTERVAL.get(trunc_unit, "1 day")

            # Try to extract bounds from WHERE
            min_date, max_date = None, None
            if where_clause and source_col_name:
                # Convert string column name to exp.Column for comparison
                source_col_expr = exp.Column(this=exp.to_identifier(source_col_name))
                min_date, max_date = extract_date_bounds_from_where(
                    stmt, source_col_expr
                )

            # Build date spine SQL
            # Note: signature is (alias, trunc_unit, min_date, max_date, interval, dialect)
            if min_date and max_date:
                spine_sql = build_date_spine_sql(
                    spine_col, trunc_unit, min_date, max_date, interval, dialect
                )
            else:
                # Use data-based bounds
                # signature is (alias, trunc_unit, col_expr, source_table, where_sql, interval, dialect)
                col_expr = source_col_name or alias
                # where_sql should be a full WHERE clause like "WHERE x >= y"
                # Add null check for where_clause.this to handle malformed WHERE clauses
                # The user's condition goes in as a placeholder and is swapped for
                # its AST below, so the week retargeting never touches it.
                if where_clause and where_clause.this is not None:
                    where_sql = f"WHERE {_WHERE_PLACEHOLDER}"
                else:
                    where_sql = ""
                spine_sql = build_date_spine_from_data_sql(
                    spine_col,
                    trunc_unit,
                    col_expr,
                    source_table,
                    where_sql,
                    interval,
                    dialect,
                )

            # Parse the spine SQL into an expression
            try:
                spine_select = sqlglot.parse_one(spine_sql, dialect=dialect)
                week_start = week_start_of(inner_expr)
                if week_start:
                    spine_select = retarget_spine_weeks(spine_select, week_start)
                if where_clause and where_clause.this is not None:
                    for placeholder in list(spine_select.find_all(exp.Column)):
                        if placeholder.name == _WHERE_PLACEHOLDER:
                            placeholder.replace(where_clause.this.copy())

                # Add comment if enabled
                if settings.include_transpilation_comments:
                    comment = generate_spine_comment(
                        {
                            "alias": alias,
                            "is_date": True,
                            "trunc_unit": trunc_unit,
                            "source_column": source_col_name,
                            "source_table": source_table,
                            "needs_data_bounds": min_date is None,
                        }
                    )
                    spine_select.add_comments([comment])

                spine_cte = exp.CTE(
                    this=spine_select,
                    alias=exp.TableAlias(this=exp.to_identifier(spine_alias)),
                )
                spine_ctes.append(spine_cte)
                spine_keys.append((spine_alias, spine_col, inner_expr, key_expr))
            except Exception as e:  # noqa: BLE001
                # Log at ERROR level with context to help debugging
                logger.error(
                    f"Failed to generate date spine CTE for column '{alias}' "
                    f"(trunc_unit={trunc_unit}, table={source_table}): {e}. "
                    f"Generated SQL was: {spine_sql[:200]}..."
                )
                continue
        else:
            # Generate categorical spine CTE (SELECT DISTINCT from table)
            col_expr = inner_expr.sql()
            # Add null check for where_clause.this
            if where_clause and where_clause.this is not None:
                where_sql = f"WHERE {where_clause.this.sql()}"
            else:
                where_sql = ""
            spine_sql = build_distinct_values_spine_sql(
                spine_col, source_table, col_expr, where_sql, dialect
            )

            try:
                spine_select = sqlglot.parse_one(spine_sql, dialect=dialect)

                if settings.include_transpilation_comments:
                    comment = generate_spine_comment(
                        {
                            "alias": alias,
                            "is_date": False,
                            "source_column": inner_expr.sql(),
                            "source_table": source_table,
                        }
                    )
                    spine_select.add_comments([comment])

                spine_cte = exp.CTE(
                    this=spine_select,
                    alias=exp.TableAlias(this=exp.to_identifier(spine_alias)),
                )
                spine_ctes.append(spine_cte)
                spine_keys.append((spine_alias, spine_col, inner_expr, key_expr))
            except Exception as e:  # noqa: BLE001
                # Log at ERROR level with context
                logger.error(
                    f"Failed to generate categorical spine CTE for column '{alias}' "
                    f"(table={source_table}): {e}. "
                    f"Generated SQL was: {spine_sql[:200]}..."
                )
                continue

    if not spine_ctes:
        return _unwrap_spine_expressions(stmt)
    if len(spine_ctes) != len(spine_columns):
        raise ASQLCompilationError(
            "could not build a spine for every spine column; see logged errors"
        )

    # Combine CTEs
    all_ctes = existing_ctes + spine_ctes

    # Create new WITH clause, preserving recursive flag from original
    recursive = with_clause.args.get("recursive") if with_clause else False
    new_with = exp.With(expressions=all_ctes, recursive=recursive)

    # Update the statement
    stmt.set("with_", new_with)

    _rewire_to_spines(stmt, spine_keys)
    return stmt


def _rewire_to_spines(
    stmt: exp.Select,
    spine_keys: list[tuple[str, str, exp.Expr, exp.Expr]],
) -> None:
    """Make the spines drive the query so empty periods survive.

    FROM <spines, cross joined> LEFT JOIN <original source> ON <keys match AND WHERE>.
    The WHERE moves into the ON: left as a WHERE it would discard the NULL-extended
    rows the spine exists to produce. Spined keys in the projection and GROUP BY
    read from the spine column; COUNT(*) counts matched source rows only.
    """
    refs = [
        (inner.sql(), exp.column(spine_col, table=spine_alias), key)
        for spine_alias, spine_col, inner, key in spine_keys
    ]

    ref_by_sql = {sql: ref for sql, ref, _ in refs}

    group = stmt.args["group"]
    group.set(
        "expressions",
        [
            ref_by_sql[g.this.sql()].copy() if isinstance(g, Spine) else g
            for g in group.expressions
        ],
    )

    projections = list(stmt.expressions)
    for position, projection in enumerate(projections):
        top_ref = ref_by_sql.get(projection.sql())
        if top_ref is not None:
            # A bare key column keeps its output name rather than the spine's.
            name = projection.alias_or_name
            projections[position] = (
                exp.alias_(top_ref.copy(), name) if name else top_ref.copy()
            )
            continue
        for node in list(projection.find_all(exp.Expr)):
            ref = ref_by_sql.get(node.sql())
            if ref is not None and node.find_ancestor(exp.AggFunc) is None:
                node.replace(ref.copy())
    stmt.set("expressions", projections)
    first_key = refs[0][2]
    for count in stmt.find_all(exp.Count):
        if isinstance(count.this, exp.Star) and count.find_ancestor(exp.Select) is stmt:
            count.set("this", first_key.copy())

    source = stmt.args["from_"].this
    joins = stmt.args.get("joins") or []
    if joins:
        source.set("joins", joins)
        source = exp.Subquery(this=source)
    # Null-safe so a NULL categorical key keeps its rows instead of vanishing.
    on: exp.Expr = exp.and_(
        *[exp.NullSafeEQ(this=ref, expression=key) for _, ref, key in refs]
    )
    where = stmt.args.get("where")
    if where is not None:
        on = exp.and_(on, where.this)
        stmt.set("where", None)

    spine_tables = [exp.to_table(spine_alias) for spine_alias, *_ in spine_keys]
    stmt.set("from_", exp.From(this=spine_tables[0]))
    stmt.set(
        "joins",
        [exp.Join(this=t, kind="CROSS") for t in spine_tables[1:]]
        + [exp.Join(this=source, kind="LEFT", on=on)],
    )
