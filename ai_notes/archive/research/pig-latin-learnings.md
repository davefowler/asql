# ASQL + Pig Latin: Learning from a Data Flow Language

## Summary

This document analyzes Apache Pig Latin, a high-level data flow language that compiles to MapReduce/Tez jobs. Pig was designed for large-scale data analysis and shares several philosophical similarities with ASQL. For each key concept we examine:

1. **Pig Latin** - How it works in Pig
2. **Relevance to ASQL** - What we can learn or already implement
3. **Potential Enhancement** - Ideas worth considering

**Key insight:** Pig Latin prioritizes readability and expressiveness for data analysts, abstracting away the underlying execution engine. It embraces a "data flow" mental model rather than SQL's declarative set-based model. Many of Pig's innovations align with ASQL's goals.

---

## Core Design Principles

### 1. Named Pipeline Model

#### Pig Latin
Every operation creates a named relation (alias), forming an explicit data flow graph:

```pig
A = LOAD 'data' AS (name:chararray, age:int, gpa:float);
B = FILTER A BY age > 18;
C = GROUP B BY name;
D = FOREACH C GENERATE group, COUNT(B);
STORE D INTO 'output';
```

Each step is traceable. You can `DUMP` or `DESCRIBE` any intermediate relation.

#### ASQL Comparison
ASQL's pipeline model is similar but uses implicit flow with the pipe operator:

```asql
from students
where age > 18
group by name (count(*) as cnt)
```

#### Takeaway
Both approaches have merit:
- Pig's explicit naming is great for debugging complex transformations
- ASQL's implicit flow is more concise for simple queries

**Potential enhancement:** Consider supporting optional named subqueries for complex pipelines:
```asql
# Hypothetical - not proposing this
students_filtered := from students where age > 18
from students_filtered
group by name (count(*))
```

---

### 2. FOREACH...GENERATE: Column Operations

#### Pig Latin
FOREACH works on relations to transform columns:

```pig
-- Simple projection
X = FOREACH A GENERATE name, age;

-- With expressions
X = FOREACH A GENERATE name, age + 1 AS next_age;

-- Star expression (all fields)
X = FOREACH A GENERATE *, name || ' Smith' AS full_name;
```

This is analogous to SQL's SELECT but as a pipeline operator.

#### ASQL Comparison ✅ Already Similar
ASQL's `select` in a pipeline context serves the same purpose:

```asql
from students
select name, age + 1 as next_age
```

#### Takeaway
ASQL already captures this well. No changes needed.

---

### 3. GROUP Creates Nested Structures (Key Insight!)

#### Pig Latin
**This is fundamentally different from SQL's GROUP BY.**

In Pig, GROUP creates a nested data structure with the grouped rows preserved in a bag:

```pig
A = LOAD 'data' AS (f1:int, f2:int, f3:int);

B = GROUP A BY f1;
-- B has schema: {group: int, A: bag{f1: int, f2: int, f3: int}}

DUMP B;
-- (1,{(1,2,3)})
-- (4,{(4,2,1),(4,3,3)})
-- (8,{(8,3,4)})
```

The grouped tuples are accessible as a nested bag! You can then use FOREACH to compute aggregates OR to process individual rows within each group:

```pig
-- Aggregate (like SQL GROUP BY)
C = FOREACH B GENERATE group, SUM(A.f2) AS total;

-- Access individual fields from the bag
C = FOREACH B GENERATE group, A.f1;
-- Result: (1,{(1)}) (4,{(4),(4)}) (8,{(8)})

-- Flatten to unnest back to rows
C = FOREACH B GENERATE FLATTEN(A);
-- Back to original rows
```

#### Why This Matters
SQL's GROUP BY **destroys** the underlying rows - you can only access them through aggregates. Pig's GROUP **preserves** the underlying rows in a nested structure, enabling:
- Aggregation (like SQL)
- Per-group row operations (not possible in SQL without window functions)
- Per-group filtering/ordering (nested FOREACH)

#### ASQL Comparison
ASQL follows the SQL model where GROUP BY produces aggregates directly:

```asql
from orders
group by customer_id (sum(amount) as total)
```

The underlying rows are not preserved as a nested structure.

#### Potential Enhancement (High Value!)
Consider supporting Pig-style nested access after grouping. This would enable powerful per-group operations:

