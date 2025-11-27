# Unhandled SQL Functions in ASQL

This document lists SQL functions and constructs that appear in the Fivetran dbt examples but are not yet properly converted to clean ASQL syntax by the reverse compiler.

**Last Updated**: After analyzing 60 Fivetran dbt examples

---

## Summary

Currently handled:
- ✅ `CAST(... AS ...)` → `::` syntax
- ✅ `COALESCE(...)` → `||` operator
- ✅ **CASE statements** → DuckDB/Spark-style `case expr when value then result` syntax
- ✅ Basic aggregations (`SUM`, `AVG`, `COUNT`, `MIN`, `MAX`)

Not yet handled (in order of frequency in examples):
1. **Window functions** (`ROW_NUMBER`: 13, `RANK`: 1, `LEAD`: 1, `LAG`: 1) - Very common
2. **Date functions** (`DATEADD`: 12, `DATE_TRUNC`: 5, `DATEDIFF`: 4) - Common
3. **String functions** (`REPLACE`: 11, `SUBSTRING`: 4, `CONCAT`: 3, `STRING_AGG`: 3) - Common
4. **Comparison functions** (`GREATEST`: 5, `LEAST`: 5) - Moderate
5. **NULL handling** (`NULLIF`: 4) - Less common

**Note**: `COALESCE` (58 occurrences), `CAST` (34 occurrences), and `CASE` (70 occurrences) are now handled ✅

---

## 1. CASE Statements

**Current Status**: ✅ **IMPLEMENTED** - Converts to DuckDB/Spark-style syntax

**SQL Example (Searched CASE)**:
```sql
SELECT 
    CASE 
        WHEN status = 'active' THEN 1 
        WHEN status = 'pending' THEN 0 
        ELSE -1 
    END as status_code
FROM users
```

**ASQL Syntax (DuckDB/Spark-style)**:
```asql
from users
  select 
    case
      when status == "active" then 1
      when status == "pending" then 0
      else -1
    end as status_code
```

**SQL Example (Simple CASE)**:
```sql
SELECT 
    CASE status
        WHEN 'active' THEN 1 
        WHEN 'pending' THEN 0 
        ELSE -1 
    END as status_code
FROM users
```

**ASQL Syntax (DuckDB/Spark-style)**:
```asql
from users
  select 
    case status
      when "active" then 1
      when "pending" then 0
      else -1
    end as status_code
```

**Design Decision**: Using DuckDB/Spark-style syntax (`case expr when value then result`) which is cleaner than SQL-standard `CASE WHEN expr = value THEN result` because:
- More concise - avoids repeating the expression
- More readable - expression appears once at the top
- Familiar to users of DuckDB and Spark SQL

**Frequency**: **70 occurrences** across examples (most common construct - now handled ✅)

---

## 2. Window Functions

### 2.1 ROW_NUMBER()

**Current Status**: ❌ Not converted - stays as `ROW_NUMBER() OVER (...)`

**SQL Example**:
```sql
SELECT 
    ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY created_at DESC) as row_num
FROM orders
```

**Proposed ASQL Syntax**:
```asql
from orders
  select row_number() over (partition by customer_id order by -created_at) as row_num
```

**Alternative (more ASQL-like)**:
```asql
from orders
  partition by customer_id
  order by -created_at
  select row_number() as row_num
```

**Recommendation**: Keep `row_number() over (...)` syntax for familiarity, but ensure proper conversion

**Frequency**: ~15 occurrences

---

### 2.2 RANK() / DENSE_RANK()

**Current Status**: ❌ Not converted

**SQL Example**:
```sql
SELECT RANK() OVER (PARTITION BY department ORDER BY salary DESC) as salary_rank
FROM employees
```

**Proposed ASQL Syntax**:
```asql
from employees
  select rank() over (partition by department order by -salary) as salary_rank
```

**Frequency**: ~5 occurrences

---

### 2.3 LEAD() / LAG()

**Current Status**: ❌ Not converted

**SQL Example**:
```sql
SELECT 
    date,
    LAG(amount) OVER (ORDER BY date) as prev_amount,
    LEAD(amount) OVER (ORDER BY date) as next_amount
FROM transactions
```

**Proposed ASQL Syntax**:
```asql
from transactions
  order by date
  select 
    date,
    lag(amount) as prev_amount,
    lead(amount) as next_amount
```

**Frequency**: ~8 occurrences

---

## 3. Date Functions

### 3.1 DATEDIFF()

**Current Status**: ❌ Not converted - stays as `DATEDIFF()`

**SQL Example**:
```sql
SELECT DATEDIFF(day, start_date, end_date) as days_between
FROM events
```

**Proposed ASQL Syntax**:
```asql
from events
  select days(end_date - start_date) as days_between
```

**Alternative**:
```asql
from events
  select datediff("day", start_date, end_date) as days_between
```

**Recommendation**: Use `days()`, `months()`, `years()` functions for cleaner syntax

**Frequency**: ~12 occurrences

---

### 3.2 DATEADD() / DATE_ADD()

**Current Status**: ⚠️ Partially converted - becomes `DATE_ADD()` but not clean ASQL

**SQL Example**:
```sql
SELECT DATEADD(day, 7, order_date) as delivery_date
FROM orders
```

**Proposed ASQL Syntax**:
```asql
from orders
  select order_date + days(7) as delivery_date
```

**Alternative**:
```asql
from orders
  select order_date + 7 days as delivery_date
```

**Recommendation**: Use arithmetic with date units: `date + days(7)` or `date + 7 days`

**Frequency**: ~8 occurrences

---

### 3.3 DATE_TRUNC()

**Current Status**: ⚠️ Partially converted - becomes `TIMESTAMP_TRUNC()` but not clean ASQL

