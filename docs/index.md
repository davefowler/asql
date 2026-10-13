# ASQL: SQL with Analytics Built In

Analytic SQL (ASQL) is a query language designed for analytics work. It's a **superset of SQL** — any standard SQL query is valid ASQL — with a **pipe syntax** that flows top-to-bottom, **built-in helpers** for common analytics patterns (like dbt_utils macros), and **cross-dialect** compilation handled automatically.

Think of it as SQL with analytics superpowers. Write ASQL, get standard SQL for any dialect.

**Status**: Experimental. [GitHub](https://github.com/davefowler/asql)

---

## Why ASQL

- [Pipe syntax](syntax/pipe.md) — queries flow top-to-bottom in execution order (`from` → `where` → `group by` → `order by`), not SQL's inside-out shape. Written once, read many times.
- [Auto aliases](reference/auto-aliasing.md) — each function gets a consistent, intuitive alias automatically. No more `AS inconsistent_name` after every aggregation, and no unusable `f0_`/`count` defaults.
- [spine by](concepts/guaranteed-groups.md) — an alternative to `group by` that guarantees the groups exist with a spine. No more missing dates punching holes in your time series.
- [Filter after aggregation](syntax/aggregations.md) — write a plain `where` after a `group by` instead of reaching for `HAVING` or wrapping the query in a CTE.
- [Window helpers](syntax/window-functions.md) — `prior`, `next`, `running_sum`, `rolling_avg`, and `per X first by` collapse verbose `OVER (...)` clauses into a single readable line.
- [Cross-dialect dates](syntax/dates.md) — `7 days ago`, `month(d)`, and `@2024-01-01` compile to the right syntax per database. Write date logic once, run it anywhere.
- [Convention-based joins](syntax/joins.md) — ASQL infers join conditions from naming (`user_id` → `users.id`), so you stop typing the obvious `ON` clauses.
- [Count shorthand](concepts/shorthand.md) — `#` is `COUNT(*)`, `##col` is `COUNT(DISTINCT col)`, and `order by -x` sorts descending. Less punctuation for the patterns you write constantly.
- [Multi-dialect output](reference/index.md) — compiles to standard SQL for PostgreSQL, BigQuery, Snowflake, DuckDB, and more, so you can always read and run the generated query.

---

## Start From the SQL You Know

Any SQL query is already an ASQL query:

```asql-play
select * from users where status = 'active'
```

The upgrades start inside the familiar form — `#` for counts, `-` for
descending, dates in plain language:

```asql-play
select country, # as signups
from users
where created_at > 30 days ago
group by country
order by -signups
```

And then your SELECT statement can just... keep going. Filter after the
aggregation with a plain `where` — no HAVING, no CTE wrapping:

```asql-play
select region, sum(amount) as revenue
from orders
group by region
where revenue > 1000
order by -revenue
```

Once your queries read top-to-bottom anyway, the leading `select *` is dead
weight. Drop it — yup, ASQL is a pipe syntax. Really, it's both.

---

## Pipe Syntax: Queries That Read Like Steps

ASQL queries flow top-to-bottom in execution order:

```asql-play
from sales
  where extract(year from date) = 2024
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

## Built-in Analytics Helpers

ASQL includes common analytics patterns that you'd normally get from dbt_utils or custom macros—built right into the language.

### One-Line Window Functions

Common analytics operations become single lines:

```asql-play
-- Most recent order per customer
from orders
  per customer_id first by -order_date
```

```asql-play
-- Previous period comparison
from monthly_sales
  select month, revenue, prior(revenue) as prev_revenue
```

```asql-play
-- Running totals (the running_sum accumulates in the query's order)
from daily_sales
  order by date
  select date, revenue, running_sum(revenue) as cumulative
```

| ASQL | SQL Equivalent | dbt_utils Macro |
|------|---------------|-----------------|
| `per X first by -date` | `ROW_NUMBER() OVER (PARTITION BY X ORDER BY date DESC) = 1` | `deduplicate` |
| `prior(col)` | `LAG(col, 1) OVER (...)` | — |
| `next(col)` | `LEAD(col, 1) OVER (...)` | — |
| `running_sum(col)` | `SUM(col) OVER (ORDER BY date ROWS UNBOUNDED PRECEDING)` | — |
| `rolling_avg(col, 7)` | `AVG(col) OVER (ORDER BY date ROWS 6 PRECEDING)` | — |

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

### Convention-Based Joins

ASQL infers relationships from naming patterns:

```asql-play
-- Auto-joins on user_id → users.id
from orders
  & users
  select orders.*, users.name
```

```asql-play
-- FK shorthand: department_id matches departments.id
from employees
  join departments on department_id
```

When your tables follow standard naming conventions (`user_id` → `users.id`), ASQL figures out the join conditions. No more typing the obvious.

---

## Syntax Shortcuts

ASQL adds shorthand for patterns that are verbose in SQL.

### Count

```asql
#                    -- COUNT(*)
#col                 -- COUNT(col)
##col                -- COUNT(DISTINCT col) - double # = distinct
uniq(col)            -- COUNT(DISTINCT col) - function form
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

## Gap-Filling for Time Series

When grouping by time, SQL only returns rows that exist—missing months simply disappear from your results. ASQL can automatically fill gaps:

```asql-play
from orders
  group by spine(month(order_date)) (
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

The `spine()` function ensures all time periods appear—even April and May with no orders. The `?? 0` provides a default value for missing periods.

See [Guaranteed Groups](concepts/guaranteed-groups.md) for details.

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

- **Pipe syntax** — Queries flow top-to-bottom in execution order, like dbt and pandas
- **Built-in helpers** — Common analytics patterns (dedup, window functions, date math) built into the language
- **Dialect-portable** — Write once, run on PostgreSQL, BigQuery, Snowflake, DuckDB, and more
- **SQL-compatible** — Familiar vocabulary, compiles to standard SQL you can inspect

## What ASQL Is Not

- Not a database
- Not required—use the generated SQL directly if you prefer
- Not production-ready (yet)

---

## Getting Started

- [Quick Start](quick_start.md) — Get up and running quickly
- [Tutorial](tutorial.md) — Hands-on, step-by-step learning guide
- [Window Functions](window_functions.md) — Running totals, ranking, prior/next
- [Grouping & Aggregation](group_by.md) — GROUP BY, aggregates, gap-filling
- [Examples](examples.md) — Real queries with SQL output

## Documentation

### Concepts

Understanding ASQL's design:

- [Pipe Semantics](concepts/pipe-semantics.md) — Why FROM-first matters
- [Convention Over Configuration](concepts/conventions.md) — Smart defaults
- [Function Shorthand](concepts/shorthand.md) — Underscore/space flexibility
- [Guaranteed Groups](concepts/guaranteed-groups.md) — Automatic gap-filling

### Syntax Guide

- [Syntax Overview](syntax/index.md) — All syntax documentation
- [Pipe Basics](syntax/pipe.md) — FROM-first queries, chaining
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
- [Kusto/KQL](https://docs.microsoft.com/en-us/azure/data-explorer/kusto/query/) — Pipe syntax at scale

---

<div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 4px; padding: 16px; margin: 20px 0;">
<strong>⚠️ Work in Progress</strong><br>
ASQL is experimental. Syntax may change. Feedback welcome on <a href="https://github.com/davefowler/asql">GitHub</a>.
</div>
