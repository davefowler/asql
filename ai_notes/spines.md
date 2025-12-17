# Spines and Gap Filling

This document describes how ASQL handles "complete" data ranges - ensuring that grouped results include all expected values, not just those with data.

---

## The Problem

SQL has a fundamental behavior that's wrong for analytics: **dates (or other values) with no data simply don't appear in results.**

```sql
SELECT month, SUM(sales) FROM orders GROUP BY month
-- If no sales in Feb, Feb is MISSING from results
```

This is technically correct (no rows to aggregate) but breaks:
- Charts (gaps instead of zeros)
- Time series analysis (rolling averages, YoY comparisons)
- Reports (stakeholders expect all periods)

---

## The Solution: Auto-Spine for Dates + `guarantee()` for Everything Else

### Dates Auto-Spine (Default)

Date truncation functions in GROUP BY automatically get gap-filled:

```asql
from orders
where created_at >= @2024-01-01 and created_at < @2025-01-01
group by month(created_at) as month (
  sum(amount) ?? 0 as revenue
)
-- All 12 months appear, even those with $0 revenue
```

**Supported date functions:** `year()`, `month()`, `week()`, `day()`, `hour()`, `quarter()`, `date_trunc()`

**Range detection:**
1. Inferred from WHERE clause bounds on the date column
2. Falls back to MIN/MAX from actual data if no WHERE bounds

### `guarantee()` for Explicit Control

For non-date columns or when you want explicit control over the spine values:

```asql
-- With explicit array
from sales
group by guarantee(region, ['North', 'South', 'East', 'West']) (
  sum(amount) ?? 0 as total
)

-- With numeric range
from events
group by guarantee(hour(created_at), 0 to 23) as hour (
  count(*) ?? 0 as events
)

-- With subquery
from sales
group by guarantee(region, from regions select region) (
  sum(amount) ?? 0 as total
)

-- With no argument (uses DISTINCT from source data)
from sales
group by guarantee(region) (
  sum(amount) ?? 0 as total
)
-- Equivalent to: guarantee(region, from sales select distinct region)
```

---

## `guarantee()` Options

| Form | Description | Example |
|------|-------------|---------|
| `guarantee(col, [values])` | Explicit array of values | `guarantee(status, ['pending', 'complete', 'failed'])` |
| `guarantee(col, N to M)` | Numeric range | `guarantee(hour, 0 to 23)` |
| `guarantee(col, subquery)` | Values from another query | `guarantee(region, from regions select region)` |
| `guarantee(col)` | Auto: DISTINCT from source | `guarantee(region)` → uses distinct regions from the data |

### Important: Filters and `guarantee()` with No Arguments

When using `guarantee(col)` with no explicit values, it derives values from a DISTINCT query on the source. If you have filters applied, you may want to be explicit about where the values come from:

```asql
-- Problem: guarantee(region) might pull from unfiltered data
from sales
where region != 'Southern'  -- Ignore typo in database
group by guarantee(region) (sum(amount) ?? 0)
-- ⚠️ 'Southern' might still appear if guarantee() queries raw table!

-- Solution: Use stash to capture filtered data, then reference it
from sales
where region != 'Southern'
stash as filtered_sales
group by guarantee(region, from filtered_sales select region) (
  sum(amount) ?? 0 as total
)
-- ✅ Only regions from filtered data appear
```

---

## Opting Out: Filtering

**You don't need a special opt-out syntax.** If you don't want spine-generated rows, just filter them out:

```asql
-- Auto-spine adds all months, filter removes zeros
from orders
group by month(created_at) as month (sum(amount) as revenue)
where revenue > 0
```

This works because:
- Spine rows have `revenue = 0` (or NULL coalesced to 0)
- Real data rows have `revenue > 0`
- The filter effectively "undoes" the spine

### Edge Case: When Filtering Could Remove Real Data

If real data can legitimately have the same value as the fill value:

```asql
-- If amounts can be negative, a real month might sum to exactly 0
from orders
group by month(created_at) as month (sum(amount) as net_revenue)
where net_revenue != 0  -- This would ALSO remove real months with $0 net!
```

