# Spines, Continuous Columns, and Gap Filling

This document explores how ASQL can handle "complete" data ranges - ensuring that grouped results include all expected values, not just those with data.

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

## Continuous vs. Discrete Columns

Not all columns are the same:

| Type | Examples | Gap-fill behavior |
|------|----------|-------------------|
| **Continuous/Ordered** | Dates, timestamps, numeric ranges | Missing values in the sequence should appear |
| **Discrete/Categorical** | Status, category, region | Only actual values should appear (unless explicitly guaranteed) |

### Dates: The Obvious Case

Dates are clearly continuous - if you're grouping by month, you expect Jan, Feb, Mar... with no gaps.

### Other Continuous Dimensions

But dates aren't the only continuous type:

| Column Type | Example Use Case |
|-------------|------------------|
| **Numeric ranges** | Age buckets (0-10, 10-20, ...), price tiers |
| **Hour of day** | 0-23 should all appear in hourly analysis |
| **Day of week** | 1-7 should all appear |
| **Sequential IDs** | Order numbers (might want to see gaps) |
| **Version numbers** | Software versions (1.0, 1.1, 1.2, ...) |

### When Categorical Needs Completion

Sometimes even categorical columns need "all values":

```asql
-- Show sales by region, but include all regions even if zero
group by guarantee(region, ['North', 'South', 'East', 'West']) (
  sum(sales) ?? 0 as total
)
```

---

## Do Modeling Frameworks Specify This?

### dbt

dbt doesn't explicitly mark columns as continuous/discrete. It has:
- `meta` tags (custom, unstructured)
- Constraints (not_null, unique, etc.)
- Relationships (foreign keys)

But nothing like `continuous: true` or `dimension_type: time_series`.

**dbt semantic layer (MetricFlow)** has:
- `type: time` for time dimensions
- `type: categorical` for categorical dimensions

This is closer! But it's for metrics, not general column metadata.

### Looker / LookML

LookML has dimension types:
- `type: time` - knows it's a time series
- `type: number` - could be continuous
- `type: string` - typically categorical

The BI layer uses this for visualization (continuous vs. categorical axis).

### ASQL Opportunity

ASQL could track `continuous` as column metadata in:
- ASQL schema files
- dbt integration (via meta tags)
- Inference from usage patterns

This would enable:
- Auto-spining for continuous columns (dates by default)
- Correct axis selection in visualization layers
- Better defaults with explicit override when needed

---

## Proposal: `guarantee()` Function (or Auto-Spine)

### For Dates (Most Common)

```asql
from orders
where created_at >= @2024-01-01 and created_at < @2025-01-01
group by guarantee(month(created_at)) as month (
  sum(amount) ?? 0 as revenue
)
```

**Range detection priority:**
1. Explicit in `guarantee()`: `guarantee(month(...), @2024-01-01 to @2024-12-01)`
2. Infer from WHERE clause bounds on the same column
3. Fall back to MIN/MAX from actual data

### For Discrete Periods (Hour, Day of Week)

```asql
-- Guarantee all 24 hours appear
from events
group by guarantee(hour(created_at), 0 to 23) as hour (
  count(*) ?? 0 as events
)

-- Guarantee all 7 days of week appear
from events
group by guarantee(day_of_week(created_at), 1 to 7) as dow (
  count(*) ?? 0 as events
)
```

### For Categorical (Array or Subquery)

```asql
-- With explicit array (no dim table needed!)
from sales
group by guarantee(region, ['North', 'South', 'East', 'West']) (
  sum(amount) ?? 0 as total
)

-- With subquery
from sales
group by guarantee(region, from regions select region) (
  sum(amount) ?? 0 as total
)

-- Auto-detect from data (uses SELECT DISTINCT under the hood)
from sales
group by guarantee(region) (
  sum(amount) ?? 0 as total
)
```

---

## Alternative Names & Syntax Considered

### Function Names

