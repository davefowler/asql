# ASQL Compile Transforms: Analysis and Migration Plan

**Date**: 2026-01-18  
**Updated**: 2026-01-18 (incorporated findings from `2026-01-18-sqlglot-settings-investigation.md`)  
**Purpose**: Document each post-parse transform in `asql.compile()`, explain why it exists outside SQLGlot's standard dialect system, and propose how to migrate it.

## Overview

`asql.compile()` currently applies **12+ AST transforms** after parsing with the ASQL dialect. This means users cannot use standard SQLGlot calls like `sqlglot.transpile(query, read="asql", write="postgres")` - they must use `asql.compile()`.

The goal is to move all transforms into the dialect system so that standard SQLGlot calls "just work."

**Key insight**: SQLGlot's `dialect.settings` system provides a clean way to pass configuration through the transpile pipeline. Settings can be passed via dialect constructor (`ASQL(auto_spine=False)`) and/or inline SET statements. This solves what was thought to be a major blocker.

---

## Transform Inventory

**Status**: All transforms are now called from `ASQLParser._apply_asql_transforms()` in `asql/dialect/parser.py`. The `asql/compiler/api.py` is just a thin wrapper around `sqlglot.transpile()`.

| # | Transform | File | Schema Required? | Dialect Dependent? | Settings? |
|---|-----------|------|------------------|-------------------|-----------|
| 1 | Underscore shorthands (`days_since_col`) | `underscore_shorthands.py` | Optional | No | No |
| 2 | Implicit function aliases (`sum_amount`) | `underscore_shorthands.py` | Optional | No | No |
| 3 | Auto-aliasing (`count(*) → num`) | `auto_alias.py` | No | No | Yes |
| 4 | FK shorthand (`ON user_id`) | `join_fk_shorthand.py` | Yes | No | Yes |
| 5 | Cohort transform | `cohort_transform.py` | Optional | No | No |
| 6 | Pivot fallback (CASE/WHEN) | `pivot_fallback.py` | Optional | **Yes** | Yes |
| 7 | Explode fallback (Snowflake) | `explode_fallback.py` | No | **Yes** | No |
| 8 | Column operators fallback | `column_operators.py` | **Yes** | **Yes** | Yes |
| 9 | Auto-spine (gap filling) | `auto_spine.py` | Optional | **Yes** | Yes |
| 10 | Auto-qualify columns | `auto_qualify.py` | No | No | No |
| 11 | Alias reuse (CTE chain) | `alias_reuse.py` | No | **Yes** | No |
| 12 | SQLGlot optimizer pass | (built-in) | Optional | **Yes** | No |

---

## Detailed Analysis

### 1. Underscore Shorthands (`days_since_col`)

**Location**: `asql/compiler/underscore_shorthands.py:apply_since_until_underscore_shorthands`  
**Called from**: `asql/dialect/parser.py:_apply_asql_transforms()`

**What it does**: Expands `days_since_created_at` → `DATEDIFF(DAY, created_at, CURRENT_DATE)`

