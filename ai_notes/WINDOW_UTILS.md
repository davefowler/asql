# Window Function Utilities for ASQL

This document explores ideas for making common window function patterns easier and more intuitive in ASQL.

**Last Updated**: December 2024

---

## ✅ Implementation Status

The following features have been implemented:

| Feature | Status | Example |
|---------|--------|---------|
| QUALIFY clause | ✅ Implemented | `qualify rn == 1` |
| DISTINCT ON | ✅ Implemented | `distinct on (customer_id)` |
| prior() / next() | ✅ Implemented | `prior(revenue)`, `next(revenue, 2)` |
| first() / last() with ORDER BY | ✅ Implemented | `first(order_id order by -order_date)` |
| arg_max() / arg_min() | ✅ Implemented | `arg_max(order_id, order_date)` |
| running_sum/avg/count() | ✅ Implemented | `running_sum(amount)` |
| rolling_avg/sum() | ✅ Implemented | `rolling_avg(revenue, 7)` |
| Window functions with OVER | ✅ Implemented | `row_number() over (partition by customer_id order by -order_date)` |

---

## The Problem

Window functions are extremely powerful but have notoriously verbose syntax. The most common pattern — "get the first/last row per group" — requires a subquery with `ROW_NUMBER()`:

```sql
-- Standard SQL: Get most recent order per customer
SELECT * FROM (
    SELECT *, 
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) as rn
    FROM orders
) WHERE rn = 1
```

This is:
- 5 lines for a simple concept
- Requires a subquery
- Uses magic number `rn = 1`
- Easy to mess up the `ORDER BY` direction

---

## Part 1: Innovations in Other SQL Dialects

### 1.1 QUALIFY Clause (BigQuery, Snowflake, DuckDB, Databricks)

The `QUALIFY` clause filters on window function results without a subquery:

```sql
-- BigQuery/Snowflake/DuckDB syntax
SELECT *
FROM orders
QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) = 1
```

**Benefits**: No subquery needed, much cleaner
**ASQL Opportunity**: Support `qualify` as a clause

```asql
# Proposed ASQL
from orders
  qualify row_number() over (partition by customer_id order by -order_date) == 1
```

### 1.2 ClickHouse's argMax/argMin Functions

ClickHouse has brilliant aggregate functions that return the value of one column where another column is max/min:

```sql
-- ClickHouse: Get the order_id with the max order_date per customer
SELECT 
    customer_id,
    argMax(order_id, order_date) as latest_order_id,
    argMax(amount, order_date) as latest_order_amount
FROM orders
GROUP BY customer_id
```

**Benefits**: No window function needed at all! Works as a simple aggregate.
**ASQL Opportunity**: Add `arg_max()` and `arg_min()` functions

```asql
# Proposed ASQL
from orders
  group by customer_id (
    arg_max(order_id, order_date) as latest_order_id,
    arg_max(amount, order_date) as latest_amount
  )
```

### 1.3 PRQL's Window Syntax

PRQL uses a cleaner window function syntax with `window`:

```prql
# PRQL syntax
from orders
sort order_date
window customer_id (
  derive row_num = row_number
)
filter row_num == 1
```

**Benefits**: Separates partitioning from the function, more readable
**ASQL Opportunity**: Consider similar `partition` or `window` block syntax

### 1.4 DuckDB's FIRST/LAST Aggregates (with ORDER BY)

DuckDB supports `FIRST()` and `LAST()` as aggregate functions with an optional `ORDER BY`:

```sql
-- DuckDB syntax
SELECT 
    customer_id,
    FIRST(order_id ORDER BY order_date DESC) as latest_order_id
FROM orders
GROUP BY customer_id
```

**Benefits**: Clean, simple, intuitive
**ASQL Opportunity**: Add `first()` and `last()` aggregates with ordering

```asql
# Proposed ASQL
from orders
  group by customer_id (
    first(order_id, order by -order_date) as latest_order_id
  )
```

### 1.5 Databricks/Spark's first() Aggregate

Databricks has `first()` as an aggregate that returns the first value encountered:

```sql
-- Databricks
SELECT customer_id, first(order_id)
FROM orders
GROUP BY customer_id
```

**Note**: This doesn't guarantee ordering without a preceding ORDER BY, but it's still useful.

---

## Part 2: Common dbt Patterns & Macros

### 2.1 dbt_utils.deduplicate (Proposed/Common Pattern)

Many teams create a `deduplicate` macro:

```sql
-- Common dbt pattern
{% macro deduplicate(relation, partition_by, order_by) %}
    SELECT * FROM (
        SELECT *,
            ROW_NUMBER() OVER (PARTITION BY {{ partition_by }} ORDER BY {{ order_by }}) as _rn
        FROM {{ relation }}
    )
    WHERE _rn = 1
{% endmacro %}
```

