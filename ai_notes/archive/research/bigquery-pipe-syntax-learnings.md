# ASQL + BigQuery Pipe Syntax: Learning from Google's Pipeline SQL

## Summary

In October 2024, Google introduced pipe syntax for BigQuery - a major validation of ASQL's core design philosophy. BigQuery pipe syntax allows SQL queries to be written in a linear, pipeline style using the `|>` operator, starting with `FROM` and chaining operations sequentially.

This document analyzes BigQuery's pipe syntax, comparing it to ASQL's approach and identifying learnings.

**Key insight:** Google independently arrived at many of the same conclusions as ASQL - FROM-first, pipeline-based, with clear separation of operations. This is a significant validation of ASQL's design philosophy from one of the world's largest data platforms.

---

## Timeline & Context

- **October 2024**: BigQuery pipe syntax introduced (preview)
- **February 2025**: Available to all BigQuery users by default
- **Current status**: Widely available, no GA announcement yet

ASQL predates BigQuery pipe syntax, making this convergent evolution rather than copying. Both identified the same pain points in traditional SQL.

---

## BigQuery Pipe Syntax Overview

### Basic Structure

BigQuery pipe syntax uses `|>` to chain operations:

```sql
FROM orders
|> WHERE status = 'completed'
|> SELECT order_id, customer_id, total_amount
|> ORDER BY total_amount DESC
|> LIMIT 10
```

Compare to traditional SQL:
```sql
SELECT order_id, customer_id, total_amount
FROM orders
WHERE status = 'completed'
ORDER BY total_amount DESC
LIMIT 10
```

### Key Characteristics

1. **FROM-first**: Queries start with the data source
2. **Linear flow**: Operations applied in reading order
3. **Flexible ordering**: Clauses can appear in any order
4. **Mixable**: Can combine with standard SQL subqueries

---

## Operator Comparison

### 1. WHERE ✅ Direct Equivalent

#### BigQuery Pipe
```sql
FROM orders
|> WHERE status = 'completed'
```

#### ASQL
```asql
from orders
where status = 'completed'
```

#### Comparison
Identical semantics. Both filter rows at the pipeline stage.

---

### 2. SELECT ✅ Similar But Different Philosophy

#### BigQuery Pipe
```sql
FROM employees
|> SELECT name, salary, department
```

#### ASQL
```asql
from employees
select name, salary, department
```

**Key difference:** ASQL defaults to `SELECT *` if no select is specified, while BigQuery pipe requires explicit SELECT.

---

### 3. EXTEND (Add Columns) 🔶 ASQL Difference

#### BigQuery Pipe
The `EXTEND` operator adds new columns while keeping existing ones:

```sql
FROM sales
|> EXTEND revenue - cost AS profit
|> EXTEND profit / revenue AS margin
```

This is **additive** - it keeps all original columns plus new ones.

#### ASQL
ASQL uses `select *, expression as col`:

```asql
from sales
select *, 
  revenue - cost as profit,
  profit / revenue as margin  -- Note: This won't work (no column reuse)
```

#### Key Insight
BigQuery's `EXTEND` is cleaner for adding columns incrementally. Each EXTEND can reference columns added by previous EXTENDs in the same pipeline.

**ASQL Enhancement Opportunity:**
```asql
# Hypothetical - not current syntax
from sales
extend revenue - cost as profit
extend profit / revenue as margin
```

Or simply allow column reuse in SELECT (like DuckDB).

---

### 4. SET (Modify Columns) 🔶 Not in ASQL

#### BigQuery Pipe
`SET` modifies existing column values:

```sql
FROM products
|> SET price = price * 1.10  -- 10% increase
|> SET name = UPPER(name)
```

#### ASQL
ASQL doesn't have a direct `SET`. You'd use:

```asql
from products
select *, 
  price * 1.10 as price,  -- requires EXCLUDE
  upper(name) as name
```

But this is awkward because you're "replacing" columns.

#### Key Insight
`SET` is semantically clearer than "select all except this column, plus a new version of it."

**ASQL already proposed this in dbt-macros document as `replace`:**
```asql
from products
replace price * 1.10 as price, upper(name) as name
```

---

### 5. DROP (Remove Columns) ✅ ASQL Has `except`

#### BigQuery Pipe
```sql
FROM employees
|> DROP social_security_number, internal_notes
```

#### ASQL
```asql
from employees
except social_security_number, internal_notes
```

#### Comparison
Identical semantics. Different keyword (`DROP` vs `except`).

**Note:** BigQuery also supports `SELECT * EXCEPT(col)` in standard SQL, which ASQL also compiles to.

---

### 6. RENAME ✅ ASQL Has `rename`