**Why outside SQLGlot**:
- This is a **column identifier → function call** rewrite based on naming patterns
- SQLGlot parsers identify tokens, not semantic patterns in identifiers
- Requires optional schema awareness (if schema says `days_since_created_at` is a real column, don't expand)

**Current status**:
```
✅ ALREADY IN DIALECT (parser._apply_asql_transforms)
```
This transform is already called from the parser's post-parse hook. The implementation is conservative:
- Only expands if single FROM table can be determined
- For piped queries (CTEs), doesn't expand if CTE isn't in schema

**Complexity**: Low (already implemented correctly)

---

### 2. Implicit Function Aliases (`sum_amount`)

**Location**: `asql/compiler/underscore_shorthands.py:apply_implicit_function_aliases`  
**Called from**: `asql/dialect/parser.py:_apply_asql_transforms()`

**What it does**: In SELECT, `sum_amount` → `SUM(amount) AS sum_amount`

**Why outside SQLGlot**:
- Same as #1: identifier → function call based on naming convention
- Only applies in SELECT projection context
- Schema-aware: if `sum_amount` is a real column, don't expand

**Current status**:
```
✅ ALREADY IN DIALECT (parser._apply_asql_transforms)
```
Already called from parser's post-parse hook.

**Column tracking limitation**: Current implementation uses simple schema lookup (`_single_from_table_name`). For piped queries:
```sql
from orders group by region (sum_amount)  -- Stage 1: EXPANDS (sum_amount not in schema)
| where sum_amount > 1000                  -- Stage 2: Doesn't expand (CTE not in schema, conservative)
```
This is "correct by accident" - it doesn't expand in stage 2 because the CTE `_stage1` isn't found in the schema. A more robust solution would use SQLGlot's `qualify.qualify()` to track columns through CTEs.

**Note**: `asql/column_tracking.py` uses `sqlglot.optimizer.qualify` for the visual editor's column dropdowns, but the underscore shorthand transform doesn't use this yet.

**Complexity**: Low (already works, could be improved with SQLGlot qualify)

---

### 3. Auto-aliasing (`count(*) → num`)

**Location**: `asql/compiler/auto_alias.py:apply_auto_aliasing`

**What it does**: Adds aliases to bare function calls:
- `count(*)` → `count(*) AS num`  
- `sum(amount)` → `sum(amount) AS sum_amount`
- Supports Jinja templates for custom patterns

**Why outside SQLGlot**:
- This is a **convention-based semantic transform**, not syntax parsing
- Requires user-configurable templates via settings

**Migration proposal**:
```
✅ CAN MOVE TO DIALECT
```
SQLGlot's `dialect.settings` system handles this perfectly:
- Settings passed via dialect constructor: `ASQL(alias_template="{func}_{col}")`
- Inline SET statements mutate `self.dialect.settings`
- Transforms read settings via `self.dialect.settings.get("alias_template")`

Move to `ASQLParser._apply_asql_transforms()` which has access to `self.dialect.settings`.

**Complexity**: Low (settings plumbing solved)

---

### 4. FK Shorthand (`ON user_id`)

**Location**: `asql/compiler/join_fk_shorthand.py:transform_fk_shorthand`

**What it does**: 
- `JOIN orders ON user_id` → `JOIN orders ON users.user_id = orders.user_id`
- Auto-infers join keys from schema relationships

**Why outside SQLGlot**:
- Requires **ASQL schema with relationships** (not just column types)
- SQLGlot's `MappingSchema` is table/column/type only - no FK relationships
- Convention-based guessing (`users` + `user_id` pattern)

**Migration proposal**:
```
✅ CAN MOVE TO DIALECT (schema via dialect.settings)
```
- Schema passed via `ASQL(schema=my_schema)` or `dialect.settings["schema"]`
- Parser already handles syntax (`ON user_id` parses to `exp.Column`)
- Transform expands at generate time, reads schema from dialect.settings

**Remaining work**: Define ASQL's schema model for FK relationships (SQLGlot's `MappingSchema` is column/type only).

**Complexity**: Medium (schema model design)

---

### 5. Cohort Transform

**Location**: `asql/compiler/cohort_transform.py:transform_cohort`

**What it does**: Expands `COHORT BY month(signup_date) ON user_id` into:
- 2 CTEs (`cohort_base`, `cohort_sizes`)
- JOINs with the main query
- Modified GROUP BY/SELECT

**Why outside SQLGlot**:
- This is a **macro expansion** that generates substantial SQL
- Not a 1:1 syntax mapping - one clause → multiple CTEs + JOINs
- Requires schema for join key inference

**Migration proposal**:
```
✅ CAN MOVE TO DIALECT
```
The parser already stores `_cohort_info` on the AST. The transform:
1. Reads `_cohort_info` attribute
2. Builds CTEs and modifies the AST
3. Removes the attribute

This can move to `ASQLDialect._apply_asql_transforms()` which runs post-parse.

**Complexity**: Low (already attribute-based)

---

### 6. Pivot Fallback (CASE/WHEN)

**Location**: `asql/compiler/pivot_fallback.py:transform_pivot_for_dialect`

**What it does**: For dialects without native PIVOT (Postgres, MySQL, SQLite):
```sql
-- ASQL input
PIVOT sum(amount) FOR category IN ('A', 'B')

-- Output (Postgres)
SUM(CASE WHEN category = 'A' THEN amount END) AS A,
SUM(CASE WHEN category = 'B' THEN amount END) AS B
```

**Why outside SQLGlot**:
- SQLGlot **can parse PIVOT** but **cannot transpile** it to CASE/WHEN
- This is a missing SQLGlot feature, not an ASQL-specific transform
- Requires knowing pivot values (from query or schema)

