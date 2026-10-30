"""Show semantic-graph metrics and attributes in ``information_schema.columns``.

A query over ``information_schema.columns`` is rewritten to read a derived table:
the warehouse's rows (a portable subset of columns) UNION ALL one row per metric
and per reachable ``relationship.attribute`` of each graph model. The virtual rows
join ``information_schema.tables``, so they inherit the warehouse's catalog, schema
and identifier casing and only exist for models that exist as tables. The query's
own WHERE, GROUP BY, ORDER BY and LIMIT then apply to both kinds of row.

Metrics report ``data_type = 'METRIC'``: what matters to a reader is that the
name is an aggregate for a group-by block, not its numeric type. An attribute
reports its column's declared type when it is a bare column, else ``UNKNOWN``.
"""

from __future__ import annotations

import typing as t

from sqlglot import exp

from asql.semantic import SemanticGraph

if t.TYPE_CHECKING:
    from asql.config import CompileSettings

# Present with these names in DuckDB, Postgres, Redshift, Snowflake, BigQuery
# and MySQL, so the derived table keeps the same shape on every dialect.
PORTABLE_COLUMNS = (
    "table_catalog",
    "table_schema",
    "table_name",
    "column_name",
    "ordinal_position",
    "column_default",
    "is_nullable",
    "data_type",
)


def expand_information_schema(ast: exp.Expr, settings: CompileSettings) -> exp.Expr:
    graph = settings.schema.graph if settings.schema else None
    if graph is None:
        return ast
    rows: list[tuple[str, str, str]] | None = None
    for table in list(ast.find_all(exp.Table)):
        if table.db.lower() != "information_schema" or table.name.lower() != "columns":
            continue
        if rows is None:
            rows = virtual_columns(graph)
        table.replace(_columns_subquery(table, rows))
    return ast


def virtual_columns(graph: SemanticGraph) -> list[tuple[str, str, str]]:
    """``(model, column_name, data_type)`` for every metric and every attribute a
    model reaches through its relationships, named as a query writes them."""
    rows = [(metric.model, metric.name, "METRIC") for metric in graph.metrics.values()]
    for model in graph.models.values():
        for rel in model.relationships.values():
            for target in graph.models.values():
                grain = target.single_grain()
                if (
                    target is model
                    or grain is None
                    or grain.entity != rel.entity
                    or not isinstance(grain.key, dict)
                ):
                    continue
                for attr, expression in grain.attributes.items():
                    dtype = (
                        target.schema[expression.name.lower()]
                        if isinstance(expression, exp.Column)
                        else "UNKNOWN"
                    )
                    rows.append((model.name, f"{rel.name}.{attr}", dtype))
    return rows


def _columns_subquery(
    table: exp.Table, rows: list[tuple[str, str, str]]
) -> exp.Subquery:
    real = exp.select(*PORTABLE_COLUMNS).from_(
        exp.Table(
            this=table.this.copy(),
            db=table.args.get("db"),
            catalog=table.args.get("catalog"),
        )
    )
    tables = exp.Table(
        this=exp.to_identifier("TABLES" if table.name.isupper() else "tables"),
        db=table.args.get("db"),
        catalog=table.args.get("catalog"),
        alias=exp.TableAlias(this=exp.to_identifier("t")),
    )
    values = exp.values(rows, alias="v", columns=["model", "column_name", "data_type"])
    virtual = (
        exp.select(
            "t.table_catalog",
            "t.table_schema",
            "t.table_name",
            "v.column_name",
            exp.cast(exp.null(), "INT").as_("ordinal_position"),
            exp.cast(exp.null(), "VARCHAR").as_("column_default"),
            exp.Literal.string("YES").as_("is_nullable"),
            "v.data_type",
        )
        .from_(tables)
        .join(values, on="LOWER(t.table_name) = v.model", join_type="INNER")
    )
    return exp.Subquery(
        this=exp.union(real, virtual, distinct=False),
        alias=exp.TableAlias(this=exp.to_identifier(table.alias or table.name)),
    )
