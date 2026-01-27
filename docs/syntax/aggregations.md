# Aggregations & GROUP BY

ASQL provides a clean syntax for grouping and aggregating data, with natural language options for common patterns.

## Basic GROUP BY

Use `group by` with parentheses to define aggregations:

```asql-play
from orders
  group by customer_id (
    sum(amount) as total_spent,
    # as order_count,
    avg(amount) as avg_order
  )
```

The syntax is: `group by <columns> ( <aggregations> )`.

## Count Shorthand (`#`, `##`, `uniq`)

The `#` symbol provides flexible counting syntax. Use `##` (double hash) or `uniq()` for distinct counts.

### Basic Row Count

```asql-play
from users
  group by country (
    # as user_count          -- COUNT(*)
  )
```

### Count with Column

Use `#col` or `# col` to count non-null values in a column:

```asql
#email             -- COUNT(email)
# email            -- COUNT(email) (with space)
#(email)           -- COUNT(email) (with parens)
```

### Distinct Count (`##` or `uniq`)

Use double hash `##` or the `uniq()` function for distinct counts:

```asql
##user_id          -- COUNT(DISTINCT user_id)
## user_id         -- COUNT(DISTINCT user_id) (with space)
#(distinct email)  -- COUNT(DISTINCT email) (explicit)
uniq(user_id)      -- COUNT(DISTINCT user_id)
uniq user_id       -- COUNT(DISTINCT user_id) (space notation)
```

### Count Shorthand Reference

| Syntax | SQL Output | Use Case |
|--------|------------|----------|
| `#` | `COUNT(*)` | Count all rows |
| `#*` or `# *` | `COUNT(*)` | Explicit row count |
| `#col` or `# col` | `COUNT(col)` | Count non-null values |
| `#(col)` | `COUNT(col)` | Count with parens |
| `##col` or `## col` | `COUNT(DISTINCT col)` | Distinct count |
| `#(distinct col)` | `COUNT(DISTINCT col)` | Explicit distinct |
| `uniq(col)` | `COUNT(DISTINCT col)` | Function form |
| `uniq col` | `COUNT(DISTINCT col)` | Space notation |

## Multiple Grouping Columns

Group by multiple columns separated by commas:

```asql-play
from sales
  group by region, year(date) (
    sum(amount) as revenue,
    # as transactions
  )
```

## Aggregate Functions

| Function | Description | Example |
|----------|-------------|---------|
| `#` or `count(*)` | Count rows | `# as total` (preferred) |
| `count(col)` | Count non-null values | `count(email)` |
| `count(distinct col)` | Count distinct values | `count(distinct customer_id)` |
| `sum(col)` | Sum values | `sum(amount)` |
| `avg(col)` | Average | `avg(price)` |
| `min(col)` | Minimum | `min(date)` |
| `max(col)` | Maximum | `max(amount)` |

## Natural Language Aggregates

ASQL supports natural language syntax for aggregations:

```asql
-- All of these are equivalent:
sum(amount)
sum amount
sum_amount
sum of amount
```

Using shorthand:

```asql-play
from sales
  group by region (
    sum_amount,
    avg_price,
    # as total
  )
```

## Auto-Aliasing

When you use functions without explicit `AS` aliases, ASQL automatically generates meaningful column names:

```asql-play
from orders
  group by region (
    sum(amount),         -- → column: sum_amount
    avg(price),          -- → column: avg_price
    count(*)             -- → column: num
  )
  order by -sum_amount   -- Reference the auto-generated alias!
```

This solves SQL's problem of unusable default names like `count`, `f0_`, or `SUM(amount)`. Auto-aliases follow the `{func}_{col}` pattern and can be referenced in `ORDER BY`, `WHERE`, and subsequent queries.

See the [Auto-Aliasing Reference](../reference/auto-aliasing.md) for the complete mapping table.

## Function Aliases

Natural language aliases map to SQL functions:

| Alias | SQL Function |
|-------|--------------|
| `total` | `SUM` |
| `average` | `AVG` |
| `maximum` | `MAX` |
| `minimum` | `MIN` |

```asql-play
from sales
  group by product (
    total amount as revenue,
    average price as avg_price
  )
```

## Grouping by Expressions

Group by computed values like date truncations:

```asql-play
from orders
  group by month(created_at) (
    sum(amount) as revenue
  )
```

Group by multiple expressions:

```asql-play
from orders
  group by year(created_at), month(created_at) (
    sum(amount) as revenue,
    # as order_count
  )
```

## Aliasing Group Columns

Use `as` to alias group columns:

```asql-play
from orders
  group by month(created_at) (
    sum(amount) as revenue
  )
```

This is especially useful for date truncations where you want a clean column name.

## HAVING (Filtering After Grouping)

Filter grouped results using another `where` clause after grouping:

```asql-play
from orders
  group by customer_id (
    sum(amount) as total_spent
  )
  where total_spent > 1000
```

This compiles to a `HAVING` clause or a wrapping CTE with WHERE.

## Aggregations Without GROUP BY

You can use aggregates without grouping to get totals:

```asql
from orders
  select
    sum(amount) as total_revenue,
    # as total_rows,              -- COUNT(*) - total number of rows
    avg(amount) as avg_order_value
```

**Important**: `#` by itself is always `COUNT(*)` (row count). For distinct counts, use `##` or `uniq()`:
- `#` → `COUNT(*)` (row count)
- `##col` or `uniq(col)` → `COUNT(DISTINCT col)` (distinct count)

## Conditional Aggregates

Use `when` inside aggregates for conditional counting/summing:

```asql-play
from orders
  group by customer_id (
    # as total_orders,
    sum(status = "completed" ? 1 : 0) as completed_orders,
    sum(status = "returned" ? amount : 0) as returned_amount
  )
```

## Guaranteed Groups

By default, ASQL ensures all expected dimension values appear in grouped results—even if they have no data. See [Guaranteed Groups](../concepts/guaranteed-groups.md) for details.

```asql
-- All months from Jan-Jun will appear, even with zero revenue
from orders
  where order_date >= @2024-01-01 and order_date < @2024-07-01
  group by month(order_date) (
    sum(amount) ?? 0 as revenue
  )
```

## Default Column Selection

If you don't specify a `select` after grouping, ASQL returns all grouping columns followed by all aggregations:

```asql-play
from orders
  group by region (
    sum(amount) as revenue,
    # as orders
  )
-- Returns: region, revenue, orders
```

## Real-World Examples

### Top Customers by Revenue

```asql-play
from orders
  where status = "completed"
  group by customer_id (
    sum(amount) as total_spent,
    # as order_count
  )
  order by -total_spent
  limit 10
```

### Monthly Revenue Trend

```asql-play
from orders
  where year(created_at) = 2024
  group by month(created_at) (
    sum(amount) as revenue,
    # as orders,
    avg(amount) as avg_order
  )
  order by month
```

### Category Performance

```asql-play
from products
  & orders on products.id = orders.product_id
  group by products.category (
    sum(orders.amount) as revenue,
    count(distinct orders.customer_id) as customers,
    # as transactions
  )
  order by -revenue
```

## Next Steps

- **[Window Functions](window-functions.md)** — Running totals, ranking, and more
- **[Dates & Time](dates.md)** — Date truncation and grouping
- **[Guaranteed Groups](../concepts/guaranteed-groups.md)** — Complete dimension coverage
