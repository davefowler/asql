# Supporting Standard SQL Within ASQL

This document explores the question: **Should ASQL support mixing standard SQL syntax with ASQL features, and if so, how?**

**Last Updated**: December 2024

---

## Executive Summary

ASQL claims to be a superset of SQL, but the current preparser implementation breaks several standard SQL patterns. This document analyzes what works, what breaks, why, and explores potential fixes.

**Key Findings:**
- Pure SQL queries work fine if they don't trigger ASQL transformations
- The preparser applies transformations globally, breaking nested SQL structures
- Three main problem patterns: nested WHERE, UNION chains, and WITH...AS bodies
- Multiple fix strategies exist with different complexity/reliability tradeoffs

---

## Current State: What Works and What Breaks

### ✅ Works: Pure SQL Patterns

| Pattern | Example | Status |
|---------|---------|--------|
| SELECT-first queries | `SELECT * FROM users WHERE active` | ✅ Pass-through |
| Standard CTEs | `WITH a AS (SELECT 1) SELECT * FROM a` | ✅ Pass-through |
| JOINs | `SELECT * FROM a JOIN b ON a.id = b.a_id` | ✅ Pass-through |
| Window functions | `ROW_NUMBER() OVER (PARTITION BY x)` | ✅ Pass-through |
| CASE expressions | `CASE WHEN x THEN y ELSE z END` | ✅ Pass-through |
| LATERAL joins | `FROM users, LATERAL (SELECT ...)` | ✅ Pass-through |

### ✅ Works: ASQL Mixed with SQL

| Pattern | Example | Status |
|---------|---------|--------|
| FROM-first + SQL expressions | `from users select CASE WHEN ...` | ✅ Works |
| ASQL + SQL JOINs | `from orders join customers on ...` | ✅ Works |
| Natural aggregates | `SELECT sum amount FROM sales` | ✅ Transforms correctly |
| Order by -col | `from users order by -created_at` | ✅ Transforms correctly |
| Stash as CTEs | `from users stash as u` | ✅ Transforms correctly |

### ❌ Breaks: SQL Patterns with ASQL-like Structures

| Pattern | Example | Problem |
|---------|---------|---------|
| Subquery in WHERE | `WHERE id IN (SELECT ... WHERE ...)` | Multiple WHERE → AND |
| EXISTS subquery | `WHERE EXISTS (SELECT ... WHERE ...)` | Multiple WHERE → AND |
| UNION with ASQL | `from a UNION from b` | Only first query transformed |
| WITH + ASQL body | `WITH x AS (from y group by z (...))` | Aggregate block extracted globally |
| Multiple stash as | `... stash as a ... stash as b` | Chained stash parsing fails |

---

## Root Cause Analysis

### The Preparser's Global Transformation Problem

The preparser applies regex-based transformations to the **entire query text** without understanding SQL's nested structure:

```python
# Example: _transform_multiple_where
# This naively combines WHERE clauses without respecting nesting:
pattern = r'\bwhere\s+(.+?)\s+where\s+'
# "WHERE x IN (SELECT ... WHERE y)" becomes "WHERE x IN (SELECT ... AND y)"
```

### Specific Failure Cases

**1. Nested WHERE in Subqueries**

```sql
-- Input (valid SQL)
SELECT * FROM orders
WHERE customer_id IN (SELECT id FROM customers WHERE premium = true)

-- After preparse (broken)
SELECT * FROM orders
WHERE customer_id IN (SELECT id FROM customers AND premium = true)
```

The `_transform_multiple_where` function doesn't track parenthesis depth.

**2. Aggregate Blocks with WITH**

```sql
-- Input (ASQL + SQL mix)
WITH revenue AS (
  from sales
  group by month(created_at) (sum(amount) as total)
)
SELECT * FROM revenue

-- After preparse (broken)
SELECT month(created_at), sum(amount) as total WITH revenue AS (
  from sales GROUP BY month(created_at) )
SELECT * FROM revenue
```

The aggregate block transformation extracts the SELECT globally, not within the CTE scope.

**3. UNION Chains**

```sql
-- Input (ASQL)
from customers select id, name
UNION
from vendors select id, name

-- After preparse (broken)
SELECT id, name
UNION
from vendors select id, name from customers
```

