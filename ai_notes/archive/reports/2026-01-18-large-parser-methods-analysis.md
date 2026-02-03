# ASQL Large Parser Methods Analysis

**Date**: 2026-01-18  
**Purpose**: Deep analysis of the 5 largest methods in ASQL's parser compared to SQLGlot's patterns

## Executive Summary

ASQL's parser has 5 methods ranging from 77-116 lines each. After comparing to SQLGlot's base parser and other dialects (PRQL, DuckDB, Snowflake), most of these methods are **justifiably longer** because they implement genuinely new syntax not in SQL. However, there are refactoring opportunities to reduce complexity.

| Method | Lines | Verdict | Refactor Priority |
|--------|-------|---------|-------------------|
| `_parse_when` | 116 | Justified - new syntax | Low (well-structured) |
| `_parse_list_comprehension` | 63 | Could simplify | Medium |
| `_apply_asql_transforms` | 95 | Justified - orchestration | Low |
| `_parse_asql_cohort` | 67 | Justified - domain-specific | Low |
| `_parse_asql_recurse` | 89 | Could extract helper | Medium |

---

## 1. `_parse_when` (116 lines)

### What It Does
Parses ASQL's `when` conditional expression - a friendlier alternative to SQL's CASE/WHEN:

```sql
-- ASQL
when status is "active" then 1, is "pending" then 0, otherwise -1

-- SQL equivalent
CASE status 
  WHEN 'active' THEN 1 
  WHEN 'pending' THEN 0 
  ELSE -1 
END
```

### SQLGlot's `_parse_case` (30 lines)

```python
def _parse_case(self) -> t.Optional[exp.Expression]:
    if self._match(TokenType.DOT, advance=False):
        self._retreat(self._index - 1)
        return None

    ifs = []
    default = None
    comments = self._prev_comments
    expression = self._parse_assignment()

    while self._match(TokenType.WHEN):
        this = self._parse_assignment()
        self._match(TokenType.THEN)
        then = self._parse_assignment()
        ifs.append(self.expression(exp.If, this=this, true=then))

    if self._match(TokenType.ELSE):
        default = self._parse_assignment()

    if not self._match(TokenType.END):
        # ... error handling
        
    return self.expression(exp.Case, comments=comments, this=expression, ifs=ifs, default=default)
```

### Why ASQL's Is Longer

1. **Dual syntax support**: ASQL's `when` supports both:
   - Simple case: `when status is "active" then 1` (base expression + values)
   - Searched case: `when age < 18 then "Minor"` (full conditions)
   
   SQL CASE also has both, but the syntax explicitly differs (`CASE expr WHEN` vs `CASE WHEN`). ASQL infers which based on the first branch.

2. **Multiple operators**: Supports `is`, `is not`, `in (...)`, and comparison operators (`<`, `>`, etc.) all in the condition position.

3. **Comma-separated branches**: ASQL uses commas instead of WHEN keywords, requiring different loop structure.

4. **AND/OR detection**: Must detect compound conditions to switch from simple to searched case mid-parse.

### Verdict: **Justified**

The method is long but well-structured with clear separation:
- Lines 983-1080: First branch detection (determines simple vs searched)
- Lines 1082-1098: Loop for remaining branches
- Helper method `_parse_when_branch` (35 lines) extracts branch parsing

**Could improve**: The initial branch detection (lines 1013-1080) has ~70 lines of branching logic. Could extract to `_parse_first_when_branch()` but readability is already acceptable.

---

## 2. `_parse_list_comprehension` (63 lines)

### What It Does
Parses Python-style list comprehensions:

```sql
-- ASQL
[x * 2 for x in numbers if x > 0]

-- SQL equivalent (Postgres)
ARRAY(SELECT x * 2 FROM UNNEST(numbers) AS x WHERE x > 0)
```

### SQLGlot's `_parse_comprehension` (20 lines)

```python
def _parse_comprehension(self, this: t.Optional[exp.Expression]) -> t.Optional[exp.Comprehension]:
    index = self._index
    expression = self._parse_column()
    position = self._match(TokenType.COMMA) and self._parse_column()

    if not self._match(TokenType.IN):
        self._retreat(index - 1)
        return None
    
    iterator = self._parse_column()
    condition = self._parse_assignment() if self._match_text_seq("IF") else None
    return self.expression(
        exp.Comprehension,
        this=this,
        expression=expression,
        position=position,
        iterator=iterator,
        condition=condition,
    )
```

