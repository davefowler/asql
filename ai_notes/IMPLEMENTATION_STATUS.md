# ASQL Implementation Status - Detailed

**Last Updated**: December 2024  
**Test Status**: ✅ 434 tests (all passing)

---

## Architecture

The ASQL compiler uses a two-stage approach:

### 1. Pre-Parser (`asql/preparser.py`)
Handles structural transformations that differ from SQL:
- FROM-first → SELECT-FROM transformation
- Pipeline operators (`|`) removal
- Aggregate blocks `group by x (...)` → standard SQL
- `stash as` / `set` / `with` → SQL CTEs
- Natural aggregates (`sum amount` → `sum(amount)`)
- Underscore/space normalization (`day of week` → `day_of_week`)
- Window utilities (`per` command, `running_sum`, etc.)
- Date expressions (`N days ago`, `date + N days`, `@2024-01-01`)
- Count shorthand (`#` → `COUNT(*)`)
- Order by `-col` → `col DESC`
- COALESCE operator (`??`)

### 2. ASQL Dialect (`asql/dialect.py`)
SQLGlot dialect extension for expression parsing:
- Tokenizer rules for ASQL-specific tokens
- Parser rules for ASQL expressions
- Generator for SQL output

### 3. Compiler (`asql/compiler.py`)
Main entry point:
- Orchestrates pre-parser and SQLGlot
- Dialect-specific SQL generation
- Error handling and reporting

### 4. Reverse Compiler (`asql/reverse_compiler.py`)
SQL → ASQL translation:
- Converts SQL back to ASQL syntax
- Useful for migration and learning

---

## Implemented Features

### Core Pipeline Operators ✅

```python
# FROM
from users

# WHERE
from users where status == "active"
from users where age >= 18 and email is not null

# SELECT
from users select name, email, created_at

# GROUP BY with block syntax
from users group by country ( # as total, avg(age) as avg_age )

# JOIN
from orders join users on orders.user_id == users.id
from users left join orders on users.id == orders.user_id

# ORDER BY / SORT
from users order by -created_at, name
from users order by -total_users

# LIMIT / TAKE
from users limit 10
from users limit 100
```

### Expressions ✅

```python
# Arithmetic
from sales where amount * quantity > 100
from users select age + 5 as adjusted_age

# COALESCE (??)
from users select name ?? "Unknown" as display_name
from users select a ?? b ?? c ?? "default" as value

# Type casting (::)
from users select created_at::DATE as signup_date
from events select timestamp::TIMESTAMP as event_time

# Comparison
from users where age >= 18 and status != "inactive"
from users where email is not null
from users where status in ("active", "pending")
```

### Date & Time ✅

```python
# Date literals
from orders where order_date >= @2024-01-01

# Relative dates
from orders where created_at >= 7 days ago
from tasks where due_date <= 3 days from now

# Date arithmetic
from orders select order_date + 7 days as estimated_delivery

# Date functions
from events group by year(created_at), month(created_at) ( # as count )
from users select day_of_week(created_at) as dow

# Time since/until patterns
from users select days_since_created_at as account_age
from tasks select days_until_due_date as days_remaining

# Date spine
from date_spine(start = "2024-01-01", end = today(), grain = day)
```

### Window Functions ✅

```python
# per command - deduplication
from orders per customer_id first by -order_date  # Most recent per customer
from orders per customer_id last by order_date    # First order per customer

# per command - ranking
from employees per department rank by -salary
from employees per department dense rank by -salary
from orders per customer_id number by -order_date as order_num

# Standalone ranking (no partition)
from events number by -timestamp
from scores rank by -score

# QUALIFY
from orders select *, row_number() over (partition by customer_id order by -order_date) as rn qualify rn == 1

# DISTINCT ON
from orders distinct on (customer_id) order by customer_id, -order_date

# prior() / next()
from sales order by month select month, revenue, prior(revenue) as prev_month

# Running aggregates
from transactions order by date select running_sum(amount) as cumulative

# Rolling aggregates
from daily_sales order by date select rolling_avg(revenue, 7) as seven_day_avg

# first() / last() with order
from orders select first(order_id order by order_date) as first_order

# arg_max / arg_min
from orders select arg_max(order_id, order_date) as latest_order_id
```

