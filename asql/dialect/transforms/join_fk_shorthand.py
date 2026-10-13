"""Join condition inference and FK shorthand expansion.

Handles two cases:
1. FK shorthand: `ON user_id` → `ON orders.user_id = users.id`
2. Auto-join: No ON clause → infer from schema relationships or convention
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlglot import exp

from asql.dialect.transforms.join_inference import (
    JoinCondition,
    resolve_join_condition,
)
from asql.errors import ASQLResolutionError

if TYPE_CHECKING:
    from asql.config import CompileSettings
    from asql.schema import Schema


def transform_fk_shorthand(
    stmt: exp.Expr, settings: CompileSettings | None = None
) -> exp.Expr:
    """Expand FK shorthand and auto-infer missing join conditions.

    FK shorthand: `ON user_id` → `ON orders.user_id = users.id`
    Auto-join: No ON clause → infer from schema or convention (if infer_join_keys=True),
    else raise ASQLResolutionError
    """
    # NOTE: Join inference depends on relationship/PK information. Today we take this from ASQL's schema
    # object (`asql.schema.Schema`) because SQLGlot's Schema is table/column/type-focused and does not
    # currently expose FK relationships as a first-class API.
    schema = settings.schema if settings else None
    infer_join_keys = settings.infer_join_keys if settings else False

    # Each select (CTE, subquery, union branch) resolves only its own joins
    # against its own FROM.
    for select in stmt.find_all(exp.Select):
        _resolve_select_joins(select, schema, infer_join_keys)
    return stmt


def _resolve_select_joins(
    select: exp.Select, schema: Schema | None, infer_join_keys: bool
) -> None:
    from_clause = select.args.get("from_")
    if not from_clause or not isinstance(from_clause.this, (exp.Table, exp.Subquery)):
        return

    # An unaliased subquery has no name to qualify a condition with.
    left_table = from_clause.this.alias_or_name

    # A nested FROM-first query attaches its joins to the FROM table itself.
    joins = [
        *(from_clause.this.args.get("joins") or []),
        *(select.args.get("joins") or []),
    ]
    for join in joins:
        # CROSS joins need no ON condition.
        if join.kind and "CROSS" in join.kind.upper():
            continue
        on_cond = join.args.get("on")
        # Only ASQL joins carry a kind, so a plain SQL `JOIN`/comma join is passed
        # through unless it uses the `on <column>` shorthand (a bare column is not
        # a join condition in any dialect's SQL).
        if not join.kind and not isinstance(on_cond, exp.Column):
            continue

        right_table = (
            join.this.alias or join.this.name
            if isinstance(join.this, exp.Table)
            else None
        )
        if not right_table:
            continue

        if not left_table and (on_cond is None or isinstance(on_cond, exp.Column)):
            raise ASQLResolutionError(
                f"Cannot infer the join condition for '{right_table}': the FROM "
                "subquery has no alias. Alias it, e.g. "
                f"`from (from orders ...) as o & {right_table} on ...`, or write "
                "the full condition."
            )

        if isinstance(on_cond, exp.Column):
            # Case 1: FK shorthand - single column like `ON user_id`
            _expand_fk_shorthand(
                join, on_cond.name, left_table, right_table, schema, infer_join_keys
            )

        elif on_cond is None:
            # Case 2: No ON clause - try to auto-infer
            _auto_infer_join_condition(
                join, left_table, right_table, schema, infer_join_keys
            )

        # Update left_table for chained joins
        left_table = right_table


def _on_clause(condition: JoinCondition) -> exp.EQ:
    return exp.EQ(
        this=exp.column(condition.left_column, condition.left_table),
        expression=exp.column(condition.right_column, condition.right_table),
    )


def _expand_fk_shorthand(
    join: exp.Join,
    fk_col: str,
    left: str,
    right: str,
    schema: Schema | None,
    infer_join_keys: bool,
) -> None:
    """Expand FK shorthand: `ON user_id` → `ON orders.user_id = users.id`.

    Without a schema the column is only resolved by naming convention, which is
    opt-in via `infer_join_keys`.
    """
    condition = None
    if schema or infer_join_keys:
        condition = resolve_join_condition(left, right, schema, hint_column=fk_col)
    if condition is None:
        raise ASQLResolutionError(
            f"Cannot expand `on {fk_col}` to join '{left}' to '{right}': "
            "no schema relationship or column metadata identifies the key, and "
            "the column name does not match exactly one of the two tables. "
            f"Write the full condition, e.g. `on {left}.{fk_col} = {right}.id`, "
            "provide a schema, or enable `infer_join_keys` "
            "(`SET infer_join_keys = true`) to use the `{table}_id` naming convention."
        )
    join.set("on", _on_clause(condition))


def _auto_infer_join_condition(
    join: exp.Join,
    left: str,
    right: str,
    schema: Schema | None,
    infer_join_keys: bool,
) -> None:
    """Infer the join condition when no ON clause is provided.

    Resolution order: schema relationship (explicit, then inferred), then the
    `{table}_id` naming convention if `infer_join_keys` is on. Anything else is an
    error: a join with no condition would silently become a cross join.
    """
    condition = None
    if schema:
        found = resolve_join_condition(left, right, schema, hint_column=None)
        if found and found.source in ("explicit", "inferred"):
            condition = found
    if condition is None and infer_join_keys:
        condition = resolve_join_condition(left, right, schema=None, hint_column=None)

    if condition is None:
        guess = resolve_join_condition(left, right, schema=None)
        assert guess is not None  # convention always yields a candidate
        raise ASQLResolutionError(
            f"Cannot infer how to join '{left}' to '{right}': no `on` clause, "
            "and no relationship between the tables in the schema. "
            f"Add one, e.g. `join {right} on {guess.as_sql()}`, "
            "or define the relationship in your schema. To guess keys from the "
            f"`{{table}}_id` naming convention instead, enable `infer_join_keys` "
            f"(`SET infer_join_keys = true`). For a cartesian product use `* {right}`."
        )
    join.set("on", _on_clause(condition))
