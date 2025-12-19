# ASQL + Spark/Databricks: Feature Analysis & Integration Opportunities

## Summary

This document analyzes Apache Spark and Databricks to identify:
1. **Popular features** that data engineers love
2. **Comparisons** with ASQL syntax and capabilities  
3. **Potential integrations** or features ASQL could learn from
4. **Dialect support** considerations for Spark SQL

Spark represents one of the most important execution targets for modern analytics. Understanding its strengths helps inform ASQL's design and ensures we can compile to Spark SQL effectively.

---

## 1. Spark's Biggest Wins

### 1.1 The Pipe Syntax (Spark 4.0)

**This is huge for ASQL validation.** Apache Spark 4.0 introduced the `|>` pipe syntax, which is remarkably similar to ASQL's pipeline approach:

```sql
-- Traditional SQL (nested, hard to read)
SELECT c_count, COUNT(*) AS custdist
FROM (
  SELECT c_custkey, COUNT(o_orderkey) AS c_count
  FROM customer
  LEFT OUTER JOIN orders ON c_custkey = o_custkey
    AND o_comment NOT LIKE '%unusual%packages%'
  GROUP BY c_custkey
) AS c_orders
GROUP BY c_count
ORDER BY custdist DESC, c_count DESC;

-- Spark 4.0 Pipe Syntax
FROM customer
|> LEFT OUTER JOIN orders ON c_custkey = o_custkey
   AND o_comment NOT LIKE '%unusual%packages%'
|> AGGREGATE COUNT(o_orderkey) AS c_count
   GROUP BY c_custkey
|> AGGREGATE COUNT(*) AS custdist
   GROUP BY c_count
|> ORDER BY custdist DESC, c_count DESC;
```

**ASQL equivalent:**
```asql
from customer
&? orders on c_custkey = o_custkey and o_comment not matches '%unusual%packages%'
group by c_custkey (count(o_orderkey) as c_count)
group by c_count (count(*) as custdist)
order by -custdist, -c_count
```

**Key insight:** The industry is moving toward pipeline-style SQL. ASQL is ahead of this curve. When targeting Spark 4.0+, ASQL could potentially compile to native pipe syntax for better readability of generated SQL.

---

### 1.2 Higher-Order Functions on Arrays

Spark's higher-order functions are beloved by data engineers for processing complex nested data:

| Function | What it does | Example |
|----------|--------------|---------|
| `TRANSFORM` | Map over array elements | `TRANSFORM(arr, x -> x * 2)` |
| `FILTER` | Keep elements matching predicate | `FILTER(arr, x -> x > 10)` |
| `REDUCE` | Fold array to single value | `REDUCE(arr, 0, (acc, x) -> acc + x)` |
| `AGGREGATE` | Reduce with final transform | `AGGREGATE(arr, init, merge, finish)` |
| `EXISTS` | Check if any element matches | `EXISTS(arr, x -> x > 100)` |
| `FORALL` | Check if all elements match | `FORALL(arr, x -> x > 0)` |
| `ZIP_WITH` | Combine two arrays element-wise | `ZIP_WITH(a, b, (x, y) -> x + y)` |

**Example - element-wise transformation:**
```sql
SELECT TRANSFORM(array(1, 2, 3), x -> x * 2) AS doubled;
-- Result: [2, 4, 6]

SELECT FILTER(array(5, 10, 15, 20), x -> x >= 10) AS filtered;
-- Result: [10, 15, 20]
```

**ASQL opportunity:** Consider adding array comprehension syntax that compiles to these:

```asql
-- Potential ASQL syntax (not yet implemented)
from orders
select 
  [x * 2 for x in scores] as doubled_scores,
  [x for x in scores if x > 80] as high_scores
```

Or function-based:
```asql
from orders
select
  array_map(scores, x -> x * 2) as doubled_scores,
  array_filter(scores, x -> x > 80) as high_scores
```

**Value:** High. Semi-structured data (JSON, arrays) is increasingly common. These patterns are verbose without higher-order functions.

---

### 1.3 LATERAL VIEW + EXPLODE Pattern

This is Spark's approach to flattening nested data:

```sql
-- Spark SQL
SELECT id, tag
FROM posts
LATERAL VIEW explode(tags) AS tag

-- Multiple arrays (creates cartesian product!)
SELECT id, fruit.type, vegetable.type
FROM store_data
LATERAL VIEW explode(store.fruits) AS fruit
LATERAL VIEW explode(store.vegetables) AS vegetable
```