The FROM-first transformation only applies to the first query.

---

## Potential Solutions

### Approach 1: Fix Preparser with Parenthesis Awareness

**Complexity**: Medium  
**Reliability**: Good for most cases

Make each transformation track parenthesis depth:

```python
def _transform_multiple_where(self, text: str) -> str:
    """Only combine WHERE clauses at the same nesting level."""
    result = text
    
    while True:
        # Track paren depth at each position
        depths = self._compute_paren_depths(result)
        
        # Only match WHERE...WHERE at depth 0
        pattern = r'\bwhere\s+(.+?)\s+where\s+'
        for match in re.finditer(pattern, result, re.IGNORECASE):
            if depths[match.start()] == 0:
                # Safe to transform at top level
                ...
```

**Pros**: Targeted fix, minimal change  
**Cons**: Doesn't help WITH or UNION cases, fragile for complex nesting

### Approach 2: Try-SQLGlot-First Strategy

**Complexity**: Low  
**Reliability**: High for pure SQL, lower for mixed queries

Parse with SQLGlot first; only preparse on failure:

```python
def compile(query: str) -> str:
    # First try: pure SQL through ASQL dialect
    try:
        parsed = sqlglot.parse_one(query, read='asql')
        return generate(parsed)
    except:
        pass
    
    # Second try: preparse then parse
    preparsed = preparse_asql(query)
    parsed = sqlglot.parse_one(preparsed, read='asql')
    return generate(parsed)
```

**Pros**: Pure SQL always works correctly  
**Cons**: ASQL features inside SQL structures still break

### Approach 3: AST-Based Preprocessing

**Complexity**: High  
**Reliability**: Very high

Parse SQL structure first, then apply ASQL transforms to each nested query:

```python
def compile(query: str) -> str:
    # Parse as SQL first (may fail for FROM-first)
    try:
        ast = sqlglot.parse_one(query)
    except:
        ast = sqlglot.parse_one(preparse_asql(query))
    
    # Walk AST and transform ASQL patterns in each subquery
    for node in ast.walk():
        if isinstance(node, exp.Select):
            transform_asql_patterns(node)
    
    return ast.sql()
```

**Pros**: Handles all nesting correctly  
**Cons**: Major architecture change, much more complex

### Approach 4: Segment-Based Preparsing

**Complexity**: Medium-High  
**Reliability**: Good

Identify and preparse each "segment" (top-level query, each CTE body, each UNION part) independently:

```python
def preparse_segmented(query: str) -> str:
    # Split into segments at boundaries
    segments = identify_segments(query)  # CTEs, UNIONs, subqueries
    
    # Preparse each segment independently
    for seg in segments:
        seg.text = preparse_asql(seg.text)
    
    # Reassemble
    return reassemble(segments)
```

**Pros**: Respects SQL structure, reuses existing preparser  
**Cons**: Requires reliable segment detection

### Approach 5: Protect SQL Regions (NEW - RECOMMENDED) ⭐

**Complexity**: Low-Medium  
**Reliability**: High

Detect and protect SQL subqueries before preparsing, then restore after:

```python
def smart_compile(query: str) -> str:
    # Step 1: Check for ASQL patterns
    if not has_asql_patterns(query):
        # Pure SQL - parse directly
        return sqlglot.parse_one(query).sql()
    
    # Step 2: Protect SQL regions (parenthesized SELECT subqueries)
    protected_query, protected = protect_sql_regions(query)
    
    # Step 3: Preparse (safe - SQL regions are placeholder tokens)
    preparsed = preparse_asql(protected_query)
    
    # Step 4: Restore SQL regions
    restored = restore_sql_regions(preparsed, protected)
    
    # Step 5: Parse with SQLGlot
    return sqlglot.parse_one(restored).sql()

def protect_sql_regions(text: str) -> tuple:
    """Replace (SELECT ...) subqueries with placeholders."""
    protected = {}
    # Find parenthesized regions at depth 0
    for start, end in find_paren_regions(text):
        content = text[start:end]
        inner = content[1:-1].strip()
        # If it's a valid SQL SELECT, protect it
        if re.match(r'^\s*SELECT\b', inner, re.IGNORECASE):
            try:
                sqlglot.parse_one(inner)
                placeholder = f'__SQL_REGION_{len(protected)}__'
                protected[placeholder] = content
                text = text[:start] + placeholder + text[end:]
            except:
                pass  # Not valid SQL, don't protect
    return text, protected
```

