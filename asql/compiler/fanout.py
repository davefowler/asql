"""Fanout protection for grouped join queries.

This module implements the pre-aggregation approach described in docs/concepts/fanout.md:
when schema metadata proves that a joined table is on the many side of a relationship,
rewrite supported aggregates on that table into a subquery grouped by the foreign key.

Two sibling rewrites complete the coverage:

- Join-as-filter: a provable many-side join no aggregate references collapses
  to ``SELECT DISTINCT <fk>`` so it keeps filtering without multiplying rows.
- Reverse direction (the FROM side is the many side): the grouped select is
  re-aggregated through an inner ``GROUP BY <join key>`` stage that captures
  one-side values once per key before the outer aggregation.

Provable fanout risk that still is not rewritten emits an "ASQL fanout
warning" transpilation comment instead of failing silently.
"""

from __future__ import annotations

import typing as t
from dataclasses import dataclass

from sqlglot import exp

if t.TYPE_CHECKING:
    from asql.config import CompileSettings

# sqlglot renamed Select's FROM arg key ("from" -> "from_"); resolve once.
FROM_KEY = "from_" if "from_" in exp.Select.arg_types else "from"


@dataclass
class _ManySideJoin:
    join: exp.Join
    right_alias: str
    right_table: str
    fk_column: str
    table_expr: exp.Table


@dataclass
class _AggregatePlan:
    aggregate: exp.AggFunc
    outer_expr: exp.Expr
    inner_selects: list[exp.Expr]
    diagnostic: str


def protect_fanout_aggregates(
    ast: exp.Expr,
    settings: CompileSettings,
) -> exp.Expr:
    """Rewrite supported grouped join queries to avoid additive fanout.

    Current supported scope:
    - Requires schema metadata and fanout_protection=True
    - Only grouped SELECT queries; joins must be provable from schema + ON clause
    - Joined many side with aggregates: pre-aggregated by the foreign key
    - Joined many side no aggregate references: collapsed to SELECT DISTINCT fk
    - FROM-side many table (single reverse equi-join): stage-2 re-aggregation
    - Supports SUM/COUNT/AVG/MIN/MAX single-table aggregates across the boundary
    - Unrewritten provable risk emits "ASQL fanout warning" diagnostics
    """
    if not settings.fanout_protection or not settings.schema:
        return ast

    # Materialize before rewriting: the stage-2 rewrite nests a new grouped
    # SELECT that must not itself be visited by this pass.
    for select in list(ast.find_all(exp.Select)):
        _protect_select(select, settings)

    return ast


def _protect_select(query: exp.Select, settings: CompileSettings) -> None:
    if not query.args.get("group"):
        return

    from_clause = _select_from(query)
    if not from_clause or not isinstance(from_clause.this, exp.Table):
        return

    joins = [
        join for join in query.args.get("joins") or [] if isinstance(join, exp.Join)
    ]
    if not joins:
        return

    alias_map = _collect_aliases(query)
    if not alias_map:
        return

    diagnostics: list[str] = []
    forward_matches = _find_many_side_joins(query, alias_map, settings)
    handled_aliases: set[str] = set()

    for join_info in forward_matches:
        if _depends_on_many_side_shape(query, join_info.right_alias):
            diagnostics.append(
                f"ASQL fanout protection skipped for {join_info.right_alias}: "
                f"query shape depends on raw {join_info.right_alias} rows."
            )
            handled_aliases.add(join_info.right_alias)
            continue

        plans = _collect_aggregate_plans(query, join_info.right_alias)
        if not plans:
            if _has_aggregate_reference(query, join_info.right_alias):
                diagnostics.append(
                    f"ASQL fanout protection could not rewrite aggregates on {join_info.right_alias}: "
                    f"unsupported aggregate shape or cross-table expression."
                )
                handled_aliases.add(join_info.right_alias)
            elif _query_has_aggregates(query):
                _collapse_join_to_distinct_keys(join_info)
                _mark_rewritten(query, join_info.right_alias)
                diagnostics.append(
                    f"ASQL fanout protection: collapsed {join_info.right_alias} to "
                    f"DISTINCT {join_info.fk_column} before joining (join used as filter)."
                )
                handled_aliases.add(join_info.right_alias)
            continue

        subquery = _build_preagg_subquery(join_info, plans)
        join_info.join.set(
            "this",
            exp.Subquery(
                this=subquery,
                alias=exp.TableAlias(this=exp.to_identifier(join_info.right_alias)),
            ),
        )

        for plan in plans:
            plan.aggregate.replace(plan.outer_expr)
        _mark_rewritten(query, join_info.right_alias)

        diagnostics.append(
            f"ASQL fanout protection: pre-aggregated {join_info.right_alias} by "
            f"{join_info.fk_column} before joining."
        )
        handled_aliases.add(join_info.right_alias)

    if not forward_matches:
        stage2_diagnostic = _apply_reverse_stage2(query, alias_map, settings)
        if stage2_diagnostic:
            diagnostics.append(stage2_diagnostic)

    diagnostics.extend(
        _fanout_risk_warnings(
            query, alias_map, settings, forward_matches, handled_aliases
        )
    )

    if diagnostics and settings.include_transpilation_comments:
        query.add_comments(diagnostics)