**ASQL already has `explode`:**
```asql
from posts
explode tags as tag

-- Multiple (be careful - cartesian!)
from store_data
explode store.fruits as fruit
explode store.vegetables as vegetable
```

**Status:** ✅ ASQL's `explode` compiles to dialect-appropriate syntax:
- Spark/Databricks: `LATERAL VIEW explode(...) AS ...`
- Postgres/DuckDB: `CROSS JOIN UNNEST(...) AS ...`
- Snowflake: `CROSS JOIN TABLE(FLATTEN(...))`

**Consideration:** Spark also has `posexplode` which includes the array position:
```sql
SELECT id, pos, tag
FROM posts
LATERAL VIEW posexplode(tags) AS pos, tag
```

**ASQL opportunity:**
```asql
-- Potential syntax
from posts
explode tags as pos, tag with position

-- Or
from posts
explode tags as tag indexed by pos
```

---

### 1.4 Window Functions (No QUALIFY)

**Important for ASQL:** Spark does **not** support the `QUALIFY` clause that Snowflake and BigQuery have. This means ASQL's deduplication must compile to the subquery pattern:

```asql
-- ASQL
from events
per user_id first by -created_at
```

**Compiles to Spark SQL as:**
```sql
SELECT *
FROM (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY user_id 
    ORDER BY created_at DESC
  ) AS row_num
  FROM events
) AS ranked
WHERE row_num = 1
```

**Not this (Snowflake/BigQuery only):**
```sql
SELECT *
FROM events
QUALIFY ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) = 1
```

The ASQL compiler already handles this, but it's worth noting when users ask about Spark support.

---

### 1.5 VARIANT Data Type (Semi-Structured)

Spark 4.0 introduced the VARIANT type for semi-structured data (JSON, XML):

```sql
-- Store any JSON structure
CREATE TABLE events (
  id INT,
  payload VARIANT
);

-- Query nested fields with path syntax
SELECT payload:user:name AS user_name
FROM events
WHERE payload:event_type = 'click'
```

**Comparison with other dialects:**
| Dialect | JSON Access Syntax |
|---------|-------------------|
| Spark | `col:path:to:field` |
| Snowflake | `col:path.to.field` or `col['path']['to']['field']` |
| BigQuery | `col.path.to.field` (STRUCT) or `JSON_VALUE(col, '$.path.to.field')` |
| Postgres | `col->'path'->'to'->'field'` or `col->>'path'` |

**ASQL opportunity:** Consider a unified JSON path syntax that compiles appropriately:

```asql
-- Potential unified syntax
from events
select 
  payload->user->name as user_name,
  payload->items[0]->price as first_item_price
where payload->event_type = 'click'
```

---

## 2. Databricks-Specific Features

### 2.1 Delta Lake Integration

Delta Lake provides ACID transactions, time travel, and CDC capabilities:

**Time Travel:**
```sql
-- Query historical version
SELECT * FROM orders VERSION AS OF 5;
SELECT * FROM orders TIMESTAMP AS OF '2024-01-01';

-- Restore to previous state
RESTORE TABLE orders TO VERSION AS OF 3;

-- View change history
DESCRIBE HISTORY orders;
```

**MERGE INTO (Upserts):**
```sql
MERGE INTO target
USING source
ON target.id = source.id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

**ASQL consideration:** These are operational/DML commands rather than query patterns. ASQL focuses on analytical queries (SELECT), so these are likely out of scope. However, if ASQL ever supports mutations:

```asql
-- Hypothetical syntax (not in scope)
from target
merge source on id = source.id
  when matched then update *
  when not matched then insert *
```

### 2.2 Unity Catalog & Lakehouse Federation

Databricks Unity Catalog enables querying across:
- Delta tables
- External databases (PostgreSQL, MySQL, Snowflake, Redshift, BigQuery)
- Apache Iceberg tables
- Hudi tables

**ASQL relevance:** ASQL's dialect system could potentially output SQL that works with Unity Catalog's federated queries. The unified namespace means a single ASQL query could reference tables from multiple sources.

### 2.3 Materialized Views & Streaming Tables

```sql
-- Create a materialized view
CREATE MATERIALIZED VIEW sales_summary AS
SELECT region, SUM(amount) as total
FROM orders
GROUP BY region;