**Tested Results:**

| Query | Result |
|-------|--------|
| `SELECT * FROM orders WHERE id IN (SELECT id FROM items WHERE active)` | ✅ Works |
| `from users where active limit 10` | ✅ Works |
| `from sales group by region (sum(amount) as total)` | ✅ Works |
| `SELECT * FROM users u WHERE EXISTS (SELECT 1 FROM orders o WHERE ...)` | ✅ Works |
| `from orders where customer_id IN (SELECT id FROM vip WHERE status = 'active')` | ✅ Works |
| `WITH base AS (SELECT ...) from base where active order by -created_at` | ✅ Works |

**Pros**: 
- Low complexity, minimal changes to existing preparser
- Handles all common SQL subquery patterns
- ASQL patterns still get full transformation
- No user-facing syntax changes required

**Cons**: 
- Only protects `(SELECT ...)` patterns, not CTE bodies
- Relies on SQLGlot to validate SQL regions

---

## Ideas Considered But Not Recommended

### Idea A: Add More SQL Keywords to ASQL Dialect

**Question**: Would registering more SQL commands/keywords in the ASQL dialect help?

**Answer**: No. The problem isn't the dialect - it's the **preparser running before SQLGlot**. The ASQL dialect already inherits all SQL keywords. The issue is:

```
Input → Preparser (regex, breaks things) → SQLGlot (sees mangled SQL) → Output
```

Adding keywords to the dialect doesn't help because the preparser doesn't use the dialect's keyword list.

### Idea B: Require Parens Around SQL Chunks

**Question**: Could we require users to wrap raw SQL in parens and give helpful warnings?

**Answer**: Not needed! SQL subqueries are **already** wrapped in parens by SQL syntax:
- `WHERE id IN (SELECT ...)` 
- `WHERE EXISTS (SELECT ...)`
- `FROM (SELECT ...) AS subq`

The "Protect SQL Regions" approach (Approach 5) leverages this - we detect `(SELECT ...)` patterns and protect them automatically. No user-facing syntax change needed.

### Idea C: Smart Recovery on Parse Failure

**Question**: On error/failure, try more advanced splitting or send chunks to SQLGlot?

**Answer**: This is partially incorporated into Approach 5:

1. **Check for ASQL patterns first** - if none found, try pure SQL parsing
2. **Protect SQL regions** - uses SQLGlot to validate each `(SELECT ...)` block
3. **Fall through** - if protection + preparse still fails, report error

The key insight is: **don't wait for failure** - proactively detect and protect SQL regions before they can be mangled.

---

## Dialect Considerations

If we support SQL inside ASQL, we need to consider dialect-specific syntax:

| Dialect | Unique Syntax |
|---------|---------------|
| PostgreSQL | `DISTINCT ON`, `RETURNING`, `ILIKE` |
| BigQuery | `EXCEPT()`, `REPLACE()`, `QUALIFY` |
| Snowflake | `QUALIFY`, `SAMPLE` |
| MySQL | `STRAIGHT_JOIN`, `SQL_NO_CACHE` |
| DuckDB | `COLUMNS(*)`, `EXCLUDE` |

**Current Status**: SQLGlot handles dialect-specific parsing well. If we pass SQL through correctly, dialect support comes "for free."

**Question**: Should we detect the input dialect? Or always assume the target dialect?

---

## Recommendation

### ⭐ Recommended: Approach 5 (Protect SQL Regions)

This approach has been tested and works well for all common patterns:

1. **Detect ASQL patterns first** - only preparse if query contains ASQL syntax
2. **Protect SQL subqueries** - replace `(SELECT ...)` with placeholders before preparse
3. **Normal preparse** - all ASQL transformations run safely
4. **Restore SQL regions** - put the original SQL subqueries back
5. **Parse with SQLGlot** - final SQL generation

