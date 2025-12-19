# ASQL + DuckDB: Learning from "Friendly SQL" Extensions

## Summary

DuckDB has pioneered numerous SQL extensions under the banner of "Friendly SQL" - syntax improvements that make SQL more readable, less redundant, and more expressive. Many of these innovations align closely with ASQL's design philosophy.

This document analyzes DuckDB's SQL extensions, noting:
1. **What DuckDB does** - The extension and its syntax
2. **ASQL status** - Whether ASQL implements this or uses it when transpiling to DuckDB
3. **Learnings** - What we can learn or adopt

**Key insight:** DuckDB has validated many of the same pain points ASQL targets. Where our solutions differ, there may be opportunities to learn. Where they align, we can leverage DuckDB's native syntax when transpiling.

---

## DuckDB's "Friendly SQL" Philosophy

DuckDB's approach mirrors ASQL's core beliefs:
- Reduce verbosity and repetition
- Make queries read more naturally
- Provide sensible defaults
- Keep SQL's familiar foundation

> "Friendly SQL is a collection of smaller language features that aim to make SQL more ergonomic and approachable" — DuckDB documentation

---

## Extension Analysis

### 1. FROM-First Syntax ✅ ASQL Core Feature

#### DuckDB
DuckDB allows queries to start with FROM:

```sql
FROM orders
SELECT order_id, customer_id, total_amount
WHERE status = 'completed';
```

#### ASQL Comparison ✅ Core Design
ASQL was designed from the ground up with FROM-first as the default:

```asql
from orders
where status = 'completed'
select order_id, customer_id, total_amount
```

#### Takeaway
DuckDB validates this design choice. When transpiling to DuckDB, ASQL can emit FROM-first SQL directly (though SQLGlot normalizes to SELECT-first by default).

**Transpiling advantage:** DuckDB natively understands FROM-first, so ASQL→DuckDB could preserve this syntax for better readability in generated SQL.

---

### 2. GROUP BY ALL / ORDER BY ALL

#### DuckDB
Automatically groups/orders by all non-aggregated columns:

```sql
SELECT customer_id, product_id, SUM(quantity) AS total
FROM sales
GROUP BY ALL;

SELECT customer_id, order_date, total
FROM orders
ORDER BY ALL;
```

**Key behavior: Expressions are handled correctly!** DuckDB distinguishes between:

| Type | Examples | GROUP BY ALL Behavior |
|------|----------|----------------------|
| **Aggregate functions** | `SUM()`, `COUNT()`, `AVG()`, `MIN()`, `MAX()` | Excluded (these collapse rows) |
| **Scalar functions** | `month()`, `year()`, `UPPER()`, `LENGTH()` | Included (one row in → one row out) |
| **Plain columns** | `customer_id`, `status` | Included |

So this works as expected:

```sql
SELECT month(created_at) AS created_month, SUM(amount) AS total
FROM orders
GROUP BY ALL;
-- Groups by month(created_at), NOT by created_at
```

