# Auto-Spine Simplifications

With guaranteed groups as the default, several common SQL patterns become unnecessary or dramatically simpler. This document explores what changes in a world where grouped results are always complete.

---

## Patterns That Become Obsolete

### 1. Date Dimension Tables

**Before (traditional data warehousing):**
```sql
-- Maintain a date_dim table with all possible dates
CREATE TABLE date_dim AS
SELECT 
    d::date as date,
    DATE_TRUNC('month', d) as month,
    DATE_TRUNC('year', d) as year,
    EXTRACT(dow FROM d) as day_of_week,
    ...
FROM generate_series('2020-01-01'::date, '2030-12-31'::date, '1 day') as d;

-- Every time series query requires joining to it
SELECT 
    date_dim.month,
    COALESCE(SUM(orders.amount), 0) as revenue
FROM date_dim
LEFT JOIN orders ON DATE_TRUNC('month', orders.created_at) = date_dim.month
WHERE date_dim.month BETWEEN '2024-01-01' AND '2024-12-31'
GROUP BY date_dim.month;
```

**After (ASQL):**
```asql
from orders
  where created_at >= @2024-01-01 and created_at < @2025-01-01
  group by month(created_at) as month (
    sum(amount) ?? 0 as revenue
  )
```

**What's saved:**
- No need to create/maintain date_dim table
- No LEFT JOIN complexity
- No risk of date_dim being out of range
- Cleaner, more readable queries

### 2. Calendar CTEs

**Before:**
```sql
WITH calendar AS (
    SELECT generate_series(
        DATE_TRUNC('month', MIN(created_at)),
        DATE_TRUNC('month', MAX(created_at)),
        INTERVAL '1 month'
    )::date as month
    FROM orders
),
data AS (
    SELECT DATE_TRUNC('month', created_at) as month, SUM(amount) as revenue
    FROM orders
    GROUP BY 1
)
SELECT 
    calendar.month,
    COALESCE(data.revenue, 0) as revenue
FROM calendar
LEFT JOIN data ON calendar.month = data.month;
```

**After (ASQL):**
```asql
from orders
  group by month(created_at) as month (
    sum(amount) ?? 0 as revenue
  )
```

**What's saved:**
- No CTE boilerplate
- No MIN/MAX range detection (done automatically)
- No LEFT JOIN
- No COALESCE wrapping the join

### 3. dbt date_spine Macro

**Before (dbt):**
```sql
-- models/monthly_revenue.sql
WITH spine AS (
    {{ dbt_utils.date_spine(
        datepart="month",
        start_date="cast('2024-01-01' as date)",
        end_date="cast('2024-12-31' as date)"
    ) }}
),
data AS (
    SELECT DATE_TRUNC('month', created_at) as date_month, SUM(amount) as revenue
    FROM {{ ref('orders') }}
    GROUP BY 1
)
SELECT 
    spine.date_month,
    COALESCE(data.revenue, 0) as revenue
FROM spine
LEFT JOIN data ON spine.date_month = data.date_month
```

**After (ASQL for dbt):**
```asql
from orders
  where created_at >= @2024-01-01 and created_at < @2025-01-01
  group by month(created_at) as date_month (
    sum(amount) ?? 0 as revenue
  )
```

### 4. Post-Processing Gap Fill

**Before (Python/pandas):**
```python
# Query returns incomplete data
df = pd.read_sql("SELECT month, revenue FROM monthly_revenue", conn)

# Must fill gaps in Python
all_months = pd.date_range('2024-01-01', '2024-12-01', freq='MS')
df = df.set_index('month').reindex(all_months).fillna(0).reset_index()
```

**After:**
Query returns complete data. No post-processing needed.

---

## Patterns That Simplify

### 1. Window Functions Over Time Series

**Before:** LAG/LEAD might skip missing periods
```sql
-- If March is missing, LAG(1) from April returns February, not March
SELECT 
    month,
    revenue,
    revenue - LAG(revenue, 1) OVER (ORDER BY month) as mom_change
FROM monthly_revenue;
```

This is subtly wrong if gaps exist—the "prior month" isn't actually the prior month.

**After:** With guaranteed groups, LAG(1) always returns the actual prior period.

```asql
from orders
  group by month(created_at) as month ( sum(amount) ?? 0 as revenue )
  order by month
  select month, revenue, revenue - prior(revenue) as mom_change
```

The `prior(revenue)` is guaranteed to be the actual prior month, not a random earlier month.

### 2. Running Totals

**Before:** Running sum might have implicit gaps
```sql
SELECT 
    month,
    SUM(revenue) OVER (ORDER BY month) as cumulative
FROM monthly_revenue;
```

If months are missing, the cumulative appears to "jump" at gaps.

**After:** Running totals smoothly increment through all periods.

### 3. Multi-Dimension Cross Products

**Before:** Manual CROSS JOIN of dimension spines
```sql
WITH regions AS (SELECT DISTINCT region FROM orders),
     months AS (SELECT generate_series(...) as month),
     spine AS (SELECT * FROM regions CROSS JOIN months),
     data AS (SELECT region, month, SUM(amount) FROM orders GROUP BY 1, 2)
SELECT spine.*, COALESCE(data.amount, 0)
FROM spine LEFT JOIN data ON ...
```