def _mark_rewritten(query: exp.Select, alias: str) -> None:
    """Record a join whose rows can no longer multiply the select's aggregates."""
    query.meta.setdefault("fanout_rewritten", set()).add(alias)


def _select_from(query: exp.Select) -> exp.Expr | None:
    return query.args.get(FROM_KEY)


def _collect_aliases(query: exp.Select) -> dict[str, str]:
    alias_map: dict[str, str] = {}

    from_clause = _select_from(query)
    if from_clause and isinstance(from_clause.this, exp.Table):
        table = from_clause.this
        alias_map[table.alias_or_name.lower()] = table.name.lower()

    for join in query.args.get("joins") or []:
        if isinstance(join, exp.Join) and isinstance(join.this, exp.Table):
            table = join.this
            alias_map[table.alias_or_name.lower()] = table.name.lower()

    return alias_map


def adds_unmatched_rows(join: exp.Join) -> bool:
    """Whether the join can add rows that have no FROM-side match.

    sqlglot keeps RIGHT/FULL in `side` for SQL input and in `kind` for ASQL's
    join operators, so both are checked.
    """
    shape = f"{join.side or ''} {join.kind or ''}".upper()
    return any(word in shape for word in ("RIGHT", "FULL", "CROSS"))


def equi_join_columns(
    join: exp.Expr, include_outer: bool = False
) -> tuple[exp.Column, exp.Column] | None:
    """The two columns of a rewritable equi-join, or None for other join shapes.

    ``include_outer`` also accepts RIGHT/FULL joins, for risk detection only.
    """
    if not isinstance(join, exp.Join) or not isinstance(join.this, exp.Table):
        return None
    kinds = ("CROSS",) if include_outer else ("RIGHT", "FULL", "CROSS")
    if join.kind and any(kind in join.kind.upper() for kind in kinds):
        return None
    on_expr = join.args.get("on")
    if not isinstance(on_expr, exp.EQ):
        return None
    left_col, right_col = on_expr.this, on_expr.expression
    if not isinstance(left_col, exp.Column) or not isinstance(right_col, exp.Column):
        return None
    return left_col, right_col


def _find_many_side_joins(
    query: exp.Select,
    alias_map: dict[str, str],
    settings: CompileSettings,
) -> list[_ManySideJoin]:
    many_side: list[_ManySideJoin] = []
    schema = settings.schema
    if not schema:
        return many_side

    for join in query.args.get("joins") or []:
        columns = equi_join_columns(join)
        if columns is None:
            continue
        left_col, right_col = columns

        table_expr = join.this
        right_alias = table_expr.alias_or_name.lower()
        right_table = table_expr.name.lower()

        matched = _match_relationship(
            schema=schema,
            right_alias=right_alias,
            right_table=right_table,
            left_col=left_col,
            right_col=right_col,
            alias_map=alias_map,
        )
        if matched and _fk_declared_unique(schema, right_table, matched["fk_column"]):
            continue  # declared 1:1 - the join cannot fan out
        if matched:
            many_side.append(
                _ManySideJoin(
                    join=join,
                    right_alias=right_alias,
                    right_table=right_table,
                    table_expr=table_expr,
                    **matched,
                )
            )

    return many_side