DuckDB correctly identifies that `SUM(amount)` is the aggregate (don't group by it) while `month(created_at)` is a scalar transformation (do group by it).

#### ASQL Comparison ⚠️ Different Approach
ASQL separates grouping from aggregation using inline syntax:

```asql
from sales
group by customer_id, product_id (sum(quantity) as total)
```

ASQL requires explicit column listing in GROUP BY - we don't have an "ALL" shorthand.

#### Potential Enhancement (Medium Value)
Could add `group by all`:

```asql
from sales
select customer_id, product_id, sum(quantity) as total
group by all  -- auto-detect from select clause
```

**Pros:**
- Less repetition
- Matches DuckDB syntax for transpiling
- Handles expressions correctly (would group by `month(created_at)`, not `created_at`)

**Cons:**
- Implicit behavior can be confusing
- ASQL's inline aggregation syntax already reduces this pain

#### Takeaway
DuckDB's `GROUP BY ALL` is clever but ASQL's inline aggregation approach is arguably cleaner. Lower priority for adoption.

---

### 3. SELECT * EXCLUDE / REPLACE ✅ ASQL Uses This

#### DuckDB
Column exclusion and replacement:

```sql
SELECT * EXCLUDE (city) FROM addresses;
SELECT * REPLACE (LOWER(city) AS city) FROM addresses;
```

#### ASQL Comparison ✅ Already Uses EXCLUDE
ASQL's `except` clause compiles to EXCLUDE for DuckDB/Snowflake:

```asql
from users
except email, phone
```

Compiles to (for DuckDB):
```sql
SELECT * EXCLUDE (email, phone) FROM users
```

ASQL's column override behavior also uses EXCLUDE internally:
```asql
from users
select *, upper(name) as name  -- Override name column
```

Compiles to:
```sql
SELECT * EXCLUDE (name), UPPER(name) AS name FROM users
```

#### ASQL Status ✅ Fully Implemented
- ✅ `except` → Uses EXCLUDE when transpiling to DuckDB/Snowflake
- ✅ `replace col with expr` → Uses EXCLUDE + aliased expression

ASQL's `replace` syntax:

```asql
from users
  replace name with upper(name)

# Chained replacements (comma-separated)
from users
  replace name with upper(name), email with lower(email)

# Or separate statements
from users
  replace name with upper(name)
  replace email with lower(email)
```

Compiles to:
```sql
SELECT * EXCLUDE (name, email), upper(name) AS name, lower(email) AS email FROM users
```

See `docs/spec.md` section 13.1 for full documentation.

---

### 4. COLUMNS Expression (Dynamic Column Selection) 📋 Planned

#### DuckDB
Select columns matching a pattern:

```sql
-- Select columns matching regex
SELECT COLUMNS('.*_id') FROM orders;

-- Apply function to matching columns
SELECT COLUMNS('sales_.*')::DECIMAL(10,2) FROM quarterly_data;

-- With lambda for transformation
SELECT COLUMNS(c -> c LIKE '%_amount')::INT FROM payments;
```

#### ASQL Status: 📋 Planned for Future Implementation
ASQL doesn't currently have pattern-based column selection, but this feature is planned.

**See**: [docs/spec_future.md - Dynamic Column Selection](../../../docs/spec_future.md#dynamic-column-selection-columns-matching-future-consideration)

#### Proposed ASQL Syntax

```asql
from quarterly_data
  select columns matching 'sales_*'

from events
  select columns matching '*_at' as timestamps

from dirty_data
  select columns matching 'amount_*' :: decimal(10,2)
```

**Value:** High - very useful for ETL and wide tables with naming conventions.

---

### 5. Reusable Column Aliases 📋 Planned (High Priority)

#### DuckDB
Reference aliases in the same SELECT and subsequent clauses:

```sql
SELECT
    unit_price * (1 - discount) AS discount_price,
    discount_price * quantity AS total_price,  -- reuses discount_price!
    total_price * (1 + tax_rate) AS taxed_price
FROM order_items
WHERE taxed_price > 100;  -- can filter on derived column!
```

This is **revolutionary** compared to standard SQL, which requires CTEs or subqueries.

#### ASQL Status: 📋 Planned for Future Implementation
ASQL doesn't currently support this, but it's planned as a high-priority feature.

**See**: [docs/spec_future.md - Reusable Column Aliases](../../../docs/spec_future.md#reusable-column-aliases-future-consideration)

#### Proposed ASQL Syntax

```asql
from order_items
  select
    unit_price * (1 - discount) as discount_price,
    discount_price * quantity as total_price,
    total_price * (1 + tax_rate) as taxed_price
  where taxed_price > 100
```

**Implementation approach:**
- DuckDB target: Emit directly (native support)
- Other dialects: Auto-generate CTE chain

**Value:** Very High - addresses a major SQL pain point.

---

### 6. UNION BY NAME

#### DuckDB
Union tables by column name rather than position:

```sql
SELECT * FROM table1
UNION BY NAME
SELECT * FROM table2;
```

Columns are matched by name; missing columns get NULL.

#### ASQL Comparison ⚠️ Not Explicit
ASQL doesn't have a specific syntax for name-based unions. The `union()` function from macros.md was proposed but uses schema alignment, not explicit `BY NAME` syntax.

#### Potential Enhancement
```asql
from union by name(table1, table2, table3)

-- or as an operator
from table1
union by name table2
```

**Value:** Medium - useful for heterogeneous tables.

---

### 7. POSITIONAL JOIN

#### DuckDB
Join tables by row position (like cbind in R):

```sql
SELECT * FROM t1 POSITIONAL JOIN t2;
```

Rows are matched 1:1 by their position. If one table is shorter, NULLs are used.

#### ASQL Comparison ❌ Not Implemented
No equivalent in ASQL.

#### Takeaway
Niche feature for data-frame-style workflows. Low priority for ASQL but could be useful for importing/aligning parallel data sources.

---

### 8. ASOF JOIN 📋 Planned

#### DuckDB
Join on the nearest preceding key (essential for time-series):

```sql
SELECT *
FROM trades
ASOF JOIN quotes
ON trades.symbol = quotes.symbol
AND trades.timestamp >= quotes.timestamp;
```

Gets the most recent quote as of each trade time.

#### ASQL Status: 📋 Planned for Future Implementation
ASQL has `prior()` for LAG within a table, but no ASOF join syntax yet. This is planned.

**See**: [docs/spec_future.md - ASOF JOIN](../../../docs/spec_future.md#asof-join-future-consideration)

#### Proposed ASQL Syntax

```asql
from trades
  asof join quotes on symbol 
    and trades.timestamp >= quotes.timestamp

# Or more ASQL-style:
from trades
  & quotes on symbol asof timestamp  -- implicit >= semantics
```

**Value:** High for time-series analytics (finance, IoT, event streams).

---

### 9. PIVOT / UNPIVOT ✅ Already Implemented

#### DuckDB
Native PIVOT and UNPIVOT statements:

```sql
PIVOT cities
ON year
USING sum(population) AS total, max(population) AS max
GROUP BY country;

UNPIVOT monthly_sales
ON (jan, feb, mar) AS q1
INTO NAME quarter VALUE month_1, month_2, month_3;
```

#### ASQL Comparison ✅ Implemented
ASQL has pivot and unpivot:

```asql
from sales
pivot sum(amount) by category values ('Electronics', 'Clothing', 'Home')

from quarterly
unpivot jan, feb, mar into month, value
```

**Transpiling:** ASQL currently compiles to CASE/WHEN for portability. When targeting DuckDB, we could emit native PIVOT syntax for better performance.

#### Why ASQL Uses CASE/WHEN (Not SQLGlot's Limitation)

This is an **ASQL design choice**, not a SQLGlot limitation. ASQL's preparser (`asql/preparse/pivot.py`) converts `pivot` to CASE/WHEN expressions *before* SQLGlot ever sees it.

**SQLGlot PIVOT support tested:**
| Dialect | Native PIVOT |
|---------|--------------|
| DuckDB | ✅ Yes |
| Snowflake | ✅ Yes |
| BigQuery | ✅ Yes |
| Postgres | ❌ Drops clause! |
| MySQL | ❌ Drops clause! |

SQLGlot passes through PIVOT for dialects that support it, but **silently drops it** for dialects that don't (Postgres, MySQL). It doesn't auto-convert to CASE/WHEN.

**SQLGlot behavior for unsupported syntax:**
| Configuration | Behavior |
|---------------|----------|
| Default | Warns to stderr, **silently drops** (dangerous - wrong results!) |
| `unsupported_level=RAISE` | Throws `UnsupportedError` |
| Never | Converts to equivalent portable SQL |

SQLGlot is a transpiler, not a portability layer - it doesn't rewrite unsupported constructs.

**Why ASQL chose CASE/WHEN:** Guarantees portability across all dialects. If we emitted native PIVOT and relied on SQLGlot, queries would silently break on Postgres/MySQL.

#### Potential Enhancement
Could optimize for DuckDB/Snowflake/BigQuery while maintaining fallback:

1. **Option A**: Add dialect awareness to preparser - emit native PIVOT for supported dialects, CASE/WHEN otherwise
2. **Option B**: Emit native PIVOT always, add compiler step to convert to CASE/WHEN for unsupported dialects

```sql
-- Current ASQL output (portable)
SELECT region,
  SUM(CASE WHEN category = 'A' THEN amount END) AS A,
  SUM(CASE WHEN category = 'B' THEN amount END) AS B
FROM sales GROUP BY region

-- Could emit for DuckDB/Snowflake/BigQuery
PIVOT sales ON category USING SUM(amount) GROUP BY region
```

**Value:** Medium - native PIVOT may be faster, but CASE/WHEN is reliable.

**Tracking:** [GitHub Issue #76](https://github.com/davefowler/asql/issues/76)

---

### 10. QUALIFY Clause ✅ Already Used

#### DuckDB
Filter on window function results without a subquery:

```sql
SELECT name, salary, 
       ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC) as rn
FROM employees
QUALIFY rn <= 3;
```

**Note:** The web search initially said DuckDB doesn't support QUALIFY, but checking the codebase shows ASQL already emits QUALIFY, and DuckDB does support it.

#### ASQL Comparison ✅ Already Implemented
ASQL uses QUALIFY extensively:

- `per ... first by` emits `QUALIFY ROW_NUMBER() = 1`
- `sample N per col` uses QUALIFY
- The `qualify` keyword is directly supported

```asql
from employees
per department first by -salary  -- top earner per dept
```

Compiles to:
```sql
SELECT * FROM employees
QUALIFY ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) = 1
```

---

### 11. SAMPLE Clause ✅ ASQL Implemented

#### DuckDB
Multiple sampling methods:

```sql
SELECT * FROM table USING SAMPLE 10%;
SELECT * FROM table USING SAMPLE 100 ROWS (reservoir);
SELECT * FROM table TABLESAMPLE BERNOULLI(10);
```

#### ASQL Comparison ✅ Implemented
ASQL has `sample`:

```asql
from orders
sample 100              -- random 100 rows

from orders  
sample 10%              -- 10% sample

from orders
sample 100 per category -- stratified
```

**Transpiling opportunity:** When targeting DuckDB, could emit `USING SAMPLE 100 ROWS (reservoir)` instead of `ORDER BY RANDOM() LIMIT 100` for better performance.

---

### 12. List Comprehensions / Lambda Functions 📋 Researched

#### DuckDB
Python-style list transformations:

```sql
SELECT [LOWER(x) FOR x IN strings] AS lowered FROM t;
SELECT [x * 2 FOR x IN numbers IF x > 0] AS doubled FROM t;
SELECT list_transform([1,2,3], x -> x + 1);
```

#### ASQL Status: 📋 Researched - Feasible with Dialect-Aware Handling

**Detailed research:** See [list-comprehensions-research.md](./list-comprehensions-research.md)  
**Spec:** See [docs/spec_future.md - List Comprehensions](../../../docs/spec_future.md#list-comprehensions--array-transformations-future-consideration)

#### Key Findings

**SQLGlot transpilation tested:**

| Dialect | Portable `ARRAY(SELECT...FROM UNNEST(...))` | Works? |
|---------|---------------------------------------------|--------|
| DuckDB | ✅ Passes through | ✅ |
| BigQuery | ✅ Correct output | ✅ |
| Postgres | ✅ Correct output | ✅ |
| Snowflake | ❌ Invalid syntax generated | ❌ |
| MySQL | N/A (no arrays) | ❌ |

**Implementation strategy:**
1. Preparser parses `[expr for var in arr]` syntax
2. For DuckDB: pass through as-is
3. For Postgres/BigQuery: emit `ARRAY(SELECT expr FROM UNNEST(arr) AS var)` - SQLGlot handles these
4. For Snowflake: emit custom `ARRAY_AGG() + FLATTEN` pattern (preparser needs dialect)

**Value:** Medium - useful for nested data structures (JSON, arrays).

---

### 13. String/Array Slicing 🐛 Documented but Broken

#### DuckDB
Python-style slicing syntax:

```sql
SELECT 'DuckDB'[1:4];     -- 'Duck' (1-indexed)
SELECT 'DuckDB'[-3:];     -- 'kDB' (last 3 chars)
SELECT [1,2,3,4,5][2:4];  -- [2,3,4]
SELECT array[::2];        -- every other element
```

#### ASQL Status: 🐛 Documented but Broken for Non-DuckDB

The slice syntax is documented in `docs/spec.md` but **only works for DuckDB**!

**Tracking:** [GitHub Issue #77](https://github.com/davefowler/asql/issues/77)

**Current behavior (broken):**
| Dialect | Output | Valid? |
|---------|--------|--------|
| DuckDB | `email[1 : 5]` | ✅ Native |
| Postgres | `email[1 : 5]` | ❌ Invalid for strings |
| Snowflake | `email[GET_PATH(1, '5')]` | ❌ Wrong! |
| BigQuery | `email[1 : 5]` | ❌ Invalid |

**Fix needed:** Preparser should convert to `SUBSTRING()` for non-DuckDB dialects.

```asql
from products
select name[1:10] as short_name  -- first 10 chars
```

**Value:** Medium - syntactic sugar, but very readable.

---

### 14. Struct Access with Dot Notation ✅ Passes Through

#### DuckDB
Access struct fields naturally:

```sql
SELECT my_struct.field_name FROM table;
SELECT address.city, address.zip FROM customers;
```

#### ASQL Comparison ✅ Passes Through
ASQL doesn't interfere with dot notation for struct access. Standard SQL struct syntax works:

```asql
from customers
select address.city, address.zip
```

---

### 15. DESCRIBE / SUMMARIZE

#### DuckDB
Schema inspection and data profiling:

```sql
DESCRIBE my_table;          -- shows schema
SUMMARIZE my_table;         -- shows statistics (min, max, avg, nulls, etc.)
```

#### ASQL Comparison ❌ Not a Query Language Feature
These are metadata/introspection commands, not query transformations. ASQL focuses on data queries.

#### Takeaway
Could be CLI/tooling features rather than language features. The pandas learnings doc mentioned `describe` as a potential addition.

---

### 16. MAP and STRUCT Literal Syntax

#### DuckDB
Create maps and structs inline:

```sql
SELECT MAP {'key1': 5, 'key2': 43};
SELECT {'name': 'John', 'age': 30} AS person;
```

#### ASQL Comparison ⚠️ Dialect-Specific
ASQL passes through complex type constructors. DuckDB syntax would work when targeting DuckDB.

---

## Summary: What ASQL Can Learn from DuckDB

### ✅ Already Implemented / Used

| DuckDB Feature | ASQL Status |
|----------------|-------------|
| FROM-first syntax | ✅ Core design principle |
| EXCLUDE (column exclusion) | ✅ `except` compiles to EXCLUDE |
| QUALIFY clause | ✅ Used by `per`, `sample per`, etc. |
| SAMPLE clause | ✅ `sample N`, `sample N%`, `sample N per col` |
| PIVOT / UNPIVOT | ✅ Implemented with CASE/WHEN fallback |
| Struct dot notation | ✅ Passes through |

### 🔶 High-Value Opportunities

| DuckDB Feature | Potential ASQL Enhancement | Value |
|----------------|---------------------------|-------|
| **Reusable column aliases** | Allow alias references in same SELECT | **Very High** - major SQL pain point |
| **COLUMNS expression** | Pattern-based column selection | **High** - great for wide tables |
| **ASOF JOIN** | Time-series inexact joins | **High** - essential for time-series |
| **List comprehensions** | Array transformations | Medium - good for nested data |
| **Native PIVOT for DuckDB** | Emit DuckDB PIVOT instead of CASE/WHEN | Medium - performance optimization |

### 🔷 Medium-Value Opportunities

| DuckDB Feature | Notes |
|----------------|-------|
| UNION BY NAME | Useful for heterogeneous schemas |
| String/array slicing | Syntactic sugar |
| GROUP BY ALL | ASQL's inline aggregation may be better |
| REPLACE clause | Current pattern works fine |

### ❌ Low Priority / Not Recommended

| DuckDB Feature | Why Skip |
|----------------|----------|
| POSITIONAL JOIN | Niche use case |
| DESCRIBE/SUMMARIZE | Tooling, not language feature |
| MAP/STRUCT literals | Dialect-specific, pass through |

---

## Transpiling Optimizations

When targeting DuckDB specifically, ASQL could emit DuckDB-native syntax for better readability and performance:

| ASQL Feature | Current Output | Optimized DuckDB Output |
|--------------|----------------|------------------------|
| `except col` | `* EXCEPT(col)` | ✅ Already optimal |
| `sample 100` | `ORDER BY RANDOM() LIMIT 100` | `USING SAMPLE 100 (reservoir)` |
| `sample 10%` | `TABLESAMPLE BERNOULLI(10)` | ✅ Already optimal |
| `pivot ... values` | CASE/WHEN expressions | Native `PIVOT` statement |
| `per ... first by` | QUALIFY ROW_NUMBER() | ✅ Already optimal |

---

## Implementation Priority

Based on value and alignment with ASQL philosophy:

| Priority | Feature | Notes |
|----------|---------|-------|
| P1 | Reusable column aliases | Transformative for complex calculations |
| P1 | ASOF JOIN | High value for time-series users |
| P2 | COLUMNS expression | Pattern-based column selection |
| P2 | Native DuckDB PIVOT | Performance optimization |
| P3 | List comprehensions | Nice for array manipulation |
| P3 | UNION BY NAME | Useful but not critical |
| P4 | String/array slicing | Syntactic sugar |
| P4 | GROUP BY ALL | Lower priority, inline aggregation works |

---

## Key Insight: Convergent Evolution

DuckDB and ASQL have independently arrived at many of the same conclusions about SQL's pain points:

1. **FROM should come first** - Both prioritize this
2. **Column exclusion is essential** - Both support EXCLUDE/except
3. **QUALIFY is better than subqueries** - Both embrace it
4. **Sampling needs better syntax** - Both provide cleaner alternatives
5. **Pivot/unpivot is common enough to deserve syntax** - Both support it

This convergent evolution validates ASQL's design philosophy. Where DuckDB has gone further (reusable aliases, COLUMNS expression, ASOF joins), ASQL should consider adoption.

The key differentiator: **ASQL transpiles to multiple backends**, while DuckDB's extensions only work in DuckDB. ASQL's challenge is implementing these features portably, or gracefully degrading when targeting dialects that don't support them natively.