```asql
# Hypothetical syntax - just exploring
from orders
group by customer_id as groups
select 
  customer_id,
  sum(groups.amount) as total,           # aggregate
  max(groups.order_date) as last_order,  # aggregate  
  count(filter(groups, status = 'returned')) as returns  # nested operation!
```

This could address use cases that currently require complex window functions or self-joins.

---

### 4. Nested FOREACH Blocks

#### Pig Latin
FOREACH can contain a nested block for operations on inner bags:

```pig
B = GROUP A BY url;

X = FOREACH B {
    -- These operations work on the bag of rows for each group
    FA = FILTER A BY outlink == 'www.xyz.org';
    PA = FA.outlink;       -- projection
    DA = DISTINCT PA;       -- dedup within group
    GENERATE group, COUNT(DA);
};
```

Allowed nested operations: CROSS, DISTINCT, FILTER, FOREACH, LIMIT, ORDER BY.

#### Why This Matters
This enables per-group transformations that would require complex window functions in SQL:
- "Count distinct values per group" 
- "Top 3 items per category"
- "Filter rows within each group before aggregating"

#### ASQL Comparison
ASQL handles some of these with `per`:

```asql
# Top 1 per group
from orders
per customer_id first by -order_date
```

But more complex per-group logic requires subqueries or window functions.

#### Potential Enhancement
The nested block concept could inspire richer per-group operations. Already captured somewhat by ASQL's `per` command, but could be extended.

---

### 5. FLATTEN Operator

#### Pig Latin
FLATTEN unnests tuples, bags, and maps:

```pig
-- Flatten a tuple: (a, (b, c)) → (a, b, c)
X = FOREACH A GENERATE $0, FLATTEN($1);

-- Flatten a bag creates cross product:
-- (a, {(b,c), (d,e)}) → (a, b, c) and (a, d, e)
X = FOREACH C GENERATE group, FLATTEN(A);

-- Flatten a map creates key-value tuples:
-- (m[k1#v1, k2#v2]) → (k1, v1), (k2, v2)
X = FOREACH A GENERATE FLATTEN(m);
```

#### ASQL Comparison ✅ Already Has `explode`
ASQL's `explode` handles the bag/array case:

```asql
from posts
explode tags as tag
```

#### Gap: Tuple and Map Flattening
ASQL doesn't have a direct equivalent for:
- Flattening tuples (promoting nested fields to top level)
- Flattening maps to key-value rows

#### Potential Enhancement
Map exploding could be useful for JSON data:

```asql
# Hypothetical
from events
explode properties as key, value
```

---

### 6. COGROUP: Multi-Relation Grouping

#### Pig Latin
COGROUP groups multiple relations by a common key, preserving them as separate bags:

```pig
A = LOAD 'pets' AS (owner:chararray, pet:chararray);
B = LOAD 'friends' AS (name:chararray, friend:chararray);

X = COGROUP A BY owner, B BY name;
-- Schema: {group: chararray, A: bag{...}, B: bag{...}}

DUMP X;
-- (Alice, {(Alice,cat),(Alice,dog)}, {(Alice,Bob),(Alice,Carol)})
-- (Bob, {(Bob,fish)}, {})
```

This preserves both relations in their grouped form - like a JOIN that doesn't flatten.

#### Why This Matters
COGROUP is essentially a "grouped outer join" - it groups by key but keeps the bags separate. This enables:
- Comparing aggregates across relations
- Processing matching records from multiple sources per key
- Outer-join-like semantics with full access to underlying rows

#### ASQL Comparison
ASQL doesn't have a direct equivalent. JOINs flatten; GROUP BY only works on one relation.

#### Potential Enhancement (Medium Value)
A COGROUP-like operation could be valuable for certain analytics:

```asql
# Hypothetical - comparing sales and returns by product
from cogroup sales by product_id, returns by product_id as g
select 
  product_id,
  sum(g.sales.amount) as total_sales,
  count(g.returns) as return_count
```

---

### 7. CUBE and ROLLUP

#### Pig Latin
Built-in OLAP operations for multi-dimensional aggregation:

```pig
salesinp = LOAD 'sales' AS (product, year, region, state, city, sales:long);

-- CUBE generates all combinations of dimensions
cubed = CUBE salesinp BY CUBE(product, year);
result = FOREACH cubed GENERATE FLATTEN(group), SUM(cube.sales);
-- Outputs: (car,2012,4000), (car,,4000), (,2012,4000), (,,4000)

-- ROLLUP generates hierarchical aggregates
rolled = CUBE salesinp BY ROLLUP(region, state, city);
-- Outputs: (midwest,ohio,columbus,4000), (midwest,ohio,,4000), (midwest,,,4000), (,,,4000)
```

