"""Shared join inference utilities for ASQL preparsing.

This module consolidates join key inference logic used by both:
- cohort.py: cohort by clause join key inference
- joins.py: auto-join condition inference

The goal is to ensure consistent behavior across all ASQL features.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from asql.schema import Schema


def infer_fk_column(table_name: str) -> str:
    """
    Infer the foreign key column name for a table using naming conventions.
    
    Convention: {singular_table_name}_id
    
    Examples:
        users -> user_id
        customers -> customer_id
        order -> order_id
        people -> people_id (irregular plural not handled)
    
    Args:
        table_name: The table name to singularize
        
    Returns:
        The conventional foreign key column name (e.g., 'user_id')
    """
    # Simple singularization: strip trailing 's' if present
    # Note: This doesn't handle irregular plurals (people, children, etc.)
    singular = table_name.rstrip('s') if table_name.endswith('s') else table_name
    return f"{singular}_id"


def infer_join_key_from_schema(
    from_table: str,
    to_table: str,
    schema: Optional["Schema"],
) -> Optional[str]:
    """
    Look up join key from schema relationships.
    
    Tries both directions:
    1. from_table -> to_table relationship
    2. to_table -> from_table relationship (reverse)
    
    Args:
        from_table: The source/activity table
        to_table: The target/cohort table
        schema: Optional schema with relationship definitions
        
    Returns:
        The foreign key column name, or None if not found in schema
    """
    if not schema:
        return None
    
    # Try from_table -> to_table
    rel = schema.find_relationship(from_table, to_table)
    if rel:
        return rel.from_column
    
    # Try reverse: to_table -> from_table
    rel = schema.find_relationship(to_table, from_table)
    if rel:
        return rel.to_column
    
    return None
