# ASQL + Spark/Databricks Pipe Syntax: Learning from the Data Platform Giants

## Summary

Apache Spark 4.0 and Databricks introduced SQL pipe syntax using the `|>` operator, enabling pipeline-style queries that mirror ASQL's core design philosophy. This document analyzes Spark's pipe syntax in detail, comparing it to ASQL and identifying learnings.

**Key insight:** Both Google (BigQuery) and Databricks/Apache Spark independently arrived at pipe syntax, representing **industry-wide validation** that FROM-first, pipeline SQL is the future. ASQL predates both implementations.

---

## Timeline & Context

- **Apache Spark 4.0**: Introduced pipe syntax with `|>` operator
- **Databricks Runtime 16.2+**: Native pipe syntax support
- **November 2025**: Proposal to also support single `|` as alternative to `|>` (for Unix/Kusto alignment)

The Spark community's proposal to add `|` (single pipe) as an alternative operator is interesting - ASQL already supports this optionally.

---

## Spark Pipe Syntax Overview

### Basic Structure

Spark pipe syntax starts with `FROM` or `TABLE` and chains operations with `|>`:

```sql
FROM customer
|> LEFT OUTER JOIN orders ON c_custkey = o_custkey
   AND o_comment NOT LIKE '%unusual%packages%'
|> AGGREGATE COUNT(o_orderkey) AS c_count
   GROUP BY c_custkey
|> AGGREGATE COUNT(*) AS custdist
   GROUP BY c_count
|> ORDER BY custdist DESC, c_count DESC
```

Traditional equivalent (TPC-H Query 13):
```sql
SELECT c_count, COUNT(*) AS custdist
FROM (
  SELECT c_custkey, COUNT(o_orderkey) AS c_count
  FROM customer
  LEFT OUTER JOIN orders ON c_custkey = o_custkey
    AND o_comment NOT LIKE '%unusual%packages%'
  GROUP BY c_custkey
) AS c_orders
GROUP BY c_count
ORDER BY custdist DESC, c_count DESC
```

### Key Characteristics

1. **FROM-first**: Queries begin with data source
2. **Linear execution**: Operations applied in reading order
3. **Flexible chaining**: Any pipe operation can follow any other
4. **Mixable**: Standard SQL subqueries can be piped into

---

## Operator Comparison

### 1. WHERE ✅ Direct Equivalent

#### Spark Pipe
```sql
FROM orders
|> WHERE status = 'completed' AND amount > 100
```

#### ASQL
```asql
from orders
where status = 'completed' and amount > 100
```

#### Comparison
Identical semantics. Both filter rows in the pipeline.

---

### 2. SELECT ✅ Same Concept

#### Spark Pipe
```sql
FROM employees
|> SELECT name, salary, department
```

#### ASQL
```asql
from employees
select name, salary, department
```

**Key difference:** ASQL defaults to `SELECT *` if omitted; Spark requires explicit SELECT.

---

### 3. EXTEND (Add Columns) 🔶 ASQL Gap

#### Spark Pipe
The `EXTEND` operator adds new columns while preserving all existing ones:

```sql
FROM sales
|> EXTEND total_price = quantity * price
|> EXTEND profit = total_price - cost
|> EXTEND margin = profit / total_price
```

Each `EXTEND` can reference columns created by previous `EXTEND` operations.

#### ASQL
ASQL uses `select *, expr as col`:

```asql
from sales
select *,
  quantity * price as total_price,
  -- Cannot reference total_price here!
  (quantity * price) - cost as profit
```

**Note:** ASQL doesn't currently support referencing columns defined in the same SELECT.

#### Key Insight
`EXTEND` is significantly cleaner for incremental column creation:
- Explicit "add columns" semantics
- Each step can reference prior steps
- No need for repetitive `select *`

**ASQL Enhancement Opportunity:**
```asql
# Hypothetical syntax
from sales
extend quantity * price as total_price
extend total_price - cost as profit
extend profit / total_price as margin
```

