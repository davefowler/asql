"""Compiler transforms for ASQL column operators (except/rename/replace).

These operators parse into BigQuery/Snowflake-style star modifiers like:
    SELECT * EXCEPT(col), expr AS col

Some dialects do not support this syntax. When a schema is provided, we can
expand `*` into an explicit column list instead (Issue #80).
"""

from __future__ import annotations

from sqlglot import exp
from sqlglot.optimizer.qualify_columns import qualify_columns

from asql.config import CompileSettings
from asql.dialect_features import supports_column_exclude
from asql.errors import ASQLDialectError
from asql.compiler.sqlglot_schema_adapter import to_sqlglot_schema


def transform_column_operators_for_dialect(
    stmt: exp.Expression,
    dialect: str | None,
    settings: CompileSettings,
) -> exp.Expression:
    """Rewrite star column operators into explicit columns for unsupported dialects.

    This uses SQLGlot's schema-aware star expansion (`qualify_columns(..., expand_stars=True)`),
    which already understands `Star(except_=...)`.
    """
    if not dialect or supports_column_exclude(dialect):
        return stmt

    schema = settings.schema
    if not schema:
        # Dialect doesn't support column exclude and no schema: parser/validator should have raised,
        # but be defensive if we encounter star-exclude in the AST anyway.
        for node in stmt.walk():
            if isinstance(node, exp.Star):
                if node.args.get("except_") or node.args.get("except"):
                    raise ASQLDialectError(
                        "Column operators ('except', 'rename', 'replace') require a schema for this dialect."
                    )
        return stmt

    sqlglot_schema = to_sqlglot_schema(schema, dialect=dialect)
    if not sqlglot_schema:
        return stmt

    # NOTE: qualify_columns also performs column qualification; we allow partial qualification
    # to reduce the amount of rewriting. We only rely on the star expansion behavior here.
    return qualify_columns(
        stmt,
        schema=sqlglot_schema,
        expand_alias_refs=False,
        expand_stars=True,
        allow_partial_qualification=True,
        dialect=dialect,
    )


