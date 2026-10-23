"""Dialect-specific spellings of date extraction and timezones, and spine week alignment."""

from __future__ import annotations

import contextlib
import typing as t

from sqlglot import exp
from sqlglot.errors import OptimizeError
from sqlglot.optimizer.annotate_types import annotate_types
from sqlglot.optimizer.qualify_columns import qualify_columns

from asql.compiler.sqlglot_schema_adapter import to_sqlglot_schema
from asql.errors import ASQLDialectError
from asql.functions import ALIAS_FUNC_META, week_trunc

_CALENDAR_UNITS = frozenset({"MONTH", "QUARTER", "YEAR"})
# sqlglot's BigQuery types: TIMESTAMP is TIMESTAMPTZ, DATETIME is the naive TIMESTAMP.
_TIMESTAMP_TYPES = frozenset({exp.DType.TIMESTAMPTZ, exp.DType.TIMESTAMPLTZ})
_CALENDAR_SAFE_TYPES = frozenset(
    {exp.DType.DATE, exp.DType.DATETIME, exp.DType.TIMESTAMP}
)
_OPERAND_ID = "asql_calendar_interval_operand"


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


def transform_timezone_source(stmt: exp.Expr, dialect: str) -> exp.Expr:
    """MySQL's CONVERT_TZ needs the source zone; DATETIME values carry none, so UTC."""
    if dialect.lower() != "mysql":
        return stmt
    for node in stmt.find_all(exp.ConvertTimezone):
        if node.args.get("source_tz") is None:
            node.set("source_tz", exp.Literal.string("UTC"))
    return stmt


def _operand_type(node: exp.Expr) -> exp.DataType | None:
    """A truncation returns its argument's type; sqlglot leaves it untyped."""
    if isinstance(node, exp.ConvertTimezone):
        # BigQuery writes it as TIMESTAMP(DATETIME(ts, zone)).
        return exp.DataType.build("TIMESTAMPTZ")
    if node.type is not None and node.type.this != exp.DType.UNKNOWN:
        return node.type
    if isinstance(node, (exp.DateTrunc, exp.TimestampTrunc, exp.Paren)):
        return _operand_type(node.this)
    return None


def transform_bigquery_calendar_intervals(
    stmt: exp.Expr, dialect: str, schema: t.Any
) -> exp.Expr:
    """Route BigQuery TIMESTAMP ± MONTH/QUARTER/YEAR through DATETIME.

    BigQuery type-checks `ts - INTERVAL 1 MONTH` and then rejects it at run
    time; DATE and DATETIME accept it. The operand's type comes from a
    qualified copy, so the emitted SQL keeps the columns as written. An
    unknown type is an error: a DATE wrapped as a TIMESTAMP stops comparing
    with DATE columns.
    """
    if dialect.lower() != "bigquery":
        return stmt
    targets = [
        node
        for node in stmt.find_all(exp.Add, exp.Sub)
        if isinstance(node.expression, exp.Interval)
        and node.expression.text("unit").upper() in _CALENDAR_UNITS
    ]
    if not targets:
        return stmt

    for i, node in enumerate(targets):
        node.meta[_OPERAND_ID] = i
    typed = stmt.copy()
    for node in targets:
        del node.meta[_OPERAND_ID]
    sg_schema = to_sqlglot_schema(schema, dialect="bigquery")
    # Unresolvable columns stay UNKNOWN and raise below.
    with contextlib.suppress(OptimizeError):
        qualify_columns(typed, schema=sg_schema or {}, expand_stars=False)
    annotate_types(typed, schema=sg_schema, dialect="bigquery")
    operand_types = {
        node.meta[_OPERAND_ID]: _operand_type(node.this)
        for node in typed.find_all(exp.Add, exp.Sub)
        if _OPERAND_ID in node.meta
    }

    for i, node in enumerate(targets):
        dtype = operand_types[i]
        if dtype is not None and dtype.this in _CALENDAR_SAFE_TYPES:
            continue
        if dtype is None or dtype.this not in _TIMESTAMP_TYPES:
            raise ASQLDialectError(
                f"Can't compile month/year arithmetic on BigQuery for "
                f"`{node.this.sql('bigquery')}`: its type is unknown, and BigQuery "
                "handles TIMESTAMP and DATE differently. Declare the column's type "
                "in the schema, or cast it (`col::DATE`, `col::TIMESTAMP`)."
            )
        shifted = node.__class__(
            this=exp.func("DATETIME", node.this.copy()),
            expression=node.expression.copy(),
        )
        node.replace(exp.func("TIMESTAMP", shifted))
    return stmt


def retarget_spine_weeks(spine: exp.Expr, start: str) -> exp.Expr:
    """Make a generated spine's week truncation use `start`, matching the query side."""
    for node in list(spine.find_all(exp.DateTrunc, exp.TimestampTrunc)):
        unit = node.args["unit"]
        if isinstance(unit, exp.WeekStart) or unit.name.upper() == "WEEK":
            node.replace(week_trunc(node.this, start))
    return spine
