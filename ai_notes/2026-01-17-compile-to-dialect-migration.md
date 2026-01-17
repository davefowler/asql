# Migration: Move compile() Transforms into Dialect

**Goal**: Make `sqlglot.transpile(query, read='asql', write='postgres')` fully functional.  
**Result**: Delete `asql.compile()` wrapper entirely.

---

## Current State

`asql.compile()` applies 11 transforms that are NOT in the dialect:

```python
# From asql/compiler/api.py
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

---

## Migration Plan

### Phase 1: Parser Transforms (parse-time expansion)

These can be moved to the parser - expand syntax during parsing:

| Transform | Current Location | Target | Notes |
|-----------|-----------------|--------|-------|
| `apply_since_until_underscore_shorthands` | compiler/underscore_shorthands.py | Parser | Parse `days_since_col` as function call |
| `apply_implicit_function_aliases` | compiler/implicit_aliases.py | Parser | Add alias when parsing aggregates |
| `apply_auto_aliasing` | compiler/auto_aliasing.py | Parser | Add aliases during parse |
| `transform_fk_shorthand` | compiler/join_fk_shorthand.py | Parser | ✅ Partially done, needs schema-aware version |
| `apply_alias_reuse` | compiler/alias_reuse.py | Parser | Resolve aliases during parse |

### Phase 2: Generator Transforms (generate-time expansion)

These need schema or dialect info, best handled in Generator:

| Transform | Current Location | Target | Notes |
|-----------|-----------------|--------|-------|
| `transform_column_operators_for_dialect` | compiler/column_operators.py | Generator | Needs schema for EXCEPT expansion |
| `transform_cohort` | compiler/cohort.py | Generator | Complex CTE generation |
| `transform_pivot_for_dialect` | compiler/pivot.py | Generator | Dialect-specific pivot syntax |
| `transform_explode_for_dialect` | compiler/explode.py | Generator | Dialect-specific unnest |
| `_apply_auto_spine` | compiler/auto_spine.py | Generator | Gap-filling CTEs |
| `auto_qualify_columns` | compiler/qualify.py | Generator | Add table prefixes |

### Phase 3: Settings & Schema Plumbing

1. Pass CompileSettings through dialect options
2. Pass schema to transpile() for schema-aware features
3. Store in dialect for generator access

```python
# Usage after migration
sqlglot.transpile(
    query, 
    read="asql", 
    write="postgres",
    schema=my_schema,  # For column operators, FK shorthand
    asql_auto_spine=True,  # Dialect option
    asql_week_start="monday",
)
```

### Phase 4: Cleanup

1. Delete `asql.compile()` 
2. Delete `asql/compiler/` folder (or move to dialect/)
3. Update all tests to use `transpile()`
4. Update docs

---

## Implementation Order

### Step 1: Plumbing (do first)
- [ ] Add dialect options support for ASQL settings
- [ ] Ensure schema is accessible in Generator

### Step 2: Easy Parser Moves
- [ ] `apply_implicit_function_aliases` → Parser
- [ ] `apply_auto_aliasing` → Parser

### Step 3: Underscore Shorthands
- [ ] `apply_since_until_underscore_shorthands` → Parser
  - Parse `days_since_col` as `DATE_DIFF('day', col, CURRENT_DATE)`

### Step 4: Generator Transforms
- [ ] `transform_column_operators_for_dialect` → Generator
- [ ] `transform_pivot_for_dialect` → Generator
- [ ] `transform_explode_for_dialect` → Generator
- [ ] `auto_qualify_columns` → Generator

### Step 5: Complex Transforms
- [ ] `transform_cohort` → Generator
- [ ] `_apply_auto_spine` → Generator
- [ ] `apply_alias_reuse` → Parser/Generator

### Step 6: FK Shorthand (schema-aware)
- [ ] Move schema-aware FK expansion to Parser/Generator

### Step 7: Delete compile()
- [ ] Remove `asql.compile()`
- [ ] Update tests
- [ ] Update docs

---

## Technical Details

### How to Pass Settings to Dialect

SQLGlot dialects can receive options via `**kwargs`:

```python
class ASQL(Dialect):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.auto_spine = kwargs.get("asql_auto_spine", False)
        self.week_start = kwargs.get("asql_week_start", "sunday")
```

### How to Access Schema in Generator

```python
class ASQLGenerator(Generator):
    def select_sql(self, expression):
        # Schema is available via optimizer
        from sqlglot.optimizer.scope import build_scope
        root = build_scope(expression)
        # ... use scope for column info
```

Or pass explicitly:
```python
sqlglot.transpile(query, read="asql", write="postgres", schema=schema)
# Generator can access via self.dialect.mapping_schema
```

### How to Apply Transforms in Generator

Use `Generator.TRANSFORMS` dict (like BigQuery does):

```python
class ASQLGenerator(Generator):
    TRANSFORMS = {
        **Generator.TRANSFORMS,
        exp.Select: lambda self, e: self._transform_select(e),
    }
    
    def _transform_select(self, expression):
        # Apply auto-spine, column operators, etc.
        return super().select_sql(expression)
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing tests | Run tests after each step |
| Complex transforms hard to move | Keep as generator post-process if needed |
| Settings not available | Add plumbing first |
| Schema not available | Document that schema-aware features need schema param |

---

## Success Criteria

After migration:
- [ ] `sqlglot.transpile(query, read='asql', write='postgres')` handles ALL ASQL features
- [ ] `asql.compile()` is deleted
- [ ] All tests pass using `transpile()`
- [ ] No wrapper functions remain
