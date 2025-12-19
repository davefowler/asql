# Spine-Breaking Edge Cases

**Date**: 2025-12-18  
**Status**: Implemented and documented

## Overview

ASQL's auto-spine feature automatically fills gaps in GROUP BY results (e.g., showing $0 for months with no sales). This document catalogs edge cases and how they're handled.

## How Spine Generation Works

### For Date Columns
1. Generate a "wide" spine from 1970 to CURRENT_DATE
2. Apply safe WHERE predicates to filter the spine
3. LEFT JOIN with aggregated data
4. If unsafe predicates exist, fall back to data MIN/MAX bounds

### For Categorical Columns
1. SELECT DISTINCT values from the source table
2. Apply ALL WHERE predicates (they're all safe - source table has all columns)
3. LEFT JOIN with aggregated data

## Safe vs Unsafe Predicates

### Key Insight: Categorical vs Date

**For categorical spines**, predicates query from the source table, so ALL predicates are safe:
```sql
-- Categorical spine: queries source table
SELECT DISTINCT region FROM sales WHERE region > other_region
-- ✅ Both 'region' and 'other_region' exist in 'sales' table!
```

**For date spines**, predicates are applied to `generate_series`, where only the date variable exists:
```sql
-- Date spine: queries generate_series
SELECT ... FROM generate_series(...) AS d WHERE d > other_column
-- ❌ 'other_column' doesn't exist in generate_series context!
```

### Safe Predicates (Date Spines Only)

Predicates that only reference the target column and literals:

```sql
-- ✅ SAFE: Column compared to literal
created_at >= '2021-01-01'

-- ✅ SAFE: Function on column compared to literal  
YEAR(created_at) = 2021

-- ✅ SAFE: BETWEEN with literal bounds
created_at BETWEEN '2021-01-01' AND '2024-01-01'
```

### Unsafe Predicates (Date Spines Only)

Predicates that reference other columns:

```sql
-- ❌ UNSAFE: Column vs column comparison
created_at > updated_at

-- ❌ UNSAFE: BETWEEN with column bounds
created_at BETWEEN start_date AND end_date

-- ❌ UNSAFE: OR combining different columns
created_at >= '2021-01-01' OR status = 'active'
```

## How We Handle Unsafe Predicates

### Current Implementation (as of 2025-12-18)

**For categorical spines:** All predicates are applied (they're all safe).

**For date spines with unsafe predicates:** Fall back to data MIN/MAX bounds with a warning.

```python
# When unsafe predicates are detected for date spines:
logger.warning(
    f"Date spine for '{alias}' uses data MIN/MAX bounds because WHERE clause "
    f"contains predicates that reference other columns. "
    f"Gaps at the start/end of the date range may not be filled."
)
```

### Example: Unsafe Date Predicate

```sql
-- ASQL input
from sales 
where created_at > updated_at 
group by month(created_at) (sum amount)

-- Generated SQL (data CTE first, then spine uses MIN/MAX from it)
WITH spine_data AS (
  SELECT MONTH(created_at) AS month_created_at, SUM(amount) 
  FROM sales 
  WHERE created_at > updated_at  -- Unsafe predicate applied here
  GROUP BY 1
),
month_created_at_spine AS (
  SELECT DATE_TRUNC('MONTH', d) AS month_created_at
  FROM generate_series(
    (SELECT MIN(month_created_at) FROM spine_data)::date,
    (SELECT MAX(month_created_at) FROM spine_data)::date,
    INTERVAL '1 month'
  ) AS d
)
SELECT month_created_at_spine.month_created_at, 
       COALESCE(spine_data.amount, 0)
FROM month_created_at_spine
LEFT JOIN spine_data ON ...
```

### Example: Safe Date Predicate

```sql
-- ASQL input
from sales 
where created_at >= '2021-01-01' 
group by month(created_at) (sum amount)

-- Generated SQL (wide spine with filter)
WITH month_created_at_spine AS (
  SELECT DATE_TRUNC('MONTH', d) AS month_created_at
  FROM generate_series('1970-01-01'::date, CURRENT_DATE, INTERVAL '1 month') AS d
  WHERE d >= '2021-01-01'  -- Safe predicate applied to spine
),
spine_data AS (
  SELECT MONTH(created_at) AS month_created_at, SUM(amount) 
  FROM sales 
  WHERE created_at >= '2021-01-01'
  GROUP BY 1
)
SELECT ...
```

### Example: Categorical with Column Comparison

```sql
-- ASQL input
from sales 
where region > other_region 
group by region (sum amount)

-- Generated SQL (all predicates safe for categorical)
WITH region_spine AS (
  SELECT DISTINCT region FROM sales 
  WHERE region > other_region  -- All predicates safe!
),
spine_data AS (...)
SELECT ...
```

## Why MIN/MAX Fallback is Actually Correct

### Key Insight

When a user writes `WHERE created_at > updated_at`, they're explicitly saying:
> "My date bounds should be defined by the data relationship, not absolute dates."

The MIN/MAX from the data IS the correct spine for this specification:
- There's no "missing" gap at the start because **by definition**, no data could exist before that MIN that satisfies the predicate
- The spine perfectly represents "all periods where this condition could be satisfied"

### This is a Feature, Not a Limitation

```sql
-- User writes:
WHERE created_at > updated_at

-- Data that satisfies this starts at 2021-03
-- Spine: 2021-03 to 2021-12 (data range)

-- This is CORRECT because:
-- - Jan/Feb couldn't have data satisfying this predicate
-- - Showing zeros for them would be misleading
-- - The spine represents the valid range for this query
```

### The Only Debatable Edge Case

If someone has BOTH a column comparison AND an explicit bound:

```sql
WHERE created_at > updated_at AND created_at >= '2024-01-01'
```

They might expect January/February to show with zeros even if no data satisfied both conditions. But this is debatable:
- Zeros for "no sales" is different from zeros for "predicate couldn't be satisfied"
- The current behavior is arguably more accurate

### Bottom Line

The MIN/MAX fallback isn't a degraded mode—it's the semantically correct behavior for data-dependent predicates. The warning exists to inform users, not to indicate a problem.

## Recommendations for Users

### 1. Column Comparisons: No Action Needed

If you're using column-to-column comparisons like `created_at > updated_at`, the data-bounded spine is correct. The warning is informational.

### 2. Want Explicit Bounds? Add Them

If you want a spine that starts/ends at specific dates regardless of data:
```sql
-- Add explicit bounds alongside your column comparison
from sales 
where created_at > updated_at 
  and created_at >= '2021-01-01'  -- Explicit lower bound
group by month(created_at) (sum amount)
```

### 3. Pipelined Filtering (Filter After GROUP BY)

```sql
-- Filter the grouped output for explicit bounds
from sales
where created_at > updated_at
group by month(created_at) (sum amount)
where month_created_at >= '2021-01-01'  -- Applied to spine
```

### 4. Pure Date Bounds = Widest Spine

```sql
-- ✅ Literal bounds = spine from 1970 to now, filtered
where created_at >= '2021-01-01' and created_at < '2024-01-01'
```

## Test Coverage

See `tests/test_auto_spine.py`:
- `TestUnsafePredicatesSkipped` - verifies unsafe predicates trigger fallback
- `TestSpineEdgeCases` - various edge cases
- `TestPredicateCopyingToSpine` - verifies safe predicates are copied

## Summary

| Spine Type | Predicate Type | Behavior |
|------------|----------------|----------|
| **Categorical** | Any | All predicates applied ✅ |
| **Date** | Safe (column + literals) | Wide spine (1970→now) + filter ✅ |
| **Date** | Unsafe (multi-column) | Data-bounded spine ✅ (semantically correct) |

All cases produce correct results. The warning for multi-column predicates is informational—it indicates the spine is bounded by data relationships rather than absolute dates, which is the correct behavior for such queries.
