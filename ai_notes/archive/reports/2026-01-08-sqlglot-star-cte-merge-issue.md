## Summary

`sqlglot.optimizer.merge_subqueries.merge_ctes()` refuses to merge/in-line CTEs when the outer query is a star select (`SELECT * ...`), even when the merge is trivially safe (e.g. `WITH t AS (SELECT a FROM x) SELECT * FROM t` where `t` is referenced once and the outer query is a pure passthrough wrapper).

This blocks a common "pipeline stage wrapper" pattern, where an engine (or a transpiler) inserts intermediate CTEs and then continues from them with `SELECT * FROM __tmp`.

## Current behavior

In `sqlglot.optimizer.merge_subqueries._mergeable`, the outer select must satisfy:

- `and not outer_scope.expression.is_star`

`Select.is_star` is defined as:

- `return any(expression.is_star for expression in self.expressions)`

So *any* `SELECT *` (or other star expressions) prevents merging, regardless of whether the wrapper is otherwise mergeable.

## Repro

```sql
WITH t AS (SELECT a, b FROM x)
SELECT * FROM t
```

Expected (safe) result after `merge_subqueries()`:

```sql
SELECT x.a, x.b FROM x
```

But today this does not merge because the outer select is star.

## Proposed improvement (safe subset)

Allow merging when the outer select is a **pure passthrough star wrapper**:

- Outer query:
  - `SELECT * FROM <cte_alias>`
  - no `DISTINCT`, no `WHERE`, no `GROUP BY`, no `HAVING`, no `QUALIFY`, no `ORDER BY`, no `LIMIT/OFFSET`
  - no additional projections besides the star
- CTE selected from exactly once (already required by merge logic)
- The inner select remains subject to all existing merge safety checks

This can be implemented as:

1) Relax the guard in `_mergeable` from:
   - `and not outer_scope.expression.is_star`
   to:
   - `and (not outer_scope.expression.is_star or _is_pure_star_passthrough(outer_scope.expression, from_or_join))`

2) Implement `_is_pure_star_passthrough(select, from_or_join)` structurally:
   - `select.is_star` is True
   - `len(select.expressions) == 1` and the expression is a star-like node
   - `from_or_join` is the `FROM <cte_alias>` case being merged
   - ensure none of `Select.arg_types`/`QUERY_MODIFIERS` that affect semantics are present (where/group/having/order/limit/distinct/etc.)

## Why not rely on schema-based `*` expansion?

SQLGlot can expand stars in `qualify_columns(..., expand_stars=True)`, but:

- it requires schema (or inference) and can be brittle for joins/duplicates
- it still doesn't address the current blanket `is_star` guard; a targeted passthrough optimization is simpler and safer

## Tests to add (in sqlglot)

- `merge_subqueries` merges star wrapper CTEs when safe
- does not merge when outer has any additional semantic modifiers (e.g., WHERE/LIMIT/ORDER/DISTINCT)
- does not merge when CTE referenced multiple times


