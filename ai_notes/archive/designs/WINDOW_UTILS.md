# Window Function Utilities for ASQL

This document covers window function patterns in ASQL - how to make common operations intuitive and concise.

**Last Updated**: December 2024

**Key Principle**: All multi-word functions follow the [underscore/space principle](UNDERSCORE_SPACE_PRINCIPLE.md) - `dense_rank` and `dense rank` are interchangeable, `running_sum` and `running sum` are equivalent, etc.

---

## ✅ Implementation Status

| Feature | Status | Example |
|---------|--------|---------|
| `per ... first by ...` | ✅ Implemented | `per customer_id first by -order_date` |
| `per ... last by ...` | ✅ Implemented | `per customer_id last by order_date` |
| `per ... number by ...` | ✅ Implemented | `per customer_id number by -order_date` |
| `per ... rank by ...` | ✅ Implemented | `per customer_id rank by -salary` |
| `per ... dense rank by ...` | ✅ Implemented | `per department dense rank by -salary` |
| `number by ...` (no partition) | ✅ Implemented | `number by -timestamp` |
| `rank by ...` (no partition) | ✅ Implemented | `rank by -score` |
| first() / last() in GROUP BY | ✅ Implemented | `first(order_id order by -order_date)` |
| arg_max() / arg_min() | ✅ Implemented | `arg_max(order_id, order_date)` |
| prior() / next() | ✅ Implemented | `prior(revenue)`, `next(revenue, 2)` |
| running_sum/avg/count() | ✅ Implemented | `running_sum(amount)` |
| rolling_avg/sum() | ✅ Implemented | `rolling_avg(revenue, 7)` |

**Note**: `first`/`last` require a partition - use `per ... first by ...` for deduplication, or `first()` / `last()` as aggregates in GROUP BY.

---

## Design Philosophy

### Two Contexts for Window-like Operations

**1. GROUP BY aggregates** - collapse rows, extract values:
```asql
from orders
  group by customer_id (
    first(order_id order by -order_date) as latest_order,
    last(order_id order by order_date) as first_order
  )
```
→ One row per customer, specific columns extracted

**2. Pipeline steps** - transform row set, keep all columns:
```asql
from orders
  per customer_id first by -order_date
```
→ One row per customer, ALL columns preserved

Both are useful! The GROUP BY version is for when you want specific aggregated values. The pipeline version is for deduplication while keeping the full row.

---

## The `per` Command (Pipeline Window Operations)

The `per` command creates a window context for operations that work on partitions:

### Syntax

```
per <partition_cols> <operation> by <order_cols> [as <alias>]
```

Or without partition (whole table):
```
<operation> by <order_cols> [as <alias>]
```

### Operations

| Operation | Aliases | What it does | Default alias | Row count |
|-----------|---------|--------------|---------------|-----------|
| `first` | | Keep first row per partition | (no column) | ↓ Reduces |
| `last` | | Keep last row per partition | (no column) | ↓ Reduces |
| `number` | | Add row number column | `row_num` | Same |
| `rank` | | Add rank column | `rank` | Same |
| `dense rank` | `dense_rank` | Add dense rank column | `dense_rank` | Same |

**Note**: Following the [underscore/space principle](UNDERSCORE_SPACE_PRINCIPLE.md), `dense rank` and `dense_rank` are interchangeable.

### Examples

```asql
# DEDUPLICATION: Keep most recent order per customer
from orders
  per customer_id first by -order_date

# DEDUPLICATION: Keep earliest order per customer  
from orders
  per customer_id first by order_date

# DEDUPLICATION: Keep last (equivalent to first with reversed order)
from orders
  per customer_id last by order_date

# ADD ROW NUMBER: Number orders per customer (most recent = 1)
from orders
  per customer_id number by -order_date
# Result: adds `row_num` column

# ADD ROW NUMBER: With custom alias
from orders
  per customer_id number by -order_date as order_num

# ADD RANK: Rank employees by salary within department
from employees
  per department rank by -salary
# Result: adds `rank` column

# ADD DENSE RANK: Dense rank (no gaps)
from employees
  per department dense rank by -salary
# Result: adds `dense_rank` column

# NO PARTITION: Number all rows
from events
  number by -timestamp
# Result: adds `row_num` to all rows, ordered by timestamp desc

# NO PARTITION: Rank all rows
from scores
  rank by -score
# Result: adds `rank` to all rows
```

**Note**: Standalone `first by` / `last by` are NOT supported - they require a partition. Use `per ... first by ...` for deduplication.

### Reading the Syntax

The `per` prefix reads naturally in English:
- `per customer_id first by -order_date` → "Per customer, get the first by order date descending"
- `per department rank by -salary` → "Per department, rank by salary descending"
- `number by -timestamp` → "Number by timestamp descending"

---

## Comparison: `per ... first` vs `first()` in GROUP BY

These serve different purposes:

### `per ... first by` (Pipeline - Deduplication)

```asql
from orders
  per customer_id first by -order_date
```

**Result**: One row per customer with ALL columns from the original row
```
| customer_id | order_id | order_date | amount | status |
|-------------|----------|------------|--------|--------|
| 1           | 105      | 2024-03-15 | 99.00  | shipped|
| 2           | 203      | 2024-03-14 | 150.00 | pending|
```

### `first()` in GROUP BY (Aggregate - Value Extraction)

```asql
from orders
  group by customer_id (
    first(order_id order by -order_date) as latest_order,
    first(amount order by -order_date) as latest_amount,
    count(*) as total_orders
  )
```

