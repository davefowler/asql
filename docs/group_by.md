# Grouping & Aggregation

ASQL's `group by` works like SQL's—but with guaranteed complete results by default.

---

## Basic Syntax

```asql
from orders
  group by region (
    sum(amount) as revenue,
    count(*) as order_count
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

```asql
from orders
  group by region, month(order_date) (
    sum(amount) as revenue
  )
```

---

## Guaranteed Groups

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

### ASQL Guarantees All Values

```asql
from orders
  where order_date >= @2024-01-01 and order_date < @2024-07-01
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

ASQL automatically generates a "spine" of all expected values and fills in zeros for missing data.

### How It Works

| Column Type | Spine Source |
|-------------|--------------|
| Date truncation (`month()`, `year()`, `week()`) | Inferred from WHERE clause date range |
| Non-date columns | DISTINCT values from the source data |
| Multiple columns | Cross-join of all combinations |

### The `??` Operator

Use `??` (null coalesce) to specify the default value for missing data:

```asql
sum(amount) ?? 0 as revenue      -- zeros for missing
count(*) ?? 0 as orders          -- zeros for missing
avg(price) ?? null as avg_price  -- null for missing (explicit)
```

---

## Explicit Values with guarantee()

Sometimes you want specific values guaranteed, not just what's in the data.

```asql
from orders
  group by guarantee(status, ['pending', 'processing', 'shipped', 'delivered', 'cancelled']) (
    count(*) ?? 0 as order_count
  )
```

All five statuses will appear in results, even if some have zero orders. This is useful for:

- Dashboards with fixed categories
- Reports that need consistent row ordering
- Comparisons where all options must be present

---

## Disabling Guaranteed Groups

### Filter the Results

The most common approach—just filter out zeros:

```asql
from orders
  group by month(order_date) ( sum(amount) as revenue )
  where revenue > 0
```

### Disable for a Query

```asql
SET auto_spine = false;
from orders
  group by month(order_date) ( sum(amount) as revenue )
```

### Disable Globally

In your config file or via the API:

```yaml
# asql.config.yaml
auto_spine: false
```

---

## Alternative Syntax

ASQL supports several ways to express grouping:

### Standard (Recommended)

```asql
from orders
  group by region ( sum(amount) as revenue )
```

### Natural Language

```asql
sum of amount by region
```

### Shorthand Aggregates

```asql
from orders
  group by region ( sum(amount) as sum_amount, # as order_count )
```

All of these compile to equivalent SQL.

---

## See Also

- [Window Functions](window_functions.md) — Running totals, ranking, prior/next values
- [Language Specification](spec.md) — Complete syntax reference
