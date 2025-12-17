# CTEs & Variables

ASQL provides two ways to create CTEs (Common Table Expressions): `stash as` for inline pipeline CTEs and `set` for top-level variable definitions.

## Why CTEs Are Often Unnecessary

Because ASQL uses pipelines, you often don't need CTEs at all:

```asql
-- No CTE needed - just a continuous pipeline
from users
  where is_active
  group by country (# as total)
  where total > 100
  order by -total
```

In SQL, this would typically require a CTE or subquery. ASQL handles the complexity for you.

## `stash as` — Inline CTEs

Use `stash as` to save an intermediate result within a pipeline:

```asql
from users
  where status = "active"
  stash as active_users
  group by country (# as total)
  order by -total
```

This creates a CTE named `active_users` and continues the pipeline.

### At the End of a Pipeline

```asql
from users
  where status = "active"
  group by country (# as total)
  stash as by_country

from by_country
  order by -total
  limit 10
```

### Reusing Stashed Results

```asql
from orders
  where year(created_at) = 2024
  group by region (sum(amount) as revenue)
  stash as regional_revenue

-- First query: top regions
from regional_revenue
  order by -revenue
  limit 5;

-- Second query: regions below threshold
from regional_revenue
  where revenue < 10000
```

### Benefits of `stash as`

- **Proximity**: CTE is defined where it's used
- **Clear flow**: Data flow is visible
- **Eye-friendly**: Name appears right before usage

## `set` — Top-Level Variables

Define named CTEs at the top level:

```asql
set active_users = from users where is_active

from active_users
  group by country (# as total)
```

### Nested Variables

Variables can reference other variables:

```asql
set base = from users
  where plan = "premium"

set by_country = from base
  group by country (# as total)

from by_country
  order by -total
  limit 10
```

### When to Use `set`

Use `set` when:
- You want to define CTEs before any queries
- You'll reuse the same CTE in multiple separate queries
- You prefer a SQL-like `WITH ... AS` structure

## `stash as` vs `set`

| Feature | `stash as` | `set` |
|---------|------------|-------|
| Position | Inside pipeline | Before queries |
| Readability | Inline, near usage | Top-level, like SQL |
| Best for | Single pipeline | Multiple queries |
| Natural flow | Continues pipeline | Starts new query |

## Generated SQL

Both compile to SQL's `WITH ... AS` syntax:

```asql
set active = from users where is_active

from active
  group by country (# as total)
```

Generates:

```sql
WITH active AS (
  SELECT * FROM users WHERE is_active
)
SELECT country, COUNT(*) AS total
FROM active
GROUP BY country
```

## Complex Query Composition

### Multi-Stage Analytics

```asql
-- Stage 1: Filter and prepare data
from orders
  where year(created_at) = 2024
  where status = "completed"
  stash as completed_orders

-- Stage 2: Aggregate by customer
from completed_orders
  group by customer_id (
    sum(amount) as total_spent,
    # as order_count
  )
  stash as customer_stats

-- Stage 3: Segment customers
from customer_stats
  select
    customer_id,
    total_spent,
    order_count,
    when total_spent
      > 10000 then "platinum"
      > 5000 then "gold"
      > 1000 then "silver"
      otherwise "bronze"
    as tier
```

### Comparing Datasets

```asql
set this_month = from orders
  where month(created_at) = month(now())
  group by product_id (sum(amount) as revenue)

set last_month = from orders
  where month(created_at) = month(now()) - 1
  group by product_id (sum(amount) as revenue)

from this_month
  &? last_month on this_month.product_id = last_month.product_id
  select
    this_month.product_id,
    this_month.revenue as current_revenue,
    last_month.revenue as previous_revenue,
    this_month.revenue - (last_month.revenue ?? 0) as change
```

## Comments as Logical Markers

When you don't need a true CTE, use comments to mark logical sections:

```asql
from users
  where is_active
  -- cleaned and filtered users
  group by country (# as total)
  -- aggregated by country
  where total > 100
  order by -total
```

This keeps the pipeline simple while documenting the logical structure.

## Best Practices

1. **Start with pipelines** — Only add CTEs when you need to reuse results
2. **Use `stash as` for single-use CTEs** — Keeps the CTE close to its usage
3. **Use `set` for reused CTEs** — When multiple queries need the same intermediate result
4. **Name CTEs descriptively** — `active_premium_users` is better than `temp1`
5. **Comment logical sections** — Even without CTEs, mark where you'd create one in SQL

## Anti-Patterns

### Unnecessary CTEs

```asql
-- ❌ Unnecessary - could be a single pipeline
set step1 = from users where is_active
set step2 = from step1 group by country (# as total)
from step2 order by -total

-- ✅ Better - single pipeline
from users
  where is_active
  group by country (# as total)
  order by -total
```

### Too Many CTEs

If you have more than 3-4 CTEs, consider whether the query should be split into separate queries or dbt models.

## Next Steps

- **[Pipeline Basics](pipeline.md)** — Core pipeline syntax
- **[Examples](../examples.md)** — Real-world query patterns
- **[Aggregations](aggregations.md)** — GROUP BY with CTEs