**Migration proposal**:
```
🔶 COULD BE UPSTREAM SQLGLOT CONTRIBUTION
```
This belongs in SQLGlot itself:
- Add `Generator._generate_pivot_fallback()` method
- Dialect generators call it when they don't support native PIVOT

**Short-term**: Move to ASQL generator's pre-processing hook.

**Complexity**: Medium (dialect-aware transform)

---

### 7. Explode Fallback (Snowflake FLATTEN)

**Location**: `asql/compiler/explode_fallback.py:transform_explode_for_dialect`

**What it does**: Rewrites `CROSS JOIN UNNEST(array) AS item` for Snowflake:
```sql
-- Standard SQL
CROSS JOIN UNNEST(tags) AS tag

-- Snowflake
CROSS JOIN (SELECT value AS tag FROM TABLE(FLATTEN(INPUT => tags))) AS _tag_exploded
```

**Why outside SQLGlot**:
- Snowflake uses `FLATTEN()` table function, not `UNNEST`
- SQLGlot doesn't auto-transpile UNNEST → FLATTEN
- This is a **dialect-specific rewrite**

**Migration proposal**:
```
🔶 SHOULD BE UPSTREAM SQLGLOT
```
This is exactly what SQLGlot's transpiler should do:
- When generating Snowflake SQL from UNNEST → emit FLATTEN

**Short-term**: Move to ASQL's Snowflake-aware generator subclass.

**Complexity**: Low (simple dialect check)

---

### 8. Column Operators Fallback

**Location**: `asql/compiler/column_operators.py:transform_column_operators_for_dialect`

**What it does**: For dialects without `EXCEPT`/`REPLACE` (Postgres, MySQL):
```sql
-- ASQL input
SELECT * EXCEPT(password) FROM users

-- Output (Postgres, with schema)
SELECT id, name, email FROM users
```

**Why outside SQLGlot**:
- Requires **schema** to know what columns `*` expands to
- SQLGlot's `qualify_columns()` with `expand_stars=True` actually does this!
- We're just calling SQLGlot's optimizer with our schema

**Migration proposal**:
```
✅ ALREADY USES SQLGLOT
```
This transform is already a thin wrapper around `sqlglot.optimizer.qualify_columns()`.

Just need to call it from the right place (generator pre-process or dialect post-parse).

**Complexity**: Low (already implemented correctly)

---

### 9. Auto-spine (Gap Filling)

**Location**: `asql/compiler/auto_spine.py:_apply_auto_spine`

**What it does**: Adds CTEs that ensure GROUP BY results include all expected values:
```sql
-- ASQL input (with auto_spine=true)
FROM orders GROUP BY month(order_date) (sum(amount))

-- Output: Adds spine CTE for all months + LEFT JOIN
WITH _spine_0 AS (
  SELECT generate_series(MIN(order_date), MAX(order_date), '1 month')::date AS month
  FROM orders
)
SELECT ... FROM _spine_0 LEFT JOIN (original query) ...
```

**Why outside SQLGlot**:
- **Massive macro expansion** - generates CTEs, date ranges, LEFT JOINs
- Schema-aware for categorical columns (need distinct values)
- Dialect-aware for date generation (`generate_series` vs `SEQUENCE`)
- Controlled by `CompileSettings.auto_spine`