### Why ASQL's Is Longer

1. **Lookahead detection**: `_is_list_comprehension()` (15 lines) needs to look ahead to distinguish `[x for x in arr]` from `[1, 2, 3]` (array literal).

2. **Dialect-specific output**: DuckDB supports native comprehension syntax; other dialects need `ARRAY(SELECT ... FROM UNNEST(...))`. This logic adds ~30 lines.

3. **`_comprehension_to_array_select`** helper: 30 additional lines building the SELECT subquery.

### Verdict: **Could Simplify**

The comprehension-to-SELECT conversion could move to a post-parse transform (like SQLGlot's `transforms.py`), leaving the parser focused purely on syntax recognition.

**Recommendation**:
- Parser should just produce `exp.Array(expressions=[exp.Comprehension(...)])`
- Move dialect-specific conversion to `asql/compiler/list_comprehension.py` (which partially exists)

---

## 3. `_apply_asql_transforms` (95 lines)

### What It Does
Orchestrates all ASQL AST transforms after parsing:

```python
def _apply_asql_transforms(self, stmt: exp.Expression) -> exp.Expression:
    # 1. Read settings
    extend_dialect = self._get_setting("extend_dialect")
    schema = self._get_setting("schema")
    # ... 8 more settings
    
    # 2. Build CompileSettings
    settings = CompileSettings(...)
    
    # 3. Apply transforms in order
    stmt = apply_since_until_underscore_shorthands(stmt, settings)
    stmt = apply_implicit_function_aliases(stmt, settings)
    stmt = apply_auto_aliasing(stmt, settings)
    # ... 8 more transforms
    
    return stmt
```

### SQLGlot's Approach

SQLGlot separates transforms into:
1. **Generator transforms** - applied during SQL generation, not parsing
2. **`transforms.py`** - standalone functions that can be composed
3. **Optimizer passes** - `optimizer/qualify.py`, `optimizer/eliminate_ctes.py`, etc.

Each transform is ~20-50 lines and called independently.

### Why ASQL's Is Longer

1. **Settings extraction**: ~25 lines reading 10+ settings from dialect
2. **CompileSettings construction**: ~15 lines building the config object
3. **Import statements**: ~10 lines importing all transform functions
4. **Sequential application**: ~45 lines of ordered transform calls with conditionals

### Verdict: **Justified - Orchestration Code**

This method is fundamentally different from parsing methods - it's a configuration/orchestration function. The length comes from having many transforms, not from complexity.

**Could improve**:
1. Move settings extraction to a dedicated `_build_compile_settings()` method
2. Use a TRANSFORMS list with metadata instead of sequential if/else:

```python
ORDERED_TRANSFORMS = [
    (apply_underscore_shorthands, {"needs_schema": False}),
    (apply_auto_aliasing, {"needs_schema": False}),
    (transform_fk_shorthand, {"needs_schema": True}),
    # ...
]
```

But current form is readable and transform order is critical, so explicit ordering is defensible.

---

## 4. `_parse_asql_cohort` (67 lines + 35 lines helper)

### What It Does
Parses cohort analysis syntax:

```sql
-- ASQL
from orders
cohort by month(users.signup_date) on user_id

-- Generates complex CTEs for retention analysis
```

### SQLGlot Equivalent

**None** - Cohort analysis is domain-specific syntax that no SQL dialect has natively. The closest is dbt's cohort macros or custom CTEs.

### Why It's This Size

1. **Complex grammar**: `cohort by [segments,] <granularity_func>(<column>) [on <join_key>]`
2. **Granularity extraction**: Must parse function calls like `month(date_col)` and extract both the function and its argument
3. **Multiple expression types**: Handles `exp.Month`, `exp.Week`, `exp.Day`, `exp.Anonymous`, etc.
4. **Helper method**: `_extract_granularity_from_expr` (35 lines) handles all function expression types

### Verdict: **Justified - Domain-Specific**

This parses genuinely new syntax. There's no SQL equivalent to compare against.

**Could improve**: The `_extract_granularity_from_expr` helper has repetitive isinstance checks:

```python
if isinstance(expr, exp.Month):
    return ("month", expr.this)
if isinstance(expr, exp.Week):
    return ("week", expr.this)
# ... etc
```

Could refactor to:

```python
GRANULARITY_EXPR_TYPES = {
    exp.Month: "month",
    exp.Week: "week",
    exp.Day: "day",
    exp.Year: "year",
    exp.Quarter: "quarter",
}

for expr_type, name in GRANULARITY_EXPR_TYPES.items():
    if isinstance(expr, expr_type):
        return (name, expr.this)
```

---

## 5. `_parse_asql_recurse` (89 lines)

### What It Does
Parses recursive traversal syntax:

```sql
-- ASQL
from employees where id = 1 recurse(manager_id)

-- SQL equivalent
WITH RECURSIVE _recurse_employees AS (
  SELECT *, 1 AS _level FROM employees WHERE id = 1
  UNION ALL
  SELECT e.*, r._level + 1
  FROM employees e
  JOIN _recurse_employees r ON e.manager_id = r.id
  WHERE r._level < 100
)
SELECT * FROM _recurse_employees
```

### SQLGlot's CTE Parsing

SQLGlot's `_parse_cte` is ~40 lines but only parses the `WITH RECURSIVE name AS (...)` structure. It doesn't generate CTEs from shorthand.

### Why ASQL's Is Longer

1. **Parameter parsing**: FK column and optional max_depth (~20 lines)
2. **AST extraction**: Gets table name and WHERE condition from existing query (~15 lines)
3. **Anchor query construction**: Builds `SELECT *, 1 AS _level FROM table WHERE ...` (~10 lines)
4. **Recursive query construction**: Builds the JOIN portion (~20 lines)
5. **CTE assembly**: Combines with UNION ALL and wraps in WITH RECURSIVE (~15 lines)

### Verdict: **Could Extract Helper**

The method does three distinct things:
1. Parse the `recurse(fk_col, max_depth)` arguments
2. Extract context from the existing query
3. Build the recursive CTE AST

**Recommendation**: Split into:

```python
def _parse_asql_recurse(self, query: exp.Query) -> exp.Query:
    args = self._parse_recurse_args()  # Returns (fk_col, max_depth)
    context = self._extract_recurse_context(query)  # Returns (table_name, anchor_condition)
    return self._build_recursive_cte(args, context)  # Returns new query with CTE
```

Each helper would be ~25-30 lines, much more testable.

---

## Comparison: PRQL's Approach

PRQL (another SQL alternative in SQLGlot) uses highly declarative patterns:

```python
class Parser(parser.Parser):
    TRANSFORM_PARSERS = {
        "DERIVE": lambda self, query: self._parse_selection(query),
        "SELECT": lambda self, query: self._parse_selection(query, append=False),
        "TAKE": lambda self, query: self._parse_take(query),
        "FILTER": lambda self, query: query.where(self._parse_disjunction()),
        # ...
    }
```

Each handler is 1-10 lines. ASQL uses a similar pattern for transforms but has more complex syntax requiring larger methods.

**Key insight**: PRQL's syntax is closer to SQL (just reordered). ASQL adds genuinely new constructs (`when`, `cohort`, `recurse`) that require more parsing logic.

---

## Recommendations Summary

### High Priority
1. **`_parse_list_comprehension`**: Move dialect-specific conversion to compiler transform
2. **`_parse_asql_recurse`**: Split into parse/extract/build helpers

### Medium Priority
3. **`_parse_asql_cohort`**: Refactor `_extract_granularity_from_expr` to use dict mapping

### Low Priority (Already Acceptable)
4. **`_parse_when`**: Could extract `_parse_first_when_branch` but not necessary
5. **`_apply_asql_transforms`**: Consider transform registry pattern, but explicit ordering is fine

---

## Appendix: Line Counts Compared

| Parser | _parse_case equivalent | Comprehension | Recursive CTE |
|--------|----------------------|---------------|---------------|
| SQLGlot base | 30 lines | 20 lines | N/A (just parses WITH) |
| PRQL | N/A | N/A | N/A |
| DuckDB | inherits base | inherits base | inherits base |
| ASQL | 116 lines | 63 lines | 89 lines |

The size difference is explained by ASQL implementing **new syntax** rather than parsing existing SQL patterns.
