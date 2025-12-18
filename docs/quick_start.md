# Quick Start

Get started with Analytic SQL. This guide covers the essential language features you need to write powerful analytic queries.

## Table of Contents

- [Basic Operations](#basic-operations)
- [Filtering](#filtering)
- [Aggregations](#aggregations)
- [Ordering & Limiting](#ordering-limiting)
- [Date Functions](#date-functions)
- [Joins](#joins)
- [Window Functions](#window-functions)
- [Common Patterns](#common-patterns)

## Basic Operations

### FROM - Start with a table

Every Analytic SQL query starts with `from`:

```asql
from users
```

This selects all columns from the `users` table.

### SELECT - Choose columns

Use `select` to specify which columns you want:

```asql
from users
select name, email, created_at
```

### WHERE - Filter rows

Filter rows with `where`:

```asql
from users
where status = "active"
```

## Filtering

### Comparison Operators

- `==` - equals
- `!=` - not equals
- `<`, `>`, `<=`, `>=` - comparisons
- `is null` / `is not null` - null checks
- `in` / `not in` - membership checks

```asql
from orders
where amount > 100
  and status != "cancelled"
  and customer_id is not null
```

### Logical Operators

- `and` - logical AND
- `or` - logical OR
- `not` - logical NOT

```asql
from users
where (status = "active" or status = "pending")
  and email is not null
```

### String Matching

```asql
from products
where name contains "widget"
  and category in ("electronics", "computers")
```

## Aggregations

### GROUP BY

Group rows and compute aggregates:

```asql
from orders
group by customer_id (
    sum(amount) as total_spent,
    # as order_count
)
```

The `#` symbol is shorthand for `COUNT(*)`.

### Multiple Aggregations

You can compute multiple aggregates in a single group by:

```asql
from sales
group by product (
    sum(amount) as revenue,
    avg(amount) as avg_order_value,
    min(amount) as min_order,
    max(amount) as max_order,
    # as order_count
)
```

### Aggregation Functions

- `#` or `count(*)` - count rows
- `sum(column)` - sum values
- `avg(column)` - average values
- `min(column)` - minimum value
- `max(column)` - maximum value

## Ordering & Limiting

### ORDER BY

Order results with `order by`:

```asql
from users
order by name              # Ascending

from users
order by -created_at        # Descending (use - prefix)
```

### Multiple Order Columns

```asql
from orders
order by -amount, created_at          -- Order by amount DESC, then created_at ASC
```

### TAKE - Limit results

Use `limit` to limit the number of rows:

```asql
from users
order by -created_at
limit 10
```

## Date Functions

### Date Extraction

Extract parts of dates:

```asql
from events
group by year(date), month(date) (
    # as event_count
)
```

Available functions:
- `year(date)` - extract year
- `month(date)` - extract month
- `day(date)` - extract day
- `date(date)` - extract date (remove time)

### Date Truncation

```asql
from events
group by date_trunc("month", date) (
    # as events_per_month
)
```

### Date Formatting

```asql
from events
select 
    date_format(date, "%Y-%m") as month,
    #
```

## Joins

ASQL uses symbolic operators for joins where `&` represents the join point and `?` marks optional (nullable) sides.

### Join Operators

| Operator | Join Type | Meaning |
|----------|-----------|---------|
| `&` | INNER JOIN | Both sides must match |
| `&?` | LEFT JOIN | Right side is optional |
| `?&` | RIGHT JOIN | Left side is optional |
| `?&?` | FULL OUTER | Both sides are optional |
| `*` | CROSS JOIN | Cartesian product |

### INNER JOIN

```asql
from orders & users on orders.user_id = users.id
```

### LEFT JOIN

```asql
from users &? orders on users.id = orders.user_id
```

### Multiple Joins

```asql
from orders 
  & users on orders.user_id = users.id
  & products on orders.product_id = products.id
select 
    users.name,
    products.name as product_name,
    orders.amount
```

### FK Dot Notation (Auto-Joins)

If your columns follow the `{name}_id` pattern, you can use dot notation for automatic joins:

```asql
-- orders has user_id column → auto-joins to users
from orders
select 
    orders.amount,
    orders.user.name,      -- Auto LEFT JOIN via user_id
    orders.user.email
```

This compiles to:
```sql
SELECT orders.amount, user_1.name, user_1.email
FROM orders
LEFT JOIN users AS user_1 ON orders.user_id = user_1.id
```

## Window Functions

ASQL provides simplified syntax for common window function patterns.

### prior() and next()

Get values from previous or next rows:

```asql
from monthly_sales
order by month
select 
    month,
    revenue,
    prior(revenue) as prev_month,           # Previous row's revenue
    prior(revenue, 3) as three_months_ago,  # 3 rows back
    next(revenue) as next_month             # Next row's revenue
```

### Running Aggregates

Calculate cumulative totals:

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

### Rolling Aggregates

Calculate moving averages with a window size:

```asql
from daily_sales
order by date
select 
    date,
    revenue,
    rolling_avg(revenue, 7) as seven_day_avg
```

### Deduplication with `per`

Get the first/last row per group with the `per` command:

```asql
# Most recent order per customer
from orders
per customer_id first by -order_date

# Add row numbers per customer
from orders
per customer_id number by -order_date

# Rank employees by salary within department
from employees
per department rank by -salary
```

### QUALIFY Clause

For more complex window function filtering:

```asql
from orders
select *, row_number() over (partition by customer_id order by -order_date) as rn
qualify rn = 1
```

### DISTINCT ON

PostgreSQL-style deduplication:

```asql
from orders
distinct on (customer_id)
order by customer_id, -order_date
```

See the [Window Functions](window_functions.md) guide for more details and patterns.

---

## Common Patterns

### Top N by Group

Find the top 5 products by revenue in each category:

```asql
from sales
group by category, product (
    sum(amount) as revenue
)
order by category, -revenue
```

### Time Series Analysis

Daily revenue for the last 30 days:

```asql
from orders
where date >= 30 days ago
group by date(date) (
    sum(amount) as daily_revenue,
    # as order_count
)
order by date
```

### Cohort Analysis

User signups by month:

```asql
from users
group by year(created_at), month(created_at) (
    # as signups
)
order by year, month
```

### Filtered Aggregations

Count active users per country:

```asql
from users
where status = "active"
group by country (
    # as active_users
)
order by -active_users
```

## Complete Example

Here's a complete query that demonstrates multiple features:

```asql
from orders
  where date >= @2024-01-01
    and status = "completed"
  & products on orders.product_id = products.id
  group by products.category (
      sum(orders.amount) as revenue,
      avg(orders.amount) as avg_order_value,
      # as order_count
  )
  order by -revenue
  limit 10
```

This query:
1. Starts with orders
2. Filters to completed orders from 2024
3. Inner joins with products using `&`
4. Groups by product category
5. Computes revenue, average order value, and order count
6. Sorts by revenue descending
7. Takes the top 10 categories

## Next Steps

- **[Window Functions](window_functions.md)** - Simplified window function utilities
- **[Examples](examples.md)** - See more real-world query patterns
- **[Language Specification](spec.md)** - Complete syntax reference
- **[Playground](https://play.analyticsql.com)** - Try writing queries interactively

---

**Ready to write queries?** [Open the playground →](https://play.analyticsql.com)
