"""ASQL AST rewrites for underscore-based shorthand identifiers.

This is the first step toward moving schema-aware shorthand expansion out of the regex preparser.
"""

from __future__ import annotations

import re
import typing as t

from sqlglot import exp

from asql.config import CompileSettings
from asql.functions import ASQL_FUNCTION_REGISTRY, NATURAL_AGG_FUNCS


_SINCE_UNTIL_PATTERN = re.compile(
    r"^(?P<unit>day|days|week|weeks|month|months|year|years|hour|hours|minute|minutes|second|seconds)_(?P<dir>since|until)_(?P<col>[a-zA-Z_][a-zA-Z0-9_]*)$",
    re.IGNORECASE,
)

_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _single_from_table_name(stmt: exp.Expression) -> str | None:
    """Return the single FROM table name if the query is a simple single-table query."""
    query = stmt.find(exp.Query)
    if not isinstance(query, exp.Query):
        return None

    # If there are joins, table ownership becomes ambiguous (skip schema-aware logic).
    if query.find(exp.Join):
        return None

    tables = list(query.find_all(exp.Table))
    if len(tables) != 1:
        return None

    return tables[0].name


def apply_since_until_underscore_shorthands(
    stmt: exp.Expression,
    settings: CompileSettings,
) -> exp.Expression:
    """Expand unit_since_col / unit_until_col shorthands into DateDiff expressions.

    Behavior:
    - If no schema is present: expand unconditionally (matches historical preparser behavior).
    - If schema is present and query is single-table:
        - If the full identifier exists as a column: do NOT expand.
        - Else if the base column exists: expand.
        - Else: do NOT expand (unknown column).
    - If schema is present but query is multi-table/ambiguous: do NOT expand.
    """
    schema = settings.schema
    from_table = _single_from_table_name(stmt) if schema else None

    def _rewrite(node: exp.Expression) -> exp.Expression:
        if not isinstance(node, exp.Column):
            return node

        # Only handle unqualified identifiers: days_since_created_at
        if node.table:
            return node

        name = node.name
        if not name:
            return node

        match = _SINCE_UNTIL_PATTERN.match(name)
        if not match:
            return node

        unit = match.group("unit").upper()
        direction = match.group("dir").upper()
        col_name = match.group("col")

        func_name = f"{unit}_{direction}"
        builder = ASQL_FUNCTION_REGISTRY.get(func_name)
        if not builder:
            return node

        if schema:
            if not from_table:
                # With schema but ambiguous ownership, be conservative.
                return node

            table = schema.get_table(from_table)
            if not table:
                return node

            # If the full identifier exists as a real column, leave it alone.
            if table.has_column(name):
                return node

            # Only expand if the base column exists.
            if not table.has_column(col_name):
                return node

        col_expr = exp.Column(this=exp.to_identifier(col_name))
        return t.cast(exp.Expression, builder([col_expr]))

    return stmt.transform(_rewrite, copy=False)


def apply_implicit_function_aliases(
    stmt: exp.Expression,
    settings: CompileSettings,
) -> exp.Expression:
    """Expand `func_col` shorthand projections into `FUNC(col) AS func_col`.

    This is the compiler/AST equivalent of the legacy preparser transform
    `_transform_implicit_function_aliases`.

    Behavior:
    - Only rewrites unqualified projection columns in SELECT lists.
    - If no schema is present: expand unconditionally (matches historical behavior).
    - If schema is present and query is single-table:
        - If the full identifier exists as a column: do NOT expand.
        - Else if the base column exists: expand.
        - Else: do NOT expand.
    - If schema is present but query is multi-table/ambiguous: do NOT expand.
    """
    schema = settings.schema
    from_table = _single_from_table_name(stmt) if schema else None

    prefixes: list[str] = sorted(NATURAL_AGG_FUNCS.keys(), key=len, reverse=True)

    def _rewrite_projection(expr: exp.Expression) -> exp.Expression:
        if not isinstance(expr, exp.Column):
            return expr

        if expr.table:
            return expr

        name = expr.name
        if not name or "_" not in name:
            return expr

        if schema:
            if not from_table:
                return expr

            table = schema.get_table(from_table)
            if not table:
                return expr

            if table.has_column(name):
                return expr

        parts = name.split("_")
        if len(parts) < 2:
            return expr

        for prefix in prefixes:
            prefix_parts = prefix.lower().split("_")
            if parts[: len(prefix_parts)] != prefix_parts:
                continue

            col_name = "_".join(parts[len(prefix_parts) :])
            if not col_name or not _IDENTIFIER_PATTERN.match(col_name):
                continue

            if schema:
                table = schema.get_table(from_table) if from_table else None
                if not table or not table.has_column(col_name):
                    continue

            builder = NATURAL_AGG_FUNCS.get(prefix)
            if not builder:
                continue

            col_expr = exp.Column(this=exp.to_identifier(col_name))
            built = builder([col_expr])
            if not built:
                continue

            return exp.Alias(this=t.cast(exp.Expression, built), alias=exp.to_identifier(name))

        return expr

    def _rewrite_select(node: exp.Expression) -> exp.Expression:
        if not isinstance(node, exp.Select):
            return node

        node.set("expressions", [_rewrite_projection(e) for e in node.expressions])
        return node

    return stmt.transform(_rewrite_select, copy=False)


