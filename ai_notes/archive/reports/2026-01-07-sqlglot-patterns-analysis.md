# SQLGlot Dialect Patterns Analysis

**Date**: 2026-01-07  
**Context**: Analyzing PRQL, DuckDB, and BigQuery pipe implementations for patterns to adopt in ASQL.

## Patterns We Already Use

### ✅ 1. TRANSFORM_PARSERS / PIPE_SYNTAX_TRANSFORM_PARSERS
- Dict mapping transform keywords to parser lambdas
- Used extensively in ASQL's `ASQLParser.TRANSFORM_PARSERS`
- Pattern: `{"KEYWORD": lambda self, query: self._parse_something(query)}`

### ✅ 2. FUNCTIONS Dict with Factories
- `build_*` factories that return callables
- `exp.Class.from_arg_list` for simple mappings
- Direct lambdas for custom arg handling

### ✅ 3. `_build_pipe_cte()` Helper
- Wraps query in CTE when transforms require it (e.g., WHERE after GROUP BY)
- We have this in ASQL dialect

### ✅ 4. CONJUNCTION/DISJUNCTION Override
- PRQL uses `DAMP` (&&) for AND, `DPIPE` (||) for OR
- ASQL already has `CONJUNCTION = {..., DAMP: exp.And}`

---

## Patterns We Should Adopt

### 🎯 1. `rename_func(name)` - Generator Transform Factory

**What it does:**
```python
def rename_func(name: str) -> t.Callable[[Generator, exp.Expression], str]:
    return lambda self, expression: self.func(name, *flatten(expression.args.values()))
```

**Use case:** When an expression type maps to a different function name in output.

**Where we should use it in ASQL:**
- Generator transforms for dialect-specific function names
- Example: If we ever need `RUNNING_SUM` to generate as `SUM() OVER (...)` in a specific way

**Current opportunity:** Low priority - we're using expression building, not generator transforms.

---

### 🎯 2. `binary_from_function(expr_type)` - Binary Op Factory

**What it does:**
```python
def binary_from_function(expr_type: t.Type[B]) -> t.Callable[[t.List], B]:
    return lambda args: expr_type(this=seq_get(args, 0), expression=seq_get(args, 1))
```

**Use case:** Creating binary expressions from function calls like `XOR(a, b)` → `a XOR b`

**Where we should use it in ASQL:**
- Currently: Not needed
- Future: If we add binary operators as functions

---

### 🎯 3. `dict.fromkeys()` for Multiple Aliases

**What it does:**
```python
FUNCTION_PARSERS = {
    **parser.Parser.FUNCTION_PARSERS,
    **dict.fromkeys(("GROUP_CONCAT", "LISTAGG", "STRINGAGG"), lambda self: self._parse_string_agg()),
}
```

**Use case:** Multiple function names that use the same parser/builder.

**Where we should use it in ASQL:**

| Functions | Shared Builder |
|-----------|----------------|
| `ARG_MAX`, `ARGMAX` | `exp.ArgMax.from_arg_list` |
| `ARG_MIN`, `ARGMIN` | `exp.ArgMin.from_arg_list` |
| `TOTAL`, `SUM` | `build_natural_agg(exp.Sum)` |
| `AVERAGE`, `AVG` | `build_natural_agg(exp.Avg)` |

**Action:** Refactor `ASQL_FUNCTION_REGISTRY` to use `dict.fromkeys()` for cleaner aliasing.

---

### 🎯 4. `FUNCTIONS.pop()` for Removing Inherited Functions

**What it does:**
```python
FUNCTIONS = {
    **parser.Parser.FUNCTIONS,
    # ... overrides
}
FUNCTIONS.pop("DATE_SUB")  # Remove inherited function
FUNCTIONS.pop("GLOB")
```

**Use case:** When a dialect shouldn't support certain base functions.

**Where we should use it in ASQL:**
- Currently: Not needed
- Future: If we need to disable certain SQL functions in ASQL mode

---

### 🎯 5. `_select_all(table)` Helper (PRQL pattern)

**What it does:**
```python
def _select_all(table: exp.Expression) -> t.Optional[exp.Select]:
    return exp.select("*").from_(table, copy=False) if table else None
```

**Use case:** Creating `SELECT * FROM table` cleanly.

**Where we should use it in ASQL:**
- `_parse_query()` when building initial query from FROM clause
- `TRANSFORM_PARSERS` for APPEND/REMOVE/INTERSECT operations

**Action:** Add this helper to simplify code in multiple places.

---

### 🎯 6. PRQL's `_parse_selection()` with `parse_method` Parameter

**What it does:**
```python
def _parse_selection(self, query, parse_method=None, append=True):
    parse_method = parse_method if parse_method else self._parse_expression
    # ... uses parse_method to parse items
```

**Use case:** Reusable selection parsing with pluggable parse strategies.

**Where we should use it in ASQL:**
- `_parse_asql_select()` - could accept custom parse_method
- `_parse_asql_extend()` - similar pattern

