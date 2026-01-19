# Underscore Shorthands: Refactor to Optimizer-Based Expansion

**Date**: 2026-01-18  
**Status**: Plan  
**Related**: `2026-01-18-compile-transforms-analysis.md`

## Goal

Refactor BOTH underscore shorthand transforms to use optimizer-based expansion:

| Transform | Pattern | Expands to |
|-----------|---------|------------|
| **since/until** | `days_since_created_at` | `DATEDIFF(DAY, created_at, NOW)` |
| **function aliases** | `sum_amount` | `SUM(amount) AS sum_amount` |

Both transforms:
1. Parse as plain columns (simpler parser)
2. Expand in optimizer phase when we know what columns are available
3. Add setting to enable/disable (`enable_underscore_shorthands`)

## Current Behavior

```sql
-- Function aliases
from orders 
group by region (sum_amount)   -- Expands: sum_amount → SUM(amount) AS sum_amount
| where sum_amount > 1000      -- Currently: doesn't expand (conservative, correct by accident)

-- Since/until shorthands  
from users
select days_since_created_at   -- Expands: → DATEDIFF(DAY, created_at, NOW)
| where days_since_created_at > 30  -- Currently: doesn't expand in stage 2
```

Current implementation in `underscore_shorthands.py`:
- `apply_since_until_underscore_shorthands()` - works on ANY column reference
- `apply_implicit_function_aliases()` - works on SELECT projections only
- Both use `_single_from_table_name()` to check schema
- Both sort prefixes by length (longest first) ✅

**Problem**: Neither properly tracks columns through CTE stages. Works "by accident" because CTEs aren't in schema.

## Proposed Approach: Optimizer-Phase Expansion

### Key Insight

SQLGlot's `qualify_columns` optimizer builds scope information that tracks what columns are available at each point. We can run our expansion AFTER qualify, using that scope info.

### Architecture

```
Parser:     sum_amount → exp.Column("sum_amount")  [simpler, always same behavior]
    ↓
Qualify:    Build scope, track available columns per scope
    ↓
ASQL Transform: For each Column not in scope + matches func_col pattern → expand
```

### SQLGlot Hook Point

After `qualify_columns` runs, we have access to `Scope` objects via `traverse_scope()`:

```python
from sqlglot.optimizer.scope import build_scope, traverse_scope

def expand_implicit_function_aliases(expression, schema=None, settings=None):
    """Expand func_col patterns to function calls, respecting column availability."""
    
    if not settings or not settings.enable_implicit_function_aliases:
        return expression
    
    root = build_scope(expression)
    
    for scope in traverse_scope(root):
        # Get columns available in this scope
        available_columns = {
            col.name.lower() 
            for col in scope.columns 
            if col.name
        }
        
        # Also check source columns if schema provided
        if schema:
            for source in scope.selected_sources.values():
                if hasattr(source, 'name'):
                    table_cols = schema.get_table(source.name)
                    if table_cols:
                        available_columns.update(c.lower() for c in table_cols.columns)
        
        # Find columns to expand
        for column in scope.find_all(exp.Column):
            if column.name.lower() in available_columns:
                continue  # Real column exists, don't expand
            
            expanded = _try_expand_func_col(column.name, available_columns, schema)
            if expanded:
                column.replace(expanded)
    
    return expression
```

---

## Implementation Tasks

### 1. Add Setting: `enable_underscore_shorthands`

**File**: `asql/config.py`

```python
@dataclass
class CompileSettings:
    # ... existing fields ...
    
    # Underscore shorthands: when True, expands patterns like:
    # - sum_amount → SUM(amount) AS sum_amount
    # - days_since_created_at → DATEDIFF(DAY, created_at, NOW)
    # Only expands when the column doesn't already exist at that pipeline stage
    enable_underscore_shorthands: bool = True
```

Also add to `KNOWN_COMPILE_SETTINGS` set and `dialect.settings`.

### 2. Expose in Playground

**File**: `playground/app.py` and `playground/templates/index.html`

Add checkbox/toggle for the setting in the UI.

### 3. Refactor BOTH Transforms to Optimizer Phase

**Current location**: `asql/compiler/underscore_shorthands.py`
- `apply_since_until_underscore_shorthands()` - date diff patterns
- `apply_implicit_function_aliases()` - aggregate function patterns

**Strategy**: Both use the same pattern:
1. Parse as plain `exp.Column` 
2. After `qualify` runs, check if column exists in scope
3. If NOT exists AND matches pattern → expand
4. If exists → leave as column reference

### 4. Unified Expansion Logic

