# Guaranteed Groups

One of ASQL's most powerful features is **guaranteed groups**: when you group data, ASQL ensures all expected dimension values appear in results—even if they have no data.

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

For non-date columns, ASQL uses DISTINCT values from the source data:

```asql-play
from orders
  group by status (
    # ?? 0 as count
  )
```

If your data has orders with status "pending", "shipped", and "delivered", all three will appear even if one has zero orders in the filtered period.

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

### Performance Considerations

- Date spines are generated dynamically based on your WHERE clause
- For very large date ranges, consider explicit bounds
- Non-date DISTINCT spines query the source table

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