**Solution:** Disable auto-spine for this query:

```asql
SET auto_spine = false;
from orders
group by month(created_at) as month (sum(amount) as net_revenue)
```

---

## Disabling Auto-Spine

**Inline SET statement:**
```asql
SET auto_spine = false;
from orders group by month(created_at) as month (...)
```

**Python API:**
```python
from asql import compile, CompileSettings

sql = compile(
    "from orders group by month(created_at) as month (...)",
    settings=CompileSettings(auto_spine=False)
)
```

**Config file (`asql.config.yaml`):**
```yaml
compile:
  auto_spine: false
```

---

## How Default Values Work

When a spine row is generated with no matching data:

| Column Type | Value on Spine Row |
|-------------|-------------------|
| GROUP BY column | From spine |
| Aggregate with `?? 0` | The coalesced value (0) |
| Aggregate without `??` | NULL |

**Best Practice:** Always use `?? 0` (or appropriate default) for aggregates:

```asql
from orders
group by month(created_at) as month (
  sum(amount) ?? 0 as revenue,
  count(*) ?? 0 as order_count
)
```

---

## Mixed GROUP BY (Date + Non-Date)

When you have both date and non-date columns in GROUP BY:

```asql
from orders
group by month(created_at) as month, region (
  sum(amount) ?? 0 as revenue
)
```

**Behavior:** 
- Date columns get the date spine (all months)
- Non-date columns are cross-joined with their DISTINCT values from data
- Result: all (month × region) combinations that exist in the data's regions

This matches typical analytics expectations: see all months for each region that has any data.

---

## Multiple Date Columns

### Same Source Column (Hierarchical)

```asql
group by month(created_at) as month, 
         week(created_at) as week,
         day_of_week(created_at) as dow
```

Generates a single base date spine with all truncations applied - only valid combinations:

```sql
WITH base_spine AS (
  SELECT d FROM generate_series('2024-01-01', '2024-12-31', '1 day') as d
),
spine AS (
  SELECT DISTINCT
    DATE_TRUNC('month', d) as month,
    DATE_TRUNC('week', d) as week,
    EXTRACT(dow FROM d) as dow
  FROM base_spine
)
```

### Different Source Columns

```asql
group by month(created_at) as order_month, 
         month(shipped_at) as ship_month
```

Creates independent spines that are cross-joined (all combinations of order months × ship months).

---

## Config Reference

| Setting | Values | Default | Description |
|---------|--------|---------|-------------|
| `auto_spine` | `true`/`false` | `true` | Auto gap-fill date columns in GROUP BY |
| `week_start` | `'monday'`/`'sunday'` | `'monday'` | Week start for `week()` function |

**Settings priority (highest to lowest):**
1. Inline `SET` statements in query
2. Python API `CompileSettings(...)`
3. Config file `asql.config.yaml`
4. Built-in defaults

---

## Implementation: How Spines Compile

### Date Auto-Spine

```asql
from orders
where created_at >= @2024-01-01 and created_at < @2025-01-01
group by month(created_at) as month (sum(amount) ?? 0 as revenue)
```

Compiles to:

```sql
WITH month_spine AS (
  SELECT DATE_TRUNC('month', d) as month
  FROM generate_series('2024-01-01'::date, '2024-12-01'::date, '1 month') as d
),
data AS (
  SELECT DATE_TRUNC('month', created_at) as month, SUM(amount) as revenue
  FROM orders
  WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01'
  GROUP BY 1
)
SELECT month_spine.month, COALESCE(data.revenue, 0) as revenue
FROM month_spine
LEFT JOIN data ON month_spine.month = data.month
```

### guarantee() with Array

```asql
from sales
group by guarantee(region, ['North', 'South', 'East', 'West']) (sum(amount) ?? 0)
```

Compiles to:

