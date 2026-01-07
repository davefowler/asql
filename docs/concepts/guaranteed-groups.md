# Guaranteed Groups

One of ASQL's most powerful features is **guaranteed groups**: when you group data, ASQL ensures all expected dimension values appear in results—even if they have no data.

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

## The Solution

ASQL automatically fills gaps:

```asql-play
from orders
  group by month(order_date) (
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

## How It Works

### Date Truncations

When you group by a date truncation function (`month()`, `year()`, `week()`, etc.), ASQL:

1. Infers the date range from your WHERE clause
2. Generates all values in that range
3. LEFT JOINs your data to the complete range
4. Fills missing values with NULL (use `??` for defaults)

```asql
from orders
  where order_date >= @2024-01-01 and order_date < @2024-07-01
  group by month(order_date) (
    sum(amount) ?? 0 as revenue
  )
```

All months from January to June will appear.

### Non-Date Columns

For non-date columns, ASQL uses DISTINCT values from the **filtered** source data:

```asql-play
from orders
  group by status (
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
  group by region (
    sum(amount) ?? 0 as revenue
  )
```

This will **only show North America**—not Europe, Asia, or other regions—because the spine is generated from the filtered data.

**This is usually what you want!** When you filter to North America, you typically want results only for North America. The spine ensures you see all North American sub-categories (if grouping by something like `state`), but it respects your top-level filter.

**Want all regions to appear (even with filtered data)?** Use `guarantee()`:

```asql
from orders
  where region = 'North America'
  group by guarantee(region, ['North America', 'Europe', 'Asia', 'South America']) (
    sum(amount) ?? 0 as revenue
  )
```

Now all four regions appear—North America with actual data, the others with zero revenue.

| Scenario | Result |
|----------|--------|
| `group by region` with `where region = 'NA'` | Only NA appears |
| `group by region` (no filter) | All regions in data appear |
| `group by guarantee(region, [...])` | All listed values appear |

### Multiple GROUP BY Columns

When grouping by multiple columns, ASQL creates all combinations:

```asql-play
from orders
  group by region, month(order_date) (
    sum(amount) ?? 0 as revenue
  )
```

Every region × month combination will appear.

## Explicit Values with `guarantee()`

Specify exactly which values should appear:

```asql-play
from orders
  group by guarantee(status, ['pending', 'shipped', 'delivered', 'cancelled']) (
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
  group by month(order_date) (
    sum(amount) ?? 0 as revenue,        -- Default to 0
    # ?? 0 as orders,            -- Default to 0
    avg(amount) as avg_order            -- Leave as NULL
  )
```

Different columns can have different default behaviors.

## Disabling Guaranteed Groups

### Filter the Results

The most common approach—just filter out zeros:

```asql-play
from orders
  group by month(order_date) (
    sum(amount) as revenue
  )
  where revenue > 0
```

### Disable for a Query

Use a SET statement:

```asql
SET auto_spine = false;
from orders
  group by month(order_date) (
    sum(amount) as revenue
  )
```

### Disable Globally

Configure in your ASQL settings or via API.

## Understanding the Generated SQL

### Transpilation Comments

To understand the generated SQL, enable transpilation comments:

```asql
SET include_transpilation_comments = true;

from orders
  where order_date >= @2024-01-01 and order_date < @2024-07-01
  group by month(order_date) (
    sum(amount) ?? 0 as revenue
  )
```

The output will include a helpful explanation:

```sql
/* ASQL auto-spine: Gap-filling CTEs were generated to ensure all 
   expected GROUP BY values appear (even with zero/null aggregates). 
   Disable with: SET auto_spine = false; */
WITH month_order_date_spine AS (...)
...
```

This is especially useful when first learning how auto-spine works or when debugging complex queries.

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

Auto-spine adds minimal overhead (< 5% query time) in most cases. Here's what to expect:

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

**Tip:** If you're grouping by a categorical column frequently, ensure it's indexed. Most dimension columns (status, region, category) naturally have low cardinality and are fast regardless.

#### Multiple GROUP BY Columns: Cross-Join

When grouping by multiple columns, spines are cross-joined:

```
12 months × 5 regions = 60 spine rows
12 months × 50 states = 600 spine rows  
365 days × 100 products = 36,500 spine rows
```

For typical analytics (monthly/quarterly × reasonable dimensions), this is fine. For high-cardinality combinations, consider whether you really need gap-filling.

#### When to Disable Auto-Spine

Consider `SET auto_spine = false` when:

- You're grouping by a high-cardinality column (user_id, order_id) where gap-filling doesn't make sense—you don't want a row for every user with zero orders. Disabling is equivalent to filtering `where count != 0` afterwards, but saves 10-30% query overhead.
- You specifically don't want gap-filling behavior

#### Multiple GROUP BY Columns

When grouping by many columns, the spines are cross-joined:

```
12 months × 5 regions = 60 rows
12 months × 50 states × 20 categories = 12,000 rows
```

This is still efficient—the cross-join happens on small dimension sets, and the LEFT JOIN uses hash joins. Even for large combinations (millions of rows), expect 20-40% overhead compared to the base query. For materialized views or batch jobs where you genuinely want complete dimension coverage, this is reasonable.

One benefit of auto-spine: you don't need to pre-materialize every dimension combination "just in case." Since downstream queries also get gap-filling automatically, you can let each query fill the gaps it needs rather than over-engineering your data models for completeness upfront.

#### The Bottom Line

For typical analytics queries (time-series by month/quarter, categorical breakdowns by region/status/category), auto-spine overhead is **< 5% of query time** and usually unnoticeable. The convenience and correctness benefits far outweigh the cost.

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
4. **Filter zeros when needed** — `where revenue > 0` after grouping

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
  group by month(order_date) (
    sum(amount) ?? 0 as revenue,
    # ?? 0 as orders
  )
  order by month
```

### Status Dashboard

```asql-play
from tickets
  group by guarantee(status, ['open', 'in_progress', 'resolved', 'closed']) (
    # ?? 0 as ticket_count
  )
```

### Sales by Region and Quarter

```asql-play
from sales
  where year(sale_date) = 2024
  group by region, quarter(sale_date) (
    sum(amount) ?? 0 as revenue
  )
  order by region, quarter
```

## Next Steps

- **[Dates & Time](../syntax/dates.md)** — Date truncation and arithmetic
- **[Aggregations](../syntax/aggregations.md)** — GROUP BY syntax
- **[Convention Over Configuration](conventions.md)** — How ASQL infers defaults
