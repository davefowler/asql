"""AST transform to rewrite EXPLODE joins for dialect-specific SQL."""

from __future__ import annotations

import typing as t

import sqlglot
from sqlglot import exp


def transform_explode_for_dialect(
    stmt: exp.Expression,
    dialect: t.Optional[str] = None,
) -> exp.Expression:
    """Rewrite CROSS JOIN UNNEST(...) for dialects that don't support it (e.g. Snowflake)."""
    dialect_lower = (dialect or "").lower()
    if dialect_lower != "snowflake":
        return stmt

    # Snowflake: rewrite `CROSS JOIN UNNEST(x) AS a` into:
    # `CROSS JOIN (SELECT value AS a FROM TABLE(FLATTEN(INPUT => x))) AS _a_exploded`
    #
    # We use SQLGlot's Snowflake parser for the target subquery shape and then splice in the
    # original array expression to avoid hand-building Snowflake-specific nodes.
    for join in stmt.find_all(exp.Join):
        unnest = join.this
        if not isinstance(unnest, exp.Unnest):
            continue

        expressions = list(unnest.expressions)
        if not expressions:
            continue

        array_expr = expressions[0]

        table_alias = unnest.args.get("alias")
        alias_ident = table_alias.this if isinstance(table_alias, exp.TableAlias) else None
        alias = alias_ident.this if isinstance(alias_ident, exp.Identifier) else None
        if not alias:
            continue

        # Template: CROSS JOIN (SELECT value AS __alias__ FROM TABLE(FLATTEN(INPUT => __array__))) AS __sub__
        template = sqlglot.parse_one(
            "SELECT * FROM t CROSS JOIN (SELECT value AS __alias__ FROM TABLE(FLATTEN(INPUT => __array__))) AS __sub__",
            dialect="snowflake",
        )
        joins = template.args.get("joins")
        if not joins:
            continue
        template_join = joins[0]
        subquery = template_join.this
        if not isinstance(subquery, exp.Subquery):
            continue

        # Set the column alias in the inner SELECT
        inner_select = subquery.this
        if isinstance(inner_select, exp.Select) and inner_select.expressions:
            first_expr = inner_select.expressions[0]
            if isinstance(first_expr, exp.Alias):
                first_expr.set("alias", exp.to_identifier(alias))

        # Splice array expression into the FLATTEN/EXPLODE kwarg
        kwarg = subquery.find(exp.Kwarg)
        if isinstance(kwarg, exp.Kwarg):
            kwarg.set("expression", array_expr.copy())

        # Set the subquery alias
        subquery.set("alias", exp.TableAlias(this=exp.to_identifier(f"_{alias}_exploded")))

        # Replace join target
        join.set("this", subquery)

    return stmt


