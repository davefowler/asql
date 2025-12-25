# Recursive Queries Design Document

**Issue**: #11  
**Status**: Design/Research  
**Date**: December 20, 2025  
**PR Title**: `asql: Recursive query syntax for hierarchical data traversal (#11)`  
**Branch**: `issue-11-recursive-queries`

---

## Executive Summary

Recursive CTEs are powerful but painful. ASQL should provide syntactic sugar that makes hierarchical traversal as easy as writing a regular query, while compiling to standard SQL recursive CTEs.

---

## Design Questions & Answers

### 1. How to Limit Recursion Depth?

**Recommendation**: Always generate the `level` column, and support an optional `max_depth` parameter.

```asql
-- Simple: no limit (database's default applies)
from employees
  where id == 1
  recurse through manager_id -> id

-- With depth limit
from employees
  where id == 1
  recurse through manager_id -> id (max_depth: 5)

-- Or with inline limit syntax
from employees
  where id == 1
  recurse through manager_id -> id (max: 5)
```

**Generated SQL with max depth**:
```sql
WITH RECURSIVE cte AS (
    SELECT *, 1 AS level FROM employees WHERE id = 1
    UNION ALL
    SELECT e.*, cte.level + 1
    FROM employees e
    JOIN cte ON e.manager_id = cte.id
    WHERE cte.level < 5  -- ← max_depth limit
)
SELECT * FROM cte
```

**Why always include `level`**:
- Users frequently need it (for indentation, limiting display, etc.)
- It's required internally for max_depth enforcement
- Users can easily exclude it: `select * except level` or explicit column list
- Matches graph DB behavior (Neo4j returns path length)

**Dialect notes on limits**:
| Dialect | Default Limit | Override |
|---------|--------------|----------|
| SQL Server | 100 | `OPTION (MAXRECURSION n)` |
| PostgreSQL | None | N/A |
| MySQL 8 | 1000 | `@@cte_max_recursion_depth` |
| BigQuery | None | N/A |
| DuckDB | None | N/A |

---

### 2. Multiple Recursions in One File/Query?

**Scenario A**: Multiple recursive queries in the same file (pipeline/stash)

```asql
-- Two separate recursive traversals, each becomes its own CTE
from employees
  where id == 1
  recurse through manager_id -> id
  stash as ceo_org

from categories
  where slug == 'electronics'
  recurse through parent_id -> id
  stash as electronics_tree

from ceo_org & electronics_tree ...
```

**Generated SQL**:
```sql
WITH RECURSIVE 
  ceo_org AS (
    SELECT *, 1 AS level FROM employees WHERE id = 1
    UNION ALL
    SELECT e.*, ceo_org.level + 1
    FROM employees e
    JOIN ceo_org ON e.manager_id = ceo_org.id
  ),
  electronics_tree AS (
    SELECT *, 1 AS level FROM categories WHERE slug = 'electronics'
    UNION ALL
    SELECT c.*, electronics_tree.level + 1
    FROM categories c
    JOIN electronics_tree ON c.parent_id = electronics_tree.id
  )
SELECT ... FROM ceo_org JOIN electronics_tree ...
```

**Scenario B**: Two recursions in ONE query (rare, but possible)

This is unusual and would likely be an error or require explicit syntax. Most recursive patterns traverse one hierarchy at a time.

**Recommendation**: 
- Support multiple `stash as` recursive CTEs naturally
- Single query with multiple `recurse` clauses should be an error (force user to use stash)
- Error message: "Multiple recursive traversals in single query. Use `stash as` to separate them."

---

### 3. Using FK Mapping for Cleaner Syntax

ASQL already has FK dot notation for regular joins. We can extend this for recursion!

**Current FK Traversal** (single hop):
```asql
from orders
  select orders.customer.name  -- auto-joins via customer_id
```

**Proposed Recursive FK Traversal**:

```asql
-- Schema defines self-referential relationship:
-- employees.manager_id -> employees.id (alias: manager)

-- Current (single hop) - gets direct manager only:
from employees
  select employees.name, employees.manager.name as boss_name

-- Proposed (recursive traversal) - gets entire chain:
from employees
  where id == 1
  recurse through .manager  -- ← uses FK definition!
  select id, name, level
```

**How it would work**:
1. ASQL sees `recurse through .manager`
2. Looks up relationship: `employees.manager_id -> employees.id`
3. Generates: `recurse through manager_id -> id`
4. Compiles to recursive CTE

**Even cleaner with implicit self-ref**:

If schema defines `employees.reports` as the inverse relationship:

```yaml
# asql_schema.yml
tables:
  employees:
    columns: [id, name, manager_id]
relationships:
  - from: employees.manager_id
    to: employees.id
    alias: manager
    inverse: reports  # ← defines the reverse traversal
```