```sql
WITH region_spine AS (
  SELECT unnest(ARRAY['North', 'South', 'East', 'West']) as region
),
data AS (
  SELECT region, SUM(amount) as total
  FROM sales
  GROUP BY 1
)
SELECT region_spine.region, COALESCE(data.total, 0) as total
FROM region_spine
LEFT JOIN data ON region_spine.region = data.region
```

### guarantee() with Subquery

```asql
from sales
group by guarantee(region, from regions select region) (sum(amount) ?? 0)
```

Compiles to:

```sql
WITH region_spine AS (
  SELECT region FROM regions
),
data AS (
  SELECT region, SUM(amount) as total
  FROM sales
  GROUP BY 1
)
SELECT region_spine.region, COALESCE(data.total, 0) as total
FROM region_spine
LEFT JOIN data ON region_spine.region = data.region
```

---

## Performance FAQ

### How much overhead does auto-spine add?

| Query Size | Spine Overhead | Notes |
|------------|---------------|-------|
| Large tables (1M+ rows) | ~5% | Aggregation dominates query time |
| Medium tables (10K-1M rows) | ~10-15% | LEFT JOIN is the main cost |
| Small/simple queries | ~20-50% | Fixed overhead is proportionally larger |

### Where does the overhead come from?

1. **Spine CTE generation** - Negligible for dates (12 months = 12 rows)
2. **LEFT JOIN** - Main cost, but well-optimized in modern databases
3. **DISTINCT for non-dates** - Extra table scan if using guarantee() without explicit values

### When should I disable auto-spine?

- **Performance-critical dashboards** with many queries
- **ETL pipelines** processing billions of rows where every % matters
- **Edge case**: When real data can sum to exactly 0 (filtering would remove it)

Use `SET auto_spine = false` for these cases.

### Is spine overhead a problem for analytics?

**Usually no.** Most analytics queries are not bottlenecked by the spine:
- The aggregation (scanning and grouping data) dominates
- Modern databases optimize LEFT JOINs with small dimension tables very well
- The 5-15% overhead is often unnoticeable in interactive dashboards

The time saved debugging "why is February missing from my chart?" far exceeds any performance cost.

---

## FAQ: When Is Auto-Spine Unnecessary?

### Does spine do anything for non-date columns?

**Only if you use guarantee() with explicit values.** Otherwise:

```asql
-- These produce the SAME result:
group by region (sum(amount))                    -- Normal GROUP BY
group by guarantee(region) (sum(amount) ?? 0)    -- Spine from DISTINCT
```

Why? Because `guarantee(region)` (with no explicit values) creates a spine from `SELECT DISTINCT region` - which is exactly what GROUP BY gives you. **Same rows, just more expensive query.**

### So why would I use guarantee() without values?

**Consistency.** If you always write `guarantee()`, your code clearly signals "I expect all values to appear." It's self-documenting, even when it's technically a no-op.

### What about ROLLUP/CUBE?

These SQL features generate summary rows (subtotals, grand totals). Auto-spine doesn't currently handle these specially - they'd get spined like regular GROUP BY. This might produce unexpected results and is an area for future consideration.

---

## Summary

| Feature | Description | Status |
|---------|-------------|--------|
| `auto_spine` setting | Enable/disable auto-spine globally | ✅ Implemented (default: true) |
| Auto-spine ALL group by | Dates get range, non-dates get DISTINCT | ✅ Implemented |
| Cross-join multiple spines | All (col1 × col2 × ...) combinations | ✅ Implemented |
| WHERE clause range inference | Auto-detect spine bounds from filters | ✅ Implemented |
| `guarantee(col, [values])` | Override with explicit array | ✅ Implemented |
| `guarantee(col, N to M)` | Numeric range | 🔄 Planned |
| `guarantee(col, subquery)` | Values from subquery | 🔄 Planned |
| ROLLUP/CUBE detection | Skip auto-spine for these | 🔄 Planned |

**Key insight:** ALL group by columns get spined. Dates use range (fills gaps), non-dates use DISTINCT (no-op but consistent). Use `guarantee(col, [values])` to override with explicit values. Filter with `WHERE revenue > 0` to remove spine rows, or `SET auto_spine = false` to disable entirely.
