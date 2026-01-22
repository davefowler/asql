# CTEs & Settings

ASQL currently provides **one** way to create CTEs (Common Table Expressions): `stash as`.

`SET` is reserved for **compiler settings** (e.g. `SET dialect = 'postgres';`) and does **not** define CTEs.

## Why CTEs Are Often Unnecessary

Because ASQL uses pipelines, you often don't need CTEs at all:

```asql-play
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

```asql-play
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

## `SET` — Compiler settings (not CTEs)

Use `SET` statements to control compiler behavior:

```asql
SET dialect = 'postgres';
SET week_start = 'sunday';

from orders
  group by month(created_at) ( sum(amount) as revenue )
```

## Generated SQL

`stash as` compiles to SQL's `WITH ... AS` syntax:

```asql
from users
  where is_active
  stash as active

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
    CASE
      WHEN total_spent > 10000 THEN 'platinum'
      WHEN total_spent > 5000 THEN 'gold'
      WHEN total_spent > 1000 THEN 'silver'
      ELSE 'bronze'
    END as tier
```

### Comparing Datasets

```asql
from orders
  where month(created_at) = month(now())
  group by product_id (sum(amount) as revenue)
  stash as this_month

from orders
  where month(created_at) = month(now()) - 1
  group by product_id (sum(amount) as revenue)
  stash as last_month

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

```asql-play
from users
  where is_active
  -- cleaned and filtered users
  group by country (# as total)
  -- aggregated by country
  having total > 100
  order by -total
```

This keeps the pipeline simple while documenting the logical structure.

## Best Practices

1. **Start with pipelines** — Only add CTEs when you need to reuse results
2. **Use `stash as` for single-use CTEs** — Keeps the CTE close to its usage
3. **Use `stash as` for reused CTEs** — When multiple queries need the same intermediate result
4. **Name CTEs descriptively** — `active_premium_users` is better than `temp1`
5. **Comment logical sections** — Even without CTEs, mark where you'd create one in SQL

## Anti-Patterns

### Unnecessary CTEs

```asql
-- ❌ Unnecessary - could be a single pipeline
from users
  where is_active
  stash as step1

from step1
  group by country (# as total)
  order by -total

-- ✅ Better - single pipeline
from users
  where is_active
  group by country (# as total)
  order by -total
```

### Too Many CTEs

If you have more than 3-4 CTEs, consider whether the query should be split into separate queries or dbt models.

## Next Steps

- **[Pipe Syntax](pipe.md)** — Core pipe syntax
- **[Examples](../examples.md)** — Real-world query patterns
- **[Aggregations](aggregations.md)** — GROUP BY with CTEs