```python
def expand_underscore_shorthands(expression, schema=None, settings=None):
    """Expand underscore shorthand patterns, respecting column availability.
    
    Handles:
    - sum_amount → SUM(amount) AS sum_amount (SELECT projections)
    - days_since_created_at → DATEDIFF(...) (any column ref)
    """
    if not settings or not settings.enable_underscore_shorthands:
        return expression
    
    root = build_scope(expression)
    
    for scope in traverse_scope(root):
        available_columns = {col.name.lower() for col in scope.columns if col.name}
        
        for column in scope.find_all(exp.Column):
            if column.name.lower() in available_columns:
                continue  # Real column exists, don't expand
            
            # Try function alias pattern (sum_amount)
            expanded = _try_expand_func_col(column.name, available_columns, schema)
            if expanded:
                column.replace(expanded)
                continue
            
            # Try since/until pattern (days_since_created_at)
            expanded = _try_expand_since_until(column.name, available_columns, schema)
            if expanded:
                column.replace(expanded)
    
    return expression
```

### 5. Pattern Matchers

```python
def _try_expand_func_col(name: str, available_cols: set, schema=None) -> exp.Expression | None:
    """Try to expand func_col pattern like sum_amount."""
    # Longest-first to avoid sum matching before sum_of
    prefixes = sorted(NATURAL_AGG_FUNCS.keys(), key=len, reverse=True)
    # ... match logic ...

def _try_expand_since_until(name: str, available_cols: set, schema=None) -> exp.Expression | None:
    """Try to expand days_since_col or months_until_col patterns."""
    match = _SINCE_UNTIL_PATTERN.match(name)
    if not match:
        return None
    # ... expand to DATEDIFF ...
```

### 5. Tests

**New test file**: `tests/features/test_implicit_alias_scope.py`

```python
class TestImplicitAliasScopeAwareness:
    """Test that implicit aliases respect column availability."""
    
    def test_stage1_expands_stage2_uses_column(self):
        """sum_amount expands in stage 1, stays as column in stage 2."""
        # Stage 1: sum_amount should expand (column doesn't exist)
        # Stage 2: sum_amount should NOT expand (now it's a real column from CTE)
        result = compile("""
            from orders 
            group by region (sum_amount)
            | where sum_amount > 1000
        """, dialect="postgres")
        
        # Should have SUM(amount) in stage 1
        assert "SUM(amount)" in result.upper()
        # Should reference the alias in stage 2, not re-expand
        # (this is the key test)
    
    def test_longest_prefix_first(self):
        """Ensure 'sum_of' matches before 'sum'."""
        # If we had a prefix 'sum_of', sum_of_amount should use it
        # not accidentally match 'sum' and produce sum(of_amount)
        ...
    
    def test_setting_disable(self):
        """enable_implicit_function_aliases=False skips expansion."""
        result = compile(
            "from orders select sum_amount",
            dialect="postgres",
            settings=CompileSettings(enable_implicit_function_aliases=False)
        )
        # Should have sum_amount as a column, not SUM(amount)
        assert "SUM(amount)" not in result.upper()
        assert "sum_amount" in result.lower()
```

---

## Integration with SQLGlot's Pipeline

Two options for where to run our transform:

### Option A: After `_apply_asql_transforms`, before generate

```python
# In parser._apply_asql_transforms():
# ... existing transforms ...

# Run qualify to build scope info
from sqlglot.optimizer import qualify
stmt = qualify.qualify(stmt, schema=schema_for_qualify)

# NOW run implicit alias expansion with scope awareness
stmt = expand_implicit_function_aliases(stmt, schema, settings)
```

### Option B: Custom optimizer rule

```python
from sqlglot.optimizer import optimize

ASQL_RULES = [
    qualify_tables,
    qualify_columns,
    expand_implicit_function_aliases,  # Our custom rule
    # ... other rules ...
]

stmt = optimize(stmt, rules=ASQL_RULES, schema=schema)
```

**Recommendation**: Option A is simpler and keeps ASQL transforms in one place.

---

## Migration Path

1. **Phase 1**: Add setting (default True), no behavior change
2. **Phase 2**: Refactor to scope-aware expansion  
3. **Phase 3**: Add comprehensive tests
4. **Phase 4**: Document in playground

---

## Open Questions

1. **Performance**: Does running `qualify` add significant overhead?
   - Probably fine for typical queries
   - Could cache/skip if no implicit aliases detected

2. **Schema requirement**: Should we require schema for this to work, or be flexible?
   - Current: Flexible (no schema = expand everything)
   - Proposed: Keep flexible, but be smarter when schema IS provided

3. **Interaction with other transforms**: Does this need to run before or after cohort/pivot/etc?
   - Probably after most transforms, since those may create new CTEs with their own columns
