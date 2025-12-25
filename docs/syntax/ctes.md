# CTEs & Settings

ASQL currently provides **one** way to create CTEs (Common Table Expressions): `stash as`.

`SET` is reserved for **compiler settings** (e.g. `SET auto_spine = false;`) and does **not** define CTEs.

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

## `set` — Top-Level Variables
## `SET` — Compiler settings (not CTEs)

Use `SET` statements to control compiler behavior:

```asql
SET auto_spine = false;
SET dialect = 'postgres';

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

## Recursive Queries with `recurse()`

For hierarchical data (org charts, category trees, bill of materials), use `recurse()` to traverse self-referential relationships:

```asql-play
-- Get employee and all their reports
from employees
  where id = 1
  recurse(manager_id)
```

### Syntax

Three equivalent syntaxes are supported:

```asql
-- Function style
recurse(<fk_column> [, <max_depth>])

-- Keyword style (with 'on')
recurse on <fk_column> [, <max_depth>]

-- Bare style (shortest)
recurse <fk_column> [, <max_depth>]
```

- **`<fk_column>`** — The foreign key column to follow (e.g., `manager_id`, `parent_id`)
- **`<max_depth>`** — Optional depth limit (defaults to 100 for safety)

### Examples

```asql
-- Get 3 levels of reports only
from employees
  where id = 1
  recurse(manager_id, 3)

-- Get full category tree under 'electronics'
from categories
  where slug = 'electronics'
  recurse(parent_id)

-- Multiple roots: all Engineering org trees
from employees
  where department = 'Engineering'
  recurse(manager_id, 5)
```

### The `_level` Column

`recurse()` automatically adds a `_level` column tracking recursion depth:

| `_level` | Meaning |
|----------|---------|
| 1 | Anchor rows (matched by WHERE) |
| 2 | First level of recursion |
| 3 | Second level, etc. |

Use it for filtering or display:

```asql
from employees
  where id = 1
  recurse(manager_id)
  where _level <= 3          -- Only 3 levels deep
  order by _level, name
```

### FK Convention

By convention, `recurse(manager_id)` auto-joins to `id`:
- `manager_id` → joins to `employees.id`
- `parent_id` → joins to `categories.id`

This follows ASQL's FK naming convention: columns ending in `_id` are foreign keys to the table's `id` column.

### Generated SQL

```asql
from employees
  where id = 1
  recurse(manager_id, 5)
```

Generates:

```sql
WITH RECURSIVE _recurse_employees AS (
    SELECT *, 1 AS _level FROM employees WHERE id = 1
    UNION ALL
    SELECT e.*, _recurse_employees._level + 1
    FROM employees e
    JOIN _recurse_employees ON e.manager_id = _recurse_employees.id
    WHERE _recurse_employees._level < 5
)
SELECT * FROM _recurse_employees
```

### Dialect Support

Recursive CTEs are supported by:
- ✅ PostgreSQL
- ✅ DuckDB
- ✅ BigQuery
- ✅ Snowflake
- ✅ MySQL 8+
- ✅ SQL Server
- ❌ SQLite (limited support)

## Next Steps

- **[Pipeline Basics](pipeline.md)** — Core pipeline syntax
- **[Examples](../examples.md)** — Real-world query patterns
- **[Aggregations](aggregations.md)** — GROUP BY with CTEs