def _fanout_risk_warnings(
    query: exp.Select,
    alias_map: dict[str, str],
    settings: CompileSettings,
    forward_matches: list[_ManySideJoin],
    handled_aliases: set[str],
) -> list[str]:
    """Warn on schema-provable fanout risk the rewrite pass did not handle."""
    warnings: list[str] = []

    reverse_matches = _find_reverse_one_side_joins(query, alias_map, settings)
    for one_alias, many_alias in reverse_matches:
        if _has_aggregate_reference(query, one_alias):
            warnings.append(
                f"ASQL fanout warning: {many_alias} fans out {one_alias}; "
                f"aggregates on {one_alias} may be inflated. Pre-group "
                f"{many_alias} in an earlier pipe stage or put {one_alias} in FROM."
            )

    for join_info in forward_matches:
        alias = join_info.right_alias
        if alias in handled_aliases or _has_aggregate_reference(query, alias):
            continue
        if _query_has_aggregates(query):
            warnings.append(
                f"ASQL fanout warning: join to {alias} multiplies rows; "
                f"aggregates on other tables may be inflated."
            )

    # Only a joined many side multiplies rows; a reverse (N:1) join cannot,
    # so bare COUNT(*) is already row-accurate there.
    if forward_matches and _has_bare_count_star(query):
        warnings.append(
            "ASQL fanout warning: COUNT(*) counts joined rows at the current "
            "grain and this join can multiply rows; use COUNT(<table>.<column>) "
            "or COUNT(DISTINCT ...) to count entities."
        )

    return warnings


def _find_reverse_one_side_joins(
    query: exp.Select,
    alias_map: dict[str, str],
    settings: CompileSettings,
) -> list[tuple[str, str]]:
    """(one_alias, many_alias) pairs where the JOINED table is the referenced side."""
    matches: list[tuple[str, str]] = []
    schema = settings.schema
    if not schema:
        return matches

    for join in query.args.get("joins") or []:
        columns = equi_join_columns(join, include_outer=True)
        if columns is None:
            continue
        left_col, right_col = columns

        right_alias = join.this.alias_or_name.lower()
        right_table = join.this.name.lower()

        for one_col, many_col in ((left_col, right_col), (right_col, left_col)):
            one_alias = (one_col.table or "").lower()
            many_alias = (many_col.table or "").lower()
            if one_alias != right_alias or not many_alias:
                continue
            many_table = alias_map.get(many_alias)
            if not many_table:
                continue
            for rel in schema.find_all_relationships(many_table, right_table):
                if (
                    rel.from_column == many_col.name.lower()
                    and rel.to_column == one_col.name.lower()
                    and not _fk_declared_unique(schema, many_table, rel.from_column)
                ):
                    matches.append((one_alias, many_alias))

    return matches


def _query_has_aggregates(query: exp.Select) -> bool:
    return any(
        agg.find_ancestor(exp.Select) is query and not agg.find_ancestor(exp.Window)
        for agg in query.find_all(exp.AggFunc)
    )


def _has_bare_count_star(query: exp.Select) -> bool:
    return any(
        isinstance(agg, exp.Count)
        and isinstance(agg.this, exp.Star)
        and agg.find_ancestor(exp.Select) is query
        and not agg.find_ancestor(exp.Window)
        # A metric's COUNT(*) declares its intent: rows of its home model.
        and not agg.meta.get("semantic_metric")
        for agg in query.find_all(exp.AggFunc)
    )


def _depends_on_many_side_shape(query: exp.Select, right_alias: str) -> bool:
    group = query.args.get("group")
    if isinstance(group, exp.Group):
        for group_expr in group.expressions:
            if _references_table(group_expr, right_alias):
                return True

    for key in ("where", "having", "qualify"):
        expr = query.args.get(key)
        if expr is not None and _references_table(expr, right_alias):
            return True

    order = query.args.get("order")
    if isinstance(order, exp.Order):
        for ordered in order.expressions:
            if _references_table(ordered, right_alias):
                return True

    for expr in query.expressions:
        core = expr.this if isinstance(expr, exp.Alias) else expr
        if isinstance(core, exp.AggFunc):
            continue
        if _references_table(core, right_alias):
            return True

    return False


def _references_table(expression: exp.Expr, right_alias: str) -> bool:
    for column in expression.find_all(exp.Column):
        if (column.table or "").lower() == right_alias:
            return True
    return False


def _fk_declared_unique(schema: t.Any, table_name: str, fk_column: str) -> bool:
    """A unique-declared FK column makes the relationship 1:1 - no fanout possible."""
    table = schema.get_table(table_name)
    return bool(table and table.is_column_unique(fk_column))


