# ASQL Tutorial

A hands-on guide to learning ASQL. Follow along step-by-step to master the language.

## Prerequisites

This tutorial assumes you're familiar with basic SQL concepts like SELECT, FROM, WHERE, and GROUP BY. If you've written SQL queries before, you're ready to go.

## Part 1: Your First ASQL Query

### Start with FROM

Every ASQL query starts with `from`. No more jumping around to find where your data comes from:

```asql
from users
```

This compiles to `SELECT * FROM users`. Simple.

### Add a Filter

Chain a `where` clause:

```asql
from users
  where status = "active"
```

Notice we indent with 2 spaces. This visual hierarchy shows the data flow.

### Select Specific Columns

```asql
from users
  where status = "active"
  select name, email, created_at
```

**Key insight**: Read top-to-bottom. Data flows from `users` → filtered → projected.

---

## Part 2: Aggregations

### Count Rows

Use `#` for count:

```asql
from orders
  group by status (
    # as order_count
  )
```

The `#` symbol is just `COUNT(*)`.

### Multiple Aggregations

```asql
from orders
  group by customer_id (
    sum(amount) as total_spent,
    # as order_count,
    avg(amount) as avg_order
  )
```

### Count Entities (New!)

When followed by a table name, `#` automatically counts distinct entities:

```asql
from orders
  group by status (
    # as total_orders,
    # users as unique_customers
  )
```

The `# users` becomes `COUNT(DISTINCT user_id)` — ASQL infers the primary key!

---

## Part 3: Sorting & Limiting

### Descending Order

Use `-` prefix for descending:

```asql
from users
  order by -created_at
```

This is `ORDER BY created_at DESC`.

### Combine with Limit

```asql
from orders
  group by customer_id (sum(amount) as total)
  order by -total
  limit 10
```

Top 10 customers by total spend.

---

## Part 4: Joins

### Join Operators

ASQL uses symbolic operators:

| Operator | Type | Meaning |
|----------|------|---------|
| `&` | INNER | Both must match |
| `&?` | LEFT | Right side optional |
| `?&` | RIGHT | Left side optional |
| `?&?` | FULL | Both optional |

### Example: Left Join

```asql
from users
  &? orders on users.id = orders.user_id
  select users.name, orders.amount
```

The `?` marks the "maybe null" side.

### Multi-Table Joins

```asql
from orders
  & customers on orders.customer_id = customers.id
  & products on orders.product_id = products.id
  select customers.name, products.name, orders.amount
```

---

## Part 5: Date Handling

### Date Literals

Use `@` prefix:

```asql
from orders
  where order_date >= @2024-01-01
```

### Relative Dates

```asql
from orders
  where created_at > 7 days ago

from orders
  where due_date < 30 days from now
```

### Date Truncation

Group by month:

```asql
from orders
  group by month(created_at) as month (
    sum(amount) as revenue
  )
```

---

## Part 6: Window Functions

### Get Previous Value

```asql
from monthly_sales
  order by month
  select month, revenue, prior(revenue) as prev_month
```

### Running Totals

```asql
from daily_sales
  order by date
  select date, amount, running_sum(amount) as cumulative
```

### First/Last Per Group

Most recent order per customer:

```asql
from orders
  per customer_id first by -order_date
```

This keeps only the first row (ordered by date descending) for each customer.

---

## Part 7: Sampling (New!)

### Random Sample

Get 100 random rows:

```asql
from orders
  sample 100
```

### Percentage Sample

Get ~10% of rows:

```asql
from orders
  sample 10%
```

### Stratified Sample

100 random rows per category:

```asql
from products
  sample 100 per category
```

---

## Part 8: Reshaping Data (New!)

### Pivot: Rows to Columns

```asql
from sales
  pivot sum(amount) by status values ('pending', 'shipped', 'delivered')
  group by customer_id
```

Creates columns `pending`, `shipped`, `delivered` with sum of amounts.

### Unpivot: Columns to Rows

```asql
from quarterly_data
  unpivot q1, q2, q3, q4 into quarter, value
```

Turns wide data into long format.

### Explode: Arrays to Rows

```asql
from posts
  explode tags as tag
  group by tag (# as post_count)
```

One row per array element.

---

## Part 9: Column Operators (New!)

### Exclude Columns

```asql
from users
  except password_hash, internal_notes
```

### Rename Columns

```asql
from users
  rename id as user_id
```

### Replace Values

```asql
from users
  replace name with upper(name), email with lower(email)
```

---

## Part 10: CTEs with stash

### Save Intermediate Results

```asql
from orders
  where status = "completed"
  stash as completed_orders
  group by customer_id (sum(amount) as total)
  order by -total
  limit 10
```

The `stash as` creates a CTE and continues the pipeline.

### Top-Level Variables

```asql
from users
  where is_active
  stash as active_users

from active_users
  group by country (# as total)
```

---

## Putting It All Together

Here's a complete analytics query:

```asql
from orders
  where created_at > 30 days ago
  where status = "completed"
  &? customers on orders.customer_id = customers.id
  group by customers.country (
    sum(orders.amount) as revenue,
    # as order_count,
    # customers as unique_customers,
    avg(orders.amount) as avg_order
  )
  order by -revenue
  limit 10
  select country, revenue, unique_customers, avg_order
```

This query:
1. Filters to completed orders from last 30 days
2. Left joins with customers
3. Groups by country
4. Computes revenue, counts, and average
5. Sorts by revenue
6. Takes top 10
7. Selects final columns

---

## Quick Reference