**Result**: One row per customer with SPECIFIC aggregated columns
```
| customer_id | latest_order | latest_amount | total_orders |
|-------------|--------------|---------------|--------------|
| 1           | 105          | 99.00         | 5            |
| 2           | 203          | 150.00        | 3            |
```

**Use `per ... first`** when you want the whole row (deduplication).
**Use `first()` in GROUP BY** when you want specific values plus other aggregations.

---

## Default Column Names

All operations generate sensible default aliases:

| Operation | Equivalent Forms | Default Alias |
|-----------|------------------|---------------|
| `number by ...` | | `row_num` |
| `rank by ...` | | `rank` |
| `dense rank by ...` | `dense_rank by ...` | `dense_rank` |
| `first by ...` | | (no column - filters rows) |
| `last by ...` | | (no column - filters rows) |
| `prior(col)` | | `prior_<col>` |
| `next(col)` | | `next_<col>` |
| `running col` | `running_col`, `running_sum(col)`, `running sum(col)` | `running_<col>` |
| `running avg(col)` | `running_avg(col)` | `running_avg_<col>` |
| `rolling avg(col, n)` | `rolling_avg(col, n)` | `<col>_<n>_avg` |
| `rolling sum(col, n)` | `rolling_sum(col, n)` | `<col>_<n>_sum` |

**Note**: All multi-word functions follow the [underscore/space principle](UNDERSCORE_SPACE_PRINCIPLE.md) - underscores and spaces are interchangeable.

---

## Other Window Utilities

### arg_max() / arg_min() (ClickHouse-inspired)

Get the value of one column where another column is max/min:

```asql
# All equivalent:
arg_max(order_id, order_date)
arg max(order_id, order_date)

# Full example
from orders
  group by customer_id (
    arg max(order_id, order_date) as latest_order_id,
    arg min(order_id, order_date) as earliest_order_id
  )
```

### first() / last() in GROUP BY (DuckDB-style)

Get the first or last value when sorted (within a GROUP BY):

```asql
from orders
  group by customer_id (
    first(order_id order by -order_date) as latest_order,
    last(order_id order by -order_date) as earliest_order,
    count(*) as total_orders
  )
```

### prior() / next() (Simplified LAG/LEAD)

```asql
from monthly_sales
  order by month
  select
    month,
    revenue,
    prior(revenue) as prior_revenue,      # LAG(revenue, 1) → default alias
    prior(revenue, 3) as three_months_ago,
    next(revenue) as next_revenue         # LEAD(revenue, 1)
```

### running / running_sum() / running_avg() / running_count()

Cumulative aggregates. Following the underscore/space principle, all these are equivalent:

```asql
# All equivalent ways to write running sum:
running_sum(amount)
running sum(amount)
running_amount        # shorthand: running_<col>
running amount        # shorthand with space

# Full example
from transactions
  order by date
  select
    date,
    amount,
    running amount,                    # → running_amount (default alias)
    running avg(amount) as avg_to_date,
    running count(*) as transaction_number
```

### rolling / rolling_avg() / rolling_sum() with Window Size

Moving window aggregates:

```asql
# All equivalent:
rolling_avg(revenue, 7)
rolling avg(revenue, 7)

# Full example
from daily_sales
  order by date
  select
    date,
    revenue,
    rolling avg(revenue, 7),           # → revenue_7_avg (default alias)
    rolling sum(revenue, 30) as monthly_total
```

---

## Full Example: Customer Order Analysis

```asql
# Get each customer's most recent order with running totals
from orders
  per customer_id number by -order_date    # Adds row_num
  order by customer_id, -order_date
  select
    customer_id,
    order_id,
    order_date,
    amount,
    row_num,
    running_sum(amount) as cumulative_spend,
    prior(amount) as prev_order_amount

# Or just get the most recent order per customer
from orders
  per customer_id first by -order_date
```

---

## Quick Reference

| Intent | ASQL Syntax | Also works as |
|--------|-------------|---------------|
| Most recent row per group | `per group_col first by -date` | |
| Oldest row per group | `per group_col first by date` | |
| Add row numbers per group | `per group_col number by -date` | |
| Add rank per group | `per group_col rank by -value` | |
| Add dense rank per group | `per group_col dense rank by -value` | `dense_rank by` |
| Get column value at max | `arg_max(col, sort_col)` | `arg max(...)` |
| Previous row value | `prior(col)` | |
| Next row value | `next(col)` | |
| Cumulative sum | `running col` | `running_sum(col)`, `running sum(col)` |
| Cumulative average | `running avg(col)` | `running_avg(col)` |
| 7-day moving average | `rolling avg(col, 7)` | `rolling_avg(col, 7)` |
| First value in group | `first(col order by sort)` | GROUP BY context |

---

## References

- [DuckDB QUALIFY](https://duckdb.org/docs/sql/query_syntax/qualify.html)
- [BigQuery QUALIFY](https://cloud.google.com/bigquery/docs/reference/standard-sql/query-syntax#qualify_clause)
- [ClickHouse argMax](https://clickhouse.com/docs/en/sql-reference/aggregate-functions/reference/argmax)
- [PostgreSQL DISTINCT ON](https://www.postgresql.org/docs/current/sql-select.html#SQL-DISTINCT)
- [PRQL Window Functions](https://prql-lang.org/book/reference/stdlib/transforms/window.html)