#### BigQuery Pipe
```sql
FROM customers
|> RENAME cust_id AS customer_id, cust_name AS customer_name
```

#### ASQL
```asql
from customers
rename cust_id as customer_id, cust_name as customer_name
```

#### Comparison
Identical! ASQL and BigQuery converged on the same syntax.

---

### 7. AGGREGATE ✅ Different Syntax, Same Concept

#### BigQuery Pipe
```sql
FROM orders
|> AGGREGATE 
     SUM(total) AS revenue,
     COUNT(*) AS order_count
   GROUP BY region, EXTRACT(YEAR FROM order_date) AS year
```

#### ASQL
```asql
from orders
group by region, year(order_date) as year (
  sum(total) as revenue,
  count(*) as order_count
)
```

#### Comparison
Both separate aggregation from grouping clearly. ASQL uses inline parentheses, BigQuery uses a distinct `AGGREGATE` keyword with `GROUP BY` subclause.

**BigQuery advantage:** The `AGGREGATE` keyword makes intent very explicit.
**ASQL advantage:** More compact, grouping columns and aggregates in one statement.

---

### 8. JOIN ✅ Same Concept

#### BigQuery Pipe
```sql
FROM orders
|> LEFT JOIN customers ON orders.customer_id = customers.id
|> LEFT JOIN products ON orders.product_id = products.id
```

#### ASQL
```asql
from orders
left join customers on orders.customer_id = customers.id
left join products on orders.product_id = products.id
```

#### Comparison
Essentially identical. Both support the same join types.

---

### 9. ORDER BY / LIMIT / DISTINCT ✅ Identical

#### BigQuery Pipe
```sql
FROM products
|> DISTINCT
|> ORDER BY price DESC
|> LIMIT 10
```

#### ASQL
```asql
from products
distinct
order by -price
limit 10
```

#### Comparison
Nearly identical. ASQL uses `-price` for descending, BigQuery uses `price DESC`.

---

### 10. TABLESAMPLE ✅ Both Support Sampling

#### BigQuery Pipe
```sql
FROM large_table
|> TABLESAMPLE SYSTEM (10 PERCENT)
```

#### ASQL
```asql
from large_table
sample 10%
```

#### Comparison
ASQL is slightly more concise. Both achieve the same result.

---

### 11. Window Functions with EXTEND

#### BigQuery Pipe
```sql
FROM sales
|> EXTEND 
     SUM(revenue) OVER (PARTITION BY region ORDER BY date) AS cumulative_revenue,
     ROW_NUMBER() OVER (PARTITION BY region ORDER BY revenue DESC) AS rank
```

#### ASQL
```asql
from sales
select *,
  running_sum(revenue by region order by date) as cumulative_revenue,
  row_number() over (partition by region order by revenue desc) as rank
```

ASQL also has shortcuts for common patterns:
```asql
from employees
per department first by -salary  -- top earner per dept
```

#### Comparison
BigQuery's `EXTEND` is clean for adding window columns. ASQL has higher-level abstractions like `running_sum()` and `per ... first by`.

---

### 12. PIVOT / UNPIVOT ✅ Both Support

#### BigQuery Pipe
```sql
FROM sales_data
|> PIVOT(SUM(sales) FOR quarter IN ('Q1', 'Q2', 'Q3', 'Q4'))
```

```sql
FROM quarterly_data
|> UNPIVOT(sales FOR quarter IN (Q1, Q2, Q3, Q4))
```

#### ASQL
```asql
from sales_data
pivot sum(sales) by quarter values ('Q1', 'Q2', 'Q3', 'Q4')

from quarterly_data
unpivot q1, q2, q3, q4 into quarter, sales
```

#### Comparison
Slightly different syntax, same capabilities.

---

### 13. CALL (Invoke Functions/ML Models) 🔶 Not in ASQL

#### BigQuery Pipe
```sql
FROM reviews
|> SELECT text
|> CALL ML.PREDICT(MODEL `project.sentiment_model`)
```

This allows calling ML models and stored procedures inline in the pipeline.

#### ASQL
Not applicable - ASQL is a query language that compiles to SQL. Stored procedure invocation would be passed through.

#### Takeaway
Interesting for ML workflows but outside ASQL's scope as a query transpiler.

---

### 14. AS (Table Aliasing in Pipeline)

#### BigQuery Pipe
```sql
FROM orders AS o
|> JOIN customers AS c ON o.customer_id = c.id
|> SELECT o.*, c.name
```

#### ASQL
```asql
from orders as o
join customers as c on o.customer_id = c.id
select o.*, c.name
```

#### Comparison
Identical support for table aliases.

---

## Key Differences Summary

