# Plan: `asql.transpile()` and Explicit Spine Syntax

**Date**: 2026-01-18  
**Author**: AI (with Dave's direction)  
**Status**: APPROVED - Ready for implementation

---

## Background: The Realization

`sqlglot.transpile()` does NOT automatically run optimizer, qualify, or any intermediate transform stages. It's just:

```
parse(read_dialect) → generate(write_dialect)
```

That's it. No transforms in between.

Currently ALL transforms are crammed into `ASQLParser._apply_asql_transforms()` which runs 10 transforms in the parser. This is wrong because:
1. Some transforms need the OUTPUT dialect (alias_reuse, column_operators)
2. Parser shouldn't import from `asql.compiler.*`
3. 35+ settings references in parser (other dialects have 0)

---

## Full Transform & Syntax Inventory

### Part A: Post-Parse Transforms (in `_apply_asql_transforms()`)

| # | Transform | Module | What It Does | Needs Dialect? | Needs Schema? | Custom AST? |
|---|-----------|--------|--------------|----------------|---------------|-------------|
| 1 | `apply_since_until_underscore_shorthands` | underscore_shorthands.py | `days_since_created_at` → DATEDIFF | ❌ | Optional | ❌ No - rewrite only |
| 2 | `apply_implicit_function_aliases` | underscore_shorthands.py | Auto-name functions | ❌ | ❌ | ❌ No - rewrite only |
| 3 | `apply_auto_aliasing` | auto_alias.py | Auto-alias unaliased exprs | ❌ | ❌ | ❌ No - rewrite only |
| 4 | `transform_fk_shorthand` | join_fk_shorthand.py | `ON user_id` → full condition | ❌ | ✅ | ❌ No - rewrite only |
| 5 | `transform_cohort` | cohort_transform.py | `cohort by` → CTEs + JOINs | ❌ | ❌ | ✅ Create `exp.CohortBy` |
| 6 | `auto_qualify_columns` | auto_qualify.py | Expand `*` in JOINs | ❌ | ❌ | ❌ No - rewrite only |
| 7 | `apply_alias_reuse` | alias_reuse.py | `a+1 as b, b+1` → CTE chain | ✅ DuckDB native | ❌ | ❌ No - rewrite only |
| 8 | list comprehensions | (inline in parser) | `[x FOR x IN arr]` → ARRAY(SELECT) | ✅ DuckDB native | ❌ | ✅ Uses `exp.Comprehension` |
| 9 | `_apply_auto_spine` | auto_spine.py | Gap-filling CTEs | ✅ generate_series | ❌ | ⚠️ Uses `guarantee()` hack |
| 10 | `_remove_guarantee_wrappers` | auto_spine.py | Cleanup guarantee() | ❌ | ❌ | - |
| 11 | `transform_column_operators_for_dialect` | column_operators.py | `* EXCEPT` expansion | ✅ | ✅ | ✅ Uses `exp.Star.except_` |

### Part B: Parser-Level Syntax (TRANSFORM_PARSERS)

| Keyword | What It Does | Creates AST | Custom Node? |
|---------|--------------|-------------|--------------|
| `WHERE` | Filter rows | `exp.Where` | ❌ Standard |
| `SELECT` | Choose columns | `exp.Select` | ❌ Standard |
| `LIMIT` | Limit rows | `exp.Limit` | ❌ Standard |
| `OFFSET` | Skip rows | `exp.Offset` | ❌ Standard |
| `ORDER BY` | Sort with `-col` shorthand | `exp.Order` | ❌ Standard |
| `GROUP BY` | Group with `(aggs)` syntax | `exp.Group` | ❌ Standard |
| `HAVING` | Filter groups | `exp.Having` | ❌ Standard |
| `QUALIFY` | Filter windows | `exp.Qualify` | ❌ Standard |
| `EXTEND` | Add computed columns | modifies select | ❌ Standard |
| `EXPLODE` | Unnest arrays | `exp.Lateral` + `exp.Explode` | ❌ Standard |
| `STASH` | Named CTE | `exp.CTE` | ❌ Standard |
| `JOIN`, `LEFT`, etc. | Standard joins | `exp.Join` | ❌ Standard |
| `&`, `&?`, etc. | Symbolic joins | `exp.Join` | ❌ Just syntax sugar |
| `DISTINCT` | Dedupe | `exp.Distinct` | ❌ Standard |
| `EXCEPT` | Column exclusion | `exp.Star.except_` | ✅ SQLGlot built-in |
| `RENAME` | Column rename | modifies select | ❌ Rewrite only |
| `REPLACE` | Column replace | modifies select | ❌ Rewrite only |
| `COHORT` | Cohort analysis | `exp.CohortBy` clause | ✅ Create new node |
| `PER` | Partition windowing | `exp.Window` | ❌ Standard |
| `RECURSE` | Recursive CTEs | `exp.With` | ❌ Standard |
| `UNION`, etc. | Set operations | `exp.Union`, etc. | ❌ Standard |

### Part C: Special Functions (in FUNCTIONS dict)

| Function | What It Does | Custom Node? |
|----------|--------------|--------------|
| `#` / `count()` | Count shorthand | ❌ → `exp.Count` |
| `guarantee(col, ...)` | Mark for explicit spine | ⚠️ `exp.Anonymous` hack |
| `prior()` / `next()` | Window LAG/LEAD | ❌ → `exp.Lag`/`exp.Lead` |
| `running_*()` | Running aggregates | ❌ → window functions |
| `days_since()`, etc. | Date diffs | ❌ → `exp.DateDiff` |
| `[x FOR x IN arr]` | List comprehension | ✅ `exp.Comprehension` |

---

## Which Need Custom AST Nodes?

| Feature | Current Approach | Should Have AST Node? | Recommendation |
|---------|------------------|----------------------|----------------|
| **Spine** | Auto-detect date funcs / `guarantee()` hack | ✅ **YES** | New `exp.Spine(this=col)` |
| **Cohort** | `_cohort_info` attribute on Select | ✅ **YES** | New `exp.CohortBy(...)` |
| **Guarantee** | `exp.Anonymous("guarantee", ...)` | → Replaced by Spine | Delete, use `spine()` |
| **List Comp** | `exp.Comprehension` (SQLGlot built-in) | ✅ Already exists | Keep using it |
| **Column Exclude** | `exp.Star(except_=[...])` (SQLGlot) | ✅ Already exists | Keep using it |
| **Alias Reuse** | Detect refs in same SELECT | ❌ No need | Just AST analysis |
| **FK Shorthand** | `ON column` → detect single column | ❌ No need | Just AST pattern |
| **Underscore Shorthands** | Pattern match identifiers | ❌ No need | Just text pattern |

### Summary: New AST Nodes Needed

**Create:**
1. `exp.Spine` - mark columns for gap-filling
2. `exp.CohortBy` - cohort analysis clause (replaces `_cohort_info` attribute hack)

**Delete:**
3. `guarantee()` function - replaced by `spine()`

### Why `exp.CohortBy` instead of attribute?

Current approach has problems:
- `_cohort_info` attribute doesn't survive `.copy()` calls
- Had to add special handling in `auto_alias.py` to preserve it
- Not visible in AST (hard to debug/inspect)
- Non-standard and fragile

New approach:
```python
class CohortBy(exp.Expression):
    """Cohort analysis clause: cohort by month(users.signup_date) on user_id"""
    arg_types = {
        "this": True,           # Cohort column expr: month(users.signup_date)
        "granularity": False,   # Extracted: "month"
        "join_key": False,      # Join key: user_id
        "segments": False,      # Optional segments
    }
```

Parser creates:
```python
query.set("cohort", exp.CohortBy(
    this=exp.Month(this=exp.Column(table="users", this="signup_date")),
    granularity=exp.Literal.string("month"),
    join_key=exp.to_identifier("user_id"),
))
```

Transform reads:
```python
cohort = stmt.args.get("cohort")
if isinstance(cohort, exp.CohortBy):
    # Build CTEs and JOINs
```

Benefits:
- Survives `.copy()` automatically
- Visible in AST for debugging
- Standard SQLGlot pattern
- No special-case attribute handling needed

---

## Proposal: `asql.transpile()`

Create ONE entry point that handles everything:

```python
def transpile(
    sql: str,
    read: str | Dialect = None,
    write: str | Dialect = None,
    pretty: bool = False,
    schema: dict = None,
    **kwargs
) -> list[str]:
    """
    Transpile SQL between dialects with full ASQL transform support.
    
    For non-ASQL read dialects: just calls sqlglot.transpile()
    For ASQL/VisualASQL: adds transforms between parse and generate
    """
```

### Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        asql.transpile() Pipeline                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  IF read NOT in (asql, visual_asql):                                        │
│      return sqlglot.transpile(sql, read, write, **kwargs)  # passthrough    │
│                                                                             │
│  ELSE (ASQL pipeline):                                                      │
│                                                                             │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │   PARSER     │ ──► │  TRANSFORMS  │ ──► │  GENERATOR   │                │
│  │   (ASQL)     │     │  (dialect-   │     │  (target)    │                │
│  │              │     │   aware)     │     │              │                │
│  └──────────────┘     └──────────────┘     └──────────────┘                │
│                                                                             │
│  Parser transforms:    Post-parse transforms:    ast.sql(dialect=write)    │
│  - underscore short    - spine_transform                                    │
│  - auto_alias          - alias_reuse                                        │
│  - fk_shorthand        - column_operators                                   │
│  - cohort              - list_comprehension                                 │
│  - auto_qualify                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Where Transforms Belong

**Stay in Parser** (don't need output dialect):
- underscore_shorthands
- auto_alias  
- fk_shorthand (needs schema, not dialect)
- cohort_transform
- auto_qualify_columns

**Move to `asql.transpile()`** (need output dialect):
- spine_transform (generate_series varies by dialect)
- alias_reuse (DuckDB supports natively)
- column_operators (some dialects support EXCEPT)
- list_comprehension (DuckDB supports natively)

### Implementation Location

```
asql/
├── __init__.py          # exports transpile
├── transpile.py         # NEW: asql.transpile() implementation
└── compiler/            # Keep existing, but parser stops calling dialect-aware ones
```

---

## Proposal: Explicit Spine Syntax

**Decision**: Remove `auto_spine` setting entirely. Make spine explicit.

### Syntax 1: `spine by` keyword (like `group by`)

```sql
-- Full spine: all columns get gap-filling
from orders spine by month(created_at) (sum(amount))
```

This reads naturally: "from orders, spine by month of created_at, calculating sum of amount"

### Syntax 2: `spine()` function in GROUP BY

```sql
-- Mixed: only month gets spine treatment, region is regular GROUP BY
from orders group by spine(month(created_at)), region (sum(amount))
```

### Both Syntaxes Supported

- `spine by X, Y (aggs)` → all columns get gap-filling
- `group by spine(X), Y (aggs)` → only X gets gap-filling

### AST Design: New `exp.Spine` Node

Create a custom expression type to mark columns for spine treatment:

```python
# In asql/expressions.py (new file)
from sqlglot import exp

class Spine(exp.Func):
    """Marker for columns that need gap-filling spine treatment.
    
    Used by both syntaxes:
    - spine by month(x) → GROUP BY Spine(month(x))
    - group by spine(month(x)) → GROUP BY Spine(month(x))
    """
    arg_types = {"this": True}
```

**Why a new AST node?**
1. Parser can create `Spine(column)` for both syntaxes
2. Transform stage just looks for `exp.Spine` nodes
3. No heuristics or magic detection needed
4. Clean separation: parser marks intent, transform implements

### Parser Implementation

```python
class ASQLParser(Parser):
    TRANSFORM_PARSERS = {
        TokenType.SPINE: lambda self: self._parse_spine_by(),
        ...
    }
    
    FUNCTIONS = {
        **parent.FUNCTIONS,
        "SPINE": lambda args: exp.Spine(this=seq_get(args, 0)),
    }
    
    def _parse_spine_by(self) -> exp.Select:
        """Parse: spine by col1, col2 (aggregations)
        
        Converts to GROUP BY with each column wrapped in Spine()
        """
        self._match(TokenType.BY)  # consume 'by'
        
        columns = []
        while True:
            col = self._parse_conjunction()
            columns.append(exp.Spine(this=col))  # Wrap in Spine
            if not self._match(TokenType.COMMA):
                break
        
        # Parse aggregations in parens
        aggs = self._parse_aggregate_parens()
        
        # Build SELECT with GROUP BY
        return exp.Select(
            expressions=aggs,
            from_=...,
            group=exp.Group(expressions=columns)
        )
```

### Transform Implementation

```python
def transform_spine(ast: exp.Expression, dialect: str, schema=None) -> exp.Expression:
    """Generate gap-filling CTEs for Spine() expressions in GROUP BY.
    
    For each Spine(column) in GROUP BY:
    1. Generate a CTE with all possible values (date sequence or DISTINCT)
    2. LEFT JOIN the main query to the spine
    3. Replace Spine(column) with column in final GROUP BY
    """
    for group in ast.find_all(exp.Group):
        spine_cols = [e for e in group.expressions if isinstance(e, exp.Spine)]
        if not spine_cols:
            continue
        
        for spine in spine_cols:
            inner_col = spine.this
            
            # Generate spine CTE based on column type
            if _is_date_trunc(inner_col):
                cte = _build_date_spine_cte(inner_col, dialect)
            else:
                cte = _build_categorical_spine_cte(inner_col, ast)
            
            # Add CTE and modify query structure
            ast = _add_spine_cte_and_join(ast, cte, spine)
    
    return ast
```

---

## Migration Plan

### Phase 1: Create `asql.transpile()` 

1. Create `asql/transpile.py` with the new pipeline
2. Export from `asql/__init__.py` as `transpile`
3. Move dialect-aware transforms OUT of parser `_apply_asql_transforms()`
   - Keep: underscore_shorthands, auto_alias, fk_shorthand, cohort, auto_qualify
   - Move to transpile.py: alias_reuse, list_comprehension, column_operators
4. Update `tests/fixtures.py` to use `asql.transpile()`
5. Update `playground/app.py` to use `asql.transpile()`

### Phase 2: Implement Explicit Spine Syntax

1. Create `asql/expressions.py` with `class Spine(exp.Func)`
2. Add `SPINE` token to tokenizer
3. Add `spine by` parsing to parser (creates `Spine()` wrapped columns)
4. Add `spine()` function to parser FUNCTIONS dict
5. Create `transform_spine()` that processes `exp.Spine` nodes
6. Delete `auto_spine` setting entirely
7. Update all tests that used implicit auto_spine

### Phase 3: Cleanup

1. Remove `_apply_auto_spine` from parser
2. Remove `auto_spine` setting from config
3. Update docs (spec.md, syntax/dates.md, concepts/guaranteed-groups.md)

---

## Decisions Made

| Decision | Answer |
|----------|--------|
| Function name | `asql.transpile()` |
| Spine syntaxes | Both: `spine by` AND `group by spine()` |
| auto_spine setting | DELETE - explicit spine only |
| Backward compat | None needed - no users |
| AST approach | New `exp.Spine` node class |

---

## Transform Order in `asql.transpile()`

```python
# After parsing, before generation:

# 1. Spine transform (needs dialect for generate_series syntax)
ast = transform_spine(ast, dialect, schema)

# 2. Alias reuse (DuckDB native, others need CTE chain)
ast = transform_alias_reuse(ast, dialect)

# 3. Column operators (expand * EXCEPT for unsupported dialects)
ast = transform_column_operators(ast, dialect, schema)

# 4. List comprehension (DuckDB native, others need ARRAY(SELECT))
ast = transform_list_comprehension(ast, dialect)
```

---

## Code Sketch

```python
# asql/transpile.py

import sqlglot
from sqlglot import exp
from typing import Union

from asql.dialect import ASQL

def transpile(
    sql: str,
    read: Union[str, ASQL] = "asql",
    write: str = "duckdb",
    pretty: bool = False,
    schema: dict = None,
    **kwargs
) -> list[str]:
    """Transpile SQL with full ASQL support.
    
    For ASQL/VisualASQL input: applies dialect-aware transforms between parse and generate.
    For other inputs: passthrough to sqlglot.transpile().
    
    Args:
        sql: SQL string to transpile
        read: Source dialect (default: "asql")
        write: Target dialect (default: "duckdb")
        pretty: Format output
        schema: Schema dict for column operators, joins, etc.
        **kwargs: Passed to ASQL dialect constructor
    
    Returns:
        List of SQL strings (usually one element)
    """
    # Determine if this is ASQL input
    read_name = _get_dialect_name(read)
    
    # Non-ASQL: passthrough to sqlglot
    if read_name not in ("asql", "visual_asql"):
        return sqlglot.transpile(sql, read=read, write=write, pretty=pretty)
    
    # Build ASQL dialect with settings
    if isinstance(read, str):
        if schema:
            kwargs['schema'] = schema
        asql_dialect = ASQL(**kwargs) if kwargs else "asql"
    else:
        asql_dialect = read
    
    # Parse with ASQL (runs parser-stage transforms)
    asts = sqlglot.parse(sql, dialect=asql_dialect)
    
    results = []
    for ast in asts:
        if ast is None:
            continue
        
        # Apply dialect-aware transforms
        ast = _apply_dialect_transforms(ast, write, schema)
        
        # Generate output
        sql_out = ast.sql(dialect=write, pretty=pretty)
        results.append(sql_out)
    
    return results


def _apply_dialect_transforms(
    ast: exp.Expression,
    dialect: str,
    schema: dict = None,
) -> exp.Expression:
    """Apply transforms that need to know the output dialect."""
    
    from asql.compiler.alias_reuse import apply_alias_reuse
    from asql.compiler.column_operators import transform_column_operators_for_dialect
    from asql.compiler.list_comprehension import fix_duckdb_list_comprehensions
    from asql.config import CompileSettings
    
    # Import spine transform (new)
    from asql.compiler.spine import transform_spine
    
    settings = CompileSettings(schema=schema) if schema else CompileSettings()
    
    # 1. Spine transform (process exp.Spine nodes)
    ast = transform_spine(ast, dialect, schema)
    
    # 2. Alias reuse (DuckDB supports native, others need CTEs)
    ast = apply_alias_reuse(ast, dialect=dialect)
    
    # 3. Column operators (expand EXCEPT for unsupported dialects)
    ast = transform_column_operators_for_dialect(ast, dialect, settings)
    
    # 4. List comprehension is text-based, apply after sql() call
    # (handled separately in results loop)
    
    return ast


def _get_dialect_name(dialect) -> str:
    """Extract dialect name string from dialect or Dialect instance."""
    if dialect is None:
        return ""
    if isinstance(dialect, str):
        return dialect.lower()
    if hasattr(dialect, '__class__'):
        return dialect.__class__.__name__.lower()
    return str(dialect).lower()
```

---

## Files to Create/Modify

### New Files
- `asql/transpile.py` - Main `transpile()` function
- `asql/expressions.py` - Custom AST nodes:
  - `class Spine(exp.Func)` - mark columns for gap-filling
  - `class CohortBy(exp.Expression)` - cohort analysis clause
- `asql/compiler/spine.py` - Rename from auto_spine.py, refactor for explicit spine

### Modify
- `asql/__init__.py` - Export `transpile`
- `asql/dialect/parser.py`:
  - Add `spine` keyword and `spine()` function
  - Use `exp.CohortBy` instead of `_cohort_info` attribute
  - Remove auto_spine calls
- `asql/dialect/tokenizer.py` - Add `SPINE` token
- `asql/config.py` - Remove `auto_spine` setting
- `asql/compiler/cohort_transform.py` - Read from `exp.CohortBy` instead of attribute
- `asql/compiler/auto_alias.py` - Remove `_cohort_info` preservation hack
- `asql/column_tracking.py` - Fix broken `compile_to_ast` import
- `tests/fixtures.py` - Use `asql.transpile()`
- `playground/app.py` - Use `asql.transpile()`
- All tests using auto_spine - Update to explicit spine syntax

### Delete (eventually)
- `asql/compiler/api.py` - If it still exists
- `guarantee()` function handling

---

## What We Learned

1. **sqlglot.transpile() is minimal** - just parse→generate, no transforms
2. **Transforms need output dialect** - can't all live in parser
3. **Explicit is better than implicit** - auto_spine magic was confusing
4. **One entry point** - easier to maintain and test
5. **Custom AST nodes** - cleanest way to mark intent for later transforms

---

## Appendix: Full Codebase Audit Findings

### Where Optimizer Is Used

| File | What It Uses | Purpose |
|------|--------------|---------|
| `visual_dialect/generator.py` | `qualify_columns`, `annotate_types` | Expand stars, get column types for JSON output |
| `column_operators.py` | `qualify_columns(expand_stars=True)` | Expand `* EXCEPT` for unsupported dialects |
| `column_tracking.py` | `qualify.qualify` | Column tracking for visual editor |

### Broken Code Found

**`column_tracking.py` line 33:**
```python
from asql import compile_to_ast  # DOESN'T EXIST!
```
This needs to be fixed - either create `compile_to_ast` or change to `sqlglot.parse_one`.

### Should `asql.transpile()` Run Optimizer?

**Answer: Selectively, not fully.**

The optimizer has 14 rules by default. We probably only need:
- `qualify_columns` - for column operators (EXCEPT expansion)
- Maybe `annotate_types` - for type-aware transforms

We should NOT run full optimizer because:
- It rewrites queries for performance (not our job)
- It can inline CTEs (breaks stash/alias reuse)
- It changes query structure unpredictably

**Recommendation:**
```python
# In asql.transpile(), run specific optimizer steps:
from sqlglot.optimizer.qualify_columns import qualify_columns

if schema:
    ast = qualify_columns(ast, schema=schema, expand_stars=True)
```

### Functions Registry - All Good ✅

`asql/functions.py` has:
- Date diff functions: `days_since()`, `months_until()`, etc.
- Running aggregates: `running_sum()`, `rolling_avg()`, etc.
- Fill functions: `fill_forward()`, `fill_backward()`
- `bucket()` - discretization

All registered in `ASQL_FUNCTION_REGISTRY` and used by parser via `FUNCTIONS` dict. No issues.

### Generators - No Custom preprocess()

Neither `ASQLGenerator` nor `VisualASQLGenerator` override `preprocess()`. This means:
- No dialect-specific transforms in output generators
- All transforms must happen in `asql.transpile()` before calling `ast.sql()`

### Complete Transform Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    asql.transpile() Full Pipeline                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ PARSE (ASQLParser)                                                    │  │
│  │                                                                       │  │
│  │ Parser-stage transforms (in _apply_asql_transforms):                  │  │
│  │ ├─ underscore_shorthands   (days_since_col → DATEDIFF)               │  │
│  │ ├─ implicit_function_alias (SUM(x) → SUM(x) AS sum_x)                │  │
│  │ ├─ auto_aliasing           (template-based aliases)                  │  │
│  │ ├─ fk_shorthand            (ON user_id → full condition)             │  │
│  │ ├─ cohort_transform        (cohort by → CTEs)                        │  │
│  │ └─ auto_qualify_columns    (expand * in JOINs)                       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                              │                                              │
│                              ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ QUALIFY (optional, if schema provided)                                │  │
│  │                                                                       │  │
│  │ sqlglot.optimizer.qualify_columns(ast, schema, expand_stars=True)    │  │
│  │ - Resolves column references                                          │  │
│  │ - Expands * EXCEPT for column_operators                               │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                              │                                              │
│                              ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ DIALECT TRANSFORMS (need output dialect)                              │  │
│  │                                                                       │  │
│  │ ├─ spine_transform         (exp.Spine → gap-filling CTEs)            │  │
│  │ ├─ alias_reuse             (same-row refs → CTE chain)               │  │
│  │ ├─ column_operators        (* EXCEPT → explicit columns)             │  │
│  │ └─ list_comprehension      ([x FOR x] → ARRAY(SELECT))               │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                              │                                              │
│                              ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ GENERATE                                                              │  │
│  │                                                                       │  │
│  │ ast.sql(dialect=write, pretty=pretty)                                │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Transforms to Remove from Parser

Currently `_apply_asql_transforms()` does ALL transforms. After this refactor:

**Keep in parser:**
- underscore_shorthands
- implicit_function_alias  
- auto_aliasing
- fk_shorthand
- cohort_transform
- auto_qualify_columns

**Move to `asql.transpile()` (after parse, before generate):**
- ~~alias_reuse~~ → needs output dialect
- ~~list_comprehension~~ → needs output dialect
- ~~auto_spine~~ → DELETED (replaced by explicit spine)
- ~~guarantee wrappers~~ → DELETED (replaced by exp.Spine)

**Add to `asql.transpile()`:**
- spine_transform (NEW)
- column_operators (already exists, just wire it up)