**Action:** Consider refactoring for DRY selection parsing.

---

### 🎯 7. PRQL's `SUM` wrapped in `COALESCE`

**What it does:**
```python
"SUM": lambda args: exp.func("COALESCE", exp.Sum(this=seq_get(args, 0)), 0),
```

**Use case:** Ensure SUM returns 0 instead of NULL for empty sets.

**Where we could use it in ASQL:**
- `RUNNING_SUM` / `ROLLING_SUM` - could wrap in COALESCE for safety
- User preference: Some may want NULL, others want 0

**Action:** Consider as optional behavior (e.g., `running_sum_or_zero`).

---

### 🎯 8. `NO_PAREN_FUNCTION_PARSERS` for Symbol-Triggered Parsing

**What it does:**
```python
NO_PAREN_FUNCTION_PARSERS = {
    "MAP": lambda self: self._parse_map(),
    "@": lambda self: exp.Abs(this=self._parse_bitwise()),  # @x → ABS(x)
}
```

**Use case:** Symbols or keywords that trigger special parsing without parentheses.

**Where we should use it in ASQL:**
- `#` for COUNT - we handle this in `_parse_unary` but could move here
- `@` for date literals - we have PLACEHOLDER_PARSERS

**Action:** Consider moving `#` COUNT handling to `NO_PAREN_FUNCTION_PARSERS`.

---

### 🎯 9. `SHOW_PARSERS` Pattern (DuckDB)

**What it does:**
```python
SHOW_PARSERS = {
    "TABLES": _show_parser("TABLES"),
    "DATABASES": _show_parser("DATABASES"),
}

def _show_parser(*args, **kwargs):
    def _parse(self):
        return self._parse_show_duckdb(*args, **kwargs)
    return _parse
```

**Use case:** Factory for creating similar statement parsers with different parameters.

**Where we could use it in ASQL:**
- Currently: Not applicable
- Future: If we add SHOW-like introspection commands

---

## Summary: Priority Actions

### ✅ High Priority (Completed)

1. **✅ Add `_select_all()` helper** for cleaner query building
   - Added as module-level helper function
   - Used in `_parse_query()` for initial query construction

2. **⏭️ `dict.fromkeys()` for function aliases** - Only use for 3+ aliases
   - SQLGlot uses this for 3+ aliases (e.g., `GROUP_CONCAT`, `LISTAGG`, `STRINGAGG`)
   - For just 2 aliases, explicit listing is cleaner and more readable
   - Kept explicit style for `SUM`/`TOTAL`, `DAYS_SINCE`/`DAY_SINCE`, etc.

### ⏭️ Medium Priority (Skipped - Not Beneficial)

3. **⏭️ Move `#` COUNT to `NO_PAREN_FUNCTION_PARSERS`** - Investigated, but current `_parse_unary()` approach is correct because:
   - `NO_PAREN_FUNCTION_PARSERS` is designed for **keyword-based** functions (like `PRIOR`, `MAP`)
   - Our `#` is tokenized as `TokenType.HASH` - a **symbol**, not a keyword
   - The current implementation is idiomatic for symbol-based shortcuts

4. **⏭️ Refactor selection parsing** with pluggable `parse_method` parameter - Skipped because:
   - `_parse_asql_select` uses special transform boundary detection
   - `_parse_asql_extend` uses simple `_parse_csv` approach
   - Different enough that shared code would add complexity without benefit

### ⏭️ Low Priority (Skipped - Not Needed)

5. **✅ SUM returns 0 for empty windows** (following PRQL)
   - `running_sum`, `rolling_sum` now return `COALESCE(SUM(...), 0)` by default
   - AVG/MIN/MAX return NULL (semantically correct) - use `running_avg(col) ?? 0` if needed
   - Source: PRQL's SQLGlot dialect does this (line 69 of `prql.py`)
   - COUNT already returns 0 for empty sets

6. **Generator transforms** - Not needed yet (using expression building)

---

## Code Changes Made (2026-01-07)

### 1. ✅ Added _select_all() helper and used it

```python
# In asql/dialect.py (module level)
def _select_all(table: exp.Expression) -> t.Optional[exp.Select]:
    """Create SELECT * FROM table expression.
    PRQL pattern for cleanly building initial queries from FROM clauses.
    """
    return exp.select("*").from_(table, copy=False) if table else None

# Used in _parse_query():
query = _select_all(from_.this)
```

### 2. ✅ Kept explicit alias style (cleaner than dict.fromkeys for 2 aliases)

```python
# In asql/functions.py - explicit is cleaner for pairs
'SUM': build_natural_agg(exp.Sum),
'TOTAL': build_natural_agg(exp.Sum),  # alias
'AVG': build_natural_agg(exp.Avg),
'AVERAGE': build_natural_agg(exp.Avg),  # alias
```

**Lesson learned**: `dict.fromkeys()` is for 3+ aliases. For pairs, explicit listing is more readable.

All tests pass (2426 passed, 53 skipped, 30 xfailed).

