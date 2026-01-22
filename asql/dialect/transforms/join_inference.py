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
from typing import TYPE_CHECKING, Optional

import inflect

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
    schema: Optional["Schema"] = None,
    hint_column: Optional[str] = None,
) -> Optional[JoinCondition]:
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
        condition = _resolve_from_relationships(left_table, right_table, schema, hint_column)
        if condition:
            return condition
        
        # 2. Try column/PK detection (if hint provided)
        if hint_column:
            condition = _resolve_from_columns(left_table, right_table, schema, hint_column)
            if condition:
                return condition
    
    # 3. Convention-based guessing
    return _resolve_from_convention(left_table, right_table, hint_column)


def _resolve_from_relationships(
    left: str,
    right: str,
    schema: "Schema",
    hint_column: Optional[str] = None,
) -> Optional[JoinCondition]:
    """Try to resolve from schema relationships."""
    # Try left → right direction
    rel = schema.find_relationship(left, right)
    if rel:
        # If hint provided, verify it matches
        if hint_column and rel.from_column != hint_column:
            pass  # Don't use this relationship if hint doesn't match
        else:
            return JoinCondition(
                left_table=rel.from_table,
                left_column=rel.from_column,
                right_table=rel.to_table,
                right_column=rel.to_column,
                source="explicit" if rel.source == "explicit" else "inferred",
            )
    
    # Try right → left direction
    rel = schema.find_relationship(right, left)
    if rel:
        if hint_column and rel.from_column != hint_column:
            pass
        else:
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
    schema: "Schema",
    hint_column: str,
) -> Optional[JoinCondition]:
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
    hint_column: Optional[str] = None,
) -> Optional[JoinCondition]:
    """Fall back to convention-based guessing."""
    if hint_column:
        # Hint provided: assume it's on left table, PK is 'id' on right
        return JoinCondition(
            left_table=left,
            left_column=hint_column,
            right_table=right,
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
    result = _inflect_engine.singular_noun(name.lower())
    return result if result else name.lower()

