# Pipe Semantics

ASQL uses a pipe-based query model where data flows from top to bottom. This matches how you think about data transformations and makes complex queries easier to understand.

## The Problem with SQL

SQL's syntax puts SELECT first, even though it executes last:

```sql
SELECT region, SUM(amount) AS revenue   -- 5th: finally, what columns
FROM sales                               -- 1st: start here
WHERE year = 2024                        -- 2nd: filter
GROUP BY region                          -- 3rd: aggregate
HAVING SUM(amount) > 1000                -- 4th: filter again
ORDER BY revenue DESC                    -- 6th: sort
LIMIT 10;                                -- 7th: limit
```

This inside-out structure makes complex queries hard to:
- **Read**: You have to jump around to understand the flow
- **Write**: You can't see what columns are available until you've written the FROM
- **Review**: Code review is harder when logic isn't linear
- **Debug**: Where's the bug? Hard to trace when order is jumbled

## ASQL's Solution

ASQL puts operations in execution order:

```asql-play
from sales                               -- 1st: start here
  where year(date) = 2024                -- 2nd: filter
  group by region (sum(amount) as revenue) -- 3rd: aggregate
  where revenue > 1000                   -- 4th: filter (HAVING)
  order by -revenue                      -- 5th: sort
  limit 10                               -- 6th: limit
```

Read top-to-bottom, execute top-to-bottom.

## Key Benefits

### 1. Progressive Disclosure

Build queries step by step:

```asql-play
from orders                    -- See all orders
  where status = "completed"   -- Only completed
  group by customer_id (       -- Aggregate per customer
    sum(amount) as total
  )
  order by -total              -- Sort by total
  limit 100                    -- Top 100
```

Each line transforms the result of the previous line.

### 2. Composability

Combine transformations naturally:

```asql-play
from orders
  where status = "completed"
  & customers on orders.customer_id = customers.id
  where customers.country = "US"
  group by customers.state (
    sum(orders.amount) as revenue
  )
```

### 3. Reduced Need for CTEs

SQL often uses CTEs to linearize logic:

```sql
WITH filtered AS (
    SELECT * FROM orders WHERE status = 'completed'
),
joined AS (
    SELECT o.*, c.country FROM filtered o
    JOIN customers c ON o.customer_id = c.id
)
SELECT country, SUM(amount) FROM joined GROUP BY country;
```

ASQL handles this with pipelines:

```asql-play
from orders
  where status = "completed"
  & customers on orders.customer_id = customers.id
  group by customers.country (sum(amount) as revenue)
```

### 4. Easier Debugging

When something's wrong, you can trace the flow:

```asql
from orders                    -- ✓ Orders look right
  where status = "completed"   -- ✓ Filter is correct
  group by customer_id (...)   -- ← Bug is here: wrong column
```

## How Pipelines Work

### Each Line Transforms a Table

Every pipeline step takes a table and produces a new table:

```
orders (raw) 
  → where status = "completed" → orders (filtered)
  → group by customer_id (...) → customer_totals
  → order by -total → customer_totals (sorted)
```

### Implicit SELECT

You don't need to specify SELECT upfront:

```asql-play
from orders  -- Implicitly: SELECT * FROM orders
```

Add SELECT when you want specific columns:

```asql-play
from orders
  select id, amount, created_at
```

### Multiple WHERE Clauses

Multiple WHERE clauses combine with AND:

```asql-play
from orders
  where status = "completed"
  where amount > 100
  where created_at >= @2024-01-01
```

Equivalent to:

```asql-play
from orders
  where status = "completed" 
    and amount > 100 
    and created_at >= @2024-01-01
```

## Generated SQL

ASQL compiles to standard SQL. Simple queries map directly:

```asql-play
from users
  where is_active
  order by -created_at
  limit 10
```

```sql
SELECT * FROM users WHERE is_active ORDER BY created_at DESC LIMIT 10
```

Complex queries may use CTEs to maintain structure:

```asql-play
from orders
  where status = "completed"
  group by customer_id (sum(amount) as total)
  where total > 1000
```

```sql
WITH grouped AS (
  SELECT customer_id, SUM(amount) AS total
  FROM orders
  WHERE status = 'completed'
  GROUP BY customer_id
)
SELECT * FROM grouped WHERE total > 1000
```

## Comparison with Other Languages

| Language | Approach |
|----------|----------|
| SQL | SELECT-first, inside-out execution |
| PRQL | Pipeline-based, similar to ASQL |
| Kusto/KQL | Pipeline-based with `\|` operator |
| pandas | Method chaining |
| dplyr (R) | Pipe operator (`%>%`) |

ASQL draws inspiration from all of these while maintaining SQL familiarity.

## When SQL is Better

Pipelines aren't always better:

- **Simple queries**: `SELECT * FROM users WHERE id = 1` is fine as-is
- **Set operations**: UNION, INTERSECT, EXCEPT can be clearer in SQL
- **Subqueries**: Some correlated subqueries are cleaner in SQL

ASQL transpiles to SQL, so you can always use the generated SQL directly.

## Next Steps

- **[Pipeline Basics](../syntax/pipeline.md)** — Syntax reference
- **[CTEs & Variables](../syntax/ctes.md)** — When you do need CTEs
- **[Convention Over Configuration](conventions.md)** — How ASQL infers defaults