def _match_relationship(
    schema: t.Any,
    right_alias: str,
    right_table: str,
    left_col: exp.Column,
    right_col: exp.Column,
    alias_map: dict[str, str],
) -> dict[str, str] | None:
    for many_col, one_col in ((left_col, right_col), (right_col, left_col)):
        many_alias = (many_col.table or "").lower()
        one_alias = (one_col.table or "").lower()
        if many_alias != right_alias or not one_alias:
            continue

        one_table = alias_map.get(one_alias)
        if not one_table:
            continue

        relationships = schema.find_all_relationships(right_table, one_table)
        for rel in relationships:
            if (
                rel.from_column == many_col.name.lower()
                and rel.to_column == one_col.name.lower()
            ):
                return {"fk_column": rel.from_column}

    return None


def _decompose_aggregate(
    aggregate: exp.AggFunc,
    index: int,
    outer_column: t.Callable[[str], exp.Column],
) -> tuple[list[exp.Expr], exp.Expr, str] | None:
    """Split a decomposable aggregate into inner selects and an outer combine expression.

    The single home for the aggregate-family combine rules (SUM->SUM,
    COUNT->SUM+COALESCE, AVG->SUM/COUNT, MIN/MAX->self), shared by the forward
    pre-aggregation and the reverse stage-2 rewrite. Returns None for families
    that cannot cross a pre-aggregation boundary.
    """
    inner_selects: list[
        exp.Expr
    ]  # WHY: prevents pyright inferring list[Unknown | Alias] from the if/elif branches
    if isinstance(aggregate, exp.Sum):
        inner_alias = _aggregate_alias("sum", index, aggregate)
        outer_expr: exp.Expr = exp.Sum(this=outer_column(inner_alias))
        inner_selects = [
            exp.alias_(
                _build_inner_aggregate(aggregate.copy()), inner_alias, copy=False
            )
        ]
        verb = "SUM()"
    elif isinstance(aggregate, exp.Count) and not _is_distinct_count(aggregate):
        inner_alias = _aggregate_alias("count", index, aggregate)
        outer_expr = exp.Sum(
            this=exp.Coalesce(
                this=outer_column(inner_alias),
                expressions=[exp.Literal.number(0)],
            )
        )
        inner_selects = [
            exp.alias_(
                _build_inner_aggregate(aggregate.copy()), inner_alias, copy=False
            )
        ]
        verb = "COUNT()"
    elif isinstance(aggregate, exp.Avg):
        sum_alias = _aggregate_alias("sum", index, aggregate)
        count_alias = _aggregate_alias("count", index, aggregate)
        numerator = exp.Sum(this=outer_column(sum_alias))
        denominator = exp.Nullif(
            this=exp.Sum(
                this=exp.Coalesce(
                    this=outer_column(count_alias),
                    expressions=[exp.Literal.number(0)],
                )
            ),
            expression=exp.Literal.number(0),
        )
        outer_expr = exp.Div(this=numerator, expression=denominator)
        inner_arg = aggregate.this.copy()
        inner_selects = [
            exp.alias_(exp.Sum(this=inner_arg.copy()), sum_alias, copy=False),
            exp.alias_(exp.Count(this=inner_arg), count_alias, copy=False),
        ]
        verb = "AVG()"
    elif isinstance(aggregate, exp.Min):
        inner_alias = _aggregate_alias("min", index, aggregate)
        outer_expr = exp.Min(this=outer_column(inner_alias))
        inner_selects = [
            exp.alias_(
                _build_inner_aggregate(aggregate.copy()), inner_alias, copy=False
            )
        ]
        verb = "MIN()"
    elif isinstance(aggregate, exp.Max):
        inner_alias = _aggregate_alias("max", index, aggregate)
        outer_expr = exp.Max(this=outer_column(inner_alias))
        inner_selects = [
            exp.alias_(
                _build_inner_aggregate(aggregate.copy()), inner_alias, copy=False
            )
        ]
        verb = "MAX()"
    else:
        return None
    return inner_selects, outer_expr, verb