```asql
-- "Give me employee 1 and all their reports (recursively)"
from employees.id(1).reports*  -- The * means "recursive"

-- Or:
from employees
  where id == 1
  recurse via reports
```

**Trade-offs**:
| Syntax | Pros | Cons |
|--------|------|------|
| `recurse through col -> col` | Explicit, works without schema | Verbose |
| `recurse through .alias` | Concise, schema-aware | Requires FK naming convention |
| `.relationship*` | Most concise, graph-like | Requires schema, new syntax |

---

### 4. Rows vs Columns: How Output Works

**Confirmed: Recursion creates NEW ROWS, not new columns.**

```
Input (employees table):
id | name    | manager_id
---|---------|----------
1  | CEO     | NULL
2  | VP Eng  | 1
3  | VP Sales| 1
5  | Eng Dir | 2
8  | Dev     | 5

Query: from employees where id=1 recurse through manager_id -> id

Output (multiple rows, one per person in tree):
id | name     | manager_id | level
---|----------|------------|------
1  | CEO      | NULL       | 1
2  | VP Eng   | 1          | 2
3  | VP Sales | 1          | 2
5  | Eng Dir  | 2          | 3
8  | Dev      | 5          | 4
```

This is fundamentally different from a self-join which would add columns:

```sql
-- Self-join adds COLUMNS (only 1 level):
SELECT e.*, m.name as manager_name
FROM employees e
LEFT JOIN employees m ON e.manager_id = m.id
-- Result: same number of rows, but with manager_name column
```

**Key insight**: Recursion is about **traversing a graph and collecting nodes**, not about **denormalizing relationships into columns**.

---

### 5. Multi-Table Recursion?

**Question**: Can `recurse` work across tables, not just self-references?

**Answer**: The common case is self-referential (employees -> employees, categories -> categories). But there are multi-table recursive patterns:

**Example: Bill of Materials (BOM)**
```
products: id, name
components: product_id, component_product_id, quantity

A product can contain other products as components, which can contain other products...
```

```asql
-- Multi-table recursive query
from products
  where id == 100  -- Start with product 100
  & components on products.id = components.product_id
  recurse through components.component_product_id -> products.id
  select products.name, components.quantity, level
```

**Generated SQL**:
```sql
WITH RECURSIVE bom AS (
    SELECT p.*, c.quantity, 1 AS level
    FROM products p
    JOIN components c ON p.id = c.product_id
    WHERE p.id = 100
    UNION ALL
    SELECT p.*, c.quantity, bom.level + 1
    FROM products p
    JOIN components c ON p.id = c.product_id
    JOIN bom ON c.component_product_id = bom.id
)
SELECT name, quantity, level FROM bom
```

**Recommendation**: 
- Primary use case is self-referential (same table)
- Multi-table recursion is supported but more complex
- The syntax should work naturally: if you join tables before `recurse`, the recursion can reference the joined columns

---

### 6. Recursion as a WHERE Filter?

**Your insight**: Recursion is really answering "where this row is part of a tree rooted at X"

```asql
-- Current thinking
from employees
  where id == 1
  recurse through manager_id -> id

-- Your proposal: treat as WHERE condition
from employees
  where id == 1 or is_child_of(manager_id, 1)

-- Or:
from employees
  where in_tree(id, root: 1, via: manager_id)
```

**Analysis**:

This is a brilliant reframe! The recursive CTE is really just a fancy way to define set membership:
- "Row R is in the result if R.id = 1 OR R's manager is in the result"

**Potential Syntax Options**:

```asql
-- Option A: Explicit function-like
from employees
  where in_tree(root: 1, via: manager_id -> id)

-- Option B: descendants_of / ancestors_of
from employees
  where id == 1 or descendants_of(1, via: manager_id)

-- Option C: Using relationship name
from employees
  where id == 1 or children_of(1, through: .manager)

-- Option D: Tree membership operator
from employees
  where id in tree(1, via: manager_id)

-- Option E: Recursive where clause
from employees
  where recursive(id == 1, through: manager_id -> id)
```

**Pros of WHERE-based syntax**:
- Conceptually accurate (it IS a filter on set membership)
- Could combine with other WHERE conditions naturally
- Fits the "filtering" mental model analysts have

**Cons of WHERE-based syntax**:
- Recursion is more than filtering - it also adds the `level` column
- The traversal direction matters (up vs down the tree)
- May be confusing: looks like a simple filter but generates complex SQL

**Recommendation**: 
Keep `recurse through` as the primary syntax (makes the operation explicit), but consider adding helper predicates for common patterns:

```asql
-- Primary syntax (explicit, generates CTE)
from employees
  where id == 1
  recurse through manager_id -> id

-- Shorthand for "is this row in the tree?" (for filtering existing result sets)
from all_employees
  where in_subtree(root_id: 1, via: manager_id)
```

