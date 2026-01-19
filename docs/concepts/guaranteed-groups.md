# Guaranteed Groups (Spine)

One of ASQL's most powerful features is **spine gap-filling**: when you group data by dates, ASQL can ensure all expected time periods appear in results—even if they have no data.

This feature embodies the **[Completeness Over Fast Queries](index.md#5-completeness-over-fast-queries)** design value.

## The Problem

SQL doesn't guarantee your grouped results are complete. If a dimension value has no data, it simply won't appear:

```sql
SELECT month, SUM(amount) as revenue
FROM orders
GROUP BY month;
```

| month | revenue |
|-------|---------|
| Jan   | 1000    |
| Feb   | 1500    |
| Mar   | 800     |
| Jun   | 1200    |

April and May are missing. This isn't a bug—SQL was designed for transactional systems where you're asking "what happened?" and showing non-existent data would be wrong.

But analytics is different. When you build a time-series chart, missing data points cause real problems:
- The line jumps unexpectedly
- Month-over-month calculations use the wrong prior month
- The dashboard looks broken

## The Solution: Explicit Spine

Use `spine by` to explicitly request gap-filling:

```asql-play
from orders
  spine by month(order_date) (
    sum(amount) ?? 0 as revenue
  )
```

| month | revenue |
|-------|---------|
| Jan   | 1000    |
| Feb   | 1500    |
| Mar   | 800     |
| Apr   | 0       |
| May   | 0       |
| Jun   | 1200    |

No dimension tables. No extra CTEs. No post-processing.

## Spine Syntax

### `spine by` - Full Spine Transform

Use `spine by` as a transform (like `group by`) to spine all grouped columns:

```asql
from orders
  where order_date >= @2024-01-01 and order_date < @2024-07-01
  spine by month(order_date) (
    sum(amount) ?? 0 as revenue
  )
```

All months from January to June will appear.

### `spine()` in GROUP BY - Selective Spine

Use `spine()` within a `group by` to spine only specific columns:

```asql
from orders
  group by spine(month(order_date)), region (
    sum(amount) ?? 0 as revenue
  )
```

This spines the month column (filling date gaps) but NOT the region column (only regions with data appear).

## How It Works

### Date Truncations

When you spine a date truncation function (`month()`, `year()`, `week()`, etc.), ASQL:

1. Infers the date range from your WHERE clause
2. Generates all values in that range using `generate_series` (or equivalent)
3. LEFT JOINs your data to the complete range
4. Fills missing values with NULL (use `??` for defaults)

### Non-Date Columns

For non-date columns, the spine uses DISTINCT values from the **filtered** source data:

```asql
from orders
  spine by status (
    # ?? 0 as count
  )
```

If your data has orders with status "pending", "shipped", and "delivered", all three will appear even if one has zero orders in the filtered period.

### How Filters Affect Categorical Spines

**Important:** WHERE filters are applied when generating the spine for categorical columns. The spine is built from:

```sql
SELECT DISTINCT column FROM source_table WHERE <your filters>
```

This means if you filter your data, only values matching that filter will appear in the spine:

```asql
from orders
  where region = 'North America'
  spine by region (
    sum(amount) ?? 0 as revenue
  )
```

This will **only show North America**—not Europe, Asia, or other regions—because the spine is generated from the filtered data.

**This is usually what you want!** When you filter to North America, you typically want results only for North America.

**Want all regions to appear (even with filtered data)?** Use `guarantee()`:

```asql
from orders
  where region = 'North America'
  spine by guarantee(region, ['North America', 'Europe', 'Asia', 'South America']) (
    sum(amount) ?? 0 as revenue
  )
```

Now all four regions appear—North America with actual data, the others with zero revenue.

| Scenario | Result |
|----------|--------|
| `spine by region` with `where region = 'NA'` | Only NA appears |
| `spine by region` (no filter) | All regions in data appear |
| `spine by guarantee(region, [...])` | All listed values appear |

### Multiple Spine Columns

When spining by multiple columns, ASQL creates all combinations:

```asql
from orders
  spine by region, month(order_date) (
    sum(amount) ?? 0 as revenue
  )
```

Every region × month combination will appear.

## Explicit Values with `guarantee()`

Specify exactly which values should appear:

```asql-play
from orders
  spine by guarantee(status, ['pending', 'shipped', 'delivered', 'cancelled']) (
    # ?? 0 as order_count
  )
```

This ensures all four statuses appear, even if some have zero orders.

### Use Cases for `guarantee()`

- Fixed categories that should always appear
- Enum-like values from your data model
- Dashboard filters with known options

## Default Values with `??`

Use the nullish coalescing operator to provide defaults for missing values:

```asql-play
from orders
  spine by month(order_date) (
    sum(amount) ?? 0 as revenue,        -- Default to 0
    # ?? 0 as orders,            -- Default to 0
    avg(amount) as avg_order            -- Leave as NULL
  )
```

Different columns can have different default behaviors.

## When NOT to Use Spine

### Regular GROUP BY (No Gap-Filling)

If you don't want gap-filling, just use regular `group by`:

```asql
from orders
  group by month(order_date) (
    sum(amount) as revenue
  )
```

This returns only months with actual data—no spine CTEs, no gap-filling.

### Filter the Results

If you used spine but want to remove zero rows:

```asql
from orders
  spine by month(order_date) (
    sum(amount) as revenue
  )
  where revenue > 0
```

## Understanding the Generated SQL

### Transpilation Comments

To understand the generated SQL, enable transpilation comments:

```asql
SET include_transpilation_comments = true;

from orders
  where order_date >= @2024-01-01 and order_date < @2024-07-01
  spine by month(order_date) (
    sum(amount) ?? 0 as revenue
  )
```

The output will include a helpful explanation:

```sql
/* ASQL spine: Gap-filling CTEs were generated to ensure all 
   expected time periods appear (even with zero/null aggregates). */
WITH month_order_date_spine AS (...)
...
```

This is especially useful when first learning how spine works or when debugging complex queries.

## Technical Details

### Generated SQL

ASQL generates a "spine" CTE with all expected values, then LEFT JOINs your data:

```sql
WITH date_spine AS (
  SELECT DATE_TRUNC('month', d) AS month
  FROM generate_series('2024-01-01'::date, '2024-06-01'::date, INTERVAL '1 month') AS d
),
aggregated AS (
  SELECT DATE_TRUNC('month', order_date) AS month, SUM(amount) AS revenue
  FROM orders
  WHERE order_date >= '2024-01-01' AND order_date < '2024-07-01'
  GROUP BY 1
)
SELECT 
  date_spine.month,
  COALESCE(aggregated.revenue, 0) AS revenue
FROM date_spine
LEFT JOIN aggregated ON date_spine.month = aggregated.month
```

### Dialect Support

ASQL generates dialect-appropriate date generation:

| Dialect | Method |
|---------|--------|
| PostgreSQL | `generate_series()` |
| BigQuery | `GENERATE_DATE_ARRAY()` |
| Snowflake | `GENERATOR()` with `DATEADD` |
| DuckDB | `generate_series()` |
| Others | Recursive CTE or numbers table |

### Spines and Performance

Spine adds minimal overhead (< 5% query time) in most cases. Here's what to expect:

#### Date Spines: Negligible Cost

Date spines use in-memory generation (`generate_series`, `GENERATE_DATE_ARRAY`, etc.) which is extremely fast:

| Date Range | Spine Rows | Typical Cost |
|------------|------------|--------------|
| 1 year of months | 12 rows | < 1ms |
| 5 years of days | ~1,825 rows | < 5ms |
| 10 years of days | ~3,650 rows | < 10ms |

The spine generation itself is trivial. The only real cost is the LEFT JOIN with your aggregated data—but since your aggregated data is already grouped (small result set), this join is fast.

#### Categorical Spines: One Extra Query

For non-date columns, the spine requires:

```sql
SELECT DISTINCT column FROM source_table WHERE <your filters>
```

This hits your source table, so performance depends on:

| Factor | Impact |
|--------|--------|
| Column is indexed | Very fast (index-only scan) |
| Column has low cardinality | Fast (few distinct values) |
| Large table, no index | Can be slow |
| Already filtered by WHERE | Usually fast (smaller scan) |

**Tip:** If you're spining by a categorical column frequently, ensure it's indexed. Most dimension columns (status, region, category) naturally have low cardinality and are fast regardless.

#### Multiple Spine Columns: Cross-Join

When spining by multiple columns, spines are cross-joined:

```
12 months × 5 regions = 60 spine rows
12 months × 50 states = 600 spine rows  
365 days × 100 products = 36,500 spine rows
```

For typical analytics (monthly/quarterly × reasonable dimensions), this is fine. For high-cardinality combinations, consider whether you really need gap-filling.

#### When to Use GROUP BY Instead of SPINE BY

Use regular `group by` (not `spine by`) when:

- You're grouping by a high-cardinality column (user_id, order_id) where gap-filling doesn't make sense—you don't want a row for every user with zero orders
- You specifically don't want gap-filling behavior
- You want maximum performance and don't need completeness

#### The Bottom Line

For typical analytics queries (time-series by month/quarter, categorical breakdowns by region/status/category), spine overhead is **< 5% of query time** and usually unnoticeable. The convenience and correctness benefits far outweigh the cost.

### Column-to-Column Comparisons in WHERE

When your WHERE clause compares the grouped date column to another column, ASQL bounds the spine by your actual data:

```asql
from orders
  where created_at > updated_at  -- Data-dependent bound
  group by month(created_at) (sum(amount) ?? 0 as revenue)
```

**This is the correct behavior.** When you write `created_at > updated_at`, you're saying "my bounds should be defined by this data relationship." The spine correctly represents all periods where your predicate could be satisfied—there's no "missing" data before the MIN because by definition, no data could exist there that satisfies your condition.

**Want explicit bounds instead?** Add them:

```asql
from orders
  where created_at > updated_at 
    and created_at >= @2024-01-01  -- Explicit bound added
  group by month(created_at) (sum(amount) ?? 0 as revenue)
```

Or filter the grouped results:

```asql
from orders
  where created_at > updated_at
  group by month(created_at) (sum(amount) ?? 0 as revenue)
  where month_created_at >= @2024-01-01  -- Filter after grouping
```

## Best Practices

1. **Always use `??` for aggregates** — Decide what missing means (0? NULL? N/A?)
2. **Specify date bounds in WHERE** — Helps ASQL generate the right spine
3. **Use `guarantee()` for fixed categories** — Don't rely on data having all values
4. **Filter zeros when needed** — `where revenue > 0` after spine
5. **Use `spine by` explicitly** — Makes intent clear to readers

## Comparison with dbt

dbt's `date_spine` macro and Kimball-style dimension tables solve the same problem, but require:
- Explicit dimension table creation
- Manual maintenance
- Extra modeling work

ASQL provides this automatically for common patterns.

## Real-World Examples

### Monthly Revenue with All Months

```asql
from orders
  where order_date >= @2024-01-01 and order_date < @2025-01-01
  spine by month(order_date) (
    sum(amount) ?? 0 as revenue,
    # ?? 0 as orders
  )
  order by month
```

### Status Dashboard

```asql-play
from tickets
  spine by guarantee(status, ['open', 'in_progress', 'resolved', 'closed']) (
    # ?? 0 as ticket_count
  )
```

### Sales by Region and Quarter

```asql-play
from sales
  where year(sale_date) = 2024
  spine by region, quarter(sale_date) (
    sum(amount) ?? 0 as revenue
  )
  order by region, quarter
```

### Selective Spine (Date Only)

```asql
from orders
  group by spine(month(order_date)), region (
    sum(amount) ?? 0 as revenue
  )
```

This fills date gaps but only shows regions with actual data.

## Next Steps

- **[Dates & Time](../syntax/dates.md)** — Date truncation and arithmetic
- **[Aggregations](../syntax/aggregations.md)** — GROUP BY syntax
- **[Convention Over Configuration](conventions.md)** — How ASQL infers defaults
