"""`<window> over <col>` — ASQL shorthand for `over (partition by <col>)`.

    first(active order by period) over cohort as cohort_size
    running_sum(revenue) over cohort / cohort_size as ltv

sqlglot parses `over cohort` as a reference to a named window. When no
`WINDOW cohort AS (...)` clause defines it, ASQL reads it as the partition
column, and pushes it into the windows the expression already carries
(`first(...)`'s ordering, `running_sum`'s frame) rather than wrapping them.
"""

from __future__ import annotations

from sqlglot import exp

from asql.functions import CALL_META, OVER_META


def apply_over_shorthand(stmt: exp.Expr) -> exp.Expr:
    defined: set[str] = set()
    for select in stmt.find_all(exp.Select):
        for window in select.args.get("windows") or []:
            defined.add(window.name)  # WINDOW w AS (...): the name is `this`

    for window in list(stmt.find_all(exp.Window)):
        alias = window.args.get("alias")
        if alias is None or alias.name in defined:
            continue
        if any(
            window.args.get(key) for key in ("partition_by", "order", "spec", "first")
        ):
            continue  # a WINDOW clause definition, not a reference
        inner = window.this
        if not isinstance(inner, exp.Expr):
            continue
        partition = [exp.column(alias.name)]
        targets = (
            [inner]
            if isinstance(inner, exp.Window)
            else [w for w in inner.find_all(exp.Window) if w is not inner]
        )
        if targets:
            # The expression already is (or wraps) a window: partition that one.
            for target in targets:
                if not target.args.get("partition_by"):
                    target.set("partition_by", [c.copy() for c in partition])
            window.replace(inner)
            if CALL_META in inner.meta:
                inner.meta[OVER_META] = alias.name
        else:
            window.set("alias", None)
            window.set("partition_by", partition)
    return stmt
