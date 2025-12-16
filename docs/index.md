# ASQL: SQL, Rethought for Analytics

<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; padding: 32px; margin: 24px 0; color: white;">
<h2 style="margin-top: 0; color: white;">Write queries like you think about data</h2>
<p style="font-size: 18px; margin-bottom: 0;">ASQL (pronounced "Ask-el") is a modern query language that transpiles to SQL. It's designed to be more readable, less verbose, and better suited for analytics than traditional SQL.</p>
</div>

---

## Why ASQL?

SQL was designed in the 1970s. It's powerful, but its syntax often works against how we naturally think about data. ASQL fixes that while keeping full SQL compatibility.

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

You have to start with `SELECT`, but you don't know what columns you need yet. Filters come after the table. Grouping appears before ordering. The logic is scattered.

### The ASQL Way

```asql
-- ASQL: Read top to bottom, left to right
from sales
  where year(date) == 2025
  group by region ( sum(amount) as revenue )
  sort -revenue
  take 10
```

Start with your data, transform it step by step, and end with your result. It reads like you think.

---

## Key Features

### 📊 Pipeline Syntax

Build queries step-by-step in the order you think about them:

<div class="grid-container" style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0;">
<div>

**SQL**
```sql
SELECT country, COUNT(*) as users
FROM users
WHERE status = 'active'
GROUP BY country
ORDER BY users DESC;
```

</div>
<div>

**ASQL**
```asql
from users
  where status == "active"
  group by country ( # as users )
  sort -users
```

</div>
</div>

---

### 🔢 Clean Aggregation Syntax

Use `#` for count and natural language for other aggregations:

<div class="grid-container" style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0;">
<div>

**SQL**
```sql
SELECT 
    region,
    COUNT(*) AS total_orders,
    SUM(amount) AS revenue,
    AVG(amount) AS avg_order
FROM orders
GROUP BY region;
```

</div>
<div>

**ASQL**
```asql
from orders
  group by region (
    # as total_orders,
    sum(amount) as revenue,
    avg(amount) as avg_order
  )
```

</div>
</div>

---

### 📅 Simple Date Functions

No more `EXTRACT`, `DATE_TRUNC`, or dialect-specific date handling:

<div class="grid-container" style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0;">
<div>

**SQL (PostgreSQL)**
```sql
SELECT 
    DATE_TRUNC('month', created_at) AS month,
    COUNT(*) AS signups
FROM users
GROUP BY DATE_TRUNC('month', created_at)
ORDER BY month;
```

**SQL (MySQL)**
```sql
SELECT 
    DATE_FORMAT(created_at, '%Y-%m') AS month,
    COUNT(*) AS signups
FROM users
GROUP BY DATE_FORMAT(created_at, '%Y-%m')
ORDER BY month;
```

</div>
<div>

**ASQL (works everywhere)**
```asql
from users
  group by month(created_at) ( # as signups )
  sort month
```

One syntax. Any database.

</div>
</div>

---

### 🔗 No CTEs Needed (Usually)

SQL's pipeline limitation forces you to use CTEs. ASQL's pipeline syntax makes them unnecessary:

<div class="grid-container" style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0;">
<div>

