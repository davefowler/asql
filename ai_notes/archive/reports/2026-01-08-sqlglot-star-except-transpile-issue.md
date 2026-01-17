## Summary

SQLGlot’s optimizer can expand stars (`SELECT *`) in a **schema-aware** way via `qualify_columns(..., expand_stars=True)`. That star expansion already understands `Star(except_=...)` (and also `rename`/`replace` on star) during expansion.

However, when transpiling **from dialects which support** `SELECT * EXCEPT(...)` / `EXCLUDE(...)` to dialects which **don’t** support it, users still end up with output containing unsupported star modifiers unless they manually run `qualify_columns` with schema first (and even then, the overall optimize/transpile flow doesn’t clearly document how to do this).

It would be valuable if SQLGlot provided a first-class, schema-aware way to transpile / lower `Star(except_)` to explicit select lists when needed.

## Evidence: SQLGlot already has the core building block

In `sqlglot/optimizer/qualify_columns.py`, `_expand_stars(...)`:

- collects `except_` columns via `_add_except_columns(...)`
- enumerates `resolver.get_source_columns(...)` from schema
- produces explicit selections while omitting excluded columns

So the AST rewrite capability exists; it just needs to be surfaced and/or integrated into transpilation workflows.

## Proposal A (optimizer rule): `lower_star_modifiers`

Add an optimizer rule which:

- requires `schema` (or bails)
- runs `qualify_columns(..., expand_stars=True)` OR calls an extracted helper that expands only star modifiers
- ensures that after the rule runs there are no `Star(except_)` nodes left in the AST

This would let callers do:

```python
optimize(expr, schema=schema, rules=(..., lower_star_modifiers, ...))
```

and then generate SQL for a dialect that doesn’t support EXCEPT/EXCLUDE.

## Proposal B (transpile helper): `transpile(..., schema=...)` lowers automatically

Introduce/extend a high-level API so users can do:

```python
sqlglot.transpile(sql, read="bigquery", write="postgres", schema=schema)
```

and have star modifiers lowered automatically as part of a documented “schema-aware transpilation” flow.

This keeps the default behavior unchanged (no schema → no rewrite), while making the “right way” easy.

## Acceptance criteria

- With schema, transpiling `SELECT * EXCEPT(a)` from BigQuery → Postgres produces explicit column lists (no EXCEPT/EXCLUDE in output).
- Without schema, behavior remains unchanged or errors clearly (depending on chosen API design).
- Clear docs / examples on schema-aware transpilation.