### CTEs (stash as) ✅

```python
# stash as (mid-pipeline CTE)
from users
where status == "active"
stash as active_users
group by country ( # as total )

# Multiple CTEs via stash as chaining
from users where is_premium stash as base
from base group by country ( # as total ) stash as by_country
from by_country select *
from by_country order by -total limit 10
```

### Utility Functions ✅

```python
# safe_divide - returns NULL on divide-by-zero
from metrics select safe_divide(revenue, users) as revenue_per_user

# key - surrogate key generation
from orders select key(user_id, order_id) as order_key
```

---

## Not Implemented

### String Matching
```python
# NOT WORKING
from users where email contains "@gmail.com"
from users where name starts with "John"
from users where email ends with ".com"
```
**Workaround**: Use SQL LIKE directly: `where email like '%@gmail.com%'`

### Conditional Expressions (when)
```python
# NOT WORKING
from users select when status is "active" then 1 otherwise 0 as active_flag
```
**Workaround**: Use SQL CASE: `case when status = 'active' then 1 else 0 end`

### Natural Language Aggregates
```python
# NOT WORKING
# of Users by country
Sum of revenue by region
```
**Workaround**: Use explicit: `from users group by country ( # as total )`

### Column Operators
```python
# NOT WORKING
from users except email, phone
from users rename id as user_id
from users prefix user_
```
**Workaround**: Explicitly list columns in SELECT

### Deduplicate Operator
```python
# NOT WORKING
from events deduplicate by user_id order by -created_at
```
**Workaround**: Use `per user_id first by -created_at`

### Pivot/Unpivot
```python
# NOT WORKING
from sales pivot amount by category
```
**Workaround**: Write SQL pivot queries directly

### Fill/Gap Filling
```python
# NOT WORKING
from orders group by month(created_at) ( sum(amount) as revenue ) fill month
```
**Workaround**: Join with date_spine manually

### Safe Cast
```python
# NOT WORKING
from users select value::integer? as safe_value
```
**Workaround**: Use database-specific TRY_CAST/SAFE_CAST

---

## Test Files

| File | Tests | Coverage |
|------|-------|----------|
| test_arithmetic.py | 16 | Arithmetic operators |
| test_basic.py | 2 | Import and setup |
| test_cast.py | 14 | Type casting |
| test_coalesce.py | 6 | COALESCE operator |
| test_code_quality.py | 7 | Code quality checks |
| test_compiler.py | 37 | Core compilation |
| test_comprehensive.py | 55 | Comprehensive queries |
| test_dialect.py | 36 | ASQL dialect |
| test_edge_cases.py | 30 | Boundary conditions |
| test_error_messages.py | 10 | Error handling |
| test_example_datasets.py | 18 | Real-world patterns |
| test_fivetran_examples.py | 10 | Fivetran query patterns |
| test_fivetran_examples_compilation.py | 38 | Compilation tests |
| test_integration.py | 14 | SQLGlot integration |
| test_join.py | 12 | JOIN operations |
| test_pipeline_cte.py | 8 | Pipeline/CTE handling |
| test_preparser.py | 43 | Pre-parser transformations |
| test_reverse_translation.py | 14 | SQL→ASQL |
| test_store_as.py | 8 | stash as functionality |
| test_window_utils.py | 41 | Window functions |
| test_with_cte.py | 7 | WITH CTEs |

**Total**: 434 tests

---

## File Structure

```
asql/
├── __init__.py          # Public API (compile, reverse_compile)
├── preparser.py         # ASQL structural transformations (~1200 lines)
├── dialect.py           # SQLGlot ASQL dialect (~100 lines)
├── compiler.py          # Main compiler (~150 lines)
├── reverse_compiler.py  # SQL→ASQL translation (~200 lines)
└── errors.py            # Error classes (~50 lines)

tests/
├── __init__.py
├── fixtures.py          # Shared test data
└── test_*.py           # 21 test files
```
