# ASQL + dbt: Capturing 80% of Macro Value with a Portable Analytic Language Layer

## Summary

This document proposes a focused scope for ASQL as a dbt-native analytic query language that replaces the majority of commonly used dbt macros by elevating them into first-class language capabilities, while intentionally leaving dbt's orchestration, materialization, and runtime responsibilities untouched.

The goal is not to replace dbt macros wholesale, but to:
- eliminate the most common SQL-shape macros,
- reduce Jinja complexity,
- standardize portable analytic semantics,
- and dramatically simplify dbt model code.

This approach targets ~80% of practical macro value with ~20% of the complexity of fully re-implementing dbt's adapter and runtime system.

---

## Design Principles

1. **ASQL is a query language, not a build system**
   - dbt remains responsible for:
     - DAG construction
     - materializations
     - incremental logic
     - environment/target handling
     - testing and execution

2. **ASQL has full dbt context**
   - Access to:
     - manifest.json
     - catalog.json
     - schema metadata
     - adapter / target identity
   - Enables informed compilation without Jinja introspection hacks.

3. **Replace SQL-shape macros, not runtime macros**
   - If a macro's output is "just SQL", ASQL should own it.
   - If a macro depends on dbt execution context, it stays in dbt.

4. **Portability via semantic compilation**
   - ASQL defines intent.
   - Compilation selects an implementation strategy per warehouse.

---

## Macro Value Decomposition

In practice, widely used dbt macros fall into three categories:

### A) SQL-shape generators (high-value, low-risk)

These macros exist to reduce verbosity or repetition in SQL.

Examples:
- star / except / rename
- union_relations
- date_spine / generate_series
- surrogate_key
- pivot / unpivot
- deduplicate

These are prime ASQL targets.

### B) Adapter/capability dispatch (medium value, medium risk)

Macros that hide differences between warehouses:
- function availability
- syntax differences
- feature presence

ASQL can absorb a bounded subset of this by owning a portable analytic standard library.

### C) Runtime / orchestration macros (out of scope)

Macros tied to dbt's execution lifecycle:
- ref, source
- materializations
- is_incremental
- run_query
- testing frameworks

These remain dbt's responsibility.

---

## Proposed ASQL Capabilities (80% Coverage Set)

### 1. Column Set Operators (replaces star, except, rename macros)

**Problem today**
- dbt models littered with long SELECT lists
- `dbt_utils.star()` calls everywhere
- renaming/prefixing boilerplate

**ASQL capability**

Since ASQL defaults to `select *`, column modifiers are standalone pipeline operators:

```asql
# Exclude sensitive columns
from users
except email, phone, ssn

# Rename columns
from users
rename id as user_id

# Prefix all columns (useful after joins)
from users
prefix user_

# Combine operators in a pipeline
from users
join orders on users.id = orders.user_id
except users.email, orders.internal_notes
rename users.id as user_id
prefix orders.* with order_
```

**Compilation**
- Uses schema metadata from catalog.json
- Deterministic column ordering
- Produces explicit SELECT lists in compiled SQL

**Value**
- Removes one of the most-used macro families
- Cleaner pipeline-style syntax (no `select *` needed)
- Improves readability and diff stability

---

### 2. Relation Union with Schema Alignment (replaces union_relations)

**Problem today**
- Unioning heterogeneous tables requires macros to:
  - align columns
  - fill missing fields with NULL
  - normalize types

**ASQL capability**

A semantic union operator:

```asql
from union(users_2022, users_2023, users_2024)
```

Optional controls:

```asql
from union(relations, fill_missing = null)
```

**Compilation**
- Reads schemas from catalog
- Produces aligned SELECTs + UNION ALL
- Enforces consistent ordering

**Value**
- Major ETL simplification
- Eliminates brittle Jinja logic

---

### 3. Series / Spine Primitives (replaces date_spine, generate_series)

**Problem today**