Usage:
```sql
{{ deduplicate('orders', 'customer_id', 'order_date DESC') }}
```

**ASQL Opportunity**: Make deduplication a first-class operation

```asql
# Proposed ASQL: "distinct on" syntax (PostgreSQL-inspired)
from orders
  distinct on customer_id (order by -order_date)
  
# Or even simpler with a "first" operator
from orders
  first per customer_id (order by -order_date)
```

### 2.2 dbt_metrics Secondary Calculations

The dbt_metrics package provides window-based calculations:
- `period_over_period` - Compare to previous period
- `rolling` - Rolling window aggregations
- `prior` - Get prior period value

```sql
-- These become window functions under the hood
{{ metrics.calculate(
    metric('revenue'),
    secondary_calculations=[
        metrics.period_over_period(comparison_strategy="difference"),
        metrics.rolling(aggregate="average", interval=7)
    ]
) }}
```

**ASQL Opportunity**: Built-in period comparison functions

```asql
# Proposed ASQL
from monthly_revenue
  order by month
  select 
    month,
    revenue,
    prior(revenue) as prev_month_revenue,
    revenue - prior(revenue) as mom_change,
    rolling_avg(revenue, 3) as three_month_avg
```

---

## Part 3: Proposed ASQL Enhancements

### Priority 1: High-Impact, Low-Complexity

#### 3.1 QUALIFY Clause Support

Add `qualify` as a filter that runs after window functions:

```asql
from orders
  select *, row_number() over (partition by customer_id order by -order_date) as rn
  qualify rn == 1
```

**Implementation**: Relatively straightforward - just a new clause type that compiles to a subquery wrapper in dialects that don't support QUALIFY natively.

#### 3.2 DISTINCT ON Support (PostgreSQL-style)

PostgreSQL's `DISTINCT ON` is the cleanest way to deduplicate:

```sql
-- PostgreSQL
SELECT DISTINCT ON (customer_id) *
FROM orders
ORDER BY customer_id, order_date DESC
```

```asql
# Proposed ASQL
from orders
  distinct on (customer_id)
  order by customer_id, -order_date
```

**Implementation**: Compile to DISTINCT ON for Postgres, ROW_NUMBER() subquery for others.

### Priority 2: New Aggregate Functions

#### 3.3 first() / last() with Ordering

```asql
from orders
  group by customer_id (
    first(order_id order by -order_date) as latest_order,
    last(order_id order by order_date) as first_order
  )
```

Compiles to:
- DuckDB: Native `FIRST(... ORDER BY ...)`
- Others: Subquery with `ROW_NUMBER()`

#### 3.4 arg_max() / arg_min() (ClickHouse-inspired)

"Get the value of X where Y is max/min"

```asql
from orders
  group by customer_id (
    arg_max(order_id, order_date) as latest_order_id,
    max(order_date) as latest_order_date
  )
```

Compiles to:
- ClickHouse: Native `argMax()`
- Others: Subquery with `ROW_NUMBER()`

### Priority 3: Convenience Functions

#### 3.5 prior() / next() (Simplified LAG/LEAD)

```asql
from monthly_sales
  order by month
  select
    month,
    revenue,
    prior(revenue) as prev_month,           # LAG(revenue, 1)
    prior(revenue, 3) as three_months_ago,  # LAG(revenue, 3)
    next(revenue) as next_month             # LEAD(revenue, 1)
```

#### 3.6 running_sum() / running_avg() / running_count()

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

Compiles to:
```sql
SELECT 
    date,
    amount,
    SUM(amount) OVER (ORDER BY date ROWS UNBOUNDED PRECEDING) as cumulative_total,
    AVG(amount) OVER (ORDER BY date ROWS UNBOUNDED PRECEDING) as avg_to_date,
    COUNT(*) OVER (ORDER BY date ROWS UNBOUNDED PRECEDING) as transaction_number
```

#### 3.7 rolling_avg() / rolling_sum() with Window Size

```asql
from daily_sales
  order by date
  select
    date,
    revenue,
    rolling_avg(revenue, 7) as seven_day_avg,
    rolling_sum(revenue, 30) as thirty_day_total
```

---

## Part 4: Radical Ideas (Explore Later)

### 4.1 Implicit Window Context

What if `order by` and `group by` automatically applied to subsequent window functions?

```asql
# Current verbose
from orders
  select 
    customer_id,
    order_date,
    row_number() over (partition by customer_id order by order_date) as rn

# Proposed implicit context
from orders
  partition by customer_id
  order by order_date
  select
    customer_id,
    order_date,
    row_number() as rn  # Automatically uses context
```

