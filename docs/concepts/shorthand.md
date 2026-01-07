# Function Shorthand

ASQL provides flexible syntax for function calls where **underscores and spaces are interchangeable**. This makes queries more natural to write and read.

## The Core Principle

All of these are equivalent:

```asql
sum(amount)           -- explicit function call
sum_amount            -- underscore shorthand
sum amount            -- space shorthand
sum of amount         -- "of" style
```

All produce a column named `sum_amount`.

## Where It Applies

### Natural-language aggregate calls

Spaces (and optional `of`) are normalized to function calls:

```asql
sum amount        -- → sum(amount)
sum of amount     -- → sum(amount)
avg price         -- → avg(price)
```

### Certain multi-word functions

Certain multi-word function names can be written with spaces and normalize to underscored function names:

```asql
day of week created_at     -- → day_of_week(created_at)
week of year created_at    -- → week_of_year(created_at)
string agg(name, ', ')     -- → string_agg(name, ', ')
```

### Date “since/until” patterns

```asql
days_since_created_at   -- → DATEDIFF('day', created_at, CURRENT_TIMESTAMP)
days_until_due_date     -- → DATEDIFF('day', CURRENT_TIMESTAMP, due_date)
```

## Ambiguity Resolution

If an actual column name matches a potential function pattern, the **column takes precedence**:

```asql
-- If table has actual column "sum_revenue":
select sum_revenue    -- Uses the column, not sum(revenue)

-- To force function interpretation:
select sum(revenue) as sum_revenue
```

## Extended Patterns

### Time Since/Until

```asql
days_since_created_at     -- → days(now() - created_at)
months_since_signup_date  -- → months(now() - signup_date)
days_until_due_date       -- → days(due_date - now())
```

### Running/Rolling

```asql
running_sum_amount        -- → running_sum(amount)
rolling_avg_revenue       -- → rolling_avg(revenue)
```

## Usage in Different Contexts

| Context | Applies? | Example |
|---------|----------|---------|
| SELECT expressions | ✅ Yes | `select sum_amount` |
| GROUP BY | ✅ Yes | `group by month_created_at` |
| ORDER BY | ✅ Yes | `order by -sum_amount` |
| WHERE conditions | ✅ Yes | `where days_since_created_at > 30` |
| Column references | ❌ No | `created_at` stays as-is |
| Table names | ❌ No | `user_accounts` stays as-is |
| String literals | ❌ No | `"hello_world"` stays as-is |

## Style Guide

### When to Use Shorthand

Good for readability:
```asql-play
from sales
  group by region (
    sum_amount,
    avg_price,
    # as transactions     -- Count shorthand
  )
```

### When to Be Explicit

Complex expressions:
```asql-play
from sales
  group by region (
    sum(amount * quantity) as revenue,   -- Expression needs parens
    avg(price / 100) as avg_cents        -- Expression needs parens
  )
```

Multiple arguments:
```asql
primary_email ?? secondary_email ?? "unknown"
```

## Real-World Examples

### Natural Aggregation

```asql-play
from orders
  group by customer_id (
    total amount as total_spent,
    average amount as avg_order,
    # as order_count
  )
```

### Time Series

```asql-play
from users
  group by month_created_at (
    # as signups
  )
  order by month_created_at
```

### Analytics Dashboard

```asql-play
from sales
  where year_sale_date = 2024
  group by region (
    sum_revenue,
    avg_price,
    #(distinct customer_id) as unique_customers
  )
```

## Summary

| Pattern | Expansion |
|---------|-----------|
| `func_col` | `func(col) as func_col` |
| `func col` | `func(col) as func_col` |
| `func of col` | `func(col) as func_col` |
| `unit_since_col` | `unit(now() - col)` |
| `unit_until_col` | `unit(col - now())` |

The goal: write queries that read like natural language while maintaining precision.

## Auto-Aliasing

ASQL automatically generates meaningful column names when functions are used without explicit `AS` aliases. This eliminates SQL's unusable defaults like `count`, `f0_`, or `SUM(amount)`.

```asql
from orders
  group by customer_id (
    sum_amount,              -- → column: sum_amount
    avg_price,               -- → column: avg_price
    #                        -- → column: num
    month(created_at)        -- → column: month_created_at
  )
order by -sum_amount         -- Reference auto-aliased column directly!
```

### How It Works

| Function | Auto-Generated Alias |
|----------|---------------------|
| `sum(amount)` | `sum_amount` |
| `avg(price)` | `avg_price` |
| `count(*)` / `#` | `num` |
| `month(created_at)` | `month_created_at` |
| `upper(name)` | `upper_name` |

### Declarative Continuity

The shorthand syntax and auto-aliasing work together: when you write `sum_amount`, it expands to `sum(amount)`, and the result column is named `sum_amount`. You can reference it by the same name in `ORDER BY`, `WHERE`, or subsequent queries.

See the [Auto-Aliasing Reference](../reference/auto-aliasing.md) for the complete mapping table and configuration options.

## Next Steps

- **[Aggregations](../syntax/aggregations.md)** — Using shorthand in GROUP BY
- **[Dates & Time](../syntax/dates.md)** — Date function shorthand
- **[Convention Over Configuration](conventions.md)** — The philosophy behind these choices