-- Create a streaming table from a stream
CREATE STREAMING TABLE clean_events AS
SELECT * FROM STREAM(raw_events)
WHERE event_type IS NOT NULL;
```

**ASQL consideration:** These are DDL/materialization patterns. Similar to dbt materializations - ASQL generates the SELECT, the orchestration layer (dbt, Databricks, etc.) handles materialization strategy.

---

## 3. PySpark's Fluent API Patterns

PySpark's DataFrame API is beloved for its method chaining, which inspired ASQL's pipeline approach:

### 3.1 Method Chaining

```python
# PySpark
result = (
    df
    .filter(col("status") == "active")
    .withColumn("total", col("price") * col("quantity"))
    .groupBy("region")
    .agg(sum("total").alias("revenue"))
    .orderBy(desc("revenue"))
    .limit(10)
)
```

**ASQL equivalent:**
```asql
from orders
where status = 'active'
select *, price * quantity as total
group by region (sum(total) as revenue)
order by -revenue
limit 10
```

The mental models are nearly identical. This is intentional - ASQL should feel familiar to PySpark users.

### 3.2 Column Operations

| PySpark | ASQL |
|---------|------|
| `df.select("a", "b")` | `select a, b` |
| `df.filter(col("x") > 10)` | `where x > 10` |
| `df.withColumn("new", expr)` | `select *, expr as new` |
| `df.drop("col")` | `except col` |
| `df.withColumnRenamed("old", "new")` | `rename old as new` |
| `df.orderBy(desc("x"))` | `order by -x` |
| `df.groupBy("x").agg(sum("y"))` | `group by x (sum(y))` |

### 3.3 Join Syntax Comparison

```python
# PySpark
orders.join(customers, orders.customer_id == customers.id, "left")

# With alias
orders.alias("o").join(
    customers.alias("c"), 
    col("o.customer_id") == col("c.id")
)
```

**ASQL:**
```asql
from orders
&? customers on orders.customer_id = customers.id