| Name | Pros | Cons |
|------|------|------|
| `guarantee()` | Reads as a contract, clear intent | Novel terminology |
| `range()` | Implies generating a range, familiar | Might conflict with other meanings |
| `complete()` | R/tidyr uses this | Might imply data completeness |
| `spine()` | Describes the mechanism | Too technical |
| `ensure()` | Similar to guarantee | Less strong |
| `densify()` | Used in time series DBs | Unfamiliar |

### Shorthand Bracket Syntax?

Could we use brackets to imply "this is a guaranteed range"?

```asql
-- Potential shorthand syntax
group by [month(created_at)] as month

-- With explicit range
group by [month(created_at): @2024-01 to @2024-12] as month
```

**Pros:**
- Very concise
- Visually distinct

**Cons:**
- Might look like array syntax
- Less self-documenting than `guarantee()`
- Python/JS don't have an obvious parallel

**Other language parallels:**
- Python: No direct equivalent (would use a function)
- JavaScript: No direct equivalent
- R: `complete()` from tidyr
- SQL: No standard

**Recommendation:** Start with `guarantee()` or `range()` for clarity. Could add bracket shorthand later if it proves valuable.

---

## Should Spine Be Default?

### The Case for Default Spine (with Opt-Out)

User's insight: **In a pipeline, filters apply AFTER the spine.** So these concerns may not apply:

| Concern | Why It's Actually Fine |
|---------|------------------------|
| "Months with sales > $1M" | Filter happens after spine - zero rows get filtered out |
| "Event days only" | Filter `where count > 0` removes zero rows |
| "Data validation" | Zeros show gaps just as clearly as missing rows |
| "Staging models" | Use `nospine()` to opt out |

**The "just filter out zeros" principle:**
> Don't like auto-spines? Just filter out 0s/nulls and it's the same as no spine.

```asql
-- Auto-spine is on, but filter removes zeros
from orders
group by month(created_at) as month (sum(amount) as revenue)
where revenue > 0  -- This removes the spine rows with no data
```

### Proposed: Default Spine with Opt-Out

```asql
-- Default: spine is applied for date truncations
from orders
group by month(created_at) as month (sum(amount) as revenue)
-- All months appear!

-- Opt-out when you don't want spine
from orders
group by nospine(month(created_at)) as month (sum(amount) as revenue)
-- Only months with data appear (SQL default behavior)

-- Or via config
set spine = false
from orders
group by month(created_at) as month (...)
```

### Config Setting

Via `asql/config.py`, spine behavior could be controlled:

```python
# In config
settings = {
    "auto_spine": True,  # Default: spine date truncations
    "spine_default_fill": None,  # What to fill missing aggregates with (None = NULL, 0, etc.)
}
```

Inline override:
```asql
set auto_spine = false

from orders
group by month(created_at) as month (...)
-- No spine applied
```

---

## Multiple Date Columns / Multiple Spines

What if a query has multiple date GROUP BYs?

```asql
from orders
group by month(created_at) as order_month, 
         month(shipped_at) as ship_month (
  count(*) as orders
)
```

**Approach:**
- Each gets its own spine CTE (namespaced: `order_month_spine`, `ship_month_spine`)
- Cross-join the spines for all combinations
- Left join the data

This could get expensive for many spines, but usually you're only grouping by one date at a time. Could warn if multiple spines detected.

---

## Visualization Implications

Knowing if a column is continuous affects visualization:

| Column Type | Chart Axis | Gap Handling |
|-------------|------------|--------------|
| Continuous (date, numeric range) | Continuous axis | Interpolate or show gaps |
| Discrete (category, region) | Categorical axis | Each value is a separate tick |

### Tracking in Schema

ASQL should track `continuous` as column metadata:

```yaml
# In ASQL schema or dbt meta
columns:
  - name: order_month
    type: date
    continuous: true  # Hint for visualization and auto-spine
    grain: month      # The granularity
    
  - name: region
    type: string
    continuous: false
    valid_values: ['North', 'South', 'East', 'West']
```

