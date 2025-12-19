# List Comprehensions / Array Transformations Research

**Date:** 2024-12-19
**Status:** Research complete, feasibility assessed

## Summary

Python-style list comprehensions for array transformations are a powerful feature in DuckDB. This document analyzes the feasibility of adding this syntax to ASQL and transpiling it across different SQL dialects.

## DuckDB Syntax

DuckDB supports Python-style list comprehensions:

```sql
-- Basic transformation
SELECT [LOWER(x) FOR x IN strings] AS lowered FROM t;

-- With filter
SELECT [x * 2 FOR x IN numbers IF x > 0] AS doubled FROM t;

-- Using function
SELECT list_transform([1,2,3], x -> x + 1) AS result;
```

## Proposed ASQL Syntax

```asql
from events
  select [lower(x) for x in tags] as normalized_tags

from numbers
  select [x * 2 for x in values if x > 0] as doubled
```

## Dialect Equivalents

Each database has different syntax for array transformations:

### DuckDB
```sql
SELECT [LOWER(x) FOR x IN strings] AS lowered FROM t
```
Native list comprehension syntax. Clean and Pythonic.

### BigQuery
```sql
SELECT ARRAY(SELECT LOWER(e) FROM UNNEST(strings) AS e) AS lowered FROM t
```
Uses `ARRAY()` with a subquery over `UNNEST()`.

### Postgres
```sql
SELECT ARRAY(SELECT LOWER(e) FROM UNNEST(strings) AS e) AS lowered FROM t
```
Same pattern as BigQuery.

### Snowflake
```sql
SELECT ARRAY_AGG(LOWER(f.value)) AS lowered 
FROM t, TABLE(FLATTEN(INPUT => strings)) AS f
```
Completely different structure - requires `FLATTEN` as a table function with `ARRAY_AGG`.

### MySQL
**Not supported.** MySQL doesn't have native array types.

## SQLGlot Transpilation Analysis

### Test: Can SQLGlot convert DuckDB list comprehension to other dialects?

**Input (DuckDB):**
```sql
SELECT [LOWER(x) FOR x IN strings] AS lowered FROM t
```

**Results:**
| Dialect | Output | Valid? |
|---------|--------|--------|
| Snowflake | `[LOWER(x) FOR x IN strings]` | ❌ Just passes through |
| BigQuery | `[LOWER(x) FOR x IN strings]` | ❌ Just passes through |
| Postgres | `ARRAY[LOWER(x) FOR x IN strings]` | ❌ Invalid syntax |

**Conclusion:** SQLGlot does NOT convert DuckDB list comprehensions to equivalent syntax. It just passes through (or adds `ARRAY` prefix for Postgres).

### Test: Can we use a "portable" intermediate format?

**Input (Postgres-style):**
```sql
SELECT ARRAY(SELECT LOWER(e) FROM UNNEST(strings) AS e) AS lowered FROM t
```

**Results:**
| Dialect | Output | Valid? |
|---------|--------|--------|
| DuckDB | `ARRAY(SELECT LOWER(e) FROM UNNEST(strings) AS e)` | ✅ Works |
| BigQuery | `ARRAY(SELECT LOWER(e) FROM UNNEST(strings))` | ✅ Works |
| Postgres | `ARRAY(SELECT LOWER(e) FROM UNNEST(strings) AS e)` | ✅ Works |
| Snowflake | `[SELECT LOWER(e) FROM TABLE(FLATTEN(...))]` | ❌ Invalid! |
| MySQL | N/A | ❌ No arrays |

**Conclusion:** Postgres-style `ARRAY(SELECT ... FROM UNNEST(...))` works for DuckDB/BigQuery/Postgres, but **Snowflake output is broken** - SQLGlot generates invalid syntax.

## Implementation Strategy

### Recommended Approach

1. **Preparser parses list comprehension syntax:**
   ```asql
   [expr for var in array_col]
   [expr for var in array_col if condition]
   ```

2. **Dialect-aware transformation:**
   - **DuckDB:** Pass through as-is (native support)
   - **Postgres/BigQuery:** Emit `ARRAY(SELECT expr FROM UNNEST(array_col) AS var)`
   - **Snowflake:** Emit custom `ARRAY_AGG` + `FLATTEN` pattern
   - **MySQL:** Error with helpful message

### Example Transformations