-- With FK inference (if naming conventions followed)
from orders
select orders.*, orders.customer.name
```

---

## 4. Features to Consider for ASQL

### 4.1 Priority: High

| Feature | Spark/Databricks Pattern | ASQL Status | Recommendation |
|---------|--------------------------|-------------|----------------|
| **Explode with position** | `posexplode(arr)` | `explode` exists | Add `with position` option |
| **Array higher-order functions** | `TRANSFORM`, `FILTER`, `REDUCE` | Not implemented | Add `array_map`, `array_filter` |
| **Approximate aggregates** | `APPROX_COUNT_DISTINCT` | Not implemented | Add as dialect-portable function |
| **Percentiles** | `PERCENTILE_CONT` | Not implemented | Add `percentile(col, 0.95)` |

### 4.2 Priority: Medium

| Feature | Spark/Databricks Pattern | ASQL Status | Recommendation |
|---------|--------------------------|-------------|----------------|
| **JSON path access** | `col:path:to:field` | Uses dialect-specific | Consider unified syntax |
| **Map functions** | `map_filter`, `map_keys`, `map_values` | Not implemented | Add if map types common |
| **Explode outer** | `explode_outer(arr)` (keeps NULLs) | `explode` only | Add `explode outer` variant |
| **VARIANT/ANY type** | Native semi-structured | Not applicable | Document dialect differences |

### 4.3 Priority: Low (Out of Scope)

| Feature | Reason |
|---------|--------|
| Time travel queries | DML/operational, not analytics |
| MERGE INTO | DML, not SELECT |
| Streaming tables | Orchestration concern |
| Materialized views | DDL/materialization |
| Unity Catalog federation | Infrastructure, not query syntax |

---

## 5. Spark SQL Dialect Support

### 5.1 Current Status

SQLGlot supports Spark SQL as a target dialect. Key considerations:

| SQL Feature | Spark SQL Support | Notes |
|-------------|-------------------|-------|
| QUALIFY | ❌ No | Must use subquery pattern |
| LATERAL VIEW | ✅ Yes | For explode/unnest |
| Higher-order functions | ✅ Yes | TRANSFORM, FILTER, etc. |
| Window functions | ✅ Yes | Full support |
| DATE_TRUNC | ⚠️ Different syntax | Use `date_trunc('month', col)` |
| ILIKE | ❌ No | Use `LOWER(col) LIKE LOWER(...)` |
| SAFE_CAST | ❌ No | Use `TRY_CAST` |
| COALESCE | ✅ Yes | Standard |
| String concat | Use `CONCAT()` | `\|\|` also works |

### 5.2 Date/Time Function Mapping

| ASQL | Spark SQL |
|------|-----------|
| `year(col)` | `DATE_TRUNC('year', col)` or `YEAR(col)` |
| `month(col)` | `DATE_TRUNC('month', col)` |
| `week(col)` | `DATE_TRUNC('week', col)` |
| `day(col)` | `DATE_TRUNC('day', col)` |
| `col + 7 days` | `DATE_ADD(col, 7)` |
| `days(a - b)` | `DATEDIFF(a, b)` |

### 5.3 String Matching

| ASQL | Spark SQL |
|------|-----------|
| `col contains 'x'` | `col LIKE '%x%'` |
| `col icontains 'x'` | `LOWER(col) LIKE LOWER('%x%')` |
| `col starts with 'x'` | `col LIKE 'x%'` |
| `col ends with 'x'` | `col LIKE '%x'` |

---

## 6. What ASQL Can Learn from Spark

### 6.1 Embrace the Pipeline

Spark 4.0's adoption of pipe syntax validates ASQL's design philosophy. The industry is converging on pipeline-based SQL. ASQL is well-positioned.

### 6.2 First-Class Array Support

Semi-structured data is increasingly common. ASQL should:
1. ✅ Keep `explode` (already implemented)
2. 🔶 Add `array_map`, `array_filter` for transformations
3. 🔶 Add `explode outer` to preserve NULL arrays
4. 🔶 Consider unified JSON path syntax

### 6.3 Approximate Aggregates

For large-scale analytics, approximate functions are valuable:
```asql
-- Potential syntax
from events
group by user_id (
  approx_count_distinct(session_id) as sessions,  -- HyperLogLog
  percentile(duration, 0.95) as p95_duration      -- Approximate percentile
)
```

### 6.4 Schema Evolution Awareness

Spark/Delta handle schema evolution gracefully. ASQL's `SELECT *` expansion should be aware that schemas can change. Consider:
- Explicit column lists for stability
- Schema inference from catalog when available
- Graceful handling of missing columns

---

## 7. Documentation: "Coming from Spark"

Similar to `docs/coming-from/pandas.md`, we should create `docs/coming-from/spark.md`:

### Quick Reference

| PySpark DataFrame | Spark SQL | ASQL |
|-------------------|-----------|------|
| `df.filter(col("x") > 10)` | `WHERE x > 10` | `where x > 10` |
| `df.select("a", "b")` | `SELECT a, b` | `select a, b` |
| `df.withColumn("c", expr)` | - | `select *, expr as c` |
| `df.drop("col")` | `SELECT * EXCEPT(col)` | `except col` |
| `df.groupBy("x").agg(sum("y"))` | `GROUP BY x` | `group by x (sum(y))` |
| `df.orderBy(desc("x"))` | `ORDER BY x DESC` | `order by -x` |
| `df.dropDuplicates(["id"])` | (complex) | `per id first by ...` |
| `df.explode("arr")` | `LATERAL VIEW explode(arr)` | `explode arr as elem` |
| `df.join(df2, on="id")` | `JOIN df2 ON id` | `& df2 on id` |
| `df.join(df2, on="id", how="left")` | `LEFT JOIN` | `&? df2 on id` |

---

## 8. Action Items

### Immediate (Dialect Support)
- [x] Ensure ASQL compiles cleanly to Spark SQL via SQLGlot
- [ ] Add tests for Spark-specific patterns (no QUALIFY, LATERAL VIEW)
- [ ] Document dialect differences in generated SQL

### Short-term (Feature Additions)
- [ ] Add `explode outer` variant for NULL preservation
- [ ] Add `approx_count_distinct()` with dialect mapping
- [ ] Add `percentile(col, p)` with dialect mapping

### Medium-term (Array Support)
- [ ] Investigate `array_map()`, `array_filter()` syntax
- [ ] Research unified JSON path access syntax
- [ ] Consider Python-style comprehensions for arrays

### Long-term (Documentation)
- [ ] Create `docs/coming-from/spark.md`
- [ ] Add Spark examples to playground
- [ ] Document Databricks deployment patterns

---

## References

- [Apache Spark 4.0 Release Notes](https://spark.apache.org/releases/spark-release-4-0-0.html)
- [Spark SQL Pipe Syntax](https://spark.apache.org/docs/_site/sql-pipe-syntax.html)
- [Databricks SQL Language Manual](https://docs.databricks.com/sql/language-manual/)
- [Delta Lake Documentation](https://delta.io/)
- [Unity Catalog Overview](https://docs.databricks.com/unity-catalog/)
- [Higher-Order Functions in Spark](https://spark.apache.org/docs/latest/sql-ref-functions-builtin.html)