NULL is used to represent "all values" in aggregated dimensions.

#### ASQL Comparison
No current CUBE/ROLLUP support in ASQL.

#### Potential Enhancement (Medium Value)
These are standard SQL OLAP extensions. Could add:

```asql
from sales
group by cube(product, year) (sum(amount) as total)

from sales
group by rollup(region, state, city) (sum(amount) as total)
```

Many SQL databases support these, so compilation is straightforward.

---

### 8. SPLIT Operator

#### Pig Latin
Splits a relation into multiple relations based on conditions:

```pig
SPLIT A INTO 
    X IF f1 > 0,
    Y IF f1 < 0,
    Z IF f1 == 0;
```

Each tuple goes to one or more output relations (not mutually exclusive unless you design it that way).

#### ASQL Comparison
No equivalent. You'd need multiple queries with different WHERE clauses.

#### Potential Enhancement (Low Value)
This is rarely needed in analytics pipelines. You can always filter multiple times. Not recommended for ASQL.

---

### 9. SAMPLE Operator

#### Pig Latin
Built-in sampling:

```pig
X = SAMPLE A 0.1;  -- 10% sample
```

#### ASQL Comparison ⚠️ Gap Identified
ASQL doesn't have a portable sampling syntax. This was also identified in the pandas learnings document.

#### Potential Enhancement (Already Proposed)
From pandas-python-notebooks-learnings.md:

```asql
from orders
sample 100              -- random n rows
sample 10%              -- random percentage
sample 100 per category -- stratified sampling
```

This remains a high-value addition.

---

### 10. DISTINCT Operator

#### Pig Latin
Simple deduplication:

```pig
X = DISTINCT A;
```

Removes duplicate entire tuples.

#### ASQL Comparison
ASQL has `distinct`:

```asql
from orders
distinct
```

But also has `deduplicate` for more control:

```asql
from events
deduplicate by user_id, event_type
order by created_at desc    -- keep most recent
```

#### Takeaway
ASQL's `deduplicate` is more powerful than Pig's DISTINCT. No changes needed.

---

### 11. RANK Operator

#### Pig Latin
Adds ranking to tuples:

```pig
-- Simple sequential rank
B = RANK A;

-- Rank by field
B = RANK A BY f1 DESC;

-- Dense rank (no gaps)
B = RANK A BY f1 DENSE;
```

#### ASQL Comparison
ASQL has `per` which can add row numbers:

```asql
from products
per category number by -sales as rank
```

And standard window functions work for ranking.

#### Takeaway
ASQL covers ranking use cases. No changes needed.

---

### 12. Complex Data Types

#### Pig Latin
First-class support for tuples, bags, and maps:

```pig
-- Tuple: ordered set of fields
(John, 18, 4.0)

-- Bag: collection of tuples
{(19,2), (18,1)}

-- Map: key-value pairs
[name#John, phone#5551212]
```

Type construction is inline:
```pig
B = FOREACH A GENERATE (name, age), {(name, age)}, [name#gpa];
```

#### ASQL Comparison
ASQL inherits SQL's support for arrays and structs from underlying databases. JSON/map support varies by dialect.

#### Takeaway
No changes needed - dialect support handles this.

---

### 13. Schema Definition at Load

#### Pig Latin
Schemas are optional but can be specified at load:

```pig
A = LOAD 'data' AS (f1:int, f2:int, f3:int);
```

If no schema, fields are bytearrays and accessed by position ($0, $1).

#### ASQL Comparison
ASQL relies on the database catalog for schema information. No schema specification at load.

#### Takeaway
ASQL's approach is appropriate for a compilation layer over existing databases.

---

### 14. Star Expressions and Project-Range

#### Pig Latin
Wildcards for column selection:

```pig
-- All columns
B = FOREACH A GENERATE *;

-- Range of columns
B = FOREACH A GENERATE $0 .. $3;   -- columns 0 through 3
B = FOREACH A GENERATE $0, $2 ..;  -- column 0, then 2 to end
```

#### ASQL Comparison ✅ Already Has These
ASQL defaults to `select *` and has `except` for exclusions:

```asql
from users
except email, phone
```