**SQL**
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
ORDER BY total DESC;
```

</div>
<div>

**ASQL**
```asql
from users
  where is_active
  group by country ( # as total )
  sort -total
```

Just keep building the pipeline. When you need to reuse a step, CTEs are still available with `set`.

</div>
</div>

---

### 🎯 Intuitive Sorting

Use `-` prefix for descending. No more `DESC` keyword:

<div class="grid-container" style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0;">
<div>

**SQL**
```sql
SELECT * FROM users
ORDER BY created_at DESC, name ASC;
```

</div>
<div>

**ASQL**
```asql
from users
  sort -created_at, name
```

</div>
</div>

---

### 🪟 Simplified Window Functions

Window functions are powerful but verbose. ASQL makes common patterns intuitive:

<div class="grid-container" style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0;">
<div>

**SQL (get most recent order per customer)**
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

**ASQL**
```asql
from orders
  per customer_id first by -order_date
```

Or use `prior()` for LAG:
```asql
from sales
  sort month
  select month, revenue, 
    prior(revenue) as prev_month
```

</div>
</div>

**Built-in window utilities:**

| Function | SQL Equivalent | Example |
|----------|---------------|---------|
| `per ... first by` | ROW_NUMBER() + QUALIFY | `per customer_id first by -date` → most recent per customer |
| `per ... number by` | ROW_NUMBER() | `per customer_id number by -date` → add row numbers |
| `prior(col)` | `LAG(col, 1)` | `prior(revenue)` → previous row's revenue |
| `next(col)` | `LEAD(col, 1)` | `next(revenue)` → next row's revenue |
| `running_sum(col)` | `SUM(col) OVER (ROWS UNBOUNDED PRECEDING)` | `running_sum(amount)` |
| `rolling_avg(col, n)` | `AVG(col) OVER (ROWS n-1 PRECEDING)` | `rolling_avg(revenue, 7)` → 7-day average |

---

### 🔤 Case-Safe Identifiers

No more quoting headaches. Write `createdAt`, `created_at`, or `CreatedAt` — ASQL matches case-insensitively:

```asql
-- All of these work the same
from Users
  select firstName, createdAt
  where status == "active"
```

---

### 🌐 Multi-Dialect Support

Write once, run anywhere. ASQL transpiles to any SQL dialect via SQLGlot:

- PostgreSQL
- MySQL
- SQLite
- BigQuery
- Snowflake
- Redshift
- DuckDB
- And more...

---

## Quick Comparison

| Feature | SQL | ASQL |
|---------|-----|------|
| Query order | Inside-out, scattered | Top-to-bottom, linear |
| Start keyword | `SELECT` (before you know columns) | `from` (start with data) |
| Count syntax | `COUNT(*)` | `#` |
| Descending sort | `ORDER BY x DESC` | `sort -x` |
| Date extraction | Dialect-specific (`EXTRACT`, `DATE_TRUNC`, etc.) | Universal (`year()`, `month()`) |
| Previous row value | `LAG(col, 1) OVER (...)` | `prior(col)` |
| Running total | `SUM(col) OVER (ROWS UNBOUNDED PRECEDING)` | `running_sum(col)` |
| Deduplication | ROW_NUMBER() + subquery | `per ... first by ...` |
| Case sensitivity | Requires exact case or quotes | Case-safe by default |
| CTEs required | Often (for readability) | Rarely (pipeline handles it) |

---

## Try It Out

### Basic Query

```asql
from sales
  where year(date) == 2025
  group by region ( sum(amount) as revenue )
  sort -revenue
  take 10
```

### With Joins

```asql
from opportunities
  join owners on owner_id == owners.id
  where owners.is_active
  group by owners.name ( sum(amount) as pipeline )
  sort -pipeline
```

### Time Series Analysis

```asql
from events
  where type == "purchase"
  group by month(created_at), product_id (
    # as purchases,
    sum(amount) as revenue
  )
  sort month, -revenue
```

---

## What ASQL Is Not

- **Not a new database** — It transpiles to SQL and works with any database
- **Not a replacement for SQL** — It's an evolution that compiles to SQL
- **Not breaking changes** — All your SQL knowledge still applies
- **Not vendor lock-in** — The output is plain SQL

---

## Get Started

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; margin: 24px 0;">

<div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
<h3 style="margin-top: 0;">📖 Learn the Syntax</h3>
<p>Quick introduction to ASQL's core syntax and operators.</p>
<a href="quick_start/">Syntax Guide →</a>
</div>

<div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
<h3 style="margin-top: 0;">🪟 Window Functions</h3>
<p>Simplified window functions: prior(), running_sum(), qualify, and more.</p>
<a href="window_functions/">Window Functions →</a>
</div>

<div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
<h3 style="margin-top: 0;">📚 Language Spec</h3>
<p>Complete language specification with all features and rationale.</p>
<a href="spec/">Full Specification →</a>
</div>

<div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
<h3 style="margin-top: 0;">💡 Examples</h3>
<p>Real-world query examples with SQL comparisons.</p>
<a href="examples/">See Examples →</a>
</div>

<div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
<h3 style="margin-top: 0;">🔧 Integration</h3>
<p>Use ASQL in your Python projects.</p>
<a href="integrating/">Integration Guide →</a>
</div>

</div>

---

<div style="background: #fff3cd; border: 2px solid #ffc107; border-radius: 8px; padding: 20px; margin: 20px 0;">
<strong>⚠️ Work in Progress</strong>
<p style="margin-bottom: 0;">ASQL is in active development. The language and implementation are evolving. Not ready for production use yet, but we'd love your feedback!</p>
</div>

---

## Philosophy

ASQL is built on a few core principles:

1. **Read like you think** — Queries should flow naturally, top to bottom
2. **Convention over configuration** — Smart defaults for common patterns
3. **Familiarity over novelty** — Keep SQL's vocabulary, improve the grammar
4. **Portable by design** — Works with any database via SQL transpilation

---

<div style="text-align: center; padding: 32px 0;">
<p style="font-size: 20px; color: #666;">Ready to write queries the way you think?</p>
<a href="quick_start/" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: bold;">Get Started →</a>
</div>
