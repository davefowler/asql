# `asql/compiler/api.py` - When Is It Needed?

## The Two APIs

### `sqlglot.transpile(query, read="asql", write="postgres")`
- Parses ASQL → AST
- Generates SQL for target dialect
- **Does NOT apply output-dialect transforms**

### `asql.compile(query, dialect="postgres")`  
- Parses ASQL → AST
- **Applies output-dialect transforms** (auto-spine, alias reuse, list comprehensions, column operators)
- Generates SQL for target dialect

## They Produce DIFFERENT Output!

```python
query = 'from orders group by month(date)'

# sqlglot.transpile() - NO transforms
SELECT * FROM orders GROUP BY MONTH(date)

# asql.compile() - WITH auto-spine transform
WITH col_0_spine AS (/* Date spine... */)
SELECT ... FROM col_0_spine LEFT JOIN ...
```

## When to Use Each

### Use `asql.compile()` when you need:
| Feature | Why |
|---------|-----|
| Auto-spine | Generates gap-filling CTEs for date GROUP BY |
| Alias reuse | `select a+1 as b, b+1 as c` → CTE chain for non-DuckDB |
| List comprehensions | `[x FOR x IN arr]` → `ARRAY(SELECT...)` for non-DuckDB |
| Column operators | `* EXCEPT col` → explicit columns for non-supporting dialects |

### Use `sqlglot.transpile()` when:
- You only need basic ASQL → SQL conversion
- You're testing parser syntax, not output transforms
- You want minimal overhead

## Current State

### Playground: **BUG** - Uses transpile(), missing transforms!
```python
# playground/app.py line 250 - WRONG!
results = sqlglot.transpile(request.asql, read=asql_dialect, write=request.dialect)
```

Should use:
```python
from asql import compile
sql = compile(request.asql, dialect=request.dialect, **settings)
```

### Tests Using asql.compile():
- `test_auto_spine.py` - ✓ NEEDS compile (tests auto-spine)
- `test_alias_reuse.py` - ✓ NEEDS compile (tests alias reuse)
- `test_column_operators_fallback.py` - ✓ NEEDS compile (tests EXCEPT expansion)
- `test_list_comprehension.py` - ✓ NEEDS compile (tests dialect-specific output)
- `test_basic.py` - Could use transpile (basic syntax)
- `test_arithmetic.py` - Could use transpile (basic ops)

### Tests Using transpile():
- `tests/dialects/*` - via `ASQLValidator.validate_asql()` which calls `asql_compile`

## Key Concepts

### `extend_dialect` (INPUT)
- What SQL syntax is **allowed inside** ASQL queries
- Set on ASQL dialect: `ASQL(extend_dialect="duckdb")`
- Example: `extend_dialect="duckdb"` allows `[x FOR x IN arr]` syntax

### `output_dialect` / `write` (OUTPUT)  
- What SQL dialect to **generate**
- Passed to `compile(dialect=...)` or `transpile(write=...)`
- Used by transforms to decide what SQL patterns to emit

**These can be different!** You might allow DuckDB syntax in input but generate Postgres output.

## Why api.py Still Exists

The output-dialect transforms **cannot** move to the parser because:
1. Parser runs BEFORE we know the output dialect
2. `sqlglot.transpile()` flow: parse(read) → generate(write)
3. Parser only sees `extend_dialect` (input), not write dialect (output)

The transforms need to run AFTER parsing but BEFORE generation, knowing the output dialect.
This is what `asql.compile()` does.

## Options to Simplify

### Option A: Keep separate (current)
- `asql.compile()` for full features
- `sqlglot.transpile()` for basic conversion
- Requires users to know the difference

### Option B: Move transforms to parser with `output_dialect` setting
```python
asql = ASQL(extend_dialect="duckdb", output_dialect="postgres")
sqlglot.transpile(query, read=asql, write="postgres")  # transforms now run in parser
```
Requires passing output dialect twice (redundant but works).

### Option C: Hook into SQLGlot's optimize phase
Create custom optimizer rules that run during transpile.
Complex, may not be supported cleanly.

## Immediate TODOs

1. **Fix playground** - Use `asql.compile()` instead of `sqlglot.transpile()`
2. **Document clearly** which tests need compile vs transpile
3. **Consider Option B** for cleaner API long-term