**Implementation effort**: ~50 lines of code added to preparser  
**Risk**: Low - additive change, doesn't modify existing transformations

### Alternative: Targeted Fixes

If Approach 5 is too broad, we could fix specific transforms:

1. **Fix `_transform_multiple_where`** to respect parenthesis depth
2. Add paren-awareness to other problematic transforms

### Future: AST-Based (if needed)

For maximum reliability, move ASQL transformations from text-based regex to AST-based transformations. Only pursue this if Approach 5 proves insufficient.

---

## Should We Do This?

### Arguments For

1. **SQL expertise shouldn't be lost** - Analysts know SQL patterns; don't force them to relearn
2. **Incremental adoption** - Teams can migrate queries gradually
3. **Existing queries work** - Copy-paste from BI tools should work
4. **True superset** - "ASQL is a superset of SQL" becomes actually true

### Arguments Against

1. **Complexity** - More code paths = more bugs
2. **Confusion** - Two ways to do things can confuse users
3. **Testing burden** - Exponential combinations to test
4. **The ASQL way is better** - `stash as` is more readable than `WITH ... AS`

### Middle Ground: Limited Scope

We could explicitly support:
- ✅ Pure SQL queries (try-SQLGlot-first)
- ✅ ASQL features in top-level query
- ❌ ASQL features inside CTE bodies (use `stash as` instead)
- ❌ ASQL features inside subqueries (use `stash as` instead)

This gives us the benefits of SQL compatibility without the complexity of deep mixing.

---

## Test Cases to Add

If we proceed, these should be test cases:

```python
# Pure SQL (should always work)
"SELECT * FROM users WHERE id IN (SELECT user_id FROM orders WHERE total > 100)"
"WITH a AS (SELECT 1), b AS (SELECT * FROM a) SELECT * FROM b"
"SELECT * FROM a UNION SELECT * FROM b UNION SELECT * FROM c"
"SELECT * FROM users u WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)"

# ASQL (should work)
"from users where active stash as u"
"from sales group by region (sum(amount) as total)"
"from orders order by -created_at limit 10"

# Mixed - limited support
"from users where id IN (SELECT user_id FROM vip_list)"  # SQL subquery in ASQL
"SELECT * FROM (from orders group by user_id (count(*) as cnt)) as counts"  # ASQL subquery in SQL

# Explicitly not supported (use stash as instead)
"WITH revenue AS (from sales group by month (sum(amount))) SELECT * FROM revenue"
```

---

## Appendix: Current Preparser Flow

```
Input ASQL
    ↓
_transform_set_statements()     # Compile settings
    ↓
_transform_pipeline()           # Remove | operators
    ↓
_transform_stash_as()           # stash as → CTE
    ↓
_transform_count_shorthand()    # # → COUNT(*)
    ↓
_transform_order_desc_prefix()  # -col → col DESC
    ↓
_transform_natural_aggregates() # sum amount → sum(amount)
    ↓
_transform_date_literals()      # @2024-01-01 → DATE '...'
    ↓
_transform_relative_dates()     # 7 days ago → ...
    ↓
_transform_date_arithmetic()    # date + 7 days → ...
    ↓
_transform_since_until_patterns() # days_since_x → ...
    ↓
_transform_per_commands()       # per x first by y → window
    ↓
_transform_aggregate_blocks()   # group by x (aggs) → SELECT
    ↓
_transform_multiple_where()     # where x where y → where x AND y  ← BREAKS NESTING
    ↓
_transform_from_first()         # from x → SELECT * from x
    ↓
_transform_distinct_on()        # distinct on (x) → DISTINCT ON
    ↓
_transform_window_functions()   # prior(), running_sum() → ...
    ↓
_transform_qualify_clause()     # qualify → QUALIFY
    ↓
_transform_coalesce_operator()  # ?? → COALESCE
    ↓
_normalize_function_spaces()    # day of week → day_of_week
    ↓
_transform_equality_operators() # == → =
    ↓
Output SQL-like (for SQLGlot)
```

Most of these are safe for nested queries. The problematic ones are:
- `_transform_multiple_where` - needs paren awareness
- `_transform_aggregate_blocks` - needs scope awareness
- `_transform_from_first` - needs segment awareness for UNION
