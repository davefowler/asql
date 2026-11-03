"""`<window> over <col>` — ASQL shorthand for `over (partition by <col>)`.

    first(active order by period) over cohort as cohort_size
    running_sum(revenue) over cohort / cohort_size as ltv

sqlglot parses `over cohort` as a reference to a named window. When no
`WINDOW cohort AS (...)` clause in the same SELECT defines it, ASQL reads it
as the partition column, and pushes it into the windows the expression
already carries (`first(...)`'s ordering, `running_sum`'s frame) rather than
wrapping them. An explicit `over (...)` after `first(...)`/`last(...)` is
merged into that window the same way.
"""

from __future__ import annotations

from sqlglot import exp

from asql.errors import ASQLCompilationError
from asql.functions import CALL_META, OVER_META

_SPEC_KEYS = ("partition_by", "order", "spec", "first")


def _merge_into(target: exp.Window, outer: exp.Window, written: str) -> None:
    """Move `outer`'s window spec onto `target`; a clash is an error, not a guess."""
    for key in _SPEC_KEYS:
        value = outer.args.get(key)
        if value is None:
            continue
        if target.args.get(key) is not None:
            raise ASQLCompilationError(
                f"`{written}` sets {key.replace('_', ' ')} on a window that "
                "already has one; write a single `over (...)` with everything in it"
            )
        target.set(key, value)


def apply_over_shorthand(stmt: exp.Expr) -> exp.Expr:
    for window in list(stmt.find_all(exp.Window)):
        if window.parent is None:
            continue  # already replaced while handling an enclosing window
        inner = window.this
        if not isinstance(inner, exp.Expr):
            continue
        alias = window.args.get("alias")

        if alias is None:
            # `first(x order by y) over (partition by a)`: FIRST already is a
            # window, so the explicit spec belongs on it, not around it.
            if isinstance(inner, exp.Window):
                _merge_into(inner, window, "over (...)")
                window.replace(inner)
            continue

        select = window.find_ancestor(exp.Select)
        defined = {
            w.name for w in ((select.args.get("windows") or []) if select else [])
        }
        if alias.name in defined:
            continue  # a real named window
        if any(window.args.get(key) for key in _SPEC_KEYS):
            continue  # a WINDOW clause definition, not a reference

        written = f"over {alias.name}"
        shorthand = exp.Window(partition_by=[exp.column(alias.name)])
        targets = (
            [inner]
            if isinstance(inner, exp.Window)
            else [w for w in inner.find_all(exp.Window) if w is not inner]
        )
        if targets:
            # The expression already is (or wraps) a window: partition that one.
            for target in targets:
                _merge_into(target, shorthand.copy(), written)
            window.replace(inner)
            if CALL_META in inner.meta:
                inner.meta[OVER_META] = alias.name
        else:
            window.set("alias", None)
            window.set("partition_by", shorthand.args["partition_by"])
    return stmt
