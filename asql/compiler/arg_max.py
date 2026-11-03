"""Dialect spellings of ARG_MAX / ARG_MIN (`first(x order by k)` in an aggregate block)."""

from __future__ import annotations

from sqlglot import exp

from asql.errors import ASQLDialectError

# sqlglot spells these natively (ARG_MAX, MAX_BY, argMax, ...).
_NATIVE = frozenset(
    {
        "duckdb",
        "snowflake",
        "bigquery",
        "clickhouse",
        "spark",
        "databricks",
        "trino",
        "presto",
    }
)
# No native form, but an ordered ARRAY_AGG exists.
_ARRAY_AGG = frozenset({"postgres", "postgresql", "redshift"})


def transform_arg_max_min(stmt: exp.Expr, dialect: str) -> exp.Expr:
    name = dialect.lower()
    nodes = list(stmt.find_all(exp.ArgMax, exp.ArgMin))
    if not nodes or name in _NATIVE:
        return stmt
    if name not in _ARRAY_AGG:
        written = "arg_max" if isinstance(nodes[0], exp.ArgMax) else "arg_min"
        raise ASQLDialectError(
            f"{dialect} has no {written}(): `first(x order by k)` inside an aggregate "
            "block cannot be compiled for it. Use a window (`first(x order by k) "
            "over g`) or a correlated subquery instead."
        )
    for node in nodes:
        ordered = exp.Ordered(
            this=node.expression.copy(),
            desc=isinstance(node, exp.ArgMax),
            nulls_first=False,
        )
        agg = exp.ArrayAgg(this=exp.Order(this=node.this.copy(), expressions=[ordered]))
        # sqlglot indexes brackets from 0 and adds the dialect's base on output
        node.replace(
            exp.Bracket(this=exp.Paren(this=agg), expressions=[exp.Literal.number(0)])
        )
    return stmt