Or column reuse (like DuckDB):
```asql
from sales
select *,
  quantity * price as total_price,
  total_price - cost as profit,  -- Reference earlier column
  profit / total_price as margin
```

---

### 4. SET (Modify Columns) 🔶 ASQL Gap

#### Spark Pipe
The `SET` operator modifies existing column values in-place:

```sql
FROM products
|> SET price = price * 1.10
|> SET name = UPPER(name)
|> SET stock = stock - 1
```

#### ASQL
No direct equivalent. You'd need column replacement tricks:

```asql
from products
select * except price, price * 1.10 as price
```

This is verbose and error-prone.

#### Key Insight
`SET` is the cleanest way to express "update these columns." It's already proposed in ASQL as `replace`:

```asql
from products
replace price * 1.10 as price, upper(name) as name
```

---

### 5. DROP (Remove Columns) ✅ ASQL Has `except`

#### Spark Pipe
```sql
FROM employees
|> DROP ssn, salary_history, internal_notes
```

#### ASQL
```asql
from employees
except ssn, salary_history, internal_notes
```

#### Comparison
Identical semantics, different keyword (`DROP` vs `except`).

---

### 6. RENAME ✅ Both Have It

#### Spark Pipe
```sql
FROM orders
|> RENAME order_date AS purchase_date, cust_id AS customer_id
```

#### ASQL
```asql
from orders
rename order_date as purchase_date, cust_id as customer_id
```

#### Comparison
Identical syntax and semantics!

---

### 7. AGGREGATE ✅ Different Syntax

#### Spark Pipe
```sql
FROM orders
|> AGGREGATE 
     SUM(total) AS revenue,
     COUNT(*) AS order_count,
     AVG(total) AS avg_order
   GROUP BY region, EXTRACT(YEAR FROM order_date) AS year
```

**Notable:** Spark's AGGREGATE supports aliasing the GROUP BY expressions inline.

#### ASQL
```asql
from orders
group by region, year(order_date) as year (
  sum(total) as revenue,
  count(*) as order_count,
  avg(total) as avg_order
)
```

#### Comparison
Both separate aggregation from selection clearly:
- Spark uses `AGGREGATE ... GROUP BY` as distinct subclause
- ASQL uses inline parentheses syntax

**Spark advantage:** `AGGREGATE` keyword makes aggregation very explicit
**ASQL advantage:** More compact single-statement syntax

---

### 8. JOIN ✅ Identical

#### Spark Pipe
```sql
FROM orders
|> LEFT OUTER JOIN customers ON orders.customer_id = customers.id
|> INNER JOIN products ON orders.product_id = products.id
```

#### ASQL
```asql
from orders
left join customers on orders.customer_id = customers.id
join products on orders.product_id = products.id
```

#### Comparison
Same join syntax and semantics.

---

### 9. ORDER BY / LIMIT / DISTINCT ✅ Nearly Identical

#### Spark Pipe
```sql
FROM products
|> DISTINCT
|> ORDER BY price DESC, name ASC
|> LIMIT 10
```

#### ASQL
```asql
from products
distinct
order by -price, name
limit 10
```

#### Comparison
ASQL uses `-col` for descending; Spark uses `col DESC`.

---

### 10. TABLESAMPLE ✅ Both Support

#### Spark Pipe
```sql
FROM large_table
|> TABLESAMPLE (10 PERCENT)

FROM large_table
|> TABLESAMPLE (1000 ROWS)
```

Spark supports both percentage and row count sampling.

#### ASQL
```asql
from large_table
sample 10%

from large_table
sample 1000
```

#### Comparison
Very similar. ASQL also supports `sample N per col` for stratified sampling.

---

### 11. PIVOT / UNPIVOT ✅ Both Support

#### Spark Pipe
```sql
FROM sales
|> PIVOT (SUM(amount) FOR quarter IN ('Q1', 'Q2', 'Q3', 'Q4'))

FROM quarterly_sales
|> UNPIVOT (amount FOR quarter IN (Q1, Q2, Q3, Q4))
```

