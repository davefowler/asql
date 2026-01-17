# ASQL Code Quality Review - 2026-01-17

## Critical Issue Found: `compile()` vs `sqlglot.transpile()` Divergence

**ASQL has TWO different compilation paths that produce DIFFERENT results!**

### The Problem

1. **`sqlglot.transpile(query, read='asql', write='postgres')`** - Uses only the SQLGlot dialect (Parser + Generator)
2. **`asql.compile(query, dialect='postgres')`** - Uses the dialect PLUS additional AST transforms

These produce **different SQL** for many queries:

| Feature | `transpile()` | `compile()` |
|---------|---------------|-------------|
| Basic queries | ✅ Same | ✅ Same |
| Relative dates (`30 days ago`) | ✅ Same | ✅ Same |
| Group by with inline aggs | ✅ Works | ⚠️ Adds auto-spine CTEs |
| FK shorthand (`on user_id`) | ❌ Incomplete | ✅ Expands to full condition |
| Underscore shorthand (`days_since_col`) | ❌ Literal column | ✅ Expands to DateDiff |
| Auto-spine gap-filling | ❌ Not applied | ✅ Applied |
| Column operators (`except`, `rename`) | ❌ Not expanded | ✅ Expanded (with schema) |
| Cohort transforms | ❌ Not applied | ✅ Applied |

### Why This Is Bad

1. **Users expect `sqlglot.transpile()` to work** - It's the standard SQLGlot API
2. **The dialect is incomplete** - Parser handles syntax but doesn't transform it
3. **Two APIs = confusion** - Which one should users use?
4. **Testing gap** - We test `compile()` but users might use `transpile()`

### Root Cause

ASQL has **compiler transforms** that are NOT part of the SQLGlot dialect:

```python
# asql/compiler/api.py - These are applied by compile() but NOT by transpile()
transformed_stmt = apply_since_until_underscore_shorthands(transformed_stmt, final_settings)
transformed_stmt = apply_implicit_function_aliases(transformed_stmt, final_settings)
transformed_stmt = transform_column_operators_for_dialect(transformed_stmt, dialect, final_settings)
transformed_stmt = apply_auto_aliasing(transformed_stmt, final_settings)
transformed_stmt = transform_fk_shorthand(transformed_stmt, final_settings)
transformed_stmt = transform_cohort(transformed_stmt, final_settings)
transformed_stmt = transform_pivot_for_dialect(transformed_stmt, dialect, final_settings)
transformed_stmt = transform_explode_for_dialect(transformed_stmt, dialect)
transformed_stmt = _apply_auto_spine(transformed_stmt, final_settings, dialect)
transformed_stmt = auto_qualify_columns(transformed_stmt)
transformed_stmt = apply_alias_reuse(transformed_stmt, dialect)
```

### What Other Dialects Do

Real SQLGlot dialects put ALL transforms in the dialect:
- BigQuery's `Generator.TRANSFORMS` dict handles expression-level transforms
- Transforms are applied during generation, not as a separate step
- `transpile()` and manual `parse() + generate()` produce identical results

### Recommendations

#### Option A: Move Transforms to Dialect (Preferred)
Move all compiler transforms into `ASQLParser` or `ASQLGenerator`:
- FK shorthand expansion → Parser
- Underscore shorthands → Parser or Generator
- Auto-spine → Generator TRANSFORMS (like BigQuery's `transforms.preprocess()`)
- Column operators → Generator TRANSFORMS

**Pros**: Standard SQLGlot behavior, one code path
**Cons**: Major refactor, some transforms need settings/schema

#### Option B: Document and Deprecate `transpile()`
Make it clear that `asql.compile()` is the only supported API.

**Pros**: Quick fix
**Cons**: Non-standard, confusing for SQLGlot users

#### Option C: Wrapper Around `transpile()`
Override `sqlglot.transpile()` when ASQL is imported to use `compile()`.

**Pros**: Transparent to users
**Cons**: Monkey-patching is fragile

---

## Other Issues Found

### 1. `reverse_compiler.py` Was a Wrapper (FIXED)
- **Issue**: Had a separate `reverse_compile()` function instead of using `transpile(..., write='asql')`
- **Status**: ✅ FIXED - Deleted the file, now uses standard SQLGlot API

### 2. `json_schema.py` Duplicates Generator Logic
- **Issue**: `json_to_asql()` manually builds ASQL strings instead of using `ASQLGenerator`
- **Impact**: Two places to maintain ASQL output format
- **Recommendation**: Refactor to build AST then use `ASQLGenerator`

### 3. Settings/Config Not Passed to Dialect
- **Issue**: `StyleConfig` options (equality style, count style, etc.) are not used by `ASQLGenerator`
- **Impact**: `transpile()` can't respect user style preferences
- **Recommendation**: Pass config through SQLGlot's `dialect_options` or generator kwargs

### 4. `register_asql_dialect()` Required
- **Issue**: Must call `register_asql_dialect()` before using the dialect
- **Impact**: `import asql` has side effects, easy to forget
- **Recommendation**: Auto-register on module load (already done in `__init__.py`)

---

## Summary

**The biggest issue is the `compile()` vs `transpile()` divergence.** ASQL is not a proper SQLGlot dialect because half of its features are in a separate compiler step.

### Priority Fixes

1. **HIGH**: Document that `asql.compile()` is required (not `transpile()`)
2. **MEDIUM**: Move transforms into the dialect over time
3. **LOW**: Refactor `json_to_asql()` to use `ASQLGenerator`

---

## Wrapper Functions Audit

### ✅ Removed (Good)
- `reverse_compile()` - was in `reverse_compiler.py`, now deleted

### ⚠️ Still Exists (Necessary for some features)
- `asql.compile()` - Wrapper that applies AST transforms before generating SQL
  - **Why it exists**: Applies schema-aware transforms and auto-spine
  - **When to use**: Schema-aware FK shorthand, auto-spine gap-filling, column operators
  - **When NOT needed**: Basic queries now work with `sqlglot.transpile()`

### ✅ Fixed (2026-01-17)
- **FK shorthand** now expands at parse time: `on user_id` → `ON left.user_id = right.id`
- `transpile()` now works for basic FK shorthand (uses convention: assumes `id` as PK)
- `compile()` with schema still provides smarter FK expansion (respects actual PK names)
- **`normalize()` removed** - use `sqlglot.transpile(query, read='asql', write='asql')` instead

### ✅ OK (ASQL-specific but legitimate)
- `compile_to_ast()` - Returns AST instead of string (standard pattern)
- `get_settings_from_query()` - Extracts ASQL inline settings (`SET auto_spine = false`)
  - **Note**: ASQL-specific, not in other dialects. ASQL's `SET` statements configure the *compiler*, not the database session. Other dialects don't have compiler settings.
- **`get_preparsed()` REMOVED** - was redundant, use `sqlglot.parse_one(query, dialect="asql").sql()`

### What Other Dialects Do

Real SQLGlot dialects have **no wrapper functions**. Everything goes through:
```python
sqlglot.transpile(sql, read="dialect", write="target")
sqlglot.parse(sql, dialect="dialect")
ast.sql(dialect="target")
```

ASQL's `compile()` function is non-standard because it applies transforms that should be in the dialect.