**After:** Automatic cross-product of all grouped dimensions
```asql
from orders
  group by region, month(created_at) as month (
    sum(amount) ?? 0 as revenue
  )
```

All (region × month) combinations appear automatically.

---

## What About Set Operations?

### UNION

With guaranteed groups, UNIONing two time series becomes more predictable:

```asql
-- Both have complete months, UNION just stacks them
(from orders_2023 group by month(created_at) as month ( sum(amount) ?? 0 as revenue ))
union all
(from orders_2024 group by month(created_at) as month ( sum(amount) ?? 0 as revenue ))
```

No risk of one side having gaps that the other fills.

### INTERSECT / EXCEPT

These operate on exact row matches. With guaranteed groups:
- INTERSECT finds periods that exist in both (all of them, if ranges overlap)
- EXCEPT finds periods unique to one side (edge months outside overlap)

The semantics are cleaner because you're comparing complete sets.

---

## What's Still Needed

### 1. The `??` Operator (Null Coalesce)

You still need to specify default values for filled rows:

```asql
sum(amount) ?? 0 as revenue      -- Fill with 0
count(*) ?? 0 as orders          -- Fill with 0
avg(price) as avg_price          -- NULL for missing (might be desired)
```

The difference is this is cleaner than wrapping a LEFT JOIN result in COALESCE.

### 2. The `guarantee()` Function

For categorical columns with fixed expected values:

```asql
group by guarantee(status, ['pending', 'shipped', 'delivered'])
```

This is still needed because ASQL can't infer what values "should" exist for arbitrary categories.

### 3. Explicit Date Spine for Cross-Table Analysis

If you're joining dates from multiple unrelated tables, you might still want an explicit spine:

```asql
from date_spine(start = @2024-01-01, end = @2024-12-31, grain = month) as dates
  &? (from orders group by month(created_at) as month ( sum(amount) )) as o 
     on dates.date = o.month
  &? (from returns group by month(return_date) as month ( sum(amount) )) as r
     on dates.date = r.month
```

But for single-table analysis, this is no longer needed.

---

## Features That May Become Redundant

### 1. The `fill` Keyword (Removed)

The spec originally had a `fill` keyword for explicit gap-filling:
```asql
from orders
  group by month(created_at) as month ( sum(amount) as revenue )
  fill month with {revenue: 0}
```

With auto-spine as default, this is unnecessary. The `fill` keyword has been removed from the spec.

### 2. Complex Window Frame Specifications

Some window frame gymnastics were to handle missing data:
```sql
-- "Ignore gaps when looking back"
AVG(revenue) OVER (ORDER BY month ROWS BETWEEN 3 PRECEDING AND CURRENT ROW)
```

With guaranteed groups, a 3-row lookback always covers exactly 3 periods.

---

## Computational Considerations

### Performance

Auto-spine adds a CTE and LEFT JOIN to every grouped query. For most analytical queries, this is negligible (typically 5-15% overhead). 

However, for very simple queries or high-cardinality GROUP BYs, the overhead may be unwanted. Users can disable with:
- `SET auto_spine = false` for a query
- Config file for global default
- Filtering `WHERE revenue > 0` to remove filled rows

### Query Plan Complexity

The generated SQL is more complex:
```sql
WITH month_spine AS (...),
     spine_data AS (SELECT ... GROUP BY ...),
SELECT spine.month, COALESCE(data.revenue, 0)
FROM month_spine
LEFT JOIN spine_data ON ...
```

Modern query optimizers handle this well, but debugging the generated SQL requires understanding the spine pattern.

### Memory

For date ranges, the spine size is bounded (12 months, 365 days, etc.). For high-cardinality categorical columns, DISTINCT values could be large—but that's the same data the GROUP BY would process anyway.

---

## Philosophical Shift

Traditional SQL assumes: **"Show me what exists"**

ASQL assumes: **"Show me the complete picture"**

This aligns with how analysts actually think. When you ask "revenue by month," you expect all months. When you ask "orders by status," you might expect all possible statuses.

The default has shifted from "data-driven completeness" to "schema-driven completeness"—what the analyst expects, not just what the data contains.

---

## Summary

| Pattern | Before | After |
|---------|--------|-------|
| Date dimension tables | Required, maintained | Optional, automatic |
| Calendar CTEs | Common boilerplate | Unnecessary |
| LEFT JOIN to spine | Every time series query | Automatic |
| dbt date_spine macro | Standard practice | Unnecessary for basic cases |
| Post-processing gap fill | Python/Excel cleanup | Not needed |
| LAG/LEAD correctness | Fragile with gaps | Reliable |
| Running totals | May have jumps | Smooth |
| Multi-dimension cross join | Manual setup | Automatic |
| `fill` keyword | Was planned | Removed, redundant |

The net effect: simpler queries, fewer bugs, less infrastructure.