**Concern**: Could be confusing if you want different partitions for different functions.

### 4.2 "dedupe" as a First-Class Operation

```asql
# Get first row per group - very common pattern
from orders
  dedupe by customer_id (order by -order_date)
  
# Or with "keep first/last" semantics
from orders
  keep first per customer_id (order by -order_date)
```

### 4.3 "rank" / "number" as Operators

```asql
from orders
  number by customer_id (order by -order_date) as rn
  
from employees
  rank by department (order by -salary) as salary_rank
```

---

## Part 5: Implementation Roadmap

### Phase 1: Quick Wins
1. **QUALIFY clause** - Add support, compile to subquery for non-supporting dialects
2. **DISTINCT ON** - PostgreSQL-style, compile to ROW_NUMBER for others

### Phase 2: New Functions
3. **first() / last()** - Aggregates with ORDER BY
4. **arg_max() / arg_min()** - ClickHouse-style
5. **prior() / next()** - Simplified LAG/LEAD

### Phase 3: Convenience
6. **running_sum/avg/count()** - Running aggregates
7. **rolling_avg/sum()** - Moving window aggregates

### Phase 4: Advanced
8. **Window context blocks** - Explore implicit partition/order
9. **dedupe operator** - First-class deduplication

---

## Appendix: Frequency Analysis

From analyzing Fivetran dbt examples:

| Pattern | Occurrences | Current ASQL | Proposed |
|---------|-------------|--------------|----------|
| ROW_NUMBER for dedup | ~13 | Pass-through | `dedupe by` or `qualify` |
| LAG for prior value | ~8 | Pass-through | `prior()` |
| LEAD for next value | ~3 | Pass-through | `next()` |
| Running totals | ~5 | Pass-through | `running_sum()` |
| Rolling averages | ~4 | Pass-through | `rolling_avg()` |
| RANK for ranking | ~5 | Pass-through | Consider `rank by` |

---

## Implementation Examples

### QUALIFY Clause

```asql
# Get most recent order per customer using QUALIFY
from orders
    select *, row_number() over (partition by customer_id order by -order_date) as rn
    qualify rn == 1
```

Compiles to:
```sql
SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) AS rn 
FROM orders 
QUALIFY rn = 1
```

### DISTINCT ON

```asql
# PostgreSQL-style DISTINCT ON
from orders
    distinct on (customer_id)
    sort customer_id, -order_date
```

### prior() and next() Functions

```asql
# Calculate month-over-month change
from monthly_sales
    sort month
    select 
        month,
        revenue,
        prior(revenue) as prev_month,
        revenue - prior(revenue) as mom_change
```

Compiles to:
```sql
SELECT month, revenue, LAG(revenue, 1), revenue - LAG(revenue, 1) AS mom_change 
FROM monthly_sales 
ORDER BY month
```

### Running Aggregates

```asql
# Cumulative totals
from transactions
    sort date
    select 
        date, 
        amount, 
        running_sum(amount) as cumulative_total,
        running_avg(amount) as avg_to_date,
        running_count(*) as transaction_number
```

### Rolling Aggregates

```asql
# 7-day rolling average
from daily_sales
    sort date
    select date, revenue, rolling_avg(revenue, 7) as seven_day_avg
```

### first() / last() with ORDER BY

```asql
# Get first and last order per customer
from orders
    select 
        customer_id,
        first(order_id order by order_date) as first_order,
        last(order_id order by order_date) as latest_order
```

### arg_max() / arg_min() (ClickHouse-style)

```asql
# Get order_id where order_date is maximum per customer
from orders
    select 
        customer_id,
        arg_max(order_id, order_date) as latest_order_id,
        arg_min(order_id, order_date) as earliest_order_id
```

### Window Functions with OVER

```asql
# Explicit window function syntax
from employees
    select *, 
        rank() over (partition by department order by -salary) as salary_rank,
        sum(salary) over (partition by department) as dept_total_salary
```

---

## References

- [DuckDB QUALIFY](https://duckdb.org/docs/sql/query_syntax/qualify.html)
- [BigQuery QUALIFY](https://cloud.google.com/bigquery/docs/reference/standard-sql/query-syntax#qualify_clause)
- [ClickHouse argMax](https://clickhouse.com/docs/en/sql-reference/aggregate-functions/reference/argmax)
- [PostgreSQL DISTINCT ON](https://www.postgresql.org/docs/current/sql-select.html#SQL-DISTINCT)
- [PRQL Window Functions](https://prql-lang.org/book/reference/stdlib/transforms/window.html)
- [dbt_metrics Package](https://github.com/dbt-labs/dbt_metrics)

