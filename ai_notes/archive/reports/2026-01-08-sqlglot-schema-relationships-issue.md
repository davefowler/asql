## Summary

SQLGlot’s `Schema` (e.g., `MappingSchema`) currently models **tables/columns/types/visibility**, and is used by optimizer passes like `qualify_columns(..., expand_stars=True)` for column resolution and star expansion.

Many query languages and query builders also have **relationship / foreign-key metadata** available (explicit from dbt, information_schema, or config), and it would be valuable if SQLGlot’s schema could optionally carry this information in a standard way.

This would enable generic, schema-aware transforms (and dialect helpers) that need relationships, e.g.:

- join inference helpers / linting
- safer rewrites for shorthand join syntaxes in higher-level languages
- tooling that needs to traverse join graphs without custom sidecar metadata

## Current state in SQLGlot

In `sqlglot/schema.py`, `Schema` provides APIs like:

- `column_names(table)`
- `get_column_type(table, column)`
- `has_column(table, column)`

and `MappingSchema` stores a nested mapping of `{catalog?}{db?}{table}{column: type}`.

There is no standard place to store **FK relationships** / join edges.

## Proposal: extend Schema to optionally expose relationships

Add an optional interface (minimal, non-breaking) for relationship metadata:

### Option A (simple): add methods on Schema

- `foreign_keys(table) -> Sequence[ForeignKey]`
- `primary_key(table) -> Optional[str]`
- `relationships() -> Sequence[ForeignKey]`

Where:

```python
@dataclass(frozen=True)
class ForeignKey:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    name: Optional[str] = None
```

Default base `Schema` can return empty lists / None, so existing usage is unchanged.

### Option B (sidecar attribute): `schema.relationships`

Keep the schema mapping unchanged but allow:

- `schema.relationships: list[ForeignKey]`

This is easy but less “interface-y”.

## How schema is currently provided to SQLGlot

SQLGlot doesn’t “fetch” schema itself; callers supply it:

- `sqlglot.optimizer.optimize(expression, schema=..., dialect=...)`
- `qualify_columns(expression, schema=..., expand_stars=True, ...)`

Schema can be a nested mapping; SQLGlot converts it via `ensure_schema(...)` to `MappingSchema`.

So relationship info could be provided by callers alongside the mapping (dbt manifest, DB introspection, etc.).

## How relationship metadata could be used in SQLGlot (future)

This issue is just about **carrying** relationship metadata. Potential future uses:

- a generic helper for join path selection or FK validation
- optional rewrite pass for languages/dialects that support join shorthand
- improved lineage tools by understanding join graphs

## Acceptance criteria

- Relationship metadata can be attached to schema with minimal disruption to existing schema usage.
- Schema relationship API is stable and works with `MappingSchema`.
- No optimizer behavior changes in this PR; this is just schema plumbing and tests.


