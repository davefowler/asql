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
_TYPED_ID = "asql_typed_node"


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


def _types_on_copy(
    stmt: exp.Expr, nodes: list[exp.Expr], schema: t.Any
) -> list[exp.DataType | None]:
    """BigQuery types of `nodes`, read from a column-qualified copy of `stmt`.

    Qualifying the copy lets sqlglot type bare columns while the emitted SQL
    keeps them as written.
    """
    for i, node in enumerate(nodes):
        node.meta[_TYPED_ID] = i
    typed = stmt.copy()
    for node in nodes:
        del node.meta[_TYPED_ID]
    sg_schema = to_sqlglot_schema(schema, dialect="bigquery")
    # Unresolvable columns stay UNKNOWN.
    with contextlib.suppress(OptimizeError):
        qualify_columns(typed, schema=sg_schema or {}, expand_stars=False)
    annotate_types(typed, schema=sg_schema, dialect="bigquery")
    found = {
        node.meta[_TYPED_ID]: _operand_type(node)
        for node in typed.walk()
        if _TYPED_ID in node.meta
    }
    return [found[i] for i in range(len(nodes))]


def _is_relative_date(node: exp.Expr) -> bool:
    """`now()`, `N units ago` or `N units from now`, as the parser builds them."""
    if isinstance(node, exp.Paren):
        return _is_relative_date(node.this)
    if isinstance(node, (exp.Add, exp.Sub)):
        return isinstance(node.expression, exp.Interval) and _is_relative_date(
            node.this
        )
    return isinstance(node, exp.CurrentTimestamp)


def transform_bigquery_relative_date_comparisons(
    stmt: exp.Expr, dialect: str, schema: t.Any
) -> exp.Expr:
    """Count a relative date from today when BigQuery compares it with a DATE.

    `7 days ago` is a TIMESTAMP and BigQuery has no `DATE >= TIMESTAMP` or
    `DATETIME >= TIMESTAMP`, so against a DATE it counts from CURRENT_DATE and
    against a DATETIME from CURRENT_DATETIME(). Only relative dates move;
    comparing a DATE with another TIMESTAMP is left for BigQuery to reject.
    """
    if dialect.lower() != "bigquery":
        return stmt
    pairs: list[tuple[exp.Expr, exp.Expr]] = []
    for cmp in stmt.find_all(exp.GT, exp.GTE, exp.LT, exp.LTE, exp.EQ, exp.NEQ):
        left, right = cmp.this, cmp.expression
        if _is_relative_date(left) and not _is_relative_date(right):
            pairs.append((left, right))
        elif _is_relative_date(right) and not _is_relative_date(left):
            pairs.append((right, left))
    for between in stmt.find_all(exp.Between):
        if not _is_relative_date(between.this):
            for bound in (between.args["low"], between.args["high"]):
                if _is_relative_date(bound):
                    pairs.append((bound, between.this))
    if not pairs:
        return stmt

    others = list({id(other): other for _, other in pairs}.values())
    types = dict(
        zip(
            (id(o) for o in others),
            _types_on_copy(stmt, others, schema),
            strict=True,
        )
    )
    for relative, other in pairs:
        dtype = types[id(other)]
        if dtype is None:
            continue
        today: type[exp.Expr]
        if dtype.this == exp.DType.DATE:
            today = exp.CurrentDate
        elif dtype.this in (exp.DType.DATETIME, exp.DType.TIMESTAMP):
            today = exp.CurrentDatetime
        else:
            continue
        for now in list(relative.find_all(exp.CurrentTimestamp)):
            now.replace(today())
    return stmt


def transform_bigquery_calendar_intervals(
    stmt: exp.Expr, dialect: str, schema: t.Any
) -> exp.Expr:
    """Route BigQuery TIMESTAMP ± MONTH/QUARTER/YEAR through DATETIME.

    BigQuery type-checks `ts - INTERVAL 1 MONTH` and then rejects it at run
    time; DATE and DATETIME accept it. An unknown type is an error: a DATE
    wrapped as a TIMESTAMP stops comparing with DATE columns.
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

    operand_types = _types_on_copy(stmt, [node.this for node in targets], schema)
    for node, dtype in zip(targets, operand_types, strict=True):
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