Time series data often has gaps. If you have sales data but no sales on Jan 3rd, that day is invisible in your results. A "spine" is a complete sequence you join against to fill these gaps.

Different warehouses handle this completely differently:
- Postgres: `generate_series()`
- BigQuery: `GENERATE_DATE_ARRAY()`
- Snowflake: Recursive CTE or `GENERATOR()`
- Redshift: Numbers table hack

dbt's `dbt_utils.date_spine()` abstracts this with verbose Jinja.

**ASQL capability**

Semantic generators as table sources:

```asql
# Date spine - generates a row for each day/week/month/etc
from date_spine(start = '2020-01-01', end = today(), grain = day)

# Numeric series
from series(1, 100)
```

**Fill operator for grouped data:**

After a group by on a date column, use `fill` to complete the sequence:

```asql
from orders
group by date_trunc(created_at, month) as month
aggregate sum(amount) as revenue
fill month                        # auto-detect range from data, NULL for gaps

fill month with {revenue: 0}      # specify defaults for filled rows
```

**Range detection:**

By default, `fill` auto-detects the range from your actual data using `MIN()`/`MAX()` of the grouped column. This handles 90%+ of use cases with zero configuration.

For rare cases where you need explicit bounds (e.g., always show full year, include future months):

```asql
fill month start '2024-01-01' stop '2024-12-01'
fill month start '2024-01-01' stop today()
fill month with {revenue: 0} start '2024-01-01' stop '2024-12-01'
```

