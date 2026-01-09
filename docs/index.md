# ASQL: SQL with Analytics Built In

Analytic SQL (ASQL) is a query language designed for analytics work. It adds **built-in analytics features** that SQL lacks—guaranteed complete results, cohort analysis, cross-dialect date handling—and uses a pipeline syntax that flows top-to-bottom.

Think of it as SQL with analytics superpowers. Write ASQL, get standard SQL for any dialect.

**Status**: Experimental. [GitHub](https://github.com/davefowler/asql)

---

## The Problem with SQL for Analytics

SQL was designed in the 1970s for **transactional systems**—banking, inventory, order processing. It answers "what happened?" based on rows that exist. This works great for OLTP.

But **analytics is different**. When you're building dashboards, tracking trends, or calculating month-over-month metrics, SQL's design causes real problems:

### Missing Data Points

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

April and May are missing. Your chart line jumps. Your MoM calculation uses the wrong prior month. Your dashboard looks broken.

Every analytics team builds workarounds: date dimension tables, calendar CTEs, CROSS JOINs, post-processing in Python. It's tedious and error-prone.

### Date Dialect Chaos

```sql
-- PostgreSQL
SELECT DATE_TRUNC('month', created_at) FROM orders;

-- BigQuery  
SELECT DATE_TRUNC(created_at, MONTH) FROM orders;

-- MySQL
SELECT DATE_FORMAT(created_at, '%Y-%m-01') FROM orders;
```

Same operation, different syntax per database. Copy-paste between dialects breaks.

### Window Function Verbosity

Getting the most recent order per customer—a common analytics pattern:

```sql
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY customer_id ORDER BY order_date DESC
    ) as rn
    FROM orders
) sub WHERE rn = 1;
```

This should be one line.

---

## ASQL's Analytics Features

ASQL builds solutions to these problems **into the language**.

### Guaranteed Complete Results

ASQL automatically fills gaps in your grouped data:

```asql-play
from orders
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

No dimension tables. No CTEs. No post-processing. ASQL ensures all expected time periods appear in your results—analytically correct by default.

See [Guaranteed Groups](concepts/guaranteed-groups.md) for details.

### Cross-Dialect Date Handling

Write once, run on any database:

```asql
where created_at > 7 days ago
where due_date < 30 days from now
select order_date + 14 days as delivery_date
```

| Operation | PostgreSQL | BigQuery | ASQL |
|-----------|------------|----------|------|
| Truncate to month | `DATE_TRUNC('month', d)` | `DATE_TRUNC(d, MONTH)` | `month(d)` |
| Add days | `d + INTERVAL '7 days'` | `DATE_ADD(d, INTERVAL 7 DAY)` | `d + 7 days` |
| Date literal | `DATE '2024-01-01'` | `DATE '2024-01-01'` | `@2024-01-01` |

ASQL compiles to the correct syntax for your target database.

### One-Line Window Patterns

Common analytics operations become single lines:

```asql-play
-- Most recent order per customer
from orders
  per customer_id first by -order_date

-- Previous period comparison
from monthly_sales
  select month, revenue, prior(revenue) as prev_revenue

-- Running totals
from daily_sales
  select date, revenue, running_sum(revenue) as cumulative
```

| ASQL | SQL Equivalent |
|------|---------------|
| `per X first by -date` | `ROW_NUMBER() OVER (PARTITION BY X ORDER BY date DESC) = 1` |
| `prior(col)` | `LAG(col, 1) OVER (...)` |
| `next(col)` | `LEAD(col, 1) OVER (...)` |
| `running_sum(col)` | `SUM(col) OVER (ROWS UNBOUNDED PRECEDING)` |
| `rolling_avg(col, 7)` | `AVG(col) OVER (ROWS 6 PRECEDING)` |

### Convention-Based Inference

ASQL infers relationships from naming patterns:

```asql-play
-- Auto-joins on user_id → users.id
from orders
  & users
  select orders.*, users.name

-- FK shorthand: department_id matches departments.id
from employees
  join departments on department_id
```

When your tables follow standard naming conventions (`user_id` → `users.id`), ASQL figures out the join conditions. No more typing the obvious.

---

## Pipeline Syntax

ASQL queries flow top-to-bottom in execution order:

```asql-play
from sales
  where year(date) = 2024
  group by region ( sum(amount) as revenue )
  where revenue > 1000
  order by -revenue
  limit 10
```

Compare to SQL's inside-out structure:

```sql
SELECT region, SUM(amount) as revenue  -- 5th
FROM sales                              -- 1st
WHERE YEAR(date) = 2024                 -- 2nd
GROUP BY region                         -- 3rd
HAVING SUM(amount) > 1000               -- 4th
ORDER BY revenue DESC                   -- 6th
LIMIT 10;                               -- 7th
```

This matters most for analytics work—dbt models, ELT pipelines, dashboards—where queries are written once and read many times. Linear flow makes code review, debugging, and refactoring significantly easier.

### CTEs When You Need Them

When you need to reuse intermediate results, use `stash as`:

```asql-play
from users
  where is_active
  stash as active_users

  group by country ( # as total )
```

---

## Syntax Shortcuts

ASQL adds shorthand for patterns that are verbose in SQL.

### Count

```asql
--                    -- COUNT(*)
-- users              -- COUNT(DISTINCT user_id)
#(distinct user_id)  -- COUNT(DISTINCT user_id) - explicit
```

### Descending Sort

```asql
order by -revenue    -- ORDER BY revenue DESC
```

### Natural Aggregates

These are equivalent:

```asql
sum(amount)
sum amount
sum_amount
```

All produce a column named `sum_amount`.

---

## Column Operations

### Exclude Columns

```asql-play
from users
  except password_hash, internal_notes
```

### Rename

```asql-play
from users
  rename id as user_id
```

### Replace Values

```asql-play
from users
  replace name with upper(name), salary with round(salary, 2)
```

---

## Sampling

```asql
-- Fixed sample size
from orders sample 100

-- Percentage sample
from orders sample 10%

-- Stratified sampling (N per group)
from orders sample 100 per category
```

---

## Pivot & Unpivot

```asql
-- Rows to columns
from sales
  pivot sum(amount) by category values ('Electronics', 'Clothing')

-- Columns to rows
from metrics
  unpivot jan, feb, mar into month, value

-- Expand arrays
from posts
  explode tags as tag
```

---

## Multi-Dialect Output

ASQL uses [SQLGlot](https://github.com/tobymao/sqlglot) for transpilation:

PostgreSQL, MySQL, SQLite, BigQuery, Snowflake, Redshift, DuckDB, Trino, Spark SQL, and [more](https://github.com/tobymao/sqlglot#dialects).

---

## What ASQL Is

- **Analytics-first** — Built-in features for dashboards, time series, and reporting
- **Analytically correct** — Guaranteed complete results prevent missing data bugs
- **SQL-compatible** — Familiar vocabulary, compiles to standard SQL
- **Dialect-portable** — Write once, run on any database

## What ASQL Is Not

- Not a database
- Not required—use the generated SQL directly if you prefer
- Not production-ready (yet)

---

## Getting Started

- [Quick Start](quick_start.md) — Get up and running quickly
- [Tutorial](tutorial.md) — Hands-on, step-by-step learning guide
- [Grouping & Aggregation](group_by.md) — Guaranteed groups, aggregates
- [Window Functions](window_functions.md) — Running totals, ranking, prior/next
- [Examples](examples.md) — Real queries with SQL output

## Documentation

### Concepts

Understanding ASQL's design:

- [Guaranteed Groups](concepts/guaranteed-groups.md) — Automatic gap-filling
- [Pipeline Semantics](concepts/pipelines.md) — Why FROM-first matters
- [Convention Over Configuration](concepts/conventions.md) — Smart defaults
- [Function Shorthand](concepts/shorthand.md) — Underscore/space flexibility

### Syntax Guide

- [Syntax Overview](syntax/index.md) — All syntax documentation
- [Pipeline Basics](syntax/pipeline.md) — FROM-first queries, chaining
- [Aggregations](syntax/aggregations.md) — GROUP BY deep dive
- [Joins](syntax/joins.md) — Join operators, FK inference
- [Dates & Time](syntax/dates.md) — Date functions, arithmetic
- [Window Functions](syntax/window-functions.md) — Ranking, running totals
- [CTEs & Variables](syntax/ctes.md) — stash as, set
- [Sampling](syntax/sampling.md) — Random, percentage, stratified sampling
- [Pivot, Unpivot & Explode](syntax/pivot-unpivot.md) — Data reshaping

### Reference

- [Functions Reference](reference/functions.md) — All built-in functions
- [Operators Reference](reference/operators.md) — All operators
- [Keywords Reference](reference/keywords.md) — Reserved keywords
- [Language Specification](spec.md) — Complete language reference

### Development

- [Testing](testing.md) — How ASQL is tested, database coverage
- [Dialect Limitations](dialect-limitations.md) — Known dialect-specific limitations

---

## Inspiration

- [SQLGlot](https://github.com/tobymao/sqlglot) — SQL parsing and transpilation
- [pandas](https://pandas.pydata.org/) — Method chaining, column operations
- [PRQL](https://prql-lang.org/) — Pipeline approach to SQL
- [dbt](https://www.getdbt.com/) — Many ASQL features are built-in versions of dbt macro patterns
- [Kusto/KQL](https://docs.microsoft.com/en-us/azure/data-explorer/kusto/query/) — Pipeline syntax at scale

---

<div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 4px; padding: 16px; margin: 20px 0;">
<strong>⚠️ Work in Progress</strong><br>
ASQL is experimental. Syntax may change. Feedback welcome on <a href="https://github.com/davefowler/asql">GitHub</a>.
</div>
