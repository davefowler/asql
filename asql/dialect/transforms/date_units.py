"""Parser-stage handling of the truncating unit functions (`month(x)`, `week(x)`, ...)."""

from __future__ import annotations

from sqlglot import exp

from asql.errors import ASQLCompilationError
from asql.functions import ALIAS_FUNC_META, unit_function_arg, week_trunc

_COMPARISONS = (exp.EQ, exp.NEQ, exp.LT, exp.GT, exp.LTE, exp.GTE)


def fill_default_week_start(stmt: exp.Expr, week_start: str) -> exp.Expr:
    """Resolve every bare `week(x)` to the `week_start` setting's start day."""
    for node in list(stmt.find_all(exp.DateTrunc)):
        unit = node.args["unit"]
        if isinstance(unit, exp.WeekStart) and unit.this is None:
            resolved = week_trunc(node.this, week_start)
            resolved.meta.update(node.meta)
            if node is stmt:
                stmt = resolved
            else:
                node.replace(resolved)
    return stmt


def _written_unit_function(node: exp.Expr) -> str | None:
    """The ASQL unit function (`month`) that built `node`, if it was written in ASQL."""
    name = node.meta.get(ALIAS_FUNC_META)
    return str(name).split("_")[0] if name else None


def _is_number(node: exp.Expr | None) -> bool:
    if isinstance(node, exp.Neg):
        node = node.this
    return isinstance(node, exp.Literal) and node.is_number


def reject_numeric_comparisons(stmt: exp.Expr) -> exp.Expr:
    """Raise when a truncating unit function is compared with a number.

    `year(created_at) = 2024` compares a date to an integer and never matches
    (or fails to run); the number-valued spelling is `extract(year from col)`.
    """
    for node in stmt.walk():
        if isinstance(node, _COMPARISONS):
            pairs = [(node.left, node.right), (node.right, node.left)]
        elif isinstance(node, exp.In):
            pairs = [(node.this, value) for value in node.expressions]
        elif isinstance(node, exp.Between):
            pairs = [(node.this, node.args["low"]), (node.this, node.args["high"])]
        else:
            continue
        for call, other in pairs:
            unit = _written_unit_function(call)
            if unit and _is_number(other):
                col = unit_function_arg(call).sql()
                raise ASQLCompilationError(
                    f"{unit}({col}) truncates to the start of the {unit} (a date), "
                    f"so it cannot be compared with the number {other.sql()}. "
                    f"Use extract({unit} from {col}) for the {unit} number, or "
                    f"compare {col} against a date range."
                )
    return stmt