#### ASQL
```asql
from sales
pivot sum(amount) by quarter values ('Q1', 'Q2', 'Q3', 'Q4')

from quarterly_sales
unpivot Q1, Q2, Q3, Q4 into quarter, amount
```

#### Comparison
Slightly different syntax, same capabilities.

---

### 12. Window Functions

#### Spark Pipe
Window functions typically used with `EXTEND`:

```sql
FROM sales
|> EXTEND running_total = SUM(amount) OVER (PARTITION BY region ORDER BY date)
|> EXTEND rank = ROW_NUMBER() OVER (PARTITION BY region ORDER BY amount DESC)
```

#### ASQL
```asql
from sales
select *,
  running_sum(amount by region order by date) as running_total,
  row_number() over (partition by region order by amount desc) as rank
```

ASQL also has higher-level abstractions:
```asql
from employees
per department first by -salary  -- Top earner per dept
```

---

### 13. No QUALIFY in Spark ⚠️ Important Difference

Spark does **not** support the `QUALIFY` clause. This affects how ASQL compiles window-filtered queries.

#### BigQuery/Snowflake (with QUALIFY)
```sql
SELECT *
FROM employees
QUALIFY ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC) = 1
```

#### Spark (no QUALIFY - needs subquery)
```sql
SELECT *
FROM (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY dept ORDER BY salary DESC
  ) AS rn
  FROM employees
)
WHERE rn = 1
```

#### ASQL
```asql
from employees
per dept first by -salary
```

ASQL automatically compiles to the appropriate pattern based on target dialect.

---

### 14. Proposed `|` Single Pipe Operator

A November 2025 proposal suggests supporting single `|` as alternative to `|>`:

```sql
TABLE t
| SELECT x, y
| WHERE x < 2
```

This aligns with:
- Unix shell pipes
- Kusto (KQL) syntax
- ASQL's optional `|` separator

**ASQL already supports this optionally:**
```asql
from orders | where status = 'completed' | select id, total
```

---

## Key Differences Summary

| Feature | Spark Pipe | ASQL | Notes |
|---------|-----------|------|-------|
| Pipe operator | `\|>` (proposed: `\|`) | Newline (or `\|`) | ASQL uses implicit piping |
| Add columns | `EXTEND` | `select *, expr` | Spark cleaner for incremental |
| Modify columns | `SET` | Not supported | Spark advantage |
| Remove columns | `DROP` | `except` | Same semantics |
| Rename | `RENAME` | `rename` | Identical |
| Aggregation | `AGGREGATE ... GROUP BY` | `group by col (agg)` | Different syntax |
| Default select | Explicit required | `SELECT *` implied | ASQL less verbose |
| Column reuse | Via `EXTEND` chain | Not supported | Spark/DuckDB advantage |
| QUALIFY | ❌ Not supported | ✅ Compiles to subquery | ASQL handles transparently |
| Descending order | `ORDER BY col DESC` | `order by -col` | ASQL more concise |
| Sampling | `TABLESAMPLE (N %)` | `sample N%` | Both support |

---

## What ASQL Can Learn

### ✅ Validation of ASQL's Core Design

Spark's pipe syntax validates these ASQL design choices:
- FROM-first query structure
- Pipeline-based transformations
- Separation of operations into distinct steps
- Column manipulation as first-class operations

### 🔶 High-Value Improvements to Consider

| Feature | Description | Value |
|---------|-------------|-------|
| **EXTEND keyword** | Explicit "add columns" operation | High - cleaner than `select *, expr` |
| **SET keyword** | Explicit "modify columns" operation | High - cleaner than replacement tricks |
| **Column reuse** | Reference earlier-defined columns | Very High - both DuckDB and Spark have this |

### 🔷 Already Covered

| Feature | ASQL Status |
|---------|-------------|
| Optional `\|` operator | ✅ Supported |
| QUALIFY fallback | ✅ Auto-compiles to subquery for Spark |
| TABLESAMPLE | ✅ `sample N%` syntax |
| PIVOT/UNPIVOT | ✅ Supported |

---

