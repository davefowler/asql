# ASQL: A Pipeline Syntax for SQL

ASQL is a query language that transpiles to SQL. It reorders SQL's syntax to flow top-to-bottom (like a pipeline) and adds shorthand for common analytics patterns. Think of it like CoffeeScript for SQL—you write ASQL, it outputs standard SQL for any dialect.

**Status**: Experimental. [GitHub](https://github.com/davefowler/asql)

---

## Why?

SQL's syntax was designed in the 1970s for interactive terminal use. It works, but the execution order doesn't match the written order:

```sql
SELECT region, SUM(amount)     -- 5. finally, what columns
FROM sales                      -- 1. start here
WHERE year = 2024               -- 2. filter
GROUP BY region                 -- 3. aggregate
HAVING SUM(amount) > 1000       -- 4. filter again
ORDER BY 2 DESC                 -- 6. sort
LIMIT 10;                       -- 7. limit
```

This inside-out structure makes complex queries harder to read and write. You end up with CTEs mainly to linearize the logic.

Many tools address this: notebooks let you build queries step-by-step, pandas chains transformations with method syntax, dbt macros abstract common patterns, PRQL and Kusto offer pipeline syntax. ASQL takes learnings from all of these—a pipeline syntax that transpiles to any SQL dialect.

---

## Pipelined SQL

ASQL queries read top-to-bottom in execution order. This matters most for transformation and modeling work—dbt models, ELT pipelines, analytics views—where queries are written once and read many times. Linear flow makes code review, debugging, and refactoring significantly easier.

```asql
from sales
  where year(date) = 2024
  group by region ( sum(amount) as revenue )
  having revenue > 1000
  order by -revenue
  limit 10
```

The transformation is mechanical: `from` first, operations in order, and the compiler adds `SELECT` clauses as needed.

### CTEs vs Pipelines

In SQL, you often use CTEs to keep queries readable:

```sql
WITH active_users AS (
    SELECT * FROM users WHERE is_active = true
),
by_country AS (
    SELECT country, COUNT(*) as total
    FROM active_users
    GROUP BY country
)
SELECT * FROM by_country ORDER BY total DESC LIMIT 10;
```

In ASQL, the pipeline handles this:

```asql
from users
  where is_active
  group by country ( # as total )
  order by -total
  limit 10
```

When you actually need to reuse intermediate results, `set` creates CTEs:

```asql
set active_users = from users where is_active

from active_users
  group by country ( # as total )
```

---

## Syntax Shortcuts

ASQL adds shorthand for patterns that are verbose in SQL.

### Count and Sort

```asql
#                    -- COUNT(*)
#(distinct user_id)  -- COUNT(DISTINCT user_id)
order by -revenue    -- ORDER BY revenue DESC
```

### Date Truncation

```asql
year(created_at)     -- EXTRACT(YEAR FROM created_at) or DATE_TRUNC, depending on dialect
month(created_at)
week(created_at)
```

### Natural Aggregates

These are equivalent:

```asql
sum(amount)
sum amount
sum_amount
```

All produce a column named `sum_amount`.

### Date Arithmetic

```asql
where created_at > 7 days ago
where due_date < 30 days from now
select order_date + 14 days as delivery
```

---

## Window Functions

Window functions are one of SQL's most powerful features, but the syntax can be verbose. ASQL aims to make common patterns more intuitive with clearer structure and helper functions for the majority of use cases.

### First/Last Per Group

Getting the most recent order per customer is a common pattern:

**SQL:**
```sql
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY customer_id ORDER BY order_date DESC
    ) as rn
    FROM orders
) sub WHERE rn = 1;
```

**ASQL:**
```asql
from orders
  per customer_id first by -order_date
```

### Previous/Next Row

**SQL:**
```sql
SELECT month, revenue,
    LAG(revenue, 1) OVER (ORDER BY month) as prev_revenue
FROM monthly_sales;
```

**ASQL:**
```asql
from monthly_sales
  order by month
  select month, revenue, prior(revenue) as prev_revenue
```

### Running Totals

**SQL:**
```sql
SELECT date, revenue,
    SUM(revenue) OVER (ORDER BY date ROWS UNBOUNDED PRECEDING) as cumulative
FROM daily_sales;
```

**ASQL:**
```asql
from daily_sales
  order by date
  select date, revenue, running_sum(revenue) as cumulative
```

### Reference

| ASQL | SQL Equivalent |
|------|---------------|
| `per ... first by` | ROW_NUMBER() OVER (...) = 1 |
| `per ... number by` | ROW_NUMBER() OVER (...) |
| `prior(col)` | LAG(col, 1) OVER (...) |
| `next(col)` | LEAD(col, 1) OVER (...) |
| `running_sum(col)` | SUM(col) OVER (ROWS UNBOUNDED PRECEDING) |
| `rolling_avg(col, n)` | AVG(col) OVER (ROWS n-1 PRECEDING) |

---

## Column Operations

### Exclude Columns

```asql
from users
  except password_hash, internal_notes
```

### Rename

```asql
from users
  rename id as user_id
```

### Prefix After Join

```asql
from users
  join orders on users.id = orders.user_id
  prefix orders.* with order_
```

---

## Date Handling

SQL date functions vary by dialect. ASQL normalizes them:

| Operation | PostgreSQL | BigQuery | ASQL |
|-----------|------------|----------|------|
| Truncate to month | `DATE_TRUNC('month', d)` | `DATE_TRUNC(d, MONTH)` | `month(d)` |
| Add days | `d + INTERVAL '7 days'` | `DATE_ADD(d, INTERVAL 7 DAY)` | `d + 7 days` |
| Date literal | `DATE '2024-01-01'` | `DATE '2024-01-01'` | `@2024-01-01` |

### Relative Dates

```asql
where created_at > 7 days ago
where expires_at < 30 days from now
```

### Duration Columns

```asql
select
  days_since_created_at,      -- days(now() - created_at)
  months_until_subscription_end  -- months(subscription_end - now())
```

---

## Multi-Dialect Output

ASQL uses [SQLGlot](https://github.com/tobymao/sqlglot) for transpilation. Supported dialects include:

PostgreSQL, MySQL, SQLite, BigQuery, Snowflake, Redshift, DuckDB, Trino, Spark SQL, and [others](https://github.com/tobymao/sqlglot#dialects).

---

## What ASQL Is

- A syntax layer that compiles to SQL
- Useful for analytics queries that benefit from pipeline structure
- Compatible with any SQL database via transpilation

## What ASQL Is Not

- Not a database
- Not required—you can always use the generated SQL directly
- Not production-ready (yet)

---

## Getting Started

- [Syntax Guide](quick_start.md) — Core syntax reference
- [Window Functions](window_functions.md) — Detailed window function docs
- [Language Specification](spec.md) — Complete reference
- [Examples](examples.md) — Real queries with SQL output

---

## Inspiration

- [SQLGlot](https://github.com/tobymao/sqlglot) — SQL parsing and transpilation
- [pandas](https://pandas.pydata.org/) — Method chaining, `shift()` → `prior/next`, `rolling()` → `rolling_avg`, column ops like `drop/rename/add_prefix`
- [PRQL](https://prql-lang.org/) — Pipeline approach to SQL
- [Kusto/KQL](https://docs.microsoft.com/en-us/azure/data-explorer/kusto/query/) — Pipeline syntax at scale
- [dbt](https://www.getdbt.com/) — Many ASQL features are built-in versions of dbt macro patterns
- [ClickHouse](https://clickhouse.com/) — Aggregation patterns like `argMax`

---

<div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 4px; padding: 16px; margin: 20px 0;">
<strong>⚠️ Work in Progress</strong><br>
ASQL is experimental. Syntax may change. Feedback welcome on <a href="https://github.com/davefowler/asql">GitHub</a>.
</div>
