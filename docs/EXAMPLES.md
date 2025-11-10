# ASQL Examples

This document provides comprehensive examples of ASQL queries, showing how they translate to SQL.

## Table of Contents

1. [Basic Queries](#basic-queries)
2. [Filtering](#filtering)
3. [Aggregations](#aggregations)
4. [Sorting and Limiting](#sorting-and-limiting)
5. [Derived Columns](#derived-columns)
6. [Complex Queries](#complex-queries)

---

## Basic Queries

### Simple FROM

**ASQL:**
```asql
from users
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users
```

### FROM with WHERE

**ASQL:**
```asql
from users where status == "active"
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE status = 'active'
```

### FROM with SELECT

**ASQL:**
```asql
from users select name, email
```

**SQL (PostgreSQL):**
```sql
SELECT name, email FROM users
```

### FROM WHERE SELECT

**ASQL:**
```asql
from users where status == "active" select name, email
```

**SQL (PostgreSQL):**
```sql
SELECT name, email FROM users WHERE status = 'active'
```

---

## Filtering

### Comparison Operators

**ASQL:**
```asql
from users where age < 18
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE age < 18
```

**ASQL:**
```asql
from users where age > 65
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE age > 65
```

**ASQL:**
```asql
from users where age >= 18
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE age >= 18
```

**ASQL:**
```asql
from users where status != "inactive"
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE status <> 'inactive'
```

### NULL Checks

**ASQL:**
```asql
from users where email is null
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE email IS NULL
```

**ASQL:**
```asql
from users where email is not null
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE email IS NOT NULL
```

### Logical Operators

**ASQL:**
```asql
from users where status == "active" and age >= 18
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE status = 'active' AND age >= 18
```

**ASQL:**
```asql
from users where status == "active" or status == "pending"
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE status = 'active' OR status = 'pending'
```

**ASQL:**
```asql
from users where not status == "inactive"
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE NOT status = 'inactive'
```

### Multiple Conditions

**ASQL:**
```asql
from users where status == "active" and age >= 18 and email is not null
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users WHERE status = 'active' AND age >= 18 AND email IS NOT NULL
```

---

## Aggregations

### GROUP BY with COUNT (#)

**ASQL:**
```asql
from users group by country ( # as total_users )
```

**SQL (PostgreSQL):**
```sql
SELECT country, COUNT(*) AS total_users FROM users GROUP BY country
```

### GROUP BY with SUM

**ASQL:**
```asql
from sales group by region ( sum(amount) as revenue )
```

**SQL (PostgreSQL):**
```sql
SELECT region, SUM(amount) AS revenue FROM sales GROUP BY region
```

### GROUP BY with AVG

**ASQL:**
```asql
from users group by country ( avg(age) as avg_age )
```

**SQL (PostgreSQL):**
```sql
SELECT country, AVG(age) AS avg_age FROM users GROUP BY country
```

### Multiple Aggregations

**ASQL:**
```asql
from sales group by region ( 
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
from sales group by region, month ( sum(amount) as revenue )
```

**SQL (PostgreSQL):**
```sql
SELECT region, month, SUM(amount) AS revenue FROM sales GROUP BY region, month
```

### GROUP BY with WHERE

**ASQL:**
```asql
from sales where year == 2024 group by region ( sum(amount) as revenue )
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
from sales group by region (
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
from users sort name
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users ORDER BY name ASC
```

### SORT Descending

**ASQL:**
```asql
from users sort -total_users
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users ORDER BY total_users DESC
```

### Multiple Sort Columns

**ASQL:**
```asql
from users sort -total_users, name
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users ORDER BY total_users DESC, name ASC
```

### TAKE/LIMIT

**ASQL:**
```asql
from users take 10
```

**SQL (PostgreSQL):**
```sql
SELECT * FROM users LIMIT 10
```

### GROUP BY + SORT

**ASQL:**
```asql
from users group by country ( # as total_users ) sort -total_users
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
sort -total_users 
take 10
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

---

## Derived Columns

### Simple DERIVE

**ASQL:**
```asql
from users derive age as age
```

**SQL (PostgreSQL):**
```sql
SELECT *, age AS age FROM users
```

### DERIVE with WHERE

**ASQL:**
```asql
from users where status == "active" derive age as age
```

**SQL (PostgreSQL):**
```sql
SELECT *, age AS age FROM users WHERE status = 'active'
```

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
sort -revenue
take 20
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
sort -total_users
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
sort -total_revenue
take 10
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

You can try these examples using the ASQL compiler:

```python
from asql import compile

asql_query = """
from users 
where status == "active" 
group by country ( # as total_users ) 
sort -total_users 
take 10
"""

sql = compile(asql_query, dialect="postgres")
print(sql)
```

Or use the [Interactive Playground](#interactive-playground) to experiment with queries in your browser!