#### Potential Enhancement
Column range syntax could be useful:

```asql
# Hypothetical
from users
select col1 .. col5  -- columns 1 through 5
```

Low value - the `except` pattern usually suffices.

---

### 15. Execution Hints

#### Pig Latin
Join and group hints for optimization:

```pig
-- Replicated (broadcast) join
X = JOIN A BY $0, B BY $0 USING 'replicated';

-- Skewed join (for uneven key distribution)
X = JOIN A BY $0, B BY $0 USING 'skewed';

-- Merge join (for pre-sorted data)
X = JOIN A BY $0, B BY $0 USING 'merge';

-- Bloom filter join
X = JOIN A BY $0, B BY $0 USING 'bloom';
```

#### ASQL Comparison
ASQL doesn't expose execution hints - it relies on the database optimizer.

#### Takeaway
This is appropriate. ASQL is a semantic layer; execution optimization belongs to the database. However, some dialects support hints that could be passed through.

---

## Summary: What ASQL Can Learn from Pig Latin

### ✅ Already Covered in ASQL

| Pig Feature | ASQL Equivalent |
|-------------|-----------------|
| FOREACH...GENERATE | Pipeline with `select` |
| FILTER | `where` |
| DISTINCT | `distinct`, `deduplicate` |
| FLATTEN (bags) | `explode` |
| Star expressions | Default `select *`, `except` |
| RANK | `per ... number` |
| Nested FILTER per group | `per` with ordering |
| Named pipelines | CTEs / subqueries |

### 🔶 High-Value Ideas from Pig Latin

| Concept | Potential Enhancement | Value |
|---------|----------------------|-------|
| **GROUP preserves rows as nested bag** | Access grouped rows beyond aggregates | **Very High** - enables powerful per-group operations |
| **Nested FOREACH blocks** | Richer per-group transformations | High - ASQL's `per` partially covers this |
| **SAMPLE operator** | Portable sampling syntax | High - already proposed in pandas doc |

### 🔷 Medium-Value Ideas

| Concept | Potential Enhancement | Value |
|---------|----------------------|-------|
| COGROUP | Multi-relation grouped join | Medium - niche use cases |
| CUBE/ROLLUP | OLAP dimension aggregation | Medium - standard SQL feature |
| FLATTEN for maps | Explode key-value pairs | Medium - JSON use cases |

### ❌ Not Recommended for ASQL

| Pig Feature | Why Skip |
|-------------|----------|
| SPLIT operator | Filter multiple times instead |
| Execution hints | Leave to database optimizer |
| Schema at load | ASQL works with existing schemas |
| Position-based field access ($0, $1) | Named columns are clearer |

---

## Key Insight: The Nested Group Pattern

The most valuable insight from Pig Latin is the **nested group pattern** where GROUP BY preserves the underlying rows in a bag. This enables:

1. **Aggregation** (like SQL): `SUM(bag.field)`
2. **Per-group operations**: `FILTER bag BY condition` within each group
3. **Cross-group analysis**: Access to individual rows, not just aggregates

In SQL, GROUP BY destroys row-level access - you can only work with aggregates. Pig's approach keeps both.

**Example use case that's hard in SQL:**
> "For each customer, show their total spend AND the details of their most expensive order"

```pig
-- Pig: natural
grouped = GROUP orders BY customer_id;
result = FOREACH grouped {
    sorted = ORDER orders BY amount DESC;
    top = LIMIT sorted 1;
    GENERATE group, SUM(orders.amount), FLATTEN(top);
};
```

```sql
-- SQL: requires window function + self-join or subquery
WITH ranked AS (
    SELECT *, 
           SUM(amount) OVER (PARTITION BY customer_id) as total,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY amount DESC) as rn
    FROM orders
)
SELECT customer_id, total, order_id, amount
FROM ranked WHERE rn = 1;
```

ASQL's `per` helps with some of these patterns, but the full "grouped bag" concept could unlock more expressiveness.

---

## Implementation Priority

Based on value and complexity:

| Priority | Feature | Notes |
|----------|---------|-------|
| P1 | `sample` operator | Already proposed, high value, medium complexity |
| P2 | CUBE/ROLLUP | Standard SQL, straightforward compilation |
| P3 | Nested group access | High value but significant language change |
| P3 | COGROUP equivalent | Niche use cases |
| P4 | Map explode | Low priority, JSON-specific |
