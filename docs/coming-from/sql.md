# ASQL for SQL Users

If you’re already comfortable with SQL, you’re going to be productive in ASQL immediately.
ASQL is designed by (and for) people who live in SQL every day, and many of its features are directly inspired by common SQL patterns—just expressed with friendlier syntax.

ASQL is still “real SQL” (it compiles to your warehouse dialect), but it’s designed to read like a clean transformation pipeline instead of a nested, back-and-forth SQL statement.

## What will feel familiar

- **The core building blocks**: filters, projections, joins, grouping, ordering, limits.
- **SQL expressions**: arithmetic, comparisons, boolean logic, functions.
- **The end result**: a query your warehouse can optimize and execute.

## What’s different (in a good way)

- **Top-to-bottom pipelines**: start with `from ...`, then apply transforms line-by-line.
- **Less ceremony**: fewer CTEs, fewer “select lists as the control plane”, fewer giant macro helpers.
- **Ergonomic shortcuts**: things like `??`, `-col` for descending, and `per ...` for common window patterns.

## Key Differences

| SQL | ASQL | Why |
|-----|------|-----|
| `SELECT ... FROM` | `from ... select` | Pipeline order - start with data |
| `ORDER BY x DESC` | `order by -x` | Cleaner descending syntax |
| `CASE WHEN ... END` | `when ... otherwise` | Less verbose |
| `COALESCE(a, b)` | `a ?? b` | Modern null coalescing |
| `CAST(x AS int)` | `x::int` | Postgres-style casting |
| CTEs everywhere | Pipeline + comments | Often no CTEs needed |

---

## Your first ASQL query (5 minutes)

If you can write:

1) `FROM table`
2) add a `WHERE`
3) add a `GROUP BY`
4) add an `ORDER BY`

…then you can write ASQL. The main “reversal” is that you start with the dataset and then refine it.

## The Pipeline Difference

=== "SQL"
    ```sql
    SELECT 
        region,
        SUM(amount) as revenue,
        COUNT(DISTINCT customer_id) as customers
    FROM orders
    WHERE status = 'completed'
        AND created_at >= '2024-01-01'
    GROUP BY region
    HAVING SUM(amount) > 10000
    ORDER BY revenue DESC
    LIMIT 10
    ```

=== "ASQL"
    ```asql
    from orders
    where status = 'completed'
    where created_at >= @2024-01-01
    group by region (
        sum(amount) as revenue,
        count(distinct customer_id) as customers
    )
    where revenue > 10000
    order by -revenue
    limit 10
    ```

!!! note "Reading order = execution order"
    In ASQL, you read top-to-bottom and that's the order operations happen. No more jumping between SELECT and FROM.

---

## Joins

=== "SQL"
    ```sql
    SELECT o.*, c.name as customer_name
    FROM orders o
    LEFT JOIN customers c ON o.customer_id = c.id
    ```

=== "ASQL"
    ```asql
    from orders
    &? customers on orders.customer_id = customers.id
    select orders.*, customers.name as customer_name

    -- Or with dot notation (auto-join via FK convention)
    from orders
    select *, orders.customer.name as customer_name
    ```

### Join Operators

| SQL | ASQL Operator | Meaning |
|-----|---------------|---------|
| `INNER JOIN` | `&` | Both sides must match |
| `LEFT JOIN` | `&?` | Right side is optional (can be NULL) |
| `RIGHT JOIN` | `?&` | Left side is optional |
| `FULL OUTER JOIN` | `?&?` | Both sides are optional |
| `CROSS JOIN` | `*` | Cartesian product |

**Mnemonic**: The `?` marks the side that might be NULL.

---

## CASE Statements

=== "SQL"
    ```sql
    SELECT
        id,
        CASE 
            WHEN amount > 1000 THEN 'high'
            WHEN amount > 100 THEN 'medium'
            ELSE 'low'
        END as tier
    FROM orders
    ```

=== "ASQL"
    ```asql
    from orders
    select id,
        when amount
            > 1000 then 'high'
            > 100 then 'medium'
            otherwise 'low'
        as tier
    ```

### Simple CASE (Equality)

=== "SQL"
    ```sql
    CASE status
        WHEN 'A' THEN 'Active'
        WHEN 'I' THEN 'Inactive'
        ELSE 'Unknown'
    END
    ```

=== "ASQL"
    ```asql
    when status
        is 'A' then 'Active'
        is 'I' then 'Inactive'
        otherwise 'Unknown'
    ```

---

## Window Functions

=== "SQL"
    ```sql
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id 
            ORDER BY created_at DESC
        ) as rn
    FROM orders
    QUALIFY rn = 1
    ```