Both `start` and `stop` are **inclusive** (like SQL's `BETWEEN`). This matches how analysts naturally think: "from January to December" includes December.

We use `start`/`stop` instead of `from`/`to` to avoid confusion with the `from` clause.

**Future consideration:** We could potentially infer bounds from WHERE clauses (e.g., `where created_at >= '2024-01-01'`), but this adds compilation complexity and edge cases. For now, auto-detect from data is simpler and covers most needs.

**Compilation strategies**
- Native generate_series where available
- Numbers tables / CTE fallbacks otherwise

**Value**
- Standardizes time-series modeling
- Centralizes portability logic
- One-word opt-in for complete date sequences

**Why not auto-spine all date groups?**

We considered making all date-grouped queries automatically fill gaps, but rejected it:
- Changes row counts unexpectedly
- Not always desired (sparse data is sometimes intentional)
- Hard to reason about

Explicit `fill` is better — one word to opt-in, no surprises.

---

### 4. Surrogate Key Semantics (replaces surrogate_key, generate_surrogate_key)

**Problem today**
- Every project rolls its own hashing logic
- Subtle inconsistencies in null handling
- One of the most-used dbt macros

**ASQL capability**

First-class key constructor:

```asql
select key(user_id, order_id) as order_key
```

**Defined semantics**
- Stable hashing algorithm
- Explicit null treatment (nulls hash consistently)
- Type normalization before hashing

**Compilation**
- Maps to warehouse-appropriate hash functions
- Handles delimiter injection and null representation

**Value**
- Consistency across models and teams
- Removes fragile macro code

---

### 5. Pivot / Unpivot Operators

**Problem today**
- Extremely verbose and dialect-specific SQL
- Heavy macro usage
- Common pain point with SaaS data (Jira, Salesforce, HubSpot)

**ASQL capability**

Semantic reshaping:

```asql
# Pivot: rows to columns
from sales
pivot amount by category

# Unpivot: columns to rows
from monthly_metrics
unpivot jan, feb, mar, apr into month, value
```

**Killer use case: Denormalizing custom fields**

Many SaaS platforms store custom fields in Entity-Attribute-Value (EAV) tables:

```
# Jira's issue_custom_field table:
| issue_id | field_name   | field_value |
|----------|--------------|-------------|
| PROJ-123 | priority     | High        |
| PROJ-123 | sprint       | Sprint 5    |
| PROJ-123 | story_points | 8           |
```

With ASQL pivot:

```asql
from issue_custom_fields
pivot field_value by field_name
```

Produces:

```
| issue_id | priority | sprint   | story_points |
|----------|----------|----------|--------------|
| PROJ-123 | High     | Sprint 5 | 8            |
```

This replaces hundreds of lines of Jinja in Fivetran dbt packages.

**Dynamic pivot (values from query):**

```asql
from sales
pivot amount by category from (select distinct category from products)
```

**Compilation**
- Native PIVOT/UNPIVOT where supported (Snowflake, BigQuery, SQL Server)
- CASE/WHEN + GROUP BY fallback elsewhere

**Value**
- High leverage for analytics teams
- Strong justification for ASQL adoption
- Eliminates most complex dbt package code

---

### 6. Deduplicate Operator (replaces dedup macros)

**Problem today**

Deduplication is extremely common but verbose:

```sql
-- Standard pattern
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY user_id, event_type 
    ORDER BY created_at DESC
  ) as rn
  FROM events
)
SELECT * FROM ranked WHERE rn = 1
```

**ASQL capability**

```asql
from events
deduplicate by user_id, event_type
order by created_at desc    # keep most recent
```

**Compilation**
- `QUALIFY ROW_NUMBER() = 1` where supported
- CTE + filter pattern elsewhere

**Value**
- Extremely common pattern made trivial
- Clear intent vs. opaque window function logic

---

### 7. Null Coalescing Operator (`??`)

**Problem today**

SQL's `COALESCE()` is verbose and doesn't compose well:

```sql
SELECT COALESCE(COALESCE(first_name, nickname), 'Anonymous')
```

**ASQL capability**

The `??` operator provides null coalescing (matching JavaScript, C#, Swift, PHP, PRQL):

```asql
# Simple default
select name ?? 'Unknown'

# Chain multiple fallbacks
select first_name ?? nickname ?? 'Anonymous'

# Works with any expression
select revenue ?? 0
select config.timeout ?? 30
```

**Why `??` instead of `||`?**
- `||` means string concatenation in SQL — using it for coalescing would confuse SQL users
- `??` is the standard null coalescing operator in modern languages
- `??` is specifically for NULL, not falsy values (in JS, `0 || 5` returns `5`, but `0 ?? 5` returns `0`)

**Compilation**
- Compiles to `COALESCE(a, b)` or nested `COALESCE` for chains

---

### 8. Safe Casting with Defaults

**Problem today**

Type casting fails hard on dirty data:

```sql
-- This errors if ANY row has non-numeric data
SELECT CAST(user_input AS INTEGER) FROM form_submissions
```

Real-world data is messy: `"N/A"`, empty strings, `"$100"` — all cause errors.

Different warehouses handle this differently:
- BigQuery: `SAFE_CAST(x AS INT64)`
- Snowflake: `TRY_CAST(x AS INTEGER)`
- Postgres: No native safe cast (need CASE/regex)

**ASQL capability**

Casting is strict by default (SQL compatible), with easy safe mode via `?` suffix:

```asql
# Strict cast - errors on failure (default, SQL-compatible)
select value::integer

# Safe cast - returns NULL on failure
select value::integer?

# Safe cast with default (using ?? null coalescing)
select value::integer ?? 0
```

**How it works:**
- `value::integer` — strict, errors if value can't be cast
- `value::integer?` — safe, returns NULL if cast fails (shorthand for `?? null`)
- `value::integer ?? 0` — the `??` triggers safe mode AND provides the default

**Compilation**

```sql
-- value::integer
CAST(value AS INTEGER)

-- value::integer?
TRY_CAST(value AS INTEGER)  -- or SAFE_CAST, or CASE fallback

-- value::integer ?? 0
COALESCE(TRY_CAST(value AS INTEGER), 0)
```

**Value**
- Strict by default maintains SQL compatibility
- `?` suffix is intuitive ("try this, might not work")
- `??` both triggers safe mode AND provides default — elegant composition
- No need for separate `try_cast()` or `safe_cast()` functions

---

### 9. Portable Analytic Standard Library (bounded scope)

**Goal**

Provide a small, opinionated stdlib for analytics that handles capability dispatch.

**Date/Time functions:**

```asql
select now()                              # current timestamp
select today()                            # current date
select date_trunc(created_at, month)      # truncate to grain
select date_add(created_at, 7, day)       # date arithmetic
select date_diff(end_date, start_date, day)
```

**String functions:**

```asql
select split(email, '@')[1] as domain     # array access on split
select left(name, 10)
select trim(value)
```

**Math functions:**

```asql
select safe_divide(revenue, users)        # returns NULL instead of divide-by-zero
select round(value, 2)
select percentile(value, 0.95)
```

**Key constraint**
- Only functions with clear, stable semantics
- No attempt to cover everything SQL can do
- Errors when semantics cannot be preserved on target

**Compilation**
- Capability-aware mapping per dialect
- Clear error messages when unsupported

---

### 10. Group By Shorthand

**Problem today**

Repeating grouped columns is tedious and error-prone:

```sql
SELECT 
  date_trunc('month', created_at),
  category,
  region,
  SUM(amount)
FROM orders
GROUP BY 1, 2, 3  -- or worse, repeat all columns
```

**ASQL capability**

Since ASQL separates `group` from `aggregate`, this is already solved:

```asql
from orders
group by date_trunc(created_at, month), category, region
aggregate sum(amount) as total
```

But we could also support positional shorthand:

```asql
from orders
select date_trunc(created_at, month), category, region, sum(amount)
group 1, 2, 3
```

---

## Explicitly Out of Scope

ASQL intentionally does not replace:
- dbt materializations
- incremental model logic
- ref/source resolution
- macro-based tests
- adapter plugins
- execution-time branching

ASQL remains:

> **a semantic query language, not a build framework**

---

## Architecture Summary

```
ASQL
 ├─ Semantic operators (except, pivot, deduplicate, fill)
 ├─ Expressive operators (?? for coalescing, ::type? for safe cast)
 ├─ Schema-aware compilation
 ├─ Portable analytic stdlib
 ├─ Capability dispatch (bounded)
 └─ Deterministic SQL output
        ↓
dbt
 ├─ DAG + refs
 ├─ Materializations
 ├─ Incremental logic
 ├─ Tests
 └─ Execution
```

---

## Why This Gets 80% of the Value

- Removes the most common, noisy macros
- Dramatically simplifies dbt models
- Centralizes portability logic
- Keeps scope tight and maintainable
- Avoids re-building dbt

**Net effect:**
dbt models become shorter, clearer, and more semantic, while dbt itself stays focused on orchestration and execution.

---

## Implementation Priority

Based on usage frequency and complexity:

| Priority | Feature | Complexity | Value |
|----------|---------|------------|-------|
| P0 | `except` / `rename` / `prefix` | Low | Very High |
| P0 | `key()` surrogate keys | Low | Very High |
| P0 | `??` null coalescing operator | Low | High |
| P1 | `deduplicate` | Medium | High |
| P1 | Safe casting (`::type?` and `::type ?? default`) | Low | High |
| P1 | `fill` for date spines | Medium | High |
| P2 | `pivot` / `unpivot` | High | Very High |
| P2 | `union()` with alignment | Medium | Medium |
| P2 | `date_spine()` / `series()` sources | Medium | Medium |
| P3 | Full stdlib (string, date, math) | High | Medium |

---

## Operator Quick Reference

| Syntax | Meaning | Example |
|--------|---------|---------|
| `??` | Null coalescing | `name ?? 'Unknown'` |
| `::type` | Strict cast (errors on failure) | `value::integer` |
| `::type?` | Safe cast (NULL on failure) | `value::integer?` |
| `::type ?? default` | Safe cast with default | `value::integer ?? 0` |
| `\|\|` | String concatenation | `first \|\| ' ' \|\| last` |
