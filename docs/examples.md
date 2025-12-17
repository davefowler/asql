# Analytic SQL Examples

Real-world examples of Analytic SQL queries. Each example shows the Analytic SQL syntax alongside the generated SQL for different database dialects.

**Try these queries yourself:** [play.analyticsql.com](https://play.analyticsql.com)

## Table of Contents

1. [Basic Queries](#basic-queries)
2. [Filtering](#filtering)
3. [Aggregations](#aggregations)
4. [Sorting and Limiting](#sorting-and-limiting)
5. [Complex Queries](#complex-queries)

---

## Basic Queries

### Simple FROM

=== "ASQL"
    ```asql
    from users
    ```

=== "PostgreSQL"
    ```sql
    SELECT * FROM users
    ```

=== "MySQL"
    ```sql
    SELECT * FROM users
    ```

=== "BigQuery"
    ```sql
    SELECT * FROM users
    ```

=== "Snowflake"
    ```sql
    SELECT * FROM users
    ```

### FROM with WHERE

=== "ASQL"
    ```asql
    from users
    where status == "active"
    ```

=== "PostgreSQL"
    ```sql
    SELECT * FROM users WHERE status = 'active'
    ```

=== "MySQL"
    ```sql
    SELECT * FROM users WHERE status = 'active'
    ```

=== "BigQuery"
    ```sql
    SELECT * FROM users WHERE status = 'active'
    ```

=== "Snowflake"
    ```sql
    SELECT * FROM users WHERE status = 'active'
    ```

### FROM with SELECT

=== "ASQL"
    ```asql
    from users
    select name, email
    ```

=== "PostgreSQL"
    ```sql
    SELECT name, email FROM users
    ```

=== "MySQL"
    ```sql
    SELECT name, email FROM users
    ```

=== "BigQuery"
    ```sql
    SELECT name, email FROM users
    ```

=== "Snowflake"
    ```sql
    SELECT name, email FROM users
    ```

### FROM WHERE SELECT

=== "ASQL"
    ```asql
    from users
    where status == "active"
    select name, email
    ```

=== "PostgreSQL"
    ```sql
    SELECT name, email FROM users WHERE status = 'active'
    ```

=== "MySQL"
    ```sql
    SELECT name, email FROM users WHERE status = 'active'
    ```

=== "BigQuery"
    ```sql
    SELECT name, email FROM users WHERE status = 'active'
    ```

=== "Snowflake"
    ```sql
    SELECT name, email FROM users WHERE status = 'active'
    ```

---

## Filtering

### Comparison Operators

**ASQL:**
```asql
from users
where age < 18
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE age < 18
```

**ASQL:**
```asql
from users
where age > 65
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE age > 65
```

**ASQL:**
```asql
from users
where age >= 18
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE age >= 18
```

**ASQL:**
```asql
from users
where status != "inactive"
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE status <> 'inactive'
```

### NULL Checks

**ASQL:**
```asql
from users
where email is null
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE email IS NULL
```

**ASQL:**
```asql
from users
where email is not null
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE email IS NOT NULL
```

### Logical Operators

**ASQL:**
```asql
from users
where status == "active" 
    and age >= 18
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE status = 'active' AND age >= 18
```

**ASQL:**
```asql
from users
where status == "active" 
    or status == "pending"
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE status = 'active' OR status = 'pending'
```

**ASQL:**
```asql
from users
where not status == "inactive"
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE NOT status = 'inactive'
```

### Multiple Conditions

**ASQL:**
```asql
from users
where status == "active" 
    and age >= 18 
    and email is not null
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE status = 'active' AND age >= 18 AND email IS NOT NULL
```

### IN Operator

**ASQL:**
```asql
from users
where status in ("active", "pending", "verified")
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE status IN ('active', 'pending', 'verified')
```

**ASQL:**
```asql
from users
where age in (18, 19, 20, 21)
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE age IN (18, 19, 20, 21)
```

### NOT IN Operator

**ASQL:**
```asql
from users
where status not in ("inactive", "deleted", "banned")
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE NOT status IN ('inactive', 'deleted', 'banned')
```

---

## Aggregations

### GROUP BY with COUNT (#)

**ASQL:**
```asql
from users
group by country ( # as total_users )
```

**SQL (PostgreSQL):**
```sql
SELECT country, COUNT(*) AS total_users FROM users GROUP BY country
```

### GROUP BY with SUM

**ASQL:**
```asql
from sales
group by region ( sum(amount) as revenue )
```

**SQL (PostgreSQL):**
```sql
SELECT region, SUM(amount) AS revenue FROM sales GROUP BY region
```

### GROUP BY with AVG

**ASQL:**
```asql
from users
group by country ( avg(age) as avg_age )
```

**SQL (PostgreSQL):**
```sql
SELECT country, AVG(age) AS avg_age FROM users GROUP BY country
```

### Multiple Aggregations

**ASQL:**
```asql
from sales
group by region ( 
    sum(amount) as revenue, 
    # as orders, 
    avg(amount) as avg_order 
)
```

**SQL (PostgreSQL):**
```sql
SELECT region, SUM(amount) AS revenue, COUNT(*) AS orders, AVG(amount) AS avg_order 
FROM sales 
GROUP BY region
```

### Multiple Grouping Columns

**ASQL:**
```asql
from sales
group by region, month ( sum(amount) as revenue )
```

**SQL (PostgreSQL):**
```sql
SELECT region, month, SUM(amount) AS revenue FROM sales GROUP BY region, month
```

### GROUP BY with WHERE

**ASQL:**
```asql
from sales
where year == 2024
group by region ( sum(amount) as revenue )
```

**SQL (PostgreSQL):**
```sql
SELECT region, SUM(amount) AS revenue 
FROM sales 
WHERE year = 2024 
GROUP BY region
```

### All Aggregation Functions

**ASQL:**
```asql
from sales
group by region (
    sum(amount) as total_revenue,
    avg(amount) as avg_order,
    count(*) as order_count,
    min(amount) as min_order,
    max(amount) as max_order
)
```

**SQL (PostgreSQL):**
```sql
SELECT 
    region, 
    SUM(amount) AS total_revenue,
    AVG(amount) AS avg_order,
    COUNT(*) AS order_count,
    MIN(amount) AS min_order,
    MAX(amount) AS max_order
FROM sales 
GROUP BY region
```

---

## Sorting and Limiting

### SORT Ascending

**ASQL:**
```asql
from users
order by name
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users ORDER BY name ASC
```

### SORT Descending

**ASQL:**
```asql
from users
order by -total_users
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users ORDER BY total_users DESC
```

### Multiple Sort Columns

**ASQL:**
```asql
from users
order by -total_users, name
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users ORDER BY total_users DESC, name ASC
```

### TAKE/LIMIT

**ASQL:**
```asql
from users
limit 10
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users LIMIT 10
```

### GROUP BY + SORT

**ASQL:**
```asql
from users
group by country ( # as total_users )
order by -total_users
```

**SQL (PostgreSQL):**
```sql
SELECT country, COUNT(*) AS total_users 
FROM users 
GROUP BY country 
ORDER BY total_users DESC
```

### Complete Pipeline

**ASQL:**
```asql
from users 
where status == "active" 
group by country ( # as total_users ) 
order by -total_users 
limit 10
```

**SQL (PostgreSQL):**
```sql
SELECT country, COUNT(*) AS total_users 
FROM users 
WHERE status = 'active' 
GROUP BY country 
ORDER BY total_users DESC 
LIMIT 10
```

### Sort by Column (Descending)

**ASQL:**
```asql
from users
order by -updated_at
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users ORDER BY updated_at DESC
```

**ASQL:**
```asql
from users
order by -updated_at, name
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users ORDER BY updated_at DESC, name ASC
```

The `-` prefix makes it easy to order by by columns in descending order. It also works with function calls like `order by -month(created_at)`.

---

## Complex Queries

### Complex Analytics Query

**ASQL:**
```asql
from sales 
where status == "completed" and amount > 100
group by region, month ( 
    sum(amount) as revenue,
    # as order_count,
    avg(amount) as avg_order
)
order by -revenue
limit 20
```

**SQL (PostgreSQL):**
```sql
SELECT 
    region, 
    month, 
    SUM(amount) AS revenue, 
    COUNT(*) AS order_count, 
    AVG(amount) AS avg_order 
FROM sales 
WHERE status = 'completed' AND amount > 100 
GROUP BY region, month 
ORDER BY revenue DESC 
LIMIT 20
```

### User Analytics

**ASQL:**
```asql
from users
where status == "active" and age >= 18 and email is not null
group by country (
    # as total_users,
    avg(age) as avg_age
)
order by -total_users
```

**SQL (PostgreSQL):**
```sql
SELECT 
    country, 
    COUNT(*) AS total_users, 
    AVG(age) AS avg_age 
FROM users 
WHERE status = 'active' AND age >= 18 AND email IS NOT NULL 
GROUP BY country 
ORDER BY total_users DESC
```

### Sales Report

**ASQL:**
```asql
from sales
where (status == "completed" or status == "pending") 
    and amount >= 50 
    and created_at is not null
group by product_category (
    sum(amount) as total_revenue,
    # as total_orders,
    avg(amount) as avg_order_value,
    max(amount) as max_order_value
)
order by -total_revenue
limit 10
```

**SQL (PostgreSQL):**
```sql
SELECT 
    product_category, 
    SUM(amount) AS total_revenue, 
    COUNT(*) AS total_orders, 
    AVG(amount) AS avg_order_value, 
    MAX(amount) AS max_order_value 
FROM sales 
WHERE (status = 'completed' OR status = 'pending') 
    AND amount >= 50 
    AND created_at IS NOT NULL 
GROUP BY product_category 
ORDER BY total_revenue DESC 
LIMIT 10
```

---

## Try It Yourself

**The easiest way to try these examples is in the [Interactive Playground](https://play.analyticsql.com)**. Just copy any ASQL query from the examples above and paste it into the playground to see the generated SQL in real-time.

You can also use the ASQL compiler in your Python code:

```python
from asql import compile

asql_query = """
from users 
where status == "active" 
group by country ( # as total_users ) 
order by -total_users 
limit 10
"""

sql = compile(asql_query, dialect="postgres")
print(sql)
```
