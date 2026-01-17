# Failing Features Analysis
**Date**: 2024-12-24

## Summary

After running the full execution test suite against DuckDB and PostgreSQL 18.1, there are **61 xfailed tests**. However, most of these are **not unique failures** — they're the same 20 example files being tested twice (once per database) plus a few feature-specific tests.

The actual issues fall into **5 distinct categories**:

---

## 1. Multi-Query CTE Syntax (`stash as` across statements)

**Status**: ❌ Not implemented  
**Impact**: High - blocks complex analytics workflows  
**Tests**: `TestCTEExecution::test_simple_cte`, examples 03, 09, 14, 15, 17, 18, 19

### What Fails

```asql
from users
  where status = 'active'
  stash as active_users

from active_users   -- ❌ This second query can't reference the CTE
  select name
```

### Error

```
relation "active_users" does not exist
```

### Root Cause

The preparser handles `stash as` within a single query, but **multi-statement CTE references** (where a second `from` clause references a stashed result) aren't wired up. Each statement is parsed independently.

### Examples Affected

- `03_cte_with_aggregation.asql`
- `09_cohort_analysis.asql`
- `14_product_analytics.asql`
- `15_marketing_attribution.asql`
- `17_user_segmentation.asql`
- `18_revenue_recognition.asql`
- `19_retention_analysis.asql`

---

## 2. UNION Pipeline Syntax

**Status**: ❌ Not implemented  
**Impact**: Medium - alternative is standard SQL UNION  
**Tests**: `TestUnionExecution::test_simple_union`, example 08

### What Fails

```asql
from customers_us select name
union
from customers_eu select name   -- ❌ Preparser doesn't understand this
```

### Error

```
Pre-parsed: SELECT name union from customers_eu select name from customers_us
            ^^^ Garbled output
```

### Root Cause

The preparser rearranges `from ... select` but doesn't handle `union` as a statement combinator. It produces malformed SQL.

### Workaround

Use standard SQL:
```sql
SELECT name FROM customers_us
UNION
SELECT name FROM customers_eu
```

---

## 3. Nested `when/then` Expressions

**Status**: 🐛 Bug in preparser  
**Impact**: Medium - single-level works fine  
**Tests**: `TestTernaryExecution::test_nested_when_then`

### What Fails

```asql
when age < 18 then 'minor' 
otherwise when age >= 65 then 'senior'   -- ❌ Nested when breaks
otherwise 'adult'
```

### Error

```
Pre-parsed: CASE WHEN age < 18 THEN 'minor' ELSE CASE END WHEN age >= 65 ...
                                                  ^^^^^^^^ Wrong CASE END placement
```

### Root Cause

The `when/then` → `CASE/WHEN` transformation doesn't handle recursion. It closes the inner CASE prematurely.

### Workaround

Use standard SQL CASE:
```asql
case 
  when age < 18 then 'minor'
  when age >= 65 then 'senior'
  else 'adult'
end as category
```

---

## 4. `with name = from` CTE Syntax

**Status**: 🚫 Intentionally not supported  
**Impact**: Medium  

We intentionally do **not** support ASQL-only `with name = from ...` sugar. Use one of:

- `stash as` (ASQL-native)
- standard SQL `WITH name AS (SELECT ...)` (portable)

---

## 5. Subqueries with `from` Inside `exists()`

**Status**: ❌ Not implemented  
**Impact**: Low - uncommon pattern  
**Tests**: Example 20

### What Fails

```asql
where exists (
  from order_items as oi2       -- ❌ from inside exists()
  where oi2.order_id = orders.order_id
)
```

### Error

```
Expecting ). Line 11, Col: 11.
```

### Root Cause

The preparser doesn't handle `from` clauses nested inside SQL expressions like `exists()`.

---

## 6. Example Files Using Double Quotes for Strings

**Status**: ⚠️ Style issue, not a bug  
**Impact**: Low  
**Tests**: Most example `test_example_syntax_valid` tests

### What Happens

Many example files use double quotes for strings:
```asql
where status = "completed"   -- Double quotes = identifier in SQL
```

SQL standard treats `"completed"` as an **identifier** (column name), not a string literal. SQLGlot follows the standard.

### Fix

Update examples to use single quotes:
```asql
where status = 'completed'
```

---

## Priority Ranking

| Priority | Feature | Reason |
|----------|---------|--------|
| 🔴 **P1** | Multi-query CTEs | Blocks real analytics workflows |
| 🟠 **P2** | Nested when/then | Bug in existing feature |
| 🟠 **P2** | `with name = from` syntax | Alternative CTE syntax (intentionally not supported) |
| 🟡 **P3** | UNION pipeline | Has workaround (standard SQL) |
| 🟢 **P4** | Subqueries with `from` | Edge case |

---

## What's Working Well ✅

The core ASQL features all pass on **both DuckDB and PostgreSQL**:

- `from table` pipeline syntax
- `select`, `where`, `order by`, `limit`
- `group by ... ()` aggregation syntax
- `#` shorthand for `count(*)`
- JOINs with `&` and `&?`
- Window functions
- `when/then` (single-level)
- `contains`, `starts with`, `ends with`
- `??` (coalesce)
- `@date` literals
- Alias reuse (CTE chain generation)
- Slice syntax `name[1:5]`
- Spine/gap-filling

