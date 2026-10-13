"""Dialect-specific spellings of date extraction, and spine week alignment."""

from __future__ import annotations

from sqlglot import exp

from asql.functions import ALIAS_FUNC_META, week_trunc


def week_start_of(trunc: exp.Expr) -> str | None:
    """Start day (`monday`/`sunday`) of a node built by a week function, else None."""
    if isinstance(trunc, exp.Paren) and ALIAS_FUNC_META in trunc.meta:
        return "sunday"
    unit = trunc.args.get("unit")
    return unit.name.lower() if isinstance(unit, exp.WeekStart) else None


def transform_day_of_year(stmt: exp.Expr, dialect: str) -> exp.Expr:
    """BigQuery spells day-of-year DAYOFYEAR; sqlglot passes DOY through."""
    if dialect.lower() != "bigquery":
        return stmt

    def _rewrite(node: exp.Expr) -> exp.Expr:
        if isinstance(node, exp.Extract) and node.name.upper() == "DOY":
            return exp.Extract(this=exp.var("DAYOFYEAR"), expression=node.expression)
        return node

    return stmt.transform(_rewrite)


def retarget_spine_weeks(spine: exp.Expr, start: str) -> exp.Expr:
    """Make a generated spine's week truncation use `start`, matching the query side."""
    for node in list(spine.find_all(exp.DateTrunc, exp.TimestampTrunc)):
        unit = node.args["unit"]
        if isinstance(unit, exp.WeekStart) or unit.name.upper() == "WEEK":
            node.replace(week_trunc(node.this, start))
    return spine
