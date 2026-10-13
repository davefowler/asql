"""`pivot ... group by k` — group the pivot by the key columns.

A table-level PIVOT groups by every column it does not consume, so a trailing
GROUP BY cannot be emitted (it would not even be valid SQL). The keys are instead
selected into a subquery next to the pivot's own columns, which makes the pivot's
implicit grouping land exactly on them:

    SELECT * FROM (SELECT customer_id, status, amount FROM orders) PIVOT(...)
"""

from __future__ import annotations

from sqlglot import exp

from asql.errors import ASQLCompilationError


def apply_pivot_group_by(stmt: exp.Expr) -> exp.Expr:
    """Fold a trailing GROUP BY on a pivoted source into the pivot's source."""
    for select in list(stmt.find_all(exp.Select)):
        group = select.args.get("group")
        from_ = select.args.get("from_")
        if group is None or from_ is None or not isinstance(from_.this, exp.Table):
            continue
        table = from_.this
        pivots = table.args.get("pivots") or []
        if not pivots or any(p.args.get("unpivot") for p in pivots):
            continue

        keys = group.expressions
        if not all(isinstance(k, exp.Column) for k in keys):
            raise ASQLCompilationError(
                "pivot ... group by only accepts plain key columns; got "
                f"{', '.join(k.sql() for k in keys)}"
            )
        if [type(e) for e in select.expressions] != [exp.Star]:
            raise ASQLCompilationError(
                "pivot ... group by cannot be combined with an aggregate block or "
                "select list; the pivot's aggregate already defines the values"
            )

        needed: dict[str, exp.Column] = {}
        for column in keys:
            needed.setdefault(column.name, exp.column(column.name))
        for pivot in pivots:
            for node in [*pivot.expressions, *pivot.args.get("fields", [])]:
                for column in node.find_all(exp.Column):
                    needed.setdefault(column.name, exp.column(column.name))

        source = table.copy()
        source.set("pivots", None)
        inner = exp.select(*needed.values()).from_(source)
        table.replace(exp.Subquery(this=inner, pivots=[p.copy() for p in pivots]))
        select.set("group", None)
    return stmt
