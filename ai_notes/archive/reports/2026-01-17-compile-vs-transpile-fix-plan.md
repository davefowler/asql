# Fix Plan: Eliminate `compile()` vs `transpile()` Divergence

## ✅ PARTIALLY FIXED (2026-01-17)

**FK shorthand is now fixed!** It expands at parse time:

```python
# BEFORE (broken):
sqlglot.transpile("from orders & users on user_id", read="asql", write="postgres")
# → "SELECT * FROM orders INNER JOIN users ON user_id"

# AFTER (fixed):
sqlglot.transpile("from orders & users on user_id", read="asql", write="postgres")
# → "SELECT * FROM orders INNER JOIN users ON orders.user_id = users.id"
```

**Schema-aware FK shorthand** still requires `compile()` for smarter PK detection.

## The Remaining Problem

Some transforms still only run in `compile()`, not `transpile()`:
- Underscore shorthands (`days_since_col` → DateDiff)
- Auto-spine gap-filling
- Column operators (`except`, `rename`, `replace`)

The 12 remaining transforms in `compile()` are NOT in the dialect.

## How SQLGlot Dialects Work

```
┌─────────────┐    ┌─────────────┐    ┌─────────────────┐
│   Parser    │ → │    AST      │ → │   Generator     │
│  (read)     │    │             │    │   (write)       │
└─────────────┘    └─────────────┘    └─────────────────┘
     ↑                                       ↑
     │                                       │
  Transforms                             TRANSFORMS dict
  happen here                            (preprocess before
  (during parse)                          generating)
```

Transforms go in ONE of two places:
1. **Parser** - Transform while parsing (ASQL-specific)
2. **Generator.TRANSFORMS** - Transform before generating (dialect-specific)

ASQL's transforms are in NEITHER - they're in `compile()` which `transpile()` doesn't call.

## Solution: Move Transforms to Parser

Most ASQL transforms should happen **during parsing**. When `ASQLParser` produces an AST, it should already be fully transformed.

### Transforms to Move to Parser

| Transform | What it does | Move to |
|-----------|-------------|---------|
| `apply_since_until_underscore_shorthands` | `days_since_col` → DateDiff | Parser (recognize pattern) |
| `apply_implicit_function_aliases` | `sum_amount` → `SUM(amount) AS sum_amount` | Parser (recognize pattern) |
| `transform_fk_shorthand` | `on user_id` → full condition | Parser (expand during join parsing) |
| `transform_cohort` | Cohort syntax → CTEs | Parser (already mostly there) |
| `apply_auto_aliasing` | Add missing aliases | Parser (after expression parsing) |
| `auto_qualify_columns` | Qualify ambiguous columns | Parser (during select parsing) |

### Transforms to Move to Generator.TRANSFORMS

| Transform | What it does | Move to |
|-----------|-------------|---------|
| `transform_column_operators_for_dialect` | `EXCEPT` → schema expansion | Target Generator.TRANSFORMS |
| `transform_pivot_for_dialect` | PIVOT → CASE/WHEN | Target Generator.TRANSFORMS |
| `transform_explode_for_dialect` | EXPLODE → FLATTEN | Target Generator.TRANSFORMS |
| `apply_alias_reuse` | Alias references | Target Generator.TRANSFORMS |

### Special Cases

| Transform | What it does | Recommendation |
|-----------|-------------|----------------|
| `_apply_auto_spine` | Gap-filling CTEs | **Keep in compile()** - this is an advanced feature that fundamentally changes query semantics. It's opt-in via settings. |

## Implementation Plan

### Phase 1: Move Stateless Transforms to Parser

1. **`auto_qualify_columns`** - Stateless, easy to move
2. **`apply_auto_aliasing`** - Only needs parsed expressions

### Phase 2: Move Pattern-Based Transforms to Parser

3. **`apply_since_until_underscore_shorthands`** - Pattern on identifiers
4. **`apply_implicit_function_aliases`** - Pattern on identifiers
5. **`transform_fk_shorthand`** - Expand during `_parse_asql_join`

### Phase 3: Move Dialect-Specific Transforms to Generators

This requires modifying SQLGlot's built-in dialects (Postgres, BigQuery, etc.) which is not ideal. Alternative: Create ASQL-specific target generators.

```python
# Instead of:
sqlglot.transpile(asql, read="asql", write="postgres")

# We might need:
sqlglot.transpile(asql, read="asql", write="asql_postgres")
```

Or use SQLGlot's `transforms.preprocess()` mechanism.

### Phase 4: Document Auto-Spine

`_apply_auto_spine` should remain opt-in via `compile()` because:
- It fundamentally changes query semantics
- It's controlled by settings
- It generates substantial additional SQL

Document that for auto-spine, users must use `compile()`.

## Quick Win: Move `auto_qualify_columns` Now

This is stateless and can be moved immediately:

```python
# In ASQLParser, add after parsing SELECT expressions:
def _parse_query(self, ...):
    query = self._parse_base_query()
    # NEW: Auto-qualify ambiguous columns
    query = auto_qualify_columns(query)
    return query
```

This alone would fix one transform.

## Alternative: Override `transpile()` for ASQL

Instead of moving transforms, we could make ASQL's `transpile()` call `compile()`:

```python
# In asql/__init__.py
def _asql_transpile(sql, read=None, write=None, **opts):
    if read == "asql":
        # Use compile() for ASQL → X
        from asql import compile
        return [compile(sql, dialect=write)]
    return original_transpile(sql, read, write, **opts)

# Monkey-patch sqlglot.transpile when asql is imported
import sqlglot
sqlglot.transpile = _asql_transpile
```

**Pros**: Quick fix
**Cons**: Monkey-patching is fragile, affects all SQLGlot usage

## Recommendation

1. **Short term**: Document that `asql.compile()` must be used, not `transpile()`
2. **Medium term**: Move stateless transforms to Parser (Phase 1-2)
3. **Long term**: Figure out dialect-specific transforms (Phase 3)
4. **Never**: Don't move `auto_spine` - it's intentionally opt-in

## What This Means for Users

After fixes:
```python
import sqlglot
import asql  # Registers dialect

# This will work correctly:
sqlglot.transpile("from orders & users on user_id", read="asql", write="postgres")
# → "SELECT orders.*, users.* FROM orders INNER JOIN users ON orders.user_id = users.id"

# For auto-spine (advanced), still use:
asql.compile("from sales group by region (...)", dialect="postgres", settings=...)
```