=== "ASQL"
    ```asql
    -- For deduplication, use per
    from orders
    per customer_id first by -created_at

    -- For adding row numbers
    from orders
    per customer_id number by -created_at
    ```

### Window Function Shortcuts

| SQL Pattern | ASQL Shortcut |
|-------------|---------------|
| `ROW_NUMBER() OVER (PARTITION BY x ORDER BY y) = 1` | `per x first by y` |
| `ROW_NUMBER() OVER (PARTITION BY x ORDER BY y)` | `per x number by y` |
| `RANK() OVER (PARTITION BY x ORDER BY y)` | `per x rank by y` |
| `LAG(col, 1) OVER (ORDER BY x)` | `prior(col)` |
| `LEAD(col, 1) OVER (ORDER BY x)` | `next(col)` |
| `SUM(col) OVER (ORDER BY x ROWS UNBOUNDED PRECEDING)` | `running_sum(col)` |
| `AVG(col) OVER (ORDER BY x ROWS 6 PRECEDING)` | `rolling_avg(col, 7)` |

---

## CTEs

=== "SQL"
    ```sql
    WITH active_users AS (
        SELECT * FROM users WHERE is_active
    ),
    user_orders AS (
        SELECT 
            u.id,
            u.name,
            COUNT(*) as order_count
        FROM active_users u
        JOIN orders o ON u.id = o.user_id
        GROUP BY u.id, u.name
    )
    SELECT * FROM user_orders
    WHERE order_count > 5
    ORDER BY order_count DESC
    ```

=== "ASQL"
    ```asql
    -- Often no CTE needed - just pipeline
    from users
    where is_active
    & orders on users.id = orders.user_id
    group by users.id, users.name (
        count(*) as order_count
    )
    where order_count > 5
    order by -order_count

    -- Or use set/stash for reusable parts
    set active_users = from users where is_active

    from active_users
    & orders on active_users.id = orders.user_id
    group by active_users.id, active_users.name (
        count(*) as order_count
    )
    where order_count > 5
    order by -order_count
    ```

---

## Dates

=== "SQL"
    ```sql
    -- Dialect varies!
    DATE_TRUNC('month', created_at)           -- Postgres
    DATE_TRUNC(created_at, MONTH)             -- BigQuery
    TRUNC(created_at, 'MONTH')                -- Oracle
    DATETRUNC(MONTH, created_at)              -- SQL Server
    
    CURRENT_DATE - INTERVAL '7 days'          -- Postgres
    DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)  -- BigQuery
    ```

=== "ASQL"
    ```asql
    -- Same syntax everywhere, compiles to right dialect
    month(created_at)
    
    7 days ago
    today() - 7 days
    ```

### Date Functions

| Operation | ASQL | Notes |
|-----------|------|-------|
| Truncate to month | `month(created_at)` | Also: `year()`, `week()`, `day()`, `hour()` |
| Day of week | `day of week created_at` | Returns 1-7 |
| Date arithmetic | `order_date + 7 days` | Also: weeks, months, years |
| Date difference | `days(end_date - start_date)` | Returns integer |
| Relative dates | `7 days ago` | Also: `3 days from now` |
| Time since | `days_since_created_at` | Shorthand for `days(now() - created_at)` |

---

## Null Handling

=== "SQL"
    ```sql
    COALESCE(first_name, nickname, 'Unknown')
    
    NULLIF(amount, 0)
    ```

=== "ASQL"
    ```asql
    first_name ?? nickname ?? 'Unknown'
    
    when amount = 0 then null else amount
    ```

---

## Type Casting

=== "SQL"
    ```sql
    CAST(value AS INTEGER)
    
    -- Safe casting (varies by dialect)
    TRY_CAST(value AS INTEGER)   -- Snowflake
    SAFE_CAST(value AS INT64)    -- BigQuery
    ```

=== "ASQL"
    ```asql
    value::integer
    
    -- Safe casting (returns NULL on failure)
    value::integer?
    
    -- With default
    value::integer? ?? 0
    ```

---

## Aggregations in SELECT

=== "SQL"
    ```sql
    SELECT 
        region,
        SUM(amount) as total,
        COUNT(*) as count,
        COUNT(DISTINCT customer_id) as unique_customers
    FROM orders
    GROUP BY region
    ```

=== "ASQL"
    ```asql
    from orders
    group by region (
        sum(amount) as total,
        count(*) as count,
        count(distinct customer_id) as unique_customers
    )
    ```

The parentheses after `group by` contain the aggregations - clearer than mixing them in SELECT.