**Migration proposal**:
```
⚠️ KEEP SEPARATE - TOO COMPLEX FOR DIALECT
```
This is fundamentally a **semantic transform**, not syntax transpilation:
- It changes query semantics (adds rows that weren't there)
- Requires understanding of the data model
- User-controllable via settings

**Recommendation**: Keep as explicit compiler transform. Document that this requires `asql.compile()`.

**Complexity**: Very High (most complex transform)

---

### 10. Auto-qualify Columns

**Location**: `asql/compiler/auto_qualify.py:auto_qualify_columns`

**What it does**: Expands `SELECT *` in JOINs to `SELECT t1.*, t2.*`:
```sql
-- Input
SELECT * FROM users JOIN orders

-- Output  
SELECT users.*, orders.* FROM users JOIN orders
```

**Why outside SQLGlot**:
- SQLGlot has `qualify_columns()` but it requires schema
- This is a **schema-free heuristic** for disambiguating stars in joins

**Migration proposal**:
```
✅ CAN MOVE TO DIALECT
```
Move to generator's pre-processing or dialect post-parse hook.

**Complexity**: Low (simple AST walk)

---

### 11. Alias Reuse (CTE Chain)

**Location**: `asql/compiler/alias_reuse.py:apply_alias_reuse`

**What it does**: Allows referencing earlier SELECT aliases:
```sql
-- ASQL input
SELECT price * quantity AS total, total * 0.1 AS tax FROM orders

-- Output (non-DuckDB)
WITH _alias0_0 AS (SELECT *, price * quantity AS total FROM orders)
SELECT total, total * 0.1 AS tax FROM _alias0_0
```

**Why outside SQLGlot**:
- DuckDB supports this natively; others need CTE rewrite
- Requires **dependency graph analysis** of alias references
- Dialect-dependent output

**Migration proposal**:
```
✅ CAN MOVE TO DIALECT
```
Move to generator pre-processing:
- For DuckDB: emit as-is
- For others: generate CTE chain

**Complexity**: Medium (dependency analysis)

---

### 12. SQLGlot Optimizer Pass

**Location**: `asql/compiler/api.py` (inline call to `sqlglot_optimize`)

**What it does**: Runs `eliminate_ctes` and `simplify` optimizations:
- Removes unused CTEs
- Simplifies boolean expressions

**Why outside SQLGlot**:
- This IS SQLGlot! Just not called by default in `transpile()`
- We call it explicitly with a restricted rule set

**Migration proposal**:
```
✅ ALREADY SQLGLOT
```
This is fine where it is. Could be called from generator's post-process.

**Complexity**: None (already uses SQLGlot)

---

## Migration Status

**UPDATE 2026-01-18**: All transforms have been moved to `ASQLParser._apply_asql_transforms()`.

### ✅ Already in Parser (Complete)

All transforms are called from `parser._apply_asql_transforms()`:

1. 🔄 **Underscore shorthands** - `apply_since_until_underscore_shorthands()` (refactoring to optimizer phase)
2. 🔄 **Implicit function aliases** - `apply_implicit_function_aliases()` (refactoring to optimizer phase)

   **Both #1 and #2** are being refactored together - see `2026-01-18-implicit-function-aliases-refactor.md`
3. ✅ **Auto-aliasing** - `apply_auto_aliasing()`
4. ✅ **FK shorthand** - `transform_fk_shorthand()` (needs schema)
5. ✅ **Cohort transform** - `transform_cohort()`
6. ✅ **Pivot fallback** - `transform_pivot_for_dialect()` (needs extend_dialect)
7. ✅ **Explode fallback** - `transform_explode_for_dialect()` (needs extend_dialect)
8. ✅ **Column operators** - `transform_column_operators_for_dialect()` (needs schema + dialect)
9. ✅ **Auto-spine** - `_apply_auto_spine()` (needs auto_spine=True + dialect)
10. ✅ **Auto-qualify columns** - `auto_qualify_columns()`
11. ✅ **Alias reuse** - `apply_alias_reuse()` (needs extend_dialect)

---

## What `asql.compile()` Still Does (Kill List)

### ✅ DONE - Simplified `asql/compiler/api.py`

The file has been dramatically simplified. Here's what was removed:

| # | Function | Status |
|---|----------|--------|
| 1 | **CompileSettings → dialect kwargs** | ✅ DELETED (kept minimal compat shim) |
| 2 | **Dialect alias normalization** | ✅ DELETED |
| 3 | **Extract dialect from comment** | ✅ DELETED |
| 4 | **Validate dialect features** | ✅ DELETED |
| 5 | **SQLGlot optimizer** | ✅ DELETED |
| 6 | **List comprehension fixes** | ✅ DELETED (TODO: move to generator) |
| 7 | **Filter SET statements from output** | ✅ DELETED |
| 8 | **`_is_valid_sql_statement()`** | ✅ DELETED |

### In Progress 🔄

- **Underscore shorthands** (both `sum_amount` and `days_since_col`) → Moving to optimizer phase (another agent)

### Remaining TODO

- **List comprehension fixes** → Should move to ASQL generator (dialect-specific)

---

## Current State of `asql.compile()`

Now just ~100 lines - a thin wrapper around `sqlglot.transpile()`:

```python
def compile(asql_query, dialect=None, pretty=False, settings=None, **kwargs):
    """Thin wrapper around sqlglot.transpile()."""
    # Build dialect settings
    dialect_settings = {}
    if settings:  # Legacy CompileSettings support
        # ... extract settings ...
    dialect_settings.update(kwargs)
    
    if dialect:
        dialect_settings["extend_dialect"] = dialect
    
    asql_dialect = ASQL(**dialect_settings)
    output_dialect = dialect or "duckdb"
    
    results = sqlglot.transpile(asql_query, read=asql_dialect, write=output_dialect, pretty=pretty)
    return ";\n\n".join(r for r in results if r)
```

**Users should prefer direct SQLGlot API:**

```python
from asql.dialect import ASQL
import sqlglot

# Simple
sql = sqlglot.transpile(query, read="asql", write="postgres")[0]

# With settings
asql = ASQL(extend_dialect="postgres", auto_spine=False)
sql = sqlglot.transpile(query, read=asql, write="postgres")[0]
```

---

### Future Enhancement: Better Column Tracking

The underscore shorthand transforms use simple schema lookup. For piped queries, could be improved with `sqlglot.optimizer.qualify` to properly track columns through CTEs (see `2026-01-18-implicit-function-aliases-refactor.md`)

---

## Architecture: Goal State

**Goal**: `sqlglot.transpile()` should work directly. `asql.compile()` becomes unnecessary.

```
┌─────────────────────────────────────────────────────────────────┐
│  User Code                                                      │
│                                                                 │
│  from asql.dialect import ASQL                                  │
│  import sqlglot                                                 │
│                                                                 │
│  asql = ASQL(extend_dialect="postgres", auto_spine=False)       │
│  sql = sqlglot.transpile(query, read=asql, write="postgres")[0] │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     sqlglot.transpile()                         │
│                                                                 │
│  ┌────────────────────────┐    ┌──────────────────────────┐   │
│  │   ASQL Parser          │    │    Target Generator      │   │
│  │                        │    │                          │   │
│  │ • Parse ASQL syntax    │    │ • Standard SQL output    │   │
│  │ • Process SET stmts    │───>│ • Pivot fallback         │   │
│  │ • All ASQL transforms  │    │ • Explode fallback       │   │
│  │   via _apply_asql_     │    │ • List comprehension fix │   │
│  │   transforms()         │    │                          │   │
│  │                        │    │                          │   │
│  │ Settings via:          │    │                          │   │
│  │  dialect.settings      │    │                          │   │
│  └────────────────────────┘    └──────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

NO asql.compile() needed!
```

---

## Open Questions

1. ~~**Settings passing**: How do we pass `CompileSettings` through SQLGlot's API?~~  
   **✅ SOLVED**: Use `dialect.settings`! SQLGlot natively supports settings via:
   - Dialect constructor: `ASQL(auto_spine=False, week_start="sunday")`
   - Parser mutates `self.dialect.settings` for inline SET statements
   - Transforms read via `self.dialect.settings.get("setting_name")`
   - See `ai_notes/2026-01-18-sqlglot-settings-investigation.md` for details.

2. **Schema relationships**: Should we extend SQLGlot's schema model or keep ASQL's separate?
   - SQLGlot's `MappingSchema` is column/type focused
   - ASQL needs FK relationships for join inference
   - Schema can be passed via `dialect.settings["schema"]`

3. **Auto-spine**: Is this too magical for standard transpile?
   - It changes query semantics significantly
   - Maybe always require explicit `asql.compile()` call

---

## Success Criteria

After migration:

```python
# This works for most ASQL queries:
sql = sqlglot.transpile(asql_query, read="asql", write="postgres")[0]

# For custom settings, pass them to the dialect constructor:
from asql.dialect import ASQL

asql = ASQL(
    auto_spine=False,
    week_start="sunday",
    alias_prefixes={"count": "num", "sum": "total"},
)
sql = sqlglot.transpile(asql_query, read=asql, write="postgres")[0]

# Or use inline SET statements in the query itself:
query = """
SET auto_spine = false;
SET week_start = 'sunday';
from orders group by week(created_at) (count(*))
"""
sql = sqlglot.transpile(query, read="asql", write="postgres")[0]

# Only need asql.compile() for:
# - Auto-spine gap filling (semantic transform, changes query meaning)
sql = asql.compile(asql_query, dialect="postgres", auto_spine=True)
```
