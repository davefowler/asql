"""Adapters between ASQL schema objects and SQLGlot's schema.

ASQL has historically carried schema information using `asql.schema.Schema`.
SQLGlot expects schemas as either:
  - a nested mapping (table/db/catalog -> column -> type), or
  - a `sqlglot.schema.Schema` instance (e.g. `MappingSchema`).

This module provides a small conversion layer so ASQL can use SQLGlot's
schema-aware optimizer tools (star expansion, qualification, etc.) without
rewriting all schema ingestion at once.
"""

from __future__ import annotations

import typing as t

from sqlglot.schema import MappingSchema, Schema as SQLGlotSchema


def to_sqlglot_schema(
    schema: t.Any,
    *,
    dialect: str | None = None,
) -> SQLGlotSchema | None:
    """Convert an ASQL schema (or mapping) to a SQLGlot Schema.

    - If `schema` is already a SQLGlot Schema, return it.
    - If `schema` is an ASQL `asql.schema.Schema`, convert its tables/columns.
    - If `schema` is a nested mapping, wrap it in a SQLGlot MappingSchema.

    Note: we intentionally do NOT attempt to attach relationship / FK metadata to SQLGlot's
    Schema object here. SQLGlot's schema API is currently table/column/type-focused, and
    ASQL's relationship graph remains separate for now.
    """
    if not schema:
        return None

    if isinstance(schema, SQLGlotSchema):
        return schema

    # Mapping-like schemas (already in SQLGlot shape)
    if isinstance(schema, dict):
        mapping_schema = MappingSchema(schema=schema, dialect=dialect)
        return mapping_schema

    # ASQL schema object
    tables = getattr(schema, "tables", None)
    if isinstance(tables, dict):
        mapping: dict[str, dict[str, str | None]] = {}
        for table_name, table in tables.items():
            cols = getattr(table, "columns", None)
            if isinstance(cols, dict):
                # Best-effort: use known types if available, otherwise None.
                mapping[table_name] = {
                    col_name: getattr(col, "type", None) for col_name, col in cols.items()
                }

        return MappingSchema(schema=mapping, dialect=dialect)

    return None


