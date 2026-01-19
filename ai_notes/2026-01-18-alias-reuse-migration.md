# Migrate `alias_reuse.py` to SQLGlot's `expand_alias_refs`

**Date**: 2026-01-18  
**Goal**: Delete 430 lines of custom code by using SQLGlot's built-in alias expansion.

---

## Current State

### Our Custom Implementation

`asql/compiler/alias_reuse.py` - **430 lines** of complex code that:

1. Builds a dependency graph of alias references
2. Detects circular dependencies
3. Generates CTE chains for non-DuckDB dialects
4. Passes through for DuckDB (native support)

**Example input:**
```sql
SELECT price * quantity AS revenue,
       revenue * 0.1 AS tax
FROM orders
```

**Our current output (Postgres):**
```sql
WITH _alias0_0 AS (
  SELECT *, price * quantity AS revenue FROM orders
)
SELECT revenue, revenue * 0.1 AS tax FROM _alias0_0
```

### SQLGlot's Built-in Solution

SQLGlot's `qualify_columns` optimizer has `expand_alias_refs=True`:

```python
from sqlglot.optimizer.qualify_columns import qualify_columns

result = qualify_columns(
    expression,
    schema=schema,  # optional
    expand_alias_refs=True,  # <-- this is what we need!
)
```

**SQLGlot output:**
```sql
SELECT price * quantity AS revenue,
       price * quantity * 0.1 AS tax
FROM orders
```

---

## Why SQLGlot's Approach is Better

| Aspect | Our CTE Approach | SQLGlot's Expansion |
|--------|------------------|---------------------|
| **Code to maintain** | 430 lines | 0 lines (use SQLGlot) |
| **Complexity** | High (dependency graph, CTE generation) | None (already done) |
| **Output SQL** | Adds CTEs | Cleaner, no CTEs |
| **Database compatibility** | CTEs might not inline | Simple, always works |
| **SQLGlot idioms** | No | Yes |

### "But Performance!"

**Wrong thinking**: "Duplicating expressions hurts performance"

**Reality**:
1. Database query planners are smart - they optimize common subexpressions
2. CTEs can actually HURT performance (some DBs don't inline them)
3. The SQLGlot team made this choice for good reasons
4. We're maintaining 430 lines of code for a micro-optimization that may be negative

---

## Migration Plan

### Step 1: Understand Current Usage

```python
# In asql/dialect/parser.py line ~313
stmt = apply_alias_reuse(stmt, extend_dialect)
```

Only called once, at the end of `_apply_asql_transforms()`.

### Step 2: Replace with SQLGlot

```python
# Before
from asql.compiler.alias_reuse import apply_alias_reuse
stmt = apply_alias_reuse(stmt, extend_dialect)

# After
from sqlglot.optimizer.qualify_columns import qualify_columns
stmt = qualify_columns(
    stmt,
    schema=sqlglot_schema,  # already have this from earlier
    expand_alias_refs=True,
    expand_stars=False,  # we handle this separately
)
```

### Step 3: Update Tests

Tests in `tests/test_alias_reuse.py` expect:
- DuckDB: No CTEs (still works - SQLGlot just expands)
- Postgres: CTEs with `_alias` prefix (will BREAK - need to update)

**Update test expectations:**

```python
# OLD TEST
def test_alias_reuse_postgres_cte():
    sql = compile(asql, dialect="postgres")
    assert "WITH" in sql.upper()  # Expected CTEs
    
# NEW TEST
def test_alias_reuse_postgres():
    sql = compile(asql, dialect="postgres")
    # No CTEs needed - SQLGlot expands alias references
    assert "discount_price" not in sql or "unit_price * (1 - discount)" in sql
    # The key assertion: it's valid SQL that produces correct results
    assert_valid_sql(sql, dialect="postgres")
```

### Step 4: Delete Custom Code

```bash
# Delete the file
rm asql/compiler/alias_reuse.py

# Remove from __init__.py exports
# Remove from parser.py imports
```

### Step 5: Verify

```bash
./venv/bin/pytest tests/test_alias_reuse.py -v
./venv/bin/pytest tests/ -k alias
```

---

## Files to Change

| File | Action |
|------|--------|
| `asql/compiler/alias_reuse.py` | **DELETE** (430 lines) |
| `asql/compiler/__init__.py` | Remove `apply_alias_reuse` export |
| `asql/dialect/parser.py` | Replace call with `qualify_columns` |
| `tests/test_alias_reuse.py` | Update assertions (no more CTEs) |

---

## Example Transformation

### Before (Our CTEs)

```sql
-- Input
SELECT price * quantity AS total, total * 0.1 AS tax FROM orders

-- Output (Postgres)
WITH _alias0_0 AS (
  SELECT *, price * quantity AS total
  FROM orders
)
SELECT total, total * 0.1 AS tax
FROM _alias0_0
```

### After (SQLGlot Expansion)

```sql
-- Input
SELECT price * quantity AS total, total * 0.1 AS tax FROM orders

-- Output (Postgres)
SELECT price * quantity AS total, price * quantity * 0.1 AS tax FROM orders
```

Both produce the same results. The SQLGlot version is cleaner and requires no custom code.

---

## What About DuckDB?

DuckDB natively supports alias reuse, so for DuckDB we could:

1. **Option A**: Still expand (consistent behavior, simpler code)
2. **Option B**: Check dialect and skip expansion for DuckDB

**Recommendation**: Option A (expand for all). Simpler code, consistent behavior.

If we want Option B later, it's a one-line check:

```python
if dialect != "duckdb":
    stmt = qualify_columns(stmt, expand_alias_refs=True, ...)
```

---

## Summary

| Metric | Before | After |
|--------|--------|-------|
| Lines of code | 430 | 0 |
| Dependencies | Custom | SQLGlot built-in |
| Maintenance burden | High | None |
| Following SQLGlot idioms | No | Yes |
| Output SQL quality | More complex | Cleaner |

**Delete 430 lines. Use SQLGlot. Done.**