---

## Direction of Traversal

Important consideration: Walking UP vs DOWN the tree.

```
       CEO (id=1)
      /         \
   VP Eng (2)   VP Sales (3)
     |
   Dir (5)
     |
   Dev (8)
```

**Going DOWN (descendants)**: Start at CEO, find all reports
- Start: id = 1
- Follow: manager_id -> id (find rows where manager_id = current.id)
- Result: CEO, VP Eng, VP Sales, Dir, Dev

**Going UP (ancestors)**: Start at Dev, find all managers up to CEO
- Start: id = 8
- Follow: id -> manager_id (find row where id = current.manager_id)
- Result: Dev, Dir, VP Eng, CEO

The arrow direction in `recurse through X -> Y` indicates this:
- `manager_id -> id`: "for each current row, find rows where their manager_id = my id" (descendants)
- `id -> manager_id`: "for my current row, find the row where id = my manager_id" (ancestors)

```asql
-- Descendants (who reports to me?)
from employees where id == 1
  recurse through manager_id -> id
  
-- Ancestors (who do I report to?)
from employees where id == 8
  recurse through id -> manager_id
```

---

## Syntax Proposal Summary

### Primary Syntax

```asql
from <table>
  [where <base_condition>]
  recurse through <from_col> -> <to_col> [(max_depth: N)]
  [select ...]
```

### Alternative/Shorthand Syntaxes (Future)

```asql
-- Using FK relationship name
from employees
  where id == 1
  recurse via .reports

-- Graph-like traversal
from employees.id(1).reports*

-- As filter predicate
from employees
  where in_subtree(1, via: manager_id)
```

---

## Generated SQL Template

```sql
WITH RECURSIVE <cte_name> AS (
    -- Base case
    SELECT <columns>, 1 AS level
    FROM <table>
    WHERE <base_condition>
    
    UNION ALL
    
    -- Recursive case
    SELECT <columns>, <cte_name>.level + 1
    FROM <table>
    JOIN <cte_name> ON <table>.<from_col> = <cte_name>.<to_col>
    [WHERE <cte_name>.level < <max_depth>]
)
SELECT * FROM <cte_name>
```

---

## Edge Cases to Handle

### 1. Cycle Detection
What if the data has cycles? (A reports to B reports to C reports to A)

**Options**:
- Rely on max_depth (default behavior)
- Track visited nodes with array (PostgreSQL: `path text[]`)
- Error after N iterations

**Recommendation**: Default to max_depth of 100 (like SQL Server), document the cycle risk.

### 2. Multiple Starting Points

```asql
-- Start from multiple roots
from employees
  where department == 'Engineering'  -- Multiple people!
  recurse through manager_id -> id
```

This is valid! It creates a forest (multiple trees). The CTE handles this naturally.

### 3. Combining with Other Operations

```asql
from employees
  where id == 1
  recurse through manager_id -> id
  where level <= 3  -- Post-recursion filter
  group by department (count(*) as headcount)
  order by -headcount
```

---

## Implementation Notes

### Preparser Phase
1. Detect `recurse through` clause
2. Extract: base table, from_col, to_col, max_depth
3. Mark query as requiring recursive CTE generation

### Compiler Phase
1. Wrap the base query in recursive CTE structure
2. Generate UNION ALL with self-join
3. Add level column tracking
4. Apply max_depth WHERE clause if specified

### Dialect Handling
SQLGlot should handle most dialect differences, but:
- SQL Server: May need `OPTION (MAXRECURSION n)`
- MySQL 5.x: No recursive CTE support → error with helpful message

---

## Open Questions

1. **Keyword choice**: `recurse through` vs `traverse` vs `walk`?
2. **Arrow syntax**: `->` or `=>` or `to`? (Arrow matches the FK dot notation concept)
3. **Level column name**: Always `level`? Or customizable: `(level as depth)`?
4. **Include root?**: Should the starting row be included? (Default: yes, matches SQL behavior)

---

## References

- [ai_notes/archive/research/SET_THEORY_ANCESTORS.md](./archive/research/SET_THEORY_ANCESTORS.md) - Datalog context
- [PostgreSQL WITH RECURSIVE docs](https://www.postgresql.org/docs/current/queries-with.html)
- [Neo4j variable-length patterns](https://neo4j.com/docs/cypher-manual/current/patterns/variable-length-patterns/)
- Issue #11 for tracking

---

## Next Steps

1. Finalize primary syntax (`recurse through X -> Y`)
2. Implement basic recursive CTE generation
3. Add max_depth support
4. Add level column generation
5. Consider FK-based shorthand in future iteration
6. Write comprehensive tests for edge cases