def _collect_aggregate_plans(
    query: exp.Select, right_alias: str
) -> list[_AggregatePlan]:
    plans: list[_AggregatePlan] = []

    for aggregate in query.find_all(exp.AggFunc):
        if aggregate.find_ancestor(exp.Select) is not query:
            continue
        if aggregate.find_ancestor(exp.Window):
            continue

        tables = {
            (column.table or "").lower()
            for column in aggregate.find_all(exp.Column)
            if column.table
        }

        if tables != {right_alias}:
            continue

        decomposed = _decompose_aggregate(
            aggregate, len(plans), lambda name: exp.column(name, table=right_alias)
        )
        if decomposed is None:
            return []
        inner_selects, outer_expr, verb = decomposed

        plans.append(
            _AggregatePlan(
                aggregate=aggregate,
                outer_expr=outer_expr,
                inner_selects=inner_selects,
                diagnostic=f"rewrote {verb} on {right_alias}",
            )
        )

    return plans


def _is_distinct_count(aggregate: exp.Count) -> bool:
    arg = aggregate.this
    return isinstance(arg, exp.Distinct)


def _aggregate_alias(prefix: str, index: int, aggregate: exp.AggFunc) -> str:
    column = aggregate.find(exp.Column)
    suffix = column.name.lower() if column else str(index + 1)
    return f"__fanout_{prefix}_{suffix}_{index + 1}"


def _build_preagg_subquery(
    join_info: _ManySideJoin, plans: list[_AggregatePlan]
) -> exp.Select:
    select = exp.Select()
    fk_expr = exp.column(join_info.fk_column, table=join_info.right_alias)
    select.select(fk_expr.copy(), copy=False)
    select.from_(join_info.table_expr.copy(), copy=False)
    select.group_by(fk_expr.copy(), copy=False)

    for plan in plans:
        for inner_select in plan.inner_selects:
            select.select(inner_select, append=True, copy=False)

    return select


def _build_inner_aggregate(aggregate: exp.AggFunc) -> exp.Expr:
    if isinstance(aggregate, exp.Count) and isinstance(aggregate.this, exp.Star):
        return exp.Count(this=exp.Star())
    return aggregate


def _has_aggregate_reference(query: exp.Select, right_alias: str) -> bool:
    for aggregate in query.find_all(exp.AggFunc):
        if aggregate.find_ancestor(exp.Select) is not query:
            continue
        for column in aggregate.find_all(exp.Column):
            if (column.table or "").lower() == right_alias:
                return True
    return False


def _collapse_join_to_distinct_keys(join_info: _ManySideJoin) -> None:
    """Replace a join-as-filter many side with SELECT DISTINCT of its join key."""
    subquery = exp.Select(distinct=exp.Distinct()).select(
        exp.column(join_info.fk_column, table=join_info.right_alias), copy=False
    )
    subquery.from_(join_info.table_expr.copy(), copy=False)
    join_info.join.set(
        "this",
        exp.Subquery(
            this=subquery,
            alias=exp.TableAlias(this=exp.to_identifier(join_info.right_alias)),
        ),
    )


@dataclass
class _Stage2Plan:
    aggregate: exp.AggFunc
    outer_expr: exp.Expr
    inner_selects: list[exp.Expr]
    protects_one_side: bool