This metadata could:
1. Drive automatic spine behavior (spine continuous columns by default)
2. Inform BI tool axis selection
3. Enable validation (is this value in the expected set?)

**Future:** ASQL diagnostic/telemetry could infer continuous vs. discrete from usage patterns.

---

## Implementation: How Spines Work

Under the hood, spines compile to CTEs:

### For Dates

```sql
-- guarantee(month(created_at)) compiles to:
WITH month_spine AS (
  SELECT date_trunc('month', d) as month
  FROM generate_series('2024-01-01'::date, '2024-12-01'::date, '1 month') as d
),
data AS (
  SELECT date_trunc('month', created_at) as month, SUM(amount) as revenue
  FROM orders
  GROUP BY 1
)
SELECT month_spine.month, COALESCE(data.revenue, 0) as revenue
FROM month_spine
LEFT JOIN data ON month_spine.month = data.month
```

### For Categorical (Array)

```sql
-- guarantee(region, ['North', 'South', 'East', 'West']) compiles to:
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

### For Categorical (Auto-Detect)

```sql
-- guarantee(region) with no explicit values compiles to:
WITH region_spine AS (
  SELECT DISTINCT region FROM sales
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

**Note:** CTEs are namespaced (`month_spine`, `region_spine`) to support multiple spines in one query.

---

## The `fill` Command Becomes Obsolete

With `guarantee()` or auto-spine, the current `fill` command is no longer needed:

**Old way (current ASQL):**
```asql
from orders
group by month(created_at) as month (sum(amount) as revenue)
fill month with {revenue: 0}
```

**New way (with guarantee/auto-spine):**
```asql
from orders
group by guarantee(month(created_at)) as month (
  sum(amount) ?? 0 as revenue
)

-- Or if auto-spine is default:
from orders
group by month(created_at) as month (
  sum(amount) ?? 0 as revenue
)
-- Spine happens automatically!
```

The `fill` command can be deprecated or removed in favor of:
1. `guarantee()` in GROUP BY (explicit spine)
2. Auto-spine for date truncations (default behavior)
3. `?? 0` for filling NULL aggregates with defaults

---

## Related: Forward Fill vs Gap Fill

These are different operations that both involve "filling":

| Operation | What it does | When to use |
|-----------|--------------|-------------|
| **Gap Fill** (spine) | Adds missing ROWS | Complete date ranges for charts |
| **Forward Fill** | Propagates VALUES | Time series with sparse measurements |

Example:

```
Gap Fill (adds rows):
Jan: 100        Jan: 100
Mar: 150   →    Feb: 0    ← Added row
                Mar: 150

Forward Fill (propagates values):
Jan: 100        Jan: 100
Feb: NULL  →    Feb: 100  ← Filled from Jan
Mar: 150        Mar: 150
```

See also: "Forward Fill / Backward Fill" section in pandas-python-notebooks-learnings.md.

---

## Summary

| Feature | Description | Status |
|---------|-------------|--------|
| `guarantee()` or `range()` function | Explicit spine for GROUP BY | Proposed |
| Auto-spine for dates | Spine date truncations by default | Proposed (default on) |
| `nospine()` function | Opt-out of auto-spine | Proposed |
| Config setting `auto_spine` | Enable/disable auto-spine globally | Proposed |
| WHERE clause range inference | Auto-detect spine bounds from date filters | Proposed |
| Categorical spine (array) | `guarantee(col, ['a', 'b', 'c'])` | Proposed |
| Categorical spine (subquery) | `guarantee(col, from table select col)` | Proposed |
| Multiple spines | Namespaced CTEs for each spine | Supported |
| Continuous metadata | Track in schema for viz hints | Future |
| Deprecate `fill` command | Replaced by guarantee + `?? 0` | Proposed |

**Key insight:** For analytics, spine should be the default. Users who don't want it can either filter out zeros or use `nospine()`. This matches what analysts actually want 90%+ of the time.
