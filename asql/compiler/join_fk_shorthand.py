"""Join condition inference and FK shorthand expansion.

Handles two cases:
1. FK shorthand: `ON user_id` → `ON orders.user_id = users.id`
2. Auto-join: No ON clause → infer from schema relationships or convention
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from sqlglot import exp

from asql.compiler.join_inference import resolve_join_condition

if TYPE_CHECKING:
    from asql.config import CompileSettings


def transform_fk_shorthand(stmt: exp.Expression, settings: "CompileSettings | None" = None) -> exp.Expression:
    """Expand FK shorthand and auto-infer missing join conditions.
    
    FK shorthand: `ON user_id` → `ON orders.user_id = users.id`
    Auto-join: No ON clause → infer from schema or convention (if infer_join_keys=True)
    """
    if not isinstance(stmt, exp.Select):
        return stmt
    
    from_clause = stmt.find(exp.From)
    if not from_clause or not isinstance(from_clause.this, exp.Table):
        return stmt
    
    left_table = from_clause.this.alias or from_clause.this.name
    # NOTE: Join inference depends on relationship/PK information. Today we take this from ASQL's schema
    # object (`asql.schema.Schema`) because SQLGlot's Schema is table/column/type-focused and does not
    # currently expose FK relationships as a first-class API.
    schema = settings.schema if settings else None
    infer_join_keys = settings.infer_join_keys if settings else False
    
    for join in stmt.find_all(exp.Join):
        # Skip CROSS joins - they don't need ON conditions
        if join.kind and "CROSS" in join.kind.upper():
            continue
            
        right_table = join.this.alias or join.this.name if isinstance(join.this, exp.Table) else None
        if not right_table:
            continue
        
        on_cond = join.args.get("on")
        
        if isinstance(on_cond, exp.Column):
            # Case 1: FK shorthand - single column like `ON user_id`
            _expand_fk_shorthand(join, on_cond.name, left_table, right_table, schema)
            
        elif on_cond is None:
            # Case 2: No ON clause - try to auto-infer
            _auto_infer_join_condition(join, left_table, right_table, schema, infer_join_keys)
        
        # Update left_table for chained joins
        left_table = right_table
    
    return stmt


def _expand_fk_shorthand(join: exp.Join, fk_col: str, left: str, right: str, schema) -> None:
    """Expand FK shorthand: `ON user_id` → `ON orders.user_id = users.id`"""
    condition = resolve_join_condition(left, right, schema, hint_column=fk_col)
    
    if condition:
        join.set("on", exp.EQ(
            this=exp.column(condition.left_column, condition.left_table),
            expression=exp.column(condition.right_column, condition.right_table)
        ))


def _auto_infer_join_condition(join: exp.Join, left: str, right: str, schema, infer_join_keys: bool) -> None:
    """Auto-infer join condition when no ON clause provided.
    
    Only works if:
    - Schema has a relationship between the tables, OR
    - infer_join_keys=True (uses convention-based guessing)
    """
    # If we have schema, always try to find a relationship
    if schema:
        condition = resolve_join_condition(left, right, schema, hint_column=None)
        if condition and condition.source in ("explicit", "inferred"):
            join.set("on", exp.EQ(
                this=exp.column(condition.left_column, condition.left_table),
                expression=exp.column(condition.right_column, condition.right_table)
            ))
            return
    
    # Without schema relationship, only invent if setting is enabled
    if infer_join_keys:
        condition = resolve_join_condition(left, right, schema=None, hint_column=None)
        if condition:
            join.set("on", exp.EQ(
                this=exp.column(condition.left_column, condition.left_table),
                expression=exp.column(condition.right_column, condition.right_table)
            ))
