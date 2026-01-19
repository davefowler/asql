# List Comprehension Implementation Analysis

**Date**: 2026-01-18  
**Issue**: ASQL's list comprehension parsing is 102+ lines. Why?

## SQLGlot's Built-in Support

SQLGlot already has `exp.Comprehension` and `_parse_comprehension()`:

```python
# SQLGlot's _parse_comprehension - 15 lines!
def _parse_comprehension(self, this):
    index = self._index
    expression = self._parse_column()  # the loop variable
    position = self._match(TokenType.COMMA) and self._parse_column()
    if not self._match(TokenType.IN):
        self._retreat(index - 1)
        return None
    iterator = self._parse_column()  # the array
    condition = self._parse_assignment() if self._match_text_seq("IF") else None
    return exp.Comprehension(this=this, expression=expression, ...)
```

DuckDB uses this and it works:
```python
>>> sqlglot.parse_one('[x * 2 FOR x IN arr IF x > 0]', dialect='duckdb')
# Returns: Array(expressions=[Comprehension(...)])
```

## What ASQL Does Instead (102 lines)

ASQL's `_parse_list_comprehension()` does:

1. **Manual token collection** (lines 1285-1303) - Collects tokens until `FOR`
2. **Manual FOR parsing** (lines 1308-1312) - Checks for `FOR` keyword  
3. **Manual variable parsing** (lines 1314-1318)
4. **Manual IN parsing** (lines 1320-1324)
5. **Manual IF parsing** (lines 1332-1349) - Collects tokens again
6. **String-based re-parsing** (lines 1356-1362) - Parses collected tokens as strings!
7. **AST construction** (lines 1364-1378) - Builds `ARRAY(SELECT ... FROM UNNEST(...))`

### The Key Problem

ASQL converts at **parse time**:
```
[x * 2 for x in arr]  →  ARRAY(SELECT x * 2 FROM UNNEST(arr) AS x)
```

But SQLGlot's approach is:
```
[x * 2 for x in arr]  →  exp.Array(Comprehension(...))  →  dialect-specific SQL in generator
```

## Why This Matters

1. **DuckDB** - Supports native `[expr FOR var IN arr]` syntax
2. **BigQuery** - Uses `ARRAY(SELECT ... FROM UNNEST(...))`  
3. **Postgres** - Uses `ARRAY(SELECT ... FROM UNNEST(...))`
4. **Snowflake** - Doesn't support (needs error or workaround)

By converting at parse time, ASQL loses the ability to generate dialect-optimal output.

## The Fix

**Option 1: Use SQLGlot's `_parse_comprehension`** (Recommended)
- Override `_parse_bracket` to call `_parse_comprehension` 
- Keep `exp.Comprehension` in AST
- Let generators handle dialect conversion
- **Saves ~85 lines**

**Option 2: Keep current approach but simplify**
- Use `self._parse_expression()` instead of manual token collection
- Remove string-based re-parsing
- **Saves ~40 lines**

## Wait - There's a Twist!

Testing reveals SQLGlot's `Comprehension` generates:
```sql
-- DuckDB:   [LOWER(x) FOR x IN tags]     ✅ Valid DuckDB
-- Postgres: ARRAY[LOWER(x) FOR x IN tags] ❌ NOT VALID POSTGRES!
-- BigQuery: [LOWER(x) FOR x IN tags]     ✅ Valid BigQuery
```

**Postgres doesn't support comprehension syntax!** It needs:
```sql
ARRAY(SELECT LOWER(x) FROM UNNEST(tags) AS x)  -- Standard SQL
```

ASQL's current approach (`ARRAY(SELECT ... FROM UNNEST(...))`) is actually **more portable**!

## Comparison

| Approach | Lines | DuckDB | Postgres | BigQuery | Snowflake |
|----------|-------|--------|----------|----------|-----------|
| SQLGlot Comprehension | 15 | ✅ Native | ❌ Invalid! | ✅ Native | ❌ Invalid |
| ASQL ARRAY(SELECT..) | 102 | ⚠️ Works | ✅ Works | ✅ Works | ❌ Invalid |
| Ideal | ~30 | ✅ Native | ✅ SELECT | ✅ Native | ❌ Error |

## Additional Code

ASQL also has post-processing in `list_comprehension.py` (66 lines) to:
- Fix DuckDB output (convert ARRAY(SELECT...) back to native syntax)
- Detect/error on Snowflake

With Option 1, this post-processing would be unnecessary - generators would handle it.

## Revised Recommendation

ASQL's approach (`ARRAY(SELECT ... FROM UNNEST(...))`) is **correct for portability**!

The problem isn't the approach - it's the **implementation verbosity**:

### Current Problems (102 lines)
1. **Manual token collection** - Should use `_parse_expression()` 
2. **String re-parsing** - Collects tokens, joins to string, re-parses. Wasteful!
3. **FOR/IN/IF manual detection** - Parser primitives exist for this

### Simplified Implementation (~30 lines)

```python
def _parse_list_comprehension(self) -> exp.Expression:
    """Parse [expr for var in arr if cond] → ARRAY(SELECT expr FROM UNNEST(arr) AS var WHERE cond)"""
    self._advance()  # consume [
    
    # Parse expression until FOR
    expr = self._parse_assignment()
    
    if not self._match_text_seq("FOR"):
        # Not a comprehension, might be array literal
        ...
        
    var = self._parse_id_var()
    self._match_text_seq("IN")
    iterator = self._parse_column()
    
    condition = self._parse_assignment() if self._match_text_seq("IF") else None
    self._match(TokenType.R_BRACKET)
    
    # Build ARRAY(SELECT ... FROM UNNEST(...) WHERE ...)
    unnest = exp.Unnest(expressions=[iterator], alias=exp.TableAlias(this=var))
    select = exp.Select(expressions=[expr], from_=exp.From(this=unnest))
    if condition:
        select.set("where", exp.Where(this=condition))
    return exp.Array(expressions=[select])
```

### Post-processing still needed

`list_comprehension.py` (66 lines) converts to native DuckDB syntax:
```sql
ARRAY(SELECT x FROM UNNEST(arr))  →  [x FOR x IN arr]
```

This could move to DuckDB generator instead, saving the post-processing.

**Actual savings: ~45 lines** (102→57 in parser)

## ✅ IMPLEMENTED

The simplified implementation has been merged:
- Uses SQLGlot's `_parse_assignment()` which returns `exp.Comprehension`
- For DuckDB: keeps as `exp.Array(Comprehension)` → native `[x FOR x IN arr]` syntax
- For others: converts to `ARRAY(SELECT ... FROM UNNEST(...))` via `_comprehension_to_array_select()`

All 21 list comprehension tests pass.

### Alternative: Hybrid Approach

1. Parse as `exp.Comprehension` (SQLGlot native)
2. In ASQL generator, convert to `ARRAY(SELECT...)` for non-DuckDB
3. Let DuckDB generator keep native syntax

This would be cleaner but requires generator changes.