## Transpiling to Spark

When ASQL targets Spark, considerations:

1. **No QUALIFY** - Use subquery pattern for window filtering
2. **LATERAL VIEW for explode** - Use Spark's syntax for array flattening
3. **Potential: Emit pipe syntax** - For Spark 4.0+, could output pipe syntax for readability

### Example Translation

ASQL:
```asql
from orders
left join customers on orders.customer_id = customers.id
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

Could emit Spark pipe syntax (future option):
```sql
FROM orders
|> LEFT JOIN customers ON orders.customer_id = customers.id
|> WHERE status = 'completed'
|> DROP internal_notes
|> RENAME cust_id AS customer_id
|> AGGREGATE SUM(total) AS revenue, COUNT(*) AS orders
   GROUP BY region
|> ORDER BY revenue DESC
|> LIMIT 10
```

Current output (standard SQL):
```sql
SELECT region, SUM(total) AS revenue, COUNT(*) AS orders
FROM orders
LEFT JOIN customers ON orders.customer_id = customers.id
WHERE status = 'completed'
GROUP BY region
ORDER BY revenue DESC
LIMIT 10
```

---

## BigQuery vs Spark Pipe Syntax

Both BigQuery and Spark pipe syntax are remarkably similar:

| Feature | BigQuery Pipe | Spark Pipe |
|---------|--------------|------------|
| Operator | `\|>` | `\|>` (proposed: `\|`) |
| EXTEND | ✅ | ✅ |
| SET | ✅ | ✅ |
| DROP | ✅ | ✅ |
| RENAME | ✅ | ✅ |
| AGGREGATE | ✅ | ✅ |
| QUALIFY | ✅ Native | ❌ Use subquery |
| CALL (ML/procedures) | ✅ | Not in pipe context |

**Convergent evolution:** Both platforms independently designed nearly identical pipeline SQL extensions. This is strong evidence that the traditional SELECT-first syntax has real usability problems.

---

## Industry Convergence

Three major platforms now support pipeline-style SQL:

1. **ASQL** (2023+) - Multi-dialect transpiler
2. **BigQuery** (October 2024) - Google Cloud
3. **Spark/Databricks** (Spark 4.0, 2024) - Apache/Databricks

All three converged on:
- FROM-first structure
- `|>` or `|` pipe operator
- EXTEND/SET/DROP/RENAME operations
- AGGREGATE with GROUP BY

**This is not coincidence - it's industry consensus.**

---

## Implementation Priority

Based on Spark/BigQuery innovations:

| Priority | Feature | Notes |
|----------|---------|-------|
| P1 | Column reuse | DuckDB, BigQuery, Spark all have it |
| P2 | `extend` keyword | Cleaner than `select *, expr` |
| P2 | `set`/`replace` keyword | Cleaner column modification |
| P3 | Pipe syntax output option | For Spark 4.0+/BigQuery targeting |
| P4 | Explicit `\|>` support | Low priority, `\|` works |

---

## Conclusion

Spark/Databricks pipe syntax represents the **second major validation** (after BigQuery) of ASQL's core philosophy:

- **FROM should come first**
- **Operations should flow linearly**
- **Column manipulation needs first-class syntax**
- **Aggregation should be explicit**

The fact that Google (BigQuery), Apache Spark, and ASQL all independently arrived at nearly identical solutions proves that pipeline SQL is not just a nice idea - it's **the direction the industry is moving**.

ASQL's key advantages:
1. **Multi-dialect** - Works across Spark, BigQuery, Snowflake, Postgres, etc.
2. **Higher abstractions** - `per ... first by`, `running_sum()`, `sample N per col`
3. **More concise** - Implicit `SELECT *`, `-col` for descending
4. **Predates both** - ASQL was ahead of the curve

The main learnings to adopt:
1. **Column reuse** - Allow referencing earlier-defined columns
2. **EXTEND/SET keywords** - Clearer semantics than `select *, expr`

See also: `ai_notes/spark.md` for broader Spark/Databricks feature analysis beyond pipe syntax.
