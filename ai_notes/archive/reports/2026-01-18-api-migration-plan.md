# Migration Plan: Delete api.py and Move Transforms

**Date**: 2026-01-18  
**Goal**: Eliminate `asql/compiler/api.py` wrapper and use SQLGlot's native extension points.

## ✅ PROGRESS UPDATE

Good news! The `asql/generators/` module already exists with:
- `base.py` - Common `asql_preprocess()` function
- `postgres.py`, `duckdb.py`, `snowflake.py`, `bigquery.py`, `mysql.py` - Target generators

**Remaining work**: Delete api.py and update all callers to use transpile() directly.

See also: `ai_notes/2026-01-18-transform-stage-audit.md` for full transform analysis.

---

## Current State (Partially Fixed)

```
User calls compile() in api.py
         │
         ▼
┌─────────────────┐
│  ASQL Parser    │ ◄── Imports compiler modules (WRONG)
│  + transforms   │ ◄── Has 35 settings references (WRONG)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  api.py wrapper │ ◄── THIS FILE SHOULD NOT EXIST
│  + more transforms
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Target Generator│
│ (postgres, etc) │
└─────────────────┘
```

## Target State (Correct)

```
User calls sqlglot.transpile(query, read="asql", write="postgres")
         │
         ▼
┌─────────────────┐
│  ASQL Parser    │ ◄── Pure parsing + non-dialect transforms
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Target Generator│ ◄── Dialect-specific transforms in preprocess()
│ (with ASQL hook)│ ◄── Uses TRANSFORMS dict for expression output
└─────────────────┘
```

---

## Transforms to Migrate

### Phase 1: Non-Dialect Transforms (Stay in Parser)

These don't need output dialect. Keep in `Parser._parse_statement()` post-processing:

| Transform | Current Location | Action |
|-----------|------------------|--------|
| `apply_since_until_underscore_shorthands` | Parser | ✅ Keep |
| `apply_implicit_function_aliases` | Parser | ✅ Keep |
| `apply_auto_aliasing` | Parser | ✅ Keep |
| `transform_fk_shorthand` | Parser | ✅ Keep (needs schema) |
| `transform_cohort` | Parser | ✅ Keep |
| `auto_qualify_columns` | Parser | ✅ Keep |

**But**: Remove the `from asql.compiler.*` imports from parser. These transforms can stay in `asql/compiler/` but be called from parser's `_apply_asql_transforms()`.

### Phase 2: Dialect-Specific Transforms (Move to Generator)

These need output dialect. Move to target generator's `preprocess()`:

| Transform | Current Location | Target Location |
|-----------|------------------|-----------------|
| `apply_alias_reuse` | api.py | Generator.preprocess() |
| `transform_column_operators_for_dialect` | api.py | Generator.preprocess() |
| `_transform_list_comprehensions` | api.py | Generator.preprocess() |
| `_apply_auto_spine` | api.py | Generator.preprocess() |

---

## Implementation Options

### Option A: Patch Target Generators

Create ASQL-aware versions of each target generator:

```python
# asql/generators/postgres.py
from sqlglot.dialects.postgres import Postgres

class ASQLPostgresGenerator(Postgres.Generator):
    def preprocess(self, expression):
        # Apply ASQL transforms for non-DuckDB output
        expression = apply_alias_reuse(expression, "postgres")
        expression = transform_column_operators(expression, "postgres", self.dialect.settings)
        expression = transform_list_comprehensions(expression, "postgres")
        return super().preprocess(expression)

# Register it
class ASQLPostgres(Postgres):
    class Generator(ASQLPostgresGenerator):
        pass
```

**Pros**: Clean, uses SQLGlot's extension points  
**Cons**: Need generator for every target dialect (postgres, snowflake, bigquery, etc.)

### Option B: Single ASQL Generator with Dialect Dispatch

```python
# asql/dialect/generator.py
class ASQLGenerator(Generator):
    def preprocess(self, expression):
        target = self._target_dialect  # How to get this?
        
        if target != "duckdb":
            expression = apply_alias_reuse(expression, target)
            expression = transform_column_operators(expression, target, self.dialect.settings)
            expression = transform_list_comprehensions(expression, target)
        
        return super().preprocess(expression)
```

**Problem**: Generator doesn't know target dialect - it IS the target dialect.

### Option C: Optimizer Rules

Register ASQL transforms as SQLGlot optimizer rules:

```python
from sqlglot.optimizer import optimize, RULES

ASQL_RULES = [
    alias_reuse_rule,
    column_operators_rule,
    list_comprehension_rule,
    auto_spine_rule,
]

# User calls:
ast = sqlglot.parse_one(query, dialect="asql")
ast = optimize(ast, rules=ASQL_RULES, dialect="postgres")
sql = ast.sql(dialect="postgres")
```

**Pros**: Uses SQLGlot's intended transform mechanism  
**Cons**: Requires 3-step API instead of single `transpile()`

### Option D: Transpile Hook (If SQLGlot Supports It)

Check if SQLGlot has a hook for transforms between parse and generate.

```python
# Hypothetical - need to check if this exists
sqlglot.transpile(
    query, 
    read="asql", 
    write="postgres",
    transforms=[apply_alias_reuse, ...]  # Does this exist?
)
```