**ASQL Input:**
```asql
from events
  select [lower(tag) for tag in tags] as normalized
```

**DuckDB Output:**
```sql
SELECT [LOWER(tag) FOR tag IN tags] AS normalized FROM events
```

**Postgres/BigQuery Output:**
```sql
SELECT ARRAY(SELECT LOWER(tag) FROM UNNEST(tags) AS tag) AS normalized FROM events
```

**Snowflake Output:**
```sql
SELECT ARRAY_AGG(LOWER(f.value)) AS normalized 
FROM events, TABLE(FLATTEN(INPUT => tags)) AS f
```

### Handling Filters

**ASQL Input:**
```asql
from data
  select [x * 2 for x in numbers if x > 0] as doubled
```

**DuckDB Output:**
```sql
SELECT [x * 2 FOR x IN numbers IF x > 0] AS doubled FROM data
```

**Postgres/BigQuery Output:**
```sql
SELECT ARRAY(SELECT x * 2 FROM UNNEST(numbers) AS x WHERE x > 0) AS doubled FROM data
```

**Snowflake Output:**
```sql
SELECT ARRAY_AGG(f.value * 2) AS doubled 
FROM data, TABLE(FLATTEN(INPUT => numbers)) AS f
WHERE f.value > 0
```

## Complexity Assessment

### Parsing Complexity: Medium
- Need to recognize `[expr for var in col]` pattern
- Need to handle optional `if condition` clause
- Need to extract expression, variable, array column, and optional filter

### Transformation Complexity: Medium-High
- DuckDB: Trivial (pass through)
- Postgres/BigQuery: Moderate (restructure to ARRAY+UNNEST subquery)
- Snowflake: Complex (completely different structure with FLATTEN as table source)

### Edge Cases
1. **Nested comprehensions:** `[[y for y in x] for x in nested_array]`
2. **Multiple variables:** Not typically supported, but could be confusing
3. **Complex expressions:** `[func(x, other_col) for x in arr]` - referencing other columns
4. **Aggregate context:** How does this interact with GROUP BY?

## Dialect Support Matrix

| Feature | DuckDB | BigQuery | Postgres | Snowflake | MySQL |
|---------|--------|----------|----------|-----------|-------|
| Array type | ✅ | ✅ | ✅ | ✅ | ❌ |
| UNNEST | ✅ | ✅ | ✅ | ❌ (uses FLATTEN) | ❌ |
| List comprehension | ✅ Native | ❌ | ❌ | ❌ | ❌ |
| ARRAY() subquery | ✅ | ✅ | ✅ | ❌ | ❌ |
| ARRAY_AGG | ✅ | ✅ | ✅ | ✅ | ❌ |
| SQLGlot transpiles correctly | ✅ | ✅ | ✅ | ❌ | N/A |

## Recommendations

### Priority: Medium
- Useful for nested data (JSON, arrays) but not critical for most analytics
- Growing importance with JSON/semi-structured data in modern warehouses

### Implementation Order
1. **Phase 1:** Support for DuckDB only (pass through)
2. **Phase 2:** Add Postgres/BigQuery support (SQLGlot handles this)
3. **Phase 3:** Add Snowflake support (custom transformation needed)

### Alternative: Function Syntax
Instead of Python-style comprehensions, could offer a function:

```asql
from events
  select array_map(tags, t -> lower(t)) as normalized
```

This is less elegant but easier to parse and could transpile to:
- DuckDB: `list_transform(tags, t -> lower(t))`
- Others: The UNNEST/ARRAY_AGG patterns

## Related Resources

- [DuckDB List Comprehensions](https://duckdb.org/docs/sql/functions/list)
- [BigQuery UNNEST](https://cloud.google.com/bigquery/docs/reference/standard-sql/arrays)
- [Snowflake FLATTEN](https://docs.snowflake.com/en/sql-reference/functions/flatten)
- [PostgreSQL Array Functions](https://www.postgresql.org/docs/current/functions-array.html)

## Conclusion

List comprehensions are feasible to implement but require dialect-specific handling. The Postgres-style `ARRAY(SELECT ... FROM UNNEST(...))` works as a portable intermediate for most dialects, but Snowflake requires custom transformation. 

SQLGlot helps with DuckDB/BigQuery/Postgres but generates invalid Snowflake syntax, so the preparser needs dialect awareness for this feature.
