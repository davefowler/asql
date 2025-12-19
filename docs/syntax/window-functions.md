# Window Functions

ASQL provides intuitive syntax for window functions, making common patterns like deduplication, ranking, and running totals much cleaner than SQL.

## The `per` Command

The `per` command creates a window context for partitioned operations:

```
per <partition_cols> <operation> by <order_cols> [as <alias>]
```

Or without partition (whole table):

```
<operation> by <order_cols> [as <alias>]
```

### Available Operations

| Operation | What it does | Default alias | Row count |
|-----------|--------------|---------------|-----------|
| `first` | Keep first row per partition | (filters) | ↓ Reduces |
| `last` | Keep last row per partition | (filters) | ↓ Reduces |
| `number` | Add row number column | `row_num` | Same |
| `rank` | Add rank column | `rank` | Same |
| `dense rank` | Add dense rank column | `dense_rank` | Same |

## Deduplication with `first` / `last`

Keep the first or last row per group:

```asql
-- Most recent order per customer
from orders
  per customer_id first by -order_date

-- Oldest order per customer
from orders
  per customer_id first by order_date

-- Keep last row per user/event
from events
  per user_id, event_type last by timestamp
```

The `-` prefix means descending order.

## Row Numbering

Add row numbers within partitions:

```asql-play
-- Number orders per customer (most recent = 1)
from orders
  per customer_id number by -order_date

-- Adds column: row_num
```

With custom alias:

```asql-play
from orders
  per customer_id number by -order_date as order_num
```

## Ranking

Add rank columns:

```asql
-- Rank employees by salary within department
from employees
  per department rank by -salary

-- Dense rank (no gaps)
from employees
  per department dense rank by -salary
```

## Whole-Table Operations

Without partition (operates on entire table):

```asql
-- Number all rows
from events
  number by -timestamp

-- Rank all scores
from scores
  rank by -score as global_rank

-- Dense rank all
from scores
  dense rank by -score
```

## `prior()` and `next()` (LAG/LEAD)

Access previous or next row values:

```asql
from monthly_sales
  order by month
  select
    month,
    revenue,
    prior(revenue) as prev_month,        -- LAG(revenue, 1)
    prior(revenue, 3) as three_ago,      -- LAG(revenue, 3)
    next(revenue) as next_month          -- LEAD(revenue, 1)
```

The `order by` clause provides the window ordering.

### Month-over-Month Comparison

```asql
from monthly_sales
  order by month
  select
    month,
    revenue,
    prior(revenue) as prev_revenue,
    revenue - prior(revenue) as mom_change,
    (revenue - prior(revenue)) / prior(revenue) * 100 as mom_pct_change
```

## Running Aggregates (Cumulative)

Calculate cumulative totals from the start:

```asql
from transactions
  order by date
  select
    date,
    amount,
    running_sum(amount) as cumulative_total,
    running_avg(amount) as avg_to_date,
    running_count(*) as transaction_number
```

Available running functions:
- `running_sum(col)` — Cumulative sum
- `running_avg(col)` — Cumulative average
- `running_count(*)` — Row number (cumulative count)

## Rolling Aggregates (Moving Window)

Calculate moving averages with a specified window size:

```asql
from daily_sales
  order by date
  select
    date,
    revenue,
    rolling_avg(revenue, 7) as seven_day_avg,
    rolling_sum(revenue, 30) as thirty_day_total
```

The second parameter is the window size (number of rows).

## `first()` and `last()` in GROUP BY

Get the first or last value when aggregating:

```asql-play
from orders
  group by customer_id (
    first(order_id order by -order_date) as latest_order,
    last(order_id order by order_date) as first_order,
    # as total_orders
  )
```

### `per ... first` vs `first()` in GROUP BY

| Use Case | Syntax | Purpose |
|----------|--------|---------|
| Keep whole row | `per customer_id first by -date` | Deduplication |
| Extract specific value | `first(order_id order by -date)` | Aggregation |

## `arg_max()` / `arg_min()`

Get the value of one column where another column is max/min (ClickHouse-inspired):

```asql-play
from orders
  group by customer_id (
    arg_max(order_id, order_date) as latest_order_id,
    arg_min(order_id, order_date) as earliest_order_id
  )
```

- `arg_max(return_col, sort_col)` — Value of `return_col` where `sort_col` is maximum
- `arg_min(return_col, sort_col)` — Value of `return_col` where `sort_col` is minimum

## QUALIFY Clause

Filter on window function results:

```asql
from orders
  select *, row_number() over (partition by customer_id order by -order_date) as rn
  qualify rn = 1
```

This is equivalent to wrapping in a subquery and filtering.

## DISTINCT ON

PostgreSQL-style deduplication:

```asql-play
from orders
  distinct on (customer_id)
  order by customer_id, -order_date
```

Note: `per ... first by` is often clearer and more portable.

## Standard Window Functions

You can use standard SQL window functions directly:

```asql
from orders
  select 
    *,
    row_number() over (partition by customer_id order by -order_date) as rn,
    rank() over (partition by category order by -amount) as category_rank,
    sum(amount) over (partition by region) as region_total
```

### Window Frame Specifications

For advanced use cases:

```asql
from sales
  select
    date,
    revenue,
    sum(revenue) over (
      order by date 
      rows between 6 preceding and current row
    ) as seven_day_sum
```

## Quick Reference

| Intent | ASQL Syntax |
|--------|-------------|
| Most recent row per group | `per group_col first by -date` |
| Oldest row per group | `per group_col first by date` |
| Add row numbers per group | `per group_col number by -date` |
| Add rank per group | `per group_col rank by -value` |
| Add dense rank per group | `per group_col dense rank by -value` |
| Get column value at max | `arg_max(col, sort_col)` |
| Previous row value | `prior(col)` |
| Next row value | `next(col)` |
| Cumulative sum | `running_sum(col)` |
| Cumulative average | `running_avg(col)` |
| 7-day moving average | `rolling_avg(col, 7)` |
| First value in group | `first(col order by ...)` |

## Real-World Examples

### Latest Order Per Customer

```asql-play
from orders
  per customer_id first by -order_date
  select customer_id, order_id, amount, order_date
```

### Rank Products by Revenue

```asql
from order_items
  & products on order_items.product_id = products.id
  group by products.category, products.name (
    sum(order_items.amount) as revenue
  )
  per category rank by -revenue as category_rank
```

### Year-over-Year Comparison

```asql
from monthly_metrics
  order by month
  select
    month,
    revenue,
    prior(revenue, 12) as same_month_last_year,
    revenue - prior(revenue, 12) as yoy_change
```

### Running Total with Daily Revenue

```asql
from orders
  group by day(created_at) as date (
    sum(amount) as daily_revenue
  )
  order by date
  select
    date,
    daily_revenue,
    running_sum(daily_revenue) as cumulative_revenue
```

## Next Steps

- **[Aggregations](aggregations.md)** — GROUP BY with window functions
- **[CTEs & Variables](ctes.md)** — Composing complex queries
- **[Examples](../examples.md)** — More real-world patterns