| Feature | BigQuery Pipe | ASQL | Notes |
|---------|--------------|------|-------|
| Pipe operator | `\|>` | Newline/indentation (or `\|`) | ASQL uses implicit piping |
| Add columns | `EXTEND` | `select *, expr` | BigQuery's EXTEND is cleaner |
| Modify columns | `SET` | Not directly supported | BigQuery advantage |
| Remove columns | `DROP` | `except` | Same semantics |
| Rename columns | `RENAME` | `rename` | Identical |
| Aggregation | `AGGREGATE ... GROUP BY` | `group by col (agg)` | Different syntax, same concept |
| Default select | Explicit required | `SELECT *` implied | ASQL less verbose |
| Column reuse | Via `EXTEND` chaining | Not supported | BigQuery advantage |
| Descending order | `ORDER BY col DESC` | `order by -col` | ASQL more concise |

---

## What ASQL Can Learn from BigQuery Pipe Syntax

### ✅ Validation of ASQL's Core Design

BigQuery pipe syntax validates these ASQL design choices:
- FROM-first query structure
- Pipeline/chain-based transformations
- Separation of operations into distinct steps
- Column exclusion/renaming as first-class operations

### 🔶 High-Value Improvements to Consider

| Feature | Description | Value |
|---------|-------------|-------|
| **EXTEND keyword** | Explicit "add columns" operation | High - clearer than `select *, expr` |
| **SET keyword** | Explicit "modify columns" operation | High - clearer than column replacement |
| **Column reuse in pipeline** | Reference earlier-defined columns | Very High - DuckDB also has this |

### 🔷 Medium-Value Improvements

| Feature | Description | Value |
|---------|-------------|-------|
| **AGGREGATE keyword** | Explicit aggregation operator | Medium - ASQL inline syntax works |
| **Explicit `\|>` operator** | Visible pipeline operator | Low - ASQL supports `\|` optionally |

---

## Transpiling to BigQuery

When ASQL targets BigQuery, we could:

1. **Emit pipe syntax** for readability (if enabled)
2. **Use native operators** like TABLESAMPLE, PIVOT, QUALIFY
3. **Preserve FROM-first** structure in output

### Example Translation

ASQL:
```asql
from orders
where status = 'completed'
except internal_notes
rename cust_id as customer_id
group by region (
  sum(total) as revenue,
  count(*) as orders
)
order by -revenue
limit 10
```

Could emit BigQuery pipe syntax:
```sql
FROM orders
|> WHERE status = 'completed'
|> DROP internal_notes
|> RENAME cust_id AS customer_id
|> AGGREGATE SUM(total) AS revenue, COUNT(*) AS orders
   GROUP BY region
|> ORDER BY revenue DESC
|> LIMIT 10
```

Or standard SQL (current behavior):
```sql
SELECT region, SUM(total) AS revenue, COUNT(*) AS orders
FROM orders
WHERE status = 'completed'
GROUP BY region
ORDER BY revenue DESC
LIMIT 10
```

---

## Key Insight: Industry Convergence

BigQuery pipe syntax represents **industry validation** of ASQL's approach:

1. **Google engineers independently concluded** that FROM-first, pipeline SQL is better
2. **Major cloud vendor adoption** legitimizes this query style
3. **Syntax similarity** means ASQL users can easily read BigQuery pipe syntax and vice versa

This is not just convergent evolution - it's evidence that the traditional SELECT-first SQL syntax has real usability problems that multiple teams are solving in similar ways.

---

## Implementation Priority

Based on BigQuery's innovations:

| Priority | Feature | Notes |
|----------|---------|-------|
| P1 | Column reuse (like DuckDB + BQ EXTEND) | Major pain point |
| P2 | `extend` keyword | Cleaner than `select *, expr` |
| P2 | `set`/`replace` keyword | Cleaner column modification |
| P3 | BigQuery pipe syntax output option | For readability when targeting BQ |
| P4 | Explicit `\|>` operator support | Low priority, `\|` already optional |

---

## Conclusion

BigQuery pipe syntax and ASQL are remarkably similar, having independently identified the same SQL pain points:

- **FROM should come first**
- **Operations should flow linearly**  
- **Column manipulation needs first-class syntax**
- **Aggregation should be explicit and separate**

The main areas where BigQuery pipe syntax offers inspiration:
1. **EXTEND** for adding columns (vs `select *, expr`)
2. **SET** for modifying columns (vs column replacement tricks)
3. **Column reuse** across pipeline stages

ASQL's advantages:
1. **Multi-dialect transpilation** (BigQuery pipe only works in BigQuery)
2. **Higher-level abstractions** (`per ... first by`, `running_sum()`, etc.)
3. **More concise syntax** (implicit `select *`, `-col` for descending)

The convergence validates ASQL's mission: **SQL can be better, and the industry is moving in this direction.**
