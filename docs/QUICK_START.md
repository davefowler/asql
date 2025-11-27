# Analytic SQL Syntax

Learn the syntax of Analytic SQL. This guide covers all the language features you need to write powerful analytic queries.

## Table of Contents

- [Basic Operations](#basic-operations)
- [Filtering](#filtering)
- [Aggregations](#aggregations)
- [Sorting & Limiting](#sorting--limiting)
- [Date Functions](#date-functions)
- [Joins](#joins)
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
where status == "active"
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
where (status == "active" or status == "pending")
  and email is not null
```

### String Matching

```asql
from products
where name like "%widget%"
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

## Sorting & Limiting

### SORT

Sort results with `sort`:

```asql
from users
sort name              # Ascending

from users
sort -created_at        # Descending (use - prefix)
```

### Multiple Sort Columns

```asql
from orders
sort -amount, created_at          # Sort by amount DESC, then created_at ASC
```

### TAKE - Limit results

Use `take` to limit the number of rows:

```asql
from users
sort -created_at
take 10
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

### INNER JOIN

```asql
from orders
join users on orders.user_id == users.id
```

### LEFT JOIN

```asql
from users
left join orders on users.id == orders.user_id
```

### Multiple Joins

```asql
from orders
join users on orders.user_id == users.id
join products on orders.product_id == products.id
select 
    users.name,
    products.name as product_name,
    orders.amount
```

## Common Patterns

### Top N by Group

Find the top 5 products by revenue in each category:

```asql
from sales
group by category, product (
    sum(amount) as revenue
)
sort category, -revenue
```

### Time Series Analysis

Daily revenue for the last 30 days:

```asql
from orders
where date >= date("now") - 30
group by date(date) (
    sum(amount) as daily_revenue,
    # as order_count
)
sort date
```

### Cohort Analysis

User signups by month:

```asql
from users
group by year(created_at), month(created_at) (
    # as signups
)
sort year, month
```

### Filtered Aggregations

Count active users per country:

```asql
from users
where status == "active"
group by country (
    # as active_users
)
sort -active_users
```

## Complete Example

Here's a complete query that demonstrates multiple features:

```asql
from orders
where date >= "2024-01-01"
  and status == "completed"
join products on orders.product_id == products.id
group by products.category (
    sum(orders.amount) as revenue,
    avg(orders.amount) as avg_order_value,
    # as order_count
)
sort -revenue
take 10
```

This query:
1. Starts with orders
2. Filters to completed orders from 2024
3. Joins with products
4. Groups by product category
5. Computes revenue, average order value, and order count
6. Sorts by revenue descending
7. Takes the top 10 categories

## Next Steps

- **[Examples](examples.md)** - See more real-world query patterns
- **[Language Specification](index.md)** - Complete syntax reference
- **[Playground](https://play.analyticsql.com)** - Try writing queries interactively

---

**Ready to write queries?** [Open the playground →](https://play.analyticsql.com)