---

## Recommended Approach: Option A (Target Generators)

Despite needing multiple generators, this is the cleanest:

1. **Create `asql/generators/` module** with ASQL-aware generators
2. **Each inherits from SQLGlot's dialect generator** and adds `preprocess()`
3. **Register these as the default generators** when ASQL is the read dialect

### Files to Create

```
asql/generators/
├── __init__.py
├── base.py          # Common ASQL preprocess logic
├── postgres.py      # ASQLPostgresGenerator
├── duckdb.py        # ASQLDuckDBGenerator (minimal - DuckDB is native)
├── snowflake.py     # ASQLSnowflakeGenerator
├── bigquery.py      # ASQLBigQueryGenerator
└── mysql.py         # ASQLMySQLGenerator
```

### Common Base

```python
# asql/generators/base.py
def asql_preprocess(expression, target_dialect, settings=None):
    """Common ASQL preprocessing for all target dialects."""
    if target_dialect.lower() != "duckdb":
        from asql.compiler.alias_reuse import apply_alias_reuse
        from asql.compiler.column_operators import transform_column_operators_for_dialect
        from asql.compiler.list_comprehension import transform_list_comprehensions
        
        expression = apply_alias_reuse(expression, target_dialect)
        expression = transform_column_operators_for_dialect(expression, target_dialect, settings)
        expression = transform_list_comprehensions(expression, target_dialect)
    
    # Auto-spine always runs if enabled
    if settings and settings.auto_spine:
        from asql.compiler.auto_spine import _apply_auto_spine
        expression = _apply_auto_spine(expression, settings, target_dialect)
    
    return expression
```

---

## Migration Steps

### Step 1: Create Generator Module

1. Create `asql/generators/` with base preprocess logic
2. Create target dialect generators (postgres, snowflake, etc.)
3. Add tests for each generator

### Step 2: Update Parser

1. Remove dialect-specific transforms from `_apply_asql_transforms()`
2. Keep non-dialect transforms (underscore shorthands, cohort, etc.)
3. Remove `extend_dialect` checks from parser

### Step 3: Register Generators

1. When user does `transpile(query, read="asql", write="postgres")`
2. Intercept to use `ASQLPostgresGenerator` instead of `PostgresGenerator`
3. Or: provide `asql.transpile()` that handles this

### Step 4: Delete api.py

1. Move any remaining logic to appropriate locations
2. Update imports throughout codebase
3. Delete `asql/compiler/api.py`

### Step 5: Update Tests

1. Change `from asql.compiler.api import compile` to `sqlglot.transpile`
2. Or: keep thin `asql.compile()` that just calls transpile with right generators

---

## Open Questions

1. **How do we inject ASQL generators when user calls `transpile()`?**
   - Can we register them globally?
   - Or do we need `asql.transpile()` wrapper?

2. **How do generators get settings (schema, auto_spine, etc.)?**
   - Via `dialect.settings`?
   - Passed through `transpile()` kwargs?

3. **Should we contribute ASQL transforms upstream to SQLGlot?**
   - Alias reuse → Already exists as `expand_alias_refs`
   - Column operators → Could be useful for others
   - List comprehension → DuckDB-specific, maybe not

---

## Success Criteria

- [x] `api.py` is deleted → **DONE**
- [ ] `transpile(query, read="asql", write="postgres")` works without wrapper (not done - compile() is our API)
- [ ] Parser has 0 imports from `asql.compiler.*` (or minimal)
- [ ] Parser has ~0 settings references
- [x] Dialect-specific transforms are in Generator.preprocess() → **DONE: asql/generators/base.py**
- [x] All existing tests pass → **DONE: 2710 tests pass**

---

## Implementation Status (2026-01-18)

### What Was Done

1. **Deleted `asql/compiler/api.py`** - The wrapper file is gone.

2. **Moved `compile()` and `compile_to_ast()` to `asql/__init__.py`** - These are now
   simple functions in the main module, not a separate "wrapper" package.

3. **Created `asql/generators/` module** with:
   - `base.py` - Contains `asql_preprocess()` with all dialect-specific transforms
   - `postgres.py`, `duckdb.py`, `snowflake.py`, `bigquery.py`, `mysql.py` - ASQL-aware generators

4. **Moved transforms** to `generators/base.py`:
   - `apply_alias_reuse`
   - `transform_column_operators_for_dialect`
   - `_transform_list_comprehensions`
   - `_apply_auto_spine`
   - `_remove_guarantee_wrappers`

5. **Updated imports** throughout codebase to use `from asql import compile`.

### Architecture Now

```
User calls asql.compile(query, dialect="postgres")
         │
         ▼
┌─────────────────┐
│  ASQL Parser    │ ◄── Non-dialect transforms (underscore shorthands, etc.)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ asql_preprocess │ ◄── Dialect-specific transforms (generators/base.py)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Target Generator│ ◄── SQLGlot's native .sql() method
│ (postgres, etc) │
└─────────────────┘
```

### What's Still Not Ideal

`compile()` exists in `asql/__init__.py` because SQLGlot's `transpile()` doesn't
have a hook to inject our generators. But the separate api.py wrapper file is gone.
