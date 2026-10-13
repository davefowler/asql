"""Shared join key inference logic.

This module provides a unified approach to resolving join conditions:
1. Schema relationships (explicit from config)
2. Schema relationships (inferred from naming conventions)
3. Column/PK detection (which table has the column)
4. Convention-based guessing ({table}_id pattern)

Used by:
- join_fk_shorthand.py - Expanding `ON user_id` to full condition
- (future) auto-join - When no ON clause is provided
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

import inflect

from asql.errors import ASQLResolutionError

if TYPE_CHECKING:
    from asql.schema import Schema

# Module-level cached inflect engine for performance
_inflect_engine = inflect.engine()


@dataclass
class JoinCondition:
    """Resolved join condition."""

    left_table: str
    left_column: str
    right_table: str
    right_column: str
    source: str  # "explicit", "inferred", "column_detection", "convention"

    def as_sql(self) -> str:
        """Return SQL-style condition string."""
        return f"{self.left_table}.{self.left_column} = {self.right_table}.{self.right_column}"


def resolve_join_condition(
    left_table: str,
    right_table: str,
    schema: Schema | None = None,
    hint_column: str | None = None,
) -> JoinCondition | None:
    """Resolve join condition between two tables.

    Resolution order:
    1. Schema relationships (explicit, then inferred)
    2. Column/PK detection (if hint_column provided)
    3. Convention-based guessing ({table}_id pattern)

    Args:
        left_table: Name of left table (FROM table)
        right_table: Name of right table (JOIN table)
        schema: Optional schema with relationships and column info
        hint_column: Optional column name hint (e.g., from `ON user_id`)

    Returns:
        JoinCondition if resolved, None if cannot determine
    """
    # NOTE: This uses ASQL's schema (`asql.schema.Schema`) because SQLGlot's `Schema` currently
    # models tables/columns/types but does not have a first-class FK/relationship graph API.
    # We track upstream work to add relationship metadata to SQLGlot Schema in:
    #   davefowler/sqlglot#2
    # 1. Try schema relationships first
    if schema:
        condition = _resolve_from_relationships(
            left_table, right_table, schema, hint_column
        )
        if condition:
            return condition

        # 2. Try column/PK detection (if hint provided)
        if hint_column:
            condition = _resolve_from_columns(
                left_table, right_table, schema, hint_column
            )
            if condition:
                return condition

    # 3. Convention-based guessing
    return _resolve_from_convention(left_table, right_table, hint_column)


def _resolve_from_relationships(
    left: str,
    right: str,
    schema: Schema,
    hint_column: str | None = None,
) -> JoinCondition | None:
    """Try to resolve from schema relationships (explicit before inferred).

    Several distinct explicit relationships between the same tables (e.g. buyer and
    seller both pointing at users) are ambiguous without a hint, so they raise.
    """
    for from_table, to_table in ((left, right), (right, left)):
        rels = schema.find_all_relationships(from_table, to_table)
        if hint_column:
            rels = [rel for rel in rels if rel.from_column == hint_column]
        explicit = [rel for rel in rels if rel.source == "explicit"]
        distinct_pairs = {(rel.from_column, rel.to_column) for rel in explicit}
        if len(distinct_pairs) > 1:
            names = ", ".join(
                sorted({rel.alias or rel.from_column for rel in explicit})
            )
            raise ASQLResolutionError(
                f'Tables "{from_table}" and "{to_table}" are related several ways '
                f"({names}); write the join condition with on."
            )
        rel = explicit[0] if explicit else (rels[0] if rels else None)
        if rel:
            return JoinCondition(
                left_table=rel.from_table,
                left_column=rel.from_column,
                right_table=rel.to_table,
                right_column=rel.to_column,
                source="explicit" if rel.source == "explicit" else "inferred",
            )

    return None


def _resolve_from_columns(
    left: str,
    right: str,
    schema: Schema,
    hint_column: str,
) -> JoinCondition | None:
    """Try to resolve from column/PK detection."""
    left_tbl = schema.get_table(left)
    right_tbl = schema.get_table(right)

    if not left_tbl and not right_tbl:
        return None

    left_has_col = left_tbl and left_tbl.has_column(hint_column)
    right_has_col = right_tbl and right_tbl.has_column(hint_column)
    left_pk = left_tbl.get_primary_key() if left_tbl else None
    right_pk = right_tbl.get_primary_key() if right_tbl else None

    # If hint column IS the PK of one table, it's the target
    if hint_column == right_pk:
        return JoinCondition(
            left_table=left,
            left_column=hint_column,
            right_table=right,
            right_column=hint_column,
            source="column_detection",
        )
    elif hint_column == left_pk:
        return JoinCondition(
            left_table=right,
            left_column=hint_column,
            right_table=left,
            right_column=hint_column,
            source="column_detection",
        )

    # FK column only exists in one table
    if left_has_col and not right_has_col:
        return JoinCondition(
            left_table=left,
            left_column=hint_column,
            right_table=right,
            right_column=right_pk or "id",
            source="column_detection",
        )
    elif right_has_col and not left_has_col:
        return JoinCondition(
            left_table=right,
            left_column=hint_column,
            right_table=left,
            right_column=left_pk or "id",
            source="column_detection",
        )

    return None


def _resolve_from_convention(
    left: str,
    right: str,
    hint_column: str | None = None,
) -> JoinCondition | None:
    """Fall back to convention-based guessing."""
    if hint_column:
        # The table whose singular name is the column's prefix is the target:
        # `user_id` joins to `users.id`, wherever the column lives.
        prefix = hint_column.removesuffix("_id")
        right_is_target = _singularize(right) == prefix
        left_is_target = _singularize(left) == prefix
        if right_is_target == left_is_target:
            return None
        target, source = (right, left) if right_is_target else (left, right)
        return JoinCondition(
            left_table=source,
            left_column=hint_column,
            right_table=target,
            right_column="id",
            source="convention",
        )

    # No hint: try to guess FK from table names
    # Convention: {singular_right}_id on left table
    right_singular = _singularize(right)
    guessed_fk = f"{right_singular}_id"

    return JoinCondition(
        left_table=left,
        left_column=guessed_fk,
        right_table=right,
        right_column="id",
        source="convention",
    )


@lru_cache(maxsize=256)
def _singularize(name: str) -> str:
    """Singularize table names using inflect library for accuracy.

    Uses module-level cached engine and lru_cache for performance.
    """
    result = _inflect_engine.singular_noun(
        name.lower()  # pyright: ignore[reportArgumentType] — inflect stubs declare Word, but str is accepted at runtime
    )
    return result if result else name.lower()