**SQL Example**:
```sql
SELECT DATE_TRUNC('month', created_at) as month_start
FROM users
```

**Proposed ASQL Syntax**:
```asql
from users
  select trunc(created_at, "month") as month_start
```

**Alternative**:
```asql
from users
  select month_start(created_at) as month_start
```

**Recommendation**: Use `trunc(date, unit)` or helper functions like `month_start()`, `week_start()`

**Frequency**: ~10 occurrences

---

## 4. String Functions

### 4.1 CONCAT()

**Current Status**: ❌ Not converted - stays as `CONCAT()`

**SQL Example**:
```sql
SELECT CONCAT(first_name, ' ', last_name) as full_name
FROM users
```

**Proposed ASQL Syntax**:
```asql
from users
  select first_name + " " + last_name as full_name
```

**Alternative**:
```asql
from users
  select first_name || " " || last_name as full_name
```

**Recommendation**: Use `+` operator for string concatenation (more intuitive than `||`)

**Frequency**: ~6 occurrences

---

### 4.2 STRING_AGG() / GROUP_CONCAT()

**Current Status**: ⚠️ Partially converted - becomes `GROUP_CONCAT()` but not clean ASQL

**SQL Example**:
```sql
SELECT 
    customer_id,
    STRING_AGG(product_name, ', ') as products
FROM orders
GROUP BY customer_id
```

**Proposed ASQL Syntax**:
```asql
from orders
  group by customer_id (
    string_agg(product_name, ", ") as products
  )
```

**Alternative**:
```asql
from orders
  group by customer_id (
    join(product_name, ", ") as products
  )
```

**Recommendation**: Use `string_agg(column, separator)` or `join(column, separator)`

**Frequency**: ~4 occurrences

---

### 4.3 SUBSTRING()

**Current Status**: ❌ Not converted - stays as `SUBSTRING()`

**SQL Example**:
```sql
SELECT SUBSTRING(email, 1, 5) as email_prefix
FROM users
```

**Proposed ASQL Syntax**:
```asql
from users
  select substring(email, 1, 5) as email_prefix
```

**Alternative**:
```asql
from users
  select email[1:5] as email_prefix
```

**Recommendation**: Keep `substring()` function (familiar) or add slice syntax `[start:end]`

**Frequency**: ~3 occurrences

---

### 4.4 REPLACE()

**Current Status**: ❌ Not converted - stays as `REPLACE()`

**SQL Example**:
```sql
SELECT REPLACE(description, 'old', 'new') as updated_desc
FROM products
```

**Proposed ASQL Syntax**:
```asql
from products
  select replace(description, "old", "new") as updated_desc
```

**Recommendation**: Keep `replace()` function (standard SQL)

**Frequency**: ~5 occurrences

---

## 5. Comparison Functions

### 5.1 GREATEST()

**Current Status**: ❌ Not converted - stays as `GREATEST()`

**SQL Example**:
```sql
SELECT GREATEST(price1, price2, price3) as max_price
FROM products
```

**Proposed ASQL Syntax**:
```asql
from products
  select max(price1, price2, price3) as max_price
```

**Alternative**:
```asql
from products
  select greatest(price1, price2, price3) as max_price
```

**Recommendation**: Use `max()` for multiple values (more intuitive) or keep `greatest()` for familiarity

**Frequency**: ~7 occurrences

---

### 5.2 LEAST()

**Current Status**: ❌ Not converted - stays as `LEAST()`

**SQL Example**:
```sql
SELECT LEAST(start_date, end_date) as earliest_date
FROM events
```

**Proposed ASQL Syntax**:
```asql
from events
  select min(start_date, end_date) as earliest_date
```

**Alternative**:
```asql
from events
  select least(start_date, end_date) as earliest_date
```

**Recommendation**: Use `min()` for multiple values or keep `least()` for familiarity

**Frequency**: ~6 occurrences

---

## 6. NULL Handling

### 6.1 NULLIF()

**Current Status**: ❌ Not converted - stays as `NULLIF()`

**SQL Example**:
```sql
SELECT NULLIF(amount, 0) as amount_or_null
FROM transactions
```

**Proposed ASQL Syntax**:
```asql
from transactions
  select nullif(amount, 0) as amount_or_null
```

**Alternative**:
```asql
from transactions
  select if amount == 0 then null else amount as amount_or_null
```

**Recommendation**: Keep `nullif()` function (standard SQL, concise)

**Frequency**: ~2 occurrences

---

## Implementation Priority

Based on frequency and importance:

1. **High Priority**:
   - **CASE statements** (70 occurrences - most common, critical for business logic)
   - Window functions (`ROW_NUMBER`: 13, `RANK`, `LEAD`, `LAG`) - very common
   - Date functions (`DATEADD`: 12, `DATE_TRUNC`: 5, `DATEDIFF`: 4) - common

2. **Medium Priority**:
   - String functions (`CONCAT`, `STRING_AGG`, `SUBSTRING`, `REPLACE`)
   - Comparison functions (`GREATEST`, `LEAST`)

3. **Low Priority**:
   - `NULLIF()` (less common, can use CASE as workaround)

---

## Notes

- All functions currently pass through to SQL unchanged, which works but doesn't provide the clean ASQL syntax
- Some functions (like `DATE_TRUNC`) are converted to dialect-specific equivalents but not to clean ASQL
- Window functions are particularly important as they're used extensively in analytics queries
- CASE statements are essential for conditional logic and appear in almost half of the examples

---

## Related Documentation

- See `docs/spec.md` for ASQL language specification
- See `SQLGLOT_PARSING_ISSUES.md` for parsing issues (now resolved)
- See `asql/reverse_compiler.py` for current implementation

