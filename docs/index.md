# ASQL: SQL, Rethought for Analytics

<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; padding: 32px; margin: 24px 0; color: white;">
<h2 style="margin-top: 0; color: white;">Write queries like you think about data</h2>
<p style="font-size: 18px; margin-bottom: 0;">ASQL (pronounced "Ask-el") is a modern, pipeline-based query language designed for analytical workloads. It transpiles to any SQL dialect, making your queries more readable, less verbose, and dramatically simpler than traditional SQL.</p>
</div>

---

## Philosophy & Purpose

SQL was designed in the 1970s for transactional databases. It's powerful, but its syntax often works against how we naturally think about data transformations. ASQL was created with a few core principles:

### 🎯 Read Like You Think

Queries should flow naturally, top to bottom, in the order you reason about data:

1. Start with your data source
2. Filter to what you care about
3. Transform and aggregate
4. Order and limit the results

Not: define output columns → specify source → add filters → remember to group → finally order.

### 📐 Convention Over Configuration

If you follow good modeling practices (like dbt's naming conventions), ASQL makes smart inferences. Foreign keys like `user_id` automatically link to `users.id`. Date columns like `created_at` work with natural date functions. Everything is configurable, but sensible defaults mean less boilerplate.

### 🔤 Familiarity Over Novelty

ASQL keeps SQL's vocabulary—`from`, `where`, `group by`, `join`. We improve the grammar, not replace the language. Your SQL knowledge transfers directly.

### 🌐 Portable By Design

ASQL compiles to any SQL dialect via [SQLGlot](https://github.com/tobymao/sqlglot). Write once, run on PostgreSQL, MySQL, BigQuery, Snowflake, Redshift, DuckDB, and more. SQLGlot handles the dialect differences so you don't have to.

---

## The Pipeline Revolution

The biggest change in ASQL is **pipeline syntax**. Inspired by Python notebooks, dplyr, and data transformation tools, ASQL lets you chain operations in the order you think about them.

### The Problem with SQL

```sql
-- SQL: Read from bottom to top, inside out
SELECT 
    region, 
    SUM(amount) AS revenue
FROM (
    SELECT * FROM sales 
    WHERE EXTRACT(YEAR FROM date) = 2025
) filtered
GROUP BY region
ORDER BY revenue DESC
LIMIT 10;
```

You start with `SELECT` before you know what columns you need. Filters come after the table. CTEs pile up because SQL has no clean way to chain transformations.

### The ASQL Way

```asql
-- ASQL: Read top to bottom, like a notebook
from sales
  where year(date) = 2025
  group by region ( sum(amount) as revenue )
  order by -revenue
  limit 10
```

Start with your data, transform it step by step, end with your result. **No CTEs needed**—the pipeline handles it.

### Goodbye CTE Mess

SQL's pipeline limitation forces you into CTEs for readability. ASQL makes them mostly unnecessary:

<div class="grid-container" style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0;">
<div>

**SQL (15 lines)**
```sql
WITH active_users AS (
    SELECT * FROM users 
    WHERE is_active = true
),
by_country AS (
    SELECT 
        country, 
        COUNT(*) as total
    FROM active_users
    GROUP BY country
)
SELECT * FROM by_country
ORDER BY total DESC
LIMIT 10;
```

</div>
<div>

**ASQL (5 lines)**
```asql
from users
  where is_active
  group by country ( # as total )
  order by -total
  limit 10
```

Just keep building the pipeline. When you need to reuse a step, CTEs are still available with `set`.

</div>
</div>

---

## dbt Macros, Built In

[dbt](https://www.getdbt.com/) revolutionized analytics engineering, and their macro ecosystem filled critical gaps in SQL. ASQL pays tribute to this work by **building many of these patterns directly into the language**.

No more Jinja templating for common operations. No more `dbt_utils.star()` or `dbt_utils.surrogate_key()`. These are now first-class syntax:

### Column Operations

```asql
from users
  join orders on users.id = orders.user_id
  except users.password_hash, orders.internal_notes   -- exclude columns
  rename users.id as user_id                          -- rename inline
  prefix orders.* with order_                         -- prefix after join
```

### Deduplication

```asql
-- Keep most recent order per customer
from orders
  deduplicate by customer_id
  order by -order_date
```

No more `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...) = 1` gymnastics.

### Pivot & Unpivot

```asql
-- Transform Jira custom fields from EAV to columns
from issue_custom_fields
  pivot field_value by field_name

-- Result: issue_id | priority | sprint | story_points
```

### Gap Filling for Time Series

```asql
from orders
  group by month(created_at) as month ( sum(amount) as revenue )
  fill month with {revenue: 0}   -- fill missing months with zero
```

### Date Spines & Series

```asql
from date_spine(start = '2024-01-01', end = today(), grain = day)
from series(1, 100)
```

### Surrogate Keys

```asql
select key(user_id, order_id) as order_key
```

### Safe Casting

```asql
select value::integer? ?? 0 as amount  -- safe cast with default
```

---

## Intuitive Window Functions

Window functions are SQL's most powerful feature—and its most confusing syntax. ASQL makes common patterns intuitive:

### First/Last Per Group

<div class="grid-container" style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0;">
<div>

**SQL (8 lines)**
```sql
SELECT * FROM (
    SELECT *, 
        ROW_NUMBER() OVER (
            PARTITION BY customer_id 
            ORDER BY order_date DESC
        ) as rn
    FROM orders
) sub WHERE rn = 1;
```

</div>
<div>

**ASQL (2 lines)**
```asql
from orders
  per customer_id first by -order_date
```

</div>
</div>

### Previous/Next Row Values

<div class="grid-container" style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0;">
<div>

**SQL**
```sql
SELECT 
    month,
    revenue,
    LAG(revenue, 1) OVER (ORDER BY month) as prev_month,
    revenue - LAG(revenue, 1) OVER (ORDER BY month) as growth
FROM monthly_sales;
```

</div>
<div>

**ASQL**
```asql
from monthly_sales
  order by month
  select month, revenue,
    prior(revenue) as prev_month,
    revenue - prior(revenue) as growth
```

</div>
</div>

### Running Totals & Moving Averages

```asql
from daily_sales
  order by date
  select date, revenue,
    running_sum(revenue) as cumulative,
    rolling_avg(revenue, 7) as week_avg
```

### Window Function Reference

| ASQL | SQL Equivalent | Example |
|------|---------------|---------|
| `per ... first by` | ROW_NUMBER() + filter | `per customer_id first by -date` |
| `per ... number by` | ROW_NUMBER() | `per customer_id number by -date` |
| `prior(col)` | `LAG(col, 1)` | `prior(revenue)` |
| `next(col)` | `LEAD(col, 1)` | `next(revenue)` |
| `running_sum(col)` | `SUM() OVER (ROWS UNBOUNDED PRECEDING)` | `running_sum(amount)` |
| `running_avg(col)` | `AVG() OVER (ROWS UNBOUNDED PRECEDING)` | `running_avg(score)` |
| `rolling_avg(col, n)` | `AVG() OVER (ROWS n-1 PRECEDING)` | `rolling_avg(revenue, 7)` |

---

## Cleaner Date Functions

Date handling in SQL is a dialect minefield. `EXTRACT`, `DATE_TRUNC`, `DATEADD`, `DATEDIFF`—each database does it differently. ASQL provides **one syntax that works everywhere**:

### Date Truncation

```asql
from events
  group by month(created_at) ( # as count )
  -- Works on Postgres, MySQL, BigQuery, Snowflake...
```

### Natural Date Arithmetic

```asql
-- Relative dates
where created_at > 7 days ago
where due_date < 30 days from now

-- Date math
select order_date + 14 days as expected_delivery

-- Date differences
select days(shipped_date - order_date) as fulfillment_days
```

### The `*_since_*` / `*_until_*` Pattern

```asql
from users
  select
    username,
    days_since_created_at,      -- → days(now() - created_at)
    days_until_subscription_end  -- → days(subscription_end - now())
```

### Date Literals

```asql
where created_at > @2024-01-01
where birthday = @1990-06-15
```

---

## Auto-Generated Aliases & Function Shorthand

ASQL auto-generates clear column names for all expressions, and goes a step further with **underscore/space flexibility**.

### The Problem

In SQL, every computed column needs an alias:

```sql
SELECT 
    SUM(amount) AS sum_amount,
    AVG(price) AS avg_price,
    DATE_TRUNC('month', created_at) AS month_created_at
FROM sales;
```

### Auto Aliases

ASQL generates sensible names automatically:

```asql
from sales
  select sum(amount), avg(price), month(created_at)
  -- Produces: sum_amount, avg_price, month_created_at
```

### Function Shorthand

But we go further—**underscores and spaces are interchangeable** in function contexts:

```asql
-- All of these are equivalent:
sum(amount)           -- explicit function call
sum_amount            -- underscore shorthand  
sum amount            -- space shorthand
sum of amount         -- natural language style
```

All produce a column named `sum_amount`. This applies everywhere:

```asql
from sales
  select sum_revenue, avg_price, month_created_at
  group by year_created_at
  order by -sum_revenue
```

### Extended Patterns

Some patterns expand to more complex expressions:

```asql
days_since_created_at     -- → days(now() - created_at)
months_until_due_date     -- → months(due_date - now())
day_of_week_order_date    -- → day_of_week(order_date)
```

---

## Simplified Cohort Analysis

Cohort analysis—grouping users by signup date and tracking behavior over time—is notoriously complex in SQL. A basic retention query typically requires 40+ lines and 4-5 CTEs.

With ASQL's building blocks, cohorts become dramatically simpler:

```asql
-- Get cohort assignment using first()
set user_cohorts = from events
  group by user_id (
    month(first(event_date order by event_date)) as cohort_month
  )

-- Calculate retention by period
from events
  join user_cohorts on user_id
  select
    cohort_month,
    months(event_date - cohort_month) as period
  group by cohort_month, period (
    count(distinct user_id) as active_users
  )
  order by cohort_month, period
  select *, 
    running_sum(active_users) as cumulative,
    prior(active_users) as prev_period
```

Features that make this possible:
- `first(col order by ...)` for cohort membership
- `months(date1 - date2)` for period calculation
- `running_sum()` for cumulative metrics
- `prior()` for period-over-period comparison
- Pipeline syntax eliminates CTE nesting

---

## Smart Comment Handling

ASQL preserves your comments and can extract metadata from them. Powered by [SQLGlot's](https://github.com/tobymao/sqlglot) robust parsing:

```asql
-- @description: Monthly revenue by region
-- @owner: analytics-team
from sales
  where year(date) = 2025      -- Current year only
  group by region (
    sum(amount) as revenue     -- Total revenue
  )
```

Comments can be:
- Preserved in compiled SQL
- Extracted as metadata for documentation
- Used for query annotation and lineage

---

## Quick Comparison

| Feature | SQL | ASQL |
|---------|-----|------|
| Query order | Inside-out, scattered | Top-to-bottom, linear |
| Start keyword | `SELECT` (before you know columns) | `from` (start with data) |
| Count syntax | `COUNT(*)` | `#` |
| Descending sort | `ORDER BY x DESC` | `order by -x` |
| Date truncation | Dialect-specific | Universal `month()`, `year()` |
| Date arithmetic | `DATEADD`, `DATE_ADD`, `+ INTERVAL` | `date + 7 days` |
| Previous row | `LAG(col, 1) OVER (...)` | `prior(col)` |
| Running total | `SUM() OVER (ROWS UNBOUNDED PRECEDING)` | `running_sum(col)` |
| First per group | ROW_NUMBER() + subquery | `per ... first by` |
| Exclude columns | Manual column lists | `except col1, col2` |
| Pivot data | Dialect-specific or CASE/WHEN | `pivot val by key` |
| Gap fill | Complex CTE + generate_series | `fill column` |
| Safe cast | TRY_CAST / SAFE_CAST (varies) | `::type?` |
| CTEs required | Often (for readability) | Rarely (pipeline handles it) |

---

## Multi-Dialect Support

Write once, run anywhere. ASQL transpiles to any SQL dialect via [SQLGlot](https://github.com/tobymao/sqlglot):

- PostgreSQL
- MySQL / MariaDB
- SQLite
- BigQuery
- Snowflake
- Redshift
- DuckDB
- Trino / Presto
- Spark SQL
- And [many more...](https://github.com/tobymao/sqlglot#dialects)

---

## What ASQL Is Not

- **Not a new database** — It transpiles to SQL and works with any database
- **Not a replacement for SQL** — It's an evolution that compiles to SQL
- **Not breaking changes** — All your SQL knowledge still applies
- **Not vendor lock-in** — The output is plain SQL you can inspect and modify

---

## Get Started

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; margin: 24px 0;">

<div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
<h3 style="margin-top: 0;">📖 Quick Start</h3>
<p>Learn the basics in 5 minutes.</p>
<a href="quick_start/">Get Started →</a>
</div>

<div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
<h3 style="margin-top: 0;">🪟 Window Functions</h3>
<p>Simplified window functions: per, prior, running_sum, and more.</p>
<a href="window_functions/">Window Functions →</a>
</div>

<div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
<h3 style="margin-top: 0;">📅 Date Functions</h3>
<p>Universal date handling that works on any database.</p>
<a href="dates/">Date Functions →</a>
</div>

<div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
<h3 style="margin-top: 0;">🔧 Data Transformations</h3>
<p>Built-in pivot, deduplicate, fill, and more.</p>
<a href="transformations/">Transformations →</a>
</div>

<div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
<h3 style="margin-top: 0;">📚 Language Spec</h3>
<p>Complete language specification with all features.</p>
<a href="spec/">Full Specification →</a>
</div>

<div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
<h3 style="margin-top: 0;">💡 Examples</h3>
<p>Real-world queries with SQL comparisons.</p>
<a href="examples/">See Examples →</a>
</div>

</div>

---

<div style="background: #fff3cd; border: 2px solid #ffc107; border-radius: 8px; padding: 20px; margin: 20px 0;">
<strong>⚠️ Work in Progress</strong>
<p style="margin-bottom: 0;">ASQL is in active development. The language and implementation are evolving. Not ready for production use yet, but we'd love your feedback!</p>
</div>

---

## Credits & Inspiration

ASQL stands on the shoulders of giants:

- **[SQLGlot](https://github.com/tobymao/sqlglot)** — Powers our SQL parsing and multi-dialect transpilation
- **[dbt](https://www.getdbt.com/)** — Pioneered analytics engineering; many ASQL features are built-in versions of dbt macros
- **[PRQL](https://prql-lang.org/)** — Inspired the pipeline-first approach to SQL
- **[Kusto/KQL](https://docs.microsoft.com/en-us/azure/data-explorer/kusto/query/)** — Proved pipeline syntax works at scale
- **Python & Notebooks** — Influenced the top-to-bottom, iterative workflow

---

<div style="text-align: center; padding: 32px 0;">
<p style="font-size: 20px; color: #666;">Ready to write queries the way you think?</p>
<a href="quick_start/" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: bold;">Get Started →</a>
</div>
