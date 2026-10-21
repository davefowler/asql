"""Auto-qualify conflicting column names in joins."""

from __future__ import annotations

from sqlglot import exp


def _collect_joined_tables(expression: exp.Expr) -> list[tuple[str, str | None]]:
    """
    Collect all table names and aliases from a query with joins.

    Returns list of (table_name, alias) tuples.
    """
    tables: list[tuple[str, str | None]] = []

    if isinstance(expression, exp.Select):
        # Only this SELECT's own FROM/JOINs: a closed pipeline stage (CTE) is a
        # table to the SELECT reading it, not its joined tables.
        # Get the FROM table
        from_expr = expression.args.get("from_")
        if from_expr:
            from_table = from_expr.this
            if isinstance(from_table, exp.Table):
                tables.append((from_table.name, from_table.alias))
            elif isinstance(from_table, exp.Alias):
                if isinstance(from_table.this, exp.Table):
                    tables.append((from_table.this.name, from_table.alias))

        # Get all joined tables
        for join in expression.args.get("joins") or []:
            join_table = join.this
            if isinstance(join_table, exp.Table):
                tables.append((join_table.name, join_table.alias))
            elif isinstance(join_table, exp.Alias):
                if isinstance(join_table.this, exp.Table):
                    tables.append((join_table.this.name, join_table.alias))

    return tables


def _has_joins(expression: exp.Expr) -> bool:
    """Check if a SELECT query has any joins."""
    if isinstance(expression, exp.Select):
        return bool(expression.args.get("joins"))
    return False


def _expand_select_star_with_qualification(select: exp.Select) -> None:
    """
    Expand SELECT * to table-qualified columns when joins are present.

    For queries like:
        SELECT * FROM users JOIN orders

    Expands to:
        SELECT users.*, orders.*

    This allows columns to be referenced as table.column, avoiding conflicts.
    """
    if not _has_joins(select):
        return

    tables = _collect_joined_tables(select)
    if len(tables) < 2:
        return

    # Find SELECT * expressions
    select_expressions = select.expressions
    has_star = False

    for expr in select_expressions:
        if (
            isinstance(expr, exp.Star)
            or isinstance(expr, exp.Column)
            and expr.name == "*"
            and not expr.table
        ):
            has_star = True
            break

    if not has_star:
        return

    # Replace SELECT * with table.* for each table
    new_expressions: list[exp.Expr] = []
    star_replaced = False

    for expr in select_expressions:
        is_star = isinstance(expr, exp.Star) or (
            isinstance(expr, exp.Column) and expr.name == "*" and not expr.table
        )

        if is_star and not star_replaced:
            # Replace first * with table.* for each table
            for table_name, alias in tables:
                table_ref = alias if alias else table_name
                new_expressions.append(
                    # The same node a written `t.*` parses to; a Column whose
                    # name is the identifier "*" gets aliased as a column later.
                    exp.Column(this=exp.Star(), table=exp.to_identifier(table_ref))
                )
            star_replaced = True
        elif not is_star:
            new_expressions.append(expr)

    if star_replaced:
        select.set("expressions", new_expressions)


def _qualify_unqualified_columns(select: exp.Select) -> None:
    """
    Qualify unqualified column references when they might be ambiguous.

    This handles cases where a column name appears in multiple tables.
    Without schema info, we can't detect actual conflicts, but we can
    qualify columns that are referenced without table qualification.
    """
    if not _has_joins(select):
        return

    tables = _collect_joined_tables(select)
    if len(tables) < 2:
        return

    # Find unqualified column references in SELECT, WHERE, GROUP BY, ORDER BY, HAVING
    def qualify_column_if_needed(expr: exp.Expr) -> None:
        """Recursively qualify unqualified columns."""
        if isinstance(expr, exp.Column):
            # If column is already qualified, skip
            if expr.table:
                return

            # For now, we'll leave unqualified columns as-is
            # The expansion of SELECT * to table.* handles the main case
            # Users can still explicitly qualify columns if needed
            pass
        else:
            # Recursively process children
            for child in expr.iter_expressions():
                qualify_column_if_needed(child)

    # Process SELECT expressions
    for expr in select.expressions:
        qualify_column_if_needed(expr)

    # Process WHERE clause
    if select.args.get("where"):
        qualify_column_if_needed(select.args["where"])

    # Process GROUP BY
    if select.args.get("group"):
        for expr in select.args["group"].expressions:
            qualify_column_if_needed(expr)

    # Process ORDER BY
    if select.args.get("order"):
        for expr in select.args["order"].expressions:
            qualify_column_if_needed(expr)

    # Process HAVING
    if select.args.get("having"):
        qualify_column_if_needed(select.args["having"])


def auto_qualify_columns(expression: exp.Expr) -> exp.Expr:
    """
    Auto-qualify conflicting column names in queries with joins.

    When SELECT * is used with joins, expands it to table.* for each table.
    This allows columns to be referenced as table.column, avoiding conflicts.

    Example:
        SELECT * FROM users JOIN orders
    becomes:
        SELECT users.*, orders.* FROM users JOIN orders
    """
    if isinstance(expression, exp.Select):
        _expand_select_star_with_qualification(expression)
        _qualify_unqualified_columns(expression)
    elif isinstance(expression, exp.Union):
        # Process each SELECT in UNION
        for select in expression.expressions:
            if isinstance(select, exp.Select):
                _expand_select_star_with_qualification(select)
                _qualify_unqualified_columns(select)

    return expression