def _apply_reverse_stage2(
    query: exp.Select,
    alias_map: dict[str, str],
    settings: CompileSettings,
) -> str | None:
    """Rewrite FROM-many JOIN-one grouped selects through an inner GROUP BY join key.

    Conservative first cut: a single reverse-matched equi-join, plain-column
    group keys, no HAVING/QUALIFY/ORDER/LIMIT/DISTINCT on the grouped select,
    and every aggregate classifiable (one-side capture or decomposable
    FROM-side family). Anything else is left for the risk warnings.
    """
    for blocked in ("having", "qualify", "order", "limit", "offset", "distinct"):
        if query.args.get(blocked):
            return None

    joins = query.args.get("joins") or []
    if len(joins) != 1:
        return None

    reverse_matches = _find_reverse_one_side_joins(query, alias_map, settings)
    if len(reverse_matches) != 1:
        return None
    one_alias, many_alias = reverse_matches[0]

    columns = equi_join_columns(joins[0])
    # Unmatched rows would collapse into one NULL group in the inner stage.
    if columns is None or adds_unmatched_rows(joins[0]):
        return None
    fk_col = next(
        (col for col in columns if (col.table or "").lower() == many_alias), None
    )
    if fk_col is None:
        return None

    group = query.args.get("group")
    if not isinstance(group, exp.Group):
        return None
    group_cols = list(group.expressions)
    if not all(isinstance(col, exp.Column) for col in group_cols):
        return None
    group_names = [col.name.lower() for col in group_cols]
    if len(set(group_names)) != len(group_names) or fk_col.name.lower() in group_names:
        return None

    plans = _collect_stage2_plans(query, one_alias, many_alias)
    if plans is None or not any(plan.protects_one_side for plan in plans):
        return None

    group_keys = {
        (col.table or "").lower() + "." + col.name.lower(): col for col in group_cols
    }

    # Every non-aggregate column in the select list must be a group key.
    for expr in query.expressions:
        for column in expr.find_all(exp.Column):
            if column.find_ancestor(exp.AggFunc):
                continue
            key = (column.table or "").lower() + "." + column.name.lower()
            if key not in group_keys:
                return None

    inner = exp.Select()
    inner.set(FROM_KEY, _select_from(query))
    inner.set("joins", query.args.get("joins"))
    inner.set("where", query.args.get("where"))
    inner.select(exp.column(fk_col.name, table=many_alias), copy=False)
    for col in group_cols:
        inner.select(exp.alias_(col.copy(), col.name), copy=False)
    for plan in plans:
        for inner_select in plan.inner_selects:
            inner.select(inner_select, append=True, copy=False)
    inner.group_by(
        exp.column(fk_col.name, table=many_alias),
        *[col.copy() for col in group_cols],
        copy=False,
    )

    query.set("joins", [])
    query.set("where", None)
    query.set(
        FROM_KEY,
        exp.From(
            this=exp.Subquery(
                this=inner,
                alias=exp.TableAlias(this=exp.to_identifier("__fanout_stage2")),
            )
        ),
    )
    for plan in plans:
        plan.aggregate.replace(plan.outer_expr)
    for expr in query.expressions:
        for column in list(expr.find_all(exp.Column)):
            if column.table and not column.find_ancestor(exp.AggFunc):
                column.replace(exp.column(column.name))
    query.set(
        "group",
        exp.Group(expressions=[exp.column(col.name) for col in group_cols]),
    )

    return (
        f"ASQL fanout protection: re-aggregated through {many_alias}.{fk_col.name} "
        f"to protect {one_alias} aggregates."
    )


def _collect_stage2_plans(
    query: exp.Select, one_alias: str, many_alias: str
) -> list[_Stage2Plan] | None:
    """Classify every aggregate for the stage-2 rewrite, or None if any resists.

    One-side aggregates capture their argument once per join key (MAX is the
    portable capture) and re-apply the original function outside; FROM-side
    aggregates use the shared decomposition rules; bare COUNT(*) decomposes to
    keep SQL joined-row semantics.
    """
    plans: list[_Stage2Plan] = []

    for aggregate in query.find_all(exp.AggFunc):
        if aggregate.find_ancestor(exp.Select) is not query:
            continue
        if aggregate.find_ancestor(exp.Window):
            continue

        tables = {
            (column.table or "").lower()
            for column in aggregate.find_all(exp.Column)
            if column.table
        }
        index = len(plans)
        # WHY: declared once so mypy (no-redef) and pyright (list invariance)
        # agree across the branch assignments below
        inner_selects: list[exp.Expr]
        outer_expr: exp.Expr

        if (
            not tables
            and isinstance(aggregate, exp.Count)
            and isinstance(aggregate.this, exp.Star)
        ):
            decomposed = _decompose_aggregate(aggregate, index, exp.column)
            if decomposed is None:
                return None
            inner_selects, outer_expr, _ = decomposed
            plans.append(_Stage2Plan(aggregate, outer_expr, inner_selects, False))
        elif tables == {one_alias}:
            if not isinstance(
                aggregate, (exp.Sum, exp.Count, exp.Avg, exp.Min, exp.Max)
            ) or aggregate.find(exp.Distinct):
                return None
            capture_alias = _aggregate_alias("one", index, aggregate)
            inner_selects = [
                exp.alias_(
                    exp.Max(this=aggregate.this.copy()), capture_alias, copy=False
                )
            ]
            outer_expr = type(aggregate)(this=exp.column(capture_alias))
            plans.append(_Stage2Plan(aggregate, outer_expr, inner_selects, True))
        elif tables == {many_alias}:
            decomposed = _decompose_aggregate(aggregate, index, exp.column)
            if decomposed is None:
                return None
            inner_selects, outer_expr, _ = decomposed
            plans.append(_Stage2Plan(aggregate, outer_expr, inner_selects, False))
        else:
            return None

    return plans
