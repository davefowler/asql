# Window Function Utilities

Window functions are incredibly powerful for analytics, but SQL's syntax for them is notoriously verbose. ASQL provides simplified syntax for common window function patterns.

> **See Also:** [Detailed Window Functions Guide](syntax/window-functions.md) for comprehensive documentation.

---

## The Problem with SQL Window Functions

Getting the most recent order per customer in SQL requires this:

```sql
SELECT * FROM (
    SELECT *, 
        ROW_NUMBER() OVER (
            PARTITION BY customer_id 
            ORDER BY order_date DESC
        ) as rn
    FROM orders
) subquery 
WHERE rn = 1;
```

That's 10 lines for a simple concept: "give me the latest order for each customer."

---

## ASQL Solutions

### The `per` Command (Recommended)

The `per` command is the most intuitive way to handle window-based deduplication and ranking:

```asql
-- Get the most recent order per customer
from orders
  per customer_id first by -order_date
```

That's it! One line that reads naturally: "per customer, get the first by order date descending."

#### Syntax

```
per <partition_cols> <operation> by <order_cols> [as <alias>]
```

#### Operations

| Operation | What it does | Default alias |
|-----------|--------------|---------------|
| `first` | Keep first row per partition | (no column added) |
| `last` | Keep last row per partition | (no column added) |
| `number` | Add row number column | `row_num` |
| `rank` | Add rank column | `rank` |
| `dense rank` | Add dense rank column (no gaps) | `dense_rank` |

#### Examples

```asql
-- Deduplication: most recent order per customer
from orders
  per customer_id first by -order_date

-- Add row numbers per customer
from orders
  per customer_id number by -order_date
-- Result: adds `row_num` column

-- Rank employees by salary within department
from employees
  per department rank by -salary
-- Result: adds `rank` column

-- Dense rank (no gaps in ranking)
from employees
  per department dense rank by -salary
-- Result: adds `dense_rank` column
```

Note: `dense rank` and `dense_rank` are interchangeable - underscores and spaces work the same.

---

### Standalone Window Operations (No Partition)

For operations across all rows without partitioning:

```asql
-- Number all rows
from events
  number by -timestamp
-- Result: adds `row_num` to all rows

-- Rank all rows
from scores
  rank by -score
```

---

### QUALIFY Clause (Advanced)

For more complex filtering on window function results:

```asql
from orders
  select *, row_number() over (partition by customer_id order by -order_date) as rn
  qualify rn == 1
```

This compiles to native `QUALIFY` for databases that support it (BigQuery, Snowflake, DuckDB, Databricks), or a subquery for others.

---

### DISTINCT ON (PostgreSQL-style)

For PostgreSQL-style deduplication:

```asql-play
from orders
  distinct on (customer_id)
  order by customer_id, -order_date
```

---

## Simplified Window Functions

### prior() and next()

Instead of verbose `LAG()` and `LEAD()` syntax, use `prior()` and `next()`:

```asql
from monthly_sales
  order by month
  select 
    month,
    revenue,
    prior(revenue) as prev_month,          -- LAG(revenue, 1)
    prior(revenue, 3) as three_months_ago, -- LAG(revenue, 3)
    next(revenue) as next_month            -- LEAD(revenue, 1)
```

**Compiles to:**
```sql
SELECT 
  month,
  revenue,
  LAG(revenue, 1) AS prev_month,
  LAG(revenue, 3) AS three_months_ago,
  LEAD(revenue, 1) AS next_month
FROM monthly_sales
ORDER BY month
```

---

### Running Aggregates

Calculate cumulative totals with `running_sum()`, `running_avg()`, and `running_count()`:

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

**Compiles to:**
```sql
SELECT 
  date,
  amount,
  SUM(amount) OVER (ROWS UNBOUNDED PRECEDING) AS cumulative_total,
  AVG(amount) OVER (ROWS UNBOUNDED PRECEDING) AS avg_to_date,
  COUNT(*) OVER (ROWS UNBOUNDED PRECEDING) AS transaction_number
FROM transactions
ORDER BY date
```

---

### Rolling Aggregates

Calculate moving averages with `rolling_avg()` and `rolling_sum()`:

```asql
from daily_sales
  order by date
  select 
    date,
    revenue,
    rolling_avg(revenue, 7) as seven_day_avg,
    rolling_sum(revenue, 30) as thirty_day_total
```

**Compiles to:**
```sql
SELECT 
  date,
  revenue,
  AVG(revenue) OVER (ROWS 6 PRECEDING) AS seven_day_avg,
  SUM(revenue) OVER (ROWS 29 PRECEDING) AS thirty_day_total
FROM daily_sales
ORDER BY date
```

---

### first() and last() with ORDER BY

Get the first or last value based on ordering:

```asql
from orders
  select 
    customer_id,
    first(order_id order by order_date) as first_order,
    last(order_id order by order_date) as latest_order
```

---

### arg_max() and arg_min() (ClickHouse-style)

