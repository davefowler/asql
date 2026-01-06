# Visual Example: CTE vs Expression Substitution

## Example Query

```asql
from order_items
  select
    unit_price * (1 - discount) as discount_price,
    discount_price * quantity as total_price,
    total_price * (1 + tax_rate) as taxed_price
  where taxed_price > 100
```

## Current CTE Approach

### Step 1: Dependency Analysis
```
discount_price: no dependencies → Group 1
total_price: depends on discount_price → Group 2  
taxed_price: depends on total_price → Group 3
```

### Step 2: CTE Generation

**CTE 0 (_step0):**
```sql
SELECT unit_price * (1 - discount) AS discount_price
FROM order_items
```

**CTE 1 (_step1):**
```sql
SELECT *, discount_price * quantity AS total_price
FROM _step0
```

**CTE 2 (_step2):**
```sql
SELECT *, total_price * (1 + tax_rate) AS taxed_price
FROM _step1
```

**Final SELECT:**
```sql
SELECT * FROM _step2 WHERE taxed_price > 100
```

**Total: 3 CTEs** (base + 2 dependency levels)

## Alternative: Expression Substitution

### What It Would Generate

```sql
SELECT 
  unit_price * (1 - discount) AS discount_price,
  (unit_price * (1 - discount)) * quantity AS total_price,
  ((unit_price * (1 - discount)) * quantity) * (1 + tax_rate) AS taxed_price
FROM order_items
WHERE ((unit_price * (1 - discount)) * quantity) * (1 + tax_rate) > 100
```

### Problems

1. **Expression repeated 4 times** in WHERE clause
2. **Hard to read** - nested parentheses
3. **Hard to maintain** - change `unit_price * (1 - discount)` and you must update 4 places
4. **Error-prone** - easy to miss one replacement

## With More Complex Example

```asql
select
  (price * (1 - discount) * quantity * (1 + tax_rate)) as total,
  total * 0.1 as fee,
  total + fee as final_total
```

### CTE Approach (3 CTEs)
```sql
WITH _step0 AS (
  SELECT (price * (1 - discount) * quantity * (1 + tax_rate)) AS total
  FROM ...
),
_step1 AS (
  SELECT *, total * 0.1 AS fee
  FROM _step0
),
_step2 AS (
  SELECT *, total + fee AS final_total
  FROM _step1
)
SELECT * FROM _step2
```

**Clean, readable, maintainable.**

### Expression Substitution
```sql
SELECT 
  (price * (1 - discount) * quantity * (1 + tax_rate)) AS total,
  (price * (1 - discount) * quantity * (1 + tax_rate)) * 0.1 AS fee,
  (price * (1 - discount) * quantity * (1 + tax_rate)) + 
    ((price * (1 - discount) * quantity * (1 + tax_rate)) * 0.1) AS final_total
FROM ...
```

**Messy, hard to read, error-prone.**

## When Expression Substitution Might Be OK

For **very simple** cases:
```asql
select max(amount) as m, avg(amount/m) as avg_ratio
```

Substitution:
```sql
SELECT max(amount) AS m, avg(amount/max(amount)) AS avg_ratio
```

This is fine! But the current implementation doesn't distinguish simple vs complex.

## Summary

- **CTEs**: Better for maintainability, readability, complex expressions
- **Substitution**: Simpler, faster, but breaks down with complexity
- **Current choice**: CTEs for consistency and correctness
