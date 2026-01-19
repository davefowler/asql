# Grouping & Aggregation

ASQL's `group by` works like SQL's. Use `spine by` when you want guaranteed complete results with gap-filling.

---

## Basic Syntax

```asql-play
from orders
  group by region (
    sum(amount) as revenue,
    # as order_count
  )
```

Aggregates go inside parentheses after the grouping columns. This compiles to:

```sql
SELECT region, SUM(amount) AS revenue, COUNT(*) AS order_count
FROM orders
GROUP BY region
```

---

## Multiple Columns

```asql-play
from orders
  group by region, month(order_date) (
    sum(amount) as revenue
  )
```

---

## Spine (Gap-Filling)

Here's where ASQL differs from SQL.

### The Problem with SQL

In SQL, if a dimension value has no data, it doesn't appear in results:

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

April and May are missing. This breaks charts, corrupts month-over-month calculations, and causes countless analytics bugs.

### `spine by` Guarantees All Values

Use `spine by` instead of `group by` when you want gap-filling:

```asql
from orders
  where order_date >= @2024-01-01 and order_date < @2024-07-01
  spine by month(order_date) (
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

ASQL generates a "spine" of all expected values and fills in zeros for missing data.

### `spine()` in GROUP BY

Use `spine()` within a `group by` to spine only specific columns:

```asql
from orders
  group by spine(month(order_date)), region (
    sum(amount) ?? 0 as revenue
  )
```

This spines the month column (filling date gaps) but NOT the region column.

### How It Works

| Column Type | Spine Source |
|-------------|--------------|
| Date truncation (`month()`, `year()`, `week()`) | Inferred from WHERE clause date range |
| Non-date columns | DISTINCT values from **filtered** source data |
| `guarantee(col, [...])` | Explicit list of values you specify |
| Multiple columns | Cross-join of all combinations |

**Note:** For non-date columns, the spine respects your WHERE clause. If you filter to `region = 'North America'`, only that region appears in results. Use `guarantee()` to force specific values to appear regardless of filters. See [Guaranteed Groups](concepts/guaranteed-groups.md#how-filters-affect-categorical-spines) for details.

### The `??` Operator

Use `??` (null coalesce) to specify the default value for missing data:

```asql
sum(amount) ?? 0 as revenue      -- zeros for missing
-- ?? 0 as orders          -- zeros for missing
avg(price) ?? null as avg_price  -- null for missing (explicit)
```

---

## Explicit Values with guarantee()

Sometimes you want specific values guaranteed, not just what's in the data.

```asql-play
from orders
  spine by guarantee(status, ['pending', 'processing', 'shipped', 'delivered', 'cancelled']) (
    # ?? 0 as order_count
  )
```

All five statuses will appear in results, even if some have zero orders. This is useful for:

- Dashboards with fixed categories
- Reports that need consistent row ordering
- Comparisons where all options must be present

---

## When NOT to Use Spine

### Use Regular GROUP BY

If you don't want gap-filling, just use `group by`:

```asql-play
from orders
  group by month(order_date) ( sum(amount) as revenue )
```

### Filter the Results

If you used spine but want to remove zeros:

```asql-play
from orders
  spine by month(order_date) ( sum(amount) as revenue )
  where revenue > 0
```

---

## Alternative Syntax

ASQL supports several ways to express grouping:

### Standard (Recommended)

```asql-play
from orders
  group by region ( sum(amount) as revenue )
```

### Natural Language

```asql
sum of amount by region
```

### Shorthand Aggregates

```asql-play
from orders
  group by region ( sum(amount) as sum_amount, # as order_count )
```

All of these compile to equivalent SQL.

---

## See Also

- [Window Functions](window_functions.md) — Running totals, ranking, prior/next values
- [Language Specification](spec.md) — Complete syntax reference