| ASQL | SQL |
|------|-----|
| `from users` | `SELECT * FROM users` |
| `where x = 1` | `WHERE x = 1` |
| `order by -col` | `ORDER BY col DESC` |
| `#` | `COUNT(*)` |
| `# users` | `COUNT(DISTINCT user_id)` |
| `&` | `INNER JOIN` |
| `&?` | `LEFT JOIN` |
| `@2024-01-01` | `DATE '2024-01-01'` |
| `7 days ago` | `CURRENT_DATE - INTERVAL '7 days'` |
| `prior(col)` | `LAG(col)` |
| `running_sum(col)` | `SUM(col) OVER (ROWS UNBOUNDED PRECEDING)` |
| `sample 100` | `ORDER BY RANDOM() LIMIT 100` |
| `except col` | `SELECT * EXCEPT(col)` |

---

## Next Steps

- **[Playground](https://play.analyticsql.com)** — Try these examples interactively
- **[Syntax Guide](syntax/index.md)** — Deep dive into each feature
- **[Examples](examples.md)** — More real-world patterns
- **[Language Specification](spec.md)** — Complete reference

---

## Exercises

Try writing these queries in the playground:

1. **Basic**: Get the top 5 countries by user count
2. **Joins**: Find orders with their customer names, sorted by amount
3. **Dates**: Get monthly revenue for 2024
4. **Window**: Add a running total to daily sales
5. **Sampling**: Get 50 random products per category
6. **Pivot**: Turn status counts into columns

<details>
<summary>Solutions</summary>

**1. Top 5 countries:**
```asql
from users
  group by country (# as user_count)
  order by -user_count
  limit 5
```

**2. Orders with customers:**
```asql
from orders
  &? customers on orders.customer_id = customers.id
  select orders.id, customers.name, orders.amount
  order by -orders.amount
```

**3. Monthly revenue:**
```asql
from orders
  where year(created_at) = 2024
  group by month(created_at) as month (
    sum(amount) as revenue
  )
  order by month
```

**4. Running total:**
```asql
from daily_sales
  order by date
  select date, amount, running_sum(amount) as cumulative
```

**5. Stratified sample:**
```asql
from products
  sample 50 per category
```

**6. Status pivot:**
```asql
from orders
  pivot count(*) by status values ('pending', 'shipped', 'delivered')
```

**7. Cohort analysis:**
```asql
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date)
```

This tracks monthly active users by their signup month - a complex query that would take 50+ lines in SQL!

</details>

---

## Part 8: Cohort Analysis

Cohort analysis is one of the most powerful patterns in analytics, but it's notoriously complex in SQL. ASQL makes it simple.

### What is Cohort Analysis?

Cohort analysis groups users by when they started (their "cohort") and tracks their behavior over time. For example:
- How many users from January 2024 are still active in March 2024?
- How does revenue from February signups compare to March signups?

### Basic Cohort Query

```asql
from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)
```

This single query:
- Groups events by month
- Assigns users to cohorts based on signup month
- Calculates periods since signup
- Tracks active users per period

**Output:**
- `cohort_month`: When users signed up
- `period`: Months since signup (0 = signup month, 1 = first month after, etc.)
- `active`: Active users in that period
- `cohort_size`: Total users in the cohort

### Revenue Cohorts

Track revenue by first purchase cohort:

```asql
from orders
group by month(order_date) (sum(total) as revenue)
cohort by month(customers.first_order_date)
```

### With Period-over-Period Analysis

Add window functions for period-over-period comparisons:

```asql
from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)
select
  cohort_month,
  period,
  active,
  prior(active) as prev_period_active,
  active - prior(active) as change
```

### Lifetime Value (LTV)

Calculate cumulative revenue and LTV:

```asql
from orders
group by month(order_date) (sum(total) as revenue)
cohort by month(customers.first_order_date)
select
  cohort_month,
  period,
  revenue,
  running_sum(revenue) as cumulative_revenue,
  running_sum(revenue) / cohort_size as ltv
```

### Why Cohort Analysis Matters

**SQL (50+ lines):**
```sql
WITH user_cohorts AS (
    SELECT user_id, DATE_TRUNC('month', signup_date) AS cohort_month
    FROM users
),
activity_months AS (
    SELECT user_id, DATE_TRUNC('month', event_date) AS activity_month
    FROM events
    GROUP BY 1, 2
),
cohort_sizes AS (
    SELECT cohort_month, COUNT(*) AS size
    FROM user_cohorts GROUP BY 1
),
cohort_activity AS (
    SELECT 
        uc.cohort_month,
        EXTRACT(YEAR FROM AGE(am.activity_month, uc.cohort_month)) * 12 +
        EXTRACT(MONTH FROM AGE(am.activity_month, uc.cohort_month)) AS period,
        COUNT(DISTINCT uc.user_id) AS active
    FROM user_cohorts uc
    JOIN activity_months am ON uc.user_id = am.user_id
    WHERE am.activity_month >= uc.cohort_month
    GROUP BY 1, 2
)
SELECT 
    ca.cohort_month, cs.size, ca.period,
    ca.active, ROUND(ca.active::numeric / cs.size * 100, 1) AS retention
FROM cohort_activity ca
JOIN cohort_sizes cs ON ca.cohort_month = cs.cohort_month
ORDER BY ca.cohort_month, ca.period;
```

**ASQL (3 lines):**
```asql
from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)
```

**94% reduction in complexity!** 🎉

---

## Next Steps

You've learned the fundamentals of ASQL! To dive deeper:

- **Syntax Reference**: See [syntax documentation](syntax/index.md) for detailed syntax guides
- **Examples**: Check out [more examples](examples.md) for real-world patterns
- **Specification**: Read the [full specification](spec.md) for complete language details
- **Playground**: Try queries interactively at [play.analyticsql.com](https://play.analyticsql.com)

Happy querying! 🚀
