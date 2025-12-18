# Pipeline Basics

ASQL uses a pipeline-based query structure where data flows from top to bottom. This matches how you think about transformations and makes complex queries easier to read and write.

## FROM-First Queries

Every ASQL query starts with `from`:

```asql-play
from users
```

This selects all rows and columns from the `users` table. Unlike SQL, you don't need to specify `SELECT *` upfront—ASQL adds it automatically when generating SQL.

## Pipeline Flow

Transformations are applied in sequence:

```asql-play
from users
  where status = "active"
  where age >= 18
  order by -created_at
  limit 10
```

Each line transforms the result of the previous line. This reads naturally: "From users, where status is active, where age is at least 18, order by created_at descending, take 10."

## Pipeline Operators

You can optionally use the pipe operator (`|`) to make the flow explicit:

```asql-play
from users
| where status = "active"
| group by country (# as total)
| order by -total
```

Both styles compile to the same SQL. Use whichever feels more natural:

| Style | Pros |
|-------|------|
| Indentation | Cleaner, less visual clutter, more like natural language |
| Pipe operators | Explicit flow, familiar to Unix/PowerShell users |

## Available Operations

| Operation | Purpose | Example |
|-----------|---------|---------|
| `from` | Start with a table | `from users` |
| `where` | Filter rows | `where status = "active"` |
| `select` | Choose columns | `select name, email` |
| `group by` | Aggregate data | `group by country (# as total)` |
| `order by` | Sort results | `order by -created_at` |
| `limit` | Limit row count | `limit 10` |
| `&`, `&?`, etc. | Join tables | `& orders on user_id = id` |
| `stash as` | Save as CTE | `stash as active_users` |

## Combining Operations

Operations can be combined in any logical order:

```asql-play
from orders
  where year(created_at) = 2024
  where status = "completed"
  & customers on orders.customer_id = customers.id
  group by customers.country (
    sum(amount) as revenue,
    # as order_count
  )
  order by -revenue
  limit 10
```

## Multiple WHERE Clauses

Multiple `where` clauses are combined with AND:

```asql-play
from users
  where status = "active"
  where age >= 18
  where email is not null
```

This is equivalent to:

```asql-play
from users
  where status = "active" and age >= 18 and email is not null
```

Use separate lines for readability, especially when conditions are long.

## SELECT Placement

In ASQL, `select` can appear anywhere in the pipeline:

```asql-play
from users
  where is_active
  select name, email, created_at
  order by -created_at
```

When omitted, ASQL automatically includes all columns (equivalent to `SELECT *`).

## Generated SQL

ASQL compiles to standard SQL. The pipeline structure maps to SQL clauses:

```asql-play
from users
  where is_active
  group by country (# as total)
  order by -total
```

Generates:

```sql
SELECT country, COUNT(*) AS total
FROM users
WHERE is_active
GROUP BY country
ORDER BY total DESC
```

For more complex queries with multiple transformations, ASQL may use CTEs to maintain clarity:

```asql-play
from users
  where is_active
  group by country (# as total)
  where total > 100
```

Generates:

```sql
WITH grouped AS (
  SELECT country, COUNT(*) AS total
  FROM users
  WHERE is_active
  GROUP BY country
)
SELECT * FROM grouped WHERE total > 100
```

## Next Steps

- **[Expressions & Operators](expressions.md)** — Learn about comparison, arithmetic, and logical operators
- **[Aggregations](aggregations.md)** — Deep dive into GROUP BY and aggregate functions
- **[Window Functions](window-functions.md)** — Ranking, running totals, and deduplication
