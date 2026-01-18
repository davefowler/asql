"""AST transform for cohort analysis.

Transforms queries with cohort info (set by dialect parser) into proper SQL
with CTEs for cohort_base and cohort_sizes, JOINs, and modified GROUP BY.

Example:
    from events
    group by month(event_date) (count(distinct user_id) as active)
    cohort by month(users.signup_date) on user_id

Becomes:
    WITH cohort_base AS (
      SELECT user_id, DATE_TRUNC('month', users.signup_date) AS cohort_month
      FROM users
      WHERE users.signup_date IS NOT NULL
    ),
    cohort_sizes AS (
      SELECT cohort_month, COUNT(DISTINCT user_id) AS cohort_size
      FROM cohort_base
      GROUP BY cohort_month
    )
    SELECT 
      cb.cohort_month,
      <period_expr> AS period,
      cs.cohort_size,
      COUNT(DISTINCT e.user_id) AS active
    FROM events e
    JOIN cohort_base cb ON e.user_id = cb.user_id
    JOIN cohort_sizes cs ON cb.cohort_month = cs.cohort_month
    GROUP BY cb.cohort_month, <period_expr>
    ORDER BY cb.cohort_month, period
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from sqlglot import exp

if TYPE_CHECKING:
    from asql.config import CompileSettings
    from asql.schema import Schema


def _infer_join_key(cohort_table: str, activity_table: str, schema: Optional["Schema"] = None) -> str:
    """Infer FK column for cohort join using shared resolution logic.
    
    Uses the join_inference module which checks:
    1. Schema relationships (explicit, then inferred)
    2. Convention-based guessing ({table}_id pattern)
    """
    from asql.compiler.join_inference import resolve_join_condition
    
    condition = resolve_join_condition(
        left_table=activity_table,
        right_table=cohort_table,
        schema=schema,
        hint_column=None,  # No hint - let it infer
    )
    
    if condition:
        # Return the FK column (the one on the activity table side)
        if condition.left_table.lower() == activity_table.lower():
            return condition.left_column
        else:
            return condition.right_column
    
    # Ultimate fallback - use shared singularization
    from asql.compiler.join_inference import _singularize
    singular = _singularize(cohort_table)
    return f"{singular}_id"


def _get_activity_date_column(stmt: exp.Select) -> Optional[str]:
    """Find the activity date column from GROUP BY clause.
    
    Looks for month(...), week(...), or day(...) patterns in GROUP BY.
    Falls back to common date column names.
    """
    group = stmt.args.get('group')
    if group:
        for expr in group.expressions:
            # Look for date function calls
            if isinstance(expr, (exp.Month, exp.Week, exp.Day)):
                inner = expr.this
                if isinstance(inner, exp.Column):
                    return inner.name
            # Look for function calls like MONTH(col)
            if isinstance(expr, exp.Anonymous) and expr.name.upper() in ('MONTH', 'WEEK', 'DAY'):
                args = expr.expressions
                if args and isinstance(args[0], exp.Column):
                    return args[0].name
    
    # Fall back to common date column names in SELECT
    common_dates = ['event_date', 'created_at', 'timestamp', 'date', 'order_date']
    for col_name in common_dates:
        for col in stmt.find_all(exp.Column):
            if col.name.lower() == col_name:
                return col.name
    
    return None


def _build_period_expr(activity_date_col: str, granularity: str, activity_alias: str = "e") -> exp.Expression:
    """Build the period calculation expression.
    
    Period = time elapsed since cohort_month in the given granularity.
    """
    date_col = exp.Column(this=exp.to_identifier(activity_date_col), table=exp.to_identifier(activity_alias))
    cohort_month_col = exp.Column(this=exp.to_identifier("cohort_month"), table=exp.to_identifier("cb"))
    
    if granularity == "month":
        # EXTRACT(YEAR FROM AGE(date_col, cohort_month)) * 12 + EXTRACT(MONTH FROM AGE(date_col, cohort_month))
        age_expr = exp.Anonymous(this="AGE", expressions=[date_col, cohort_month_col])
        year_part = exp.Extract(this=exp.Literal.string("YEAR"), expression=age_expr)
        month_part = exp.Extract(this=exp.Literal.string("MONTH"), expression=age_expr.copy())
        return exp.Add(
            this=exp.Mul(this=year_part, expression=exp.Literal.number(12)),
            expression=month_part
        )
    elif granularity == "week":
        # FLOOR(EXTRACT(EPOCH FROM (date_col - cohort_month)) / 604800)
        diff = exp.Sub(this=date_col, expression=cohort_month_col)
        epoch = exp.Extract(this=exp.Literal.string("EPOCH"), expression=diff)
        return exp.Anonymous(this="FLOOR", expressions=[
            exp.Div(this=epoch, expression=exp.Literal.number(604800))
        ])
    else:  # day
        # EXTRACT(DAY FROM (date_col - cohort_month))
        diff = exp.Sub(this=date_col, expression=cohort_month_col)
        return exp.Extract(this=exp.Literal.string("DAY"), expression=diff)


def _build_date_trunc(granularity: str, col: exp.Expression) -> exp.Expression:
    """Build DATE_TRUNC expression for the given granularity."""
    return exp.Anonymous(
        this="DATE_TRUNC",
        expressions=[exp.Literal.string(granularity), col]
    )


def transform_cohort(
    stmt: exp.Expression,
    settings: Optional["CompileSettings"] = None,
) -> exp.Expression:
    """Transform a query with cohort info into full cohort analysis SQL.
    
    Looks for _cohort_info attribute set by the dialect parser.
    If found, generates CTEs, JOINs, and modifies GROUP BY/SELECT.
    
    Args:
        stmt: SQLGlot expression (typically a SELECT statement)
        settings: Compile settings (for schema-based join inference)
        
    Returns:
        Modified statement with cohort analysis SQL
    """
    if not isinstance(stmt, exp.Select):
        return stmt
    
    # Check for cohort info set by parser
    cohort_info = getattr(stmt, '_cohort_info', None)
    if not cohort_info:
        return stmt
    
    granularity = cohort_info.get('granularity')
    cohort_col = cohort_info.get('cohort_col')
    explicit_join_key = cohort_info.get('join_key')
    segments = cohort_info.get('segments', [])
    
    if not granularity or not cohort_col:
        return stmt
    
    # Extract cohort table and column from cohort_col (may be table.column)
    if isinstance(cohort_col, exp.Column):
        cohort_table = cohort_col.table if cohort_col.table else None
        cohort_col_name = cohort_col.name
    else:
        cohort_table = None
        cohort_col_name = str(cohort_col)
    
    # Get the activity table from FROM clause
    from_clause = stmt.args.get('from_')
    if not from_clause:
        return stmt
    
    table = from_clause.find(exp.Table)
    if not table:
        return stmt
    
    activity_table = table.name
    activity_alias = "e"
    
    # Determine join key
    schema = settings.schema if settings else None
    if explicit_join_key:
        join_key = explicit_join_key
    elif cohort_table:
        join_key = _infer_join_key(cohort_table, activity_table, schema)
    else:
        # Can't proceed without a join key
        raise ValueError(
            "Cohort analysis requires a cohort table reference or explicit join key. "
            "Use 'cohort by month(users.signup_date)' or 'cohort by month(signup_date) on user_id'."
        )
    
    # Get the activity date column from GROUP BY
    activity_date_col = _get_activity_date_column(stmt)
    if not activity_date_col:
        raise ValueError(
            "Cannot determine activity date column for cohort analysis. "
            "Use a date function in GROUP BY (e.g., 'group by month(event_date)')."
        )
    
    # Build cohort_base CTE
    cohort_col_ref = exp.Column(
        this=exp.to_identifier(cohort_col_name),
        table=exp.to_identifier(cohort_table) if cohort_table else None
    )
    date_trunc = _build_date_trunc(granularity, cohort_col_ref)
    
    # Build expressions for cohort_base: segments + join_key + cohort_month
    cohort_base_exprs = []
    for seg in segments:
        cohort_base_exprs.append(seg.copy())
    cohort_base_exprs.append(exp.Column(this=exp.to_identifier(join_key)))
    cohort_base_exprs.append(exp.Alias(this=date_trunc, alias=exp.to_identifier("cohort_month")))
    
    cohort_base_select = exp.Select(
        expressions=cohort_base_exprs,
        from_=exp.From(this=exp.Table(this=exp.to_identifier(cohort_table or activity_table)))
    ).where(
        exp.Not(this=exp.Is(this=cohort_col_ref.copy(), expression=exp.Null()))
    )
    
    # Build cohort_sizes CTE
    # Group by segments + cohort_month
    cohort_sizes_exprs = []
    cohort_sizes_group_by = []
    for seg in segments:
        # Reference segment from cohort_base
        seg_name = seg.name if hasattr(seg, 'name') else str(seg.this)
        cohort_sizes_exprs.append(exp.Column(this=exp.to_identifier(seg_name)))
        cohort_sizes_group_by.append(exp.Column(this=exp.to_identifier(seg_name)))
    cohort_sizes_exprs.append(exp.Column(this=exp.to_identifier("cohort_month")))
    cohort_sizes_group_by.append(exp.Column(this=exp.to_identifier("cohort_month")))
    cohort_sizes_exprs.append(exp.Alias(
        this=exp.Count(this=exp.Distinct(expressions=[exp.Column(this=exp.to_identifier(join_key))])),
        alias=exp.to_identifier("cohort_size")
    ))
    
    cohort_sizes_select = exp.Select(
        expressions=cohort_sizes_exprs,
        from_=exp.From(this=exp.Table(this=exp.to_identifier("cohort_base")))
    ).group_by(*cohort_sizes_group_by)
    
    # Build WITH clause
    with_clause = exp.With(
        expressions=[
            exp.CTE(this=cohort_base_select, alias=exp.TableAlias(this=exp.to_identifier("cohort_base"))),
            exp.CTE(this=cohort_sizes_select, alias=exp.TableAlias(this=exp.to_identifier("cohort_sizes")))
        ]
    )
    
    # Modify the main query
    # 1. Add alias to activity table
    table.set('alias', exp.TableAlias(this=exp.to_identifier(activity_alias)))
    
    # 2. Add JOINs
    # Build cb_join ON condition (join_key + segments)
    cb_on_conditions = [
        exp.EQ(
            this=exp.Column(this=exp.to_identifier(join_key), table=exp.to_identifier(activity_alias)),
            expression=exp.Column(this=exp.to_identifier(join_key), table=exp.to_identifier("cb"))
        )
    ]
    for seg in segments:
        seg_name = seg.name if hasattr(seg, 'name') else str(seg.this)
        cb_on_conditions.append(exp.EQ(
            this=exp.Column(this=exp.to_identifier(seg_name), table=exp.to_identifier(activity_alias)),
            expression=exp.Column(this=exp.to_identifier(seg_name), table=exp.to_identifier("cb"))
        ))
    
    cb_on = cb_on_conditions[0]
    for cond in cb_on_conditions[1:]:
        cb_on = exp.And(this=cb_on, expression=cond)
    
    cb_join = exp.Join(
        this=exp.Table(this=exp.to_identifier("cohort_base"), alias=exp.TableAlias(this=exp.to_identifier("cb"))),
        on=cb_on
    )
    
    # Build cs_join ON condition (cohort_month + segments)
    cs_on_conditions = [
        exp.EQ(
            this=exp.Column(this=exp.to_identifier("cohort_month"), table=exp.to_identifier("cb")),
            expression=exp.Column(this=exp.to_identifier("cohort_month"), table=exp.to_identifier("cs"))
        )
    ]
    for seg in segments:
        seg_name = seg.name if hasattr(seg, 'name') else str(seg.this)
        cs_on_conditions.append(exp.EQ(
            this=exp.Column(this=exp.to_identifier(seg_name), table=exp.to_identifier("cb")),
            expression=exp.Column(this=exp.to_identifier(seg_name), table=exp.to_identifier("cs"))
        ))
    
    cs_on = cs_on_conditions[0]
    for cond in cs_on_conditions[1:]:
        cs_on = exp.And(this=cs_on, expression=cond)
    
    cs_join = exp.Join(
        this=exp.Table(this=exp.to_identifier("cohort_sizes"), alias=exp.TableAlias(this=exp.to_identifier("cs"))),
        on=cs_on
    )
    
    existing_joins = stmt.args.get('joins', [])
    stmt.set('joins', existing_joins + [cb_join, cs_join])
    
    # 3. Build period expression
    period_expr = _build_period_expr(activity_date_col, granularity, activity_alias)
    
    # 4. Modify SELECT to add cohort columns at the start (segments + cohort_month + period + cohort_size)
    cohort_columns = []
    for seg in segments:
        seg_name = seg.name if hasattr(seg, 'name') else str(seg.this)
        cohort_columns.append(exp.Column(this=exp.to_identifier(seg_name), table=exp.to_identifier("cb")))
    cohort_columns.extend([
        exp.Column(this=exp.to_identifier("cohort_month"), table=exp.to_identifier("cb")),
        exp.Alias(this=period_expr, alias=exp.to_identifier("period")),
        exp.Column(this=exp.to_identifier("cohort_size"), table=exp.to_identifier("cs")),
    ])
    
    current_exprs = stmt.expressions
    # Remove Star if present, keep other expressions
    non_star = [e for e in current_exprs if not isinstance(e, exp.Star)]
    stmt.set('expressions', cohort_columns + non_star)
    
    # 5. Modify GROUP BY to include cohort dimensions (segments + cohort_month + period)
    group_by_exprs = []
    for seg in segments:
        seg_name = seg.name if hasattr(seg, 'name') else str(seg.this)
        group_by_exprs.append(exp.Column(this=exp.to_identifier(seg_name), table=exp.to_identifier("cb")))
    group_by_exprs.extend([
        exp.Column(this=exp.to_identifier("cohort_month"), table=exp.to_identifier("cb")),
        period_expr.copy()
    ])
    new_group_by = exp.Group(expressions=group_by_exprs)
    stmt.set('group', new_group_by)
    
    # 6. Add/modify ORDER BY (segments + cohort_month + period)
    order = stmt.args.get('order')
    order_exprs = []
    for seg in segments:
        seg_name = seg.name if hasattr(seg, 'name') else str(seg.this)
        order_exprs.append(exp.Ordered(this=exp.Column(this=exp.to_identifier(seg_name), table=exp.to_identifier("cb"))))
    order_exprs.extend([
        exp.Ordered(this=exp.Column(this=exp.to_identifier("cohort_month"), table=exp.to_identifier("cb"))),
        exp.Ordered(this=exp.Column(this=exp.to_identifier("period"))),
    ])
    if order:
        # Prepend cohort ordering
        order_exprs.extend(order.expressions)
    stmt.set('order', exp.Order(expressions=order_exprs))
    
    # 7. Add WITH clause
    stmt.set('with_', with_clause)
    
    # Clean up the cohort info
    delattr(stmt, '_cohort_info')
    
    return stmt