Get the value of one column where another column is at its maximum or minimum:

```asql
from orders
  select 
    customer_id,
    arg_max(order_id, order_date) as latest_order_id,
    arg_min(order_id, order_date) as earliest_order_id
```

This returns:
- `latest_order_id`: The order_id where order_date is maximum
- `earliest_order_id`: The order_id where order_date is minimum

---

## Full Window Function Syntax

ASQL also supports the full window function syntax with `OVER`:

```asql
from employees
  select *, 
    row_number() over (partition by department order by -salary) as salary_rank,
    rank() over (partition by department order by -salary) as rank,
    sum(salary) over (partition by department) as dept_total
```

**Supported window functions:**
- `row_number()`, `rank()`, `dense_rank()`
- `lag()`, `lead()`
- `first_value()`, `last_value()`
- `sum()`, `avg()`, `count()`, `min()`, `max()` with `OVER`

---

## Function Reference

### Pipeline Commands

| ASQL Command | SQL Equivalent | Description |
|--------------|----------------|-------------|
| `per group first by col` | Subquery + ROW_NUMBER + QUALIFY | Keep first row per group |
| `per group last by col` | Subquery + ROW_NUMBER + QUALIFY | Keep last row per group |
| `per group number by col` | ROW_NUMBER() OVER (PARTITION BY) | Add row number column |
| `per group rank by col` | RANK() OVER (PARTITION BY) | Add rank column |
| `per group dense rank by col` | DENSE_RANK() OVER (PARTITION BY) | Add dense rank column |
| `number by col` | ROW_NUMBER() OVER (ORDER BY) | Add row number (all rows) |
| `rank by col` | RANK() OVER (ORDER BY) | Add rank (all rows) |

### Window Functions

| ASQL Function | SQL Equivalent | Description |
|--------------|----------------|-------------|
| `prior(col)` | `LAG(col, 1)` | Value from previous row |
| `prior(col, n)` | `LAG(col, n)` | Value from n rows before |
| `next(col)` | `LEAD(col, 1)` | Value from next row |
| `next(col, n)` | `LEAD(col, n)` | Value from n rows after |
| `running_sum(col)` | `SUM(col) OVER (ROWS UNBOUNDED PRECEDING)` | Cumulative sum |
| `running_avg(col)` | `AVG(col) OVER (ROWS UNBOUNDED PRECEDING)` | Cumulative average |
| `running_count(*)` | `COUNT(*) OVER (ROWS UNBOUNDED PRECEDING)` | Cumulative count |
| `rolling_sum(col, n)` | `SUM(col) OVER (ROWS n-1 PRECEDING)` | Rolling sum of n rows |
| `rolling_avg(col, n)` | `AVG(col) OVER (ROWS n-1 PRECEDING)` | Rolling average of n rows |
| `first(col order by x)` | `FIRST_VALUE(col) OVER (ORDER BY x)` | First value when ordered |
| `last(col order by x)` | `FIRST_VALUE(col) OVER (ORDER BY x DESC)` | Last value when ordered |
| `arg_max(col, x)` | Value of col where x is MAX | ClickHouse-style argMax |
| `arg_min(col, x)` | Value of col where x is MIN | ClickHouse-style argMin |

---

## Common Patterns

### Get Most Recent Record Per Group

```asql
-- Pattern 1: Using per command (cleanest)
from orders
  per customer_id first by -order_date

-- Pattern 2: Using QUALIFY
from orders
  select *, row_number() over (partition by customer_id order by -order_date) as rn
  qualify rn = 1

-- Pattern 3: Using DISTINCT ON (PostgreSQL-style)
from orders
  distinct on (customer_id)
  order by customer_id, -order_date
```

### Month-over-Month Comparison

```asql
from monthly_revenue
  select 
    month,
    revenue,
    prior(revenue) as prev_month,
    revenue - prior(revenue) as mom_change,
    (revenue - prior(revenue)) / prior(revenue) * 100 as mom_pct_change
  order by month
```

### Rolling 7-Day Average

```asql
from daily_metrics
  order by date
  select 
    date,
    value,
    rolling_avg(value, 7) as seven_day_avg
```

### Cumulative Running Total

```asql
from transactions
  order by date
  select 
    date,
    amount,
    running_sum(amount) as balance
```

### Rank Within Groups

```asql
-- Pattern 1: Using per command
from employees
  per department rank by -salary
  where rank <= 3  -- Top 3 in each department

-- Pattern 2: Using QUALIFY
from employees
  select 
    department,
    name,
    salary,
    rank() over (partition by department order by -salary) as salary_rank
  qualify salary_rank <= 3  -- Top 3 in each department
```

---

## Next Steps

- **[Detailed Window Functions](syntax/window-functions.md)** — Comprehensive window function documentation
- **[Aggregations](syntax/aggregations.md)** — GROUP BY with window functions
- **[Examples](examples.md)** — More real-world patterns
- **[Functions Reference](reference/functions.md)** — All window functions
