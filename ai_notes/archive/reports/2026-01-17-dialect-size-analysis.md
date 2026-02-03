# ASQL Dialect Size Analysis - 2026-01-17

## Size Comparison

| Dialect | Total Lines | Parser Methods | Generator Methods |
|---------|-------------|----------------|-------------------|
| **ASQL** | **3,449** | **84** | 31 |
| Snowflake | 1,888 | 25 | 7 |
| ClickHouse | 1,498 | - | - |
| BigQuery | 1,463 | - | - |
| DuckDB | 1,431 | - | - |
| TSQL | 1,430 | - | - |
| MySQL | 1,335 | - | - |
| PostgreSQL | 885 | - | - |
| Spark | 271 | - | - |
| PRQL | 207 | - | - |

**ASQL is ~2x larger than the biggest SQLGlot dialect (Snowflake).**

## Line Breakdown

```
ASQLTokenizer:     47 lines  (1%)
ASQLParser:     2,919 lines  (85%)  ← THE PROBLEM
ASQLGenerator:    383 lines  (11%)
ASQL Dialect:      52 lines  (1.5%)
Imports/etc:       48 lines  (1.5%)
```

## Why Is ASQL So Large?

### 1. ASQL Is a New Language, Not Just a SQL Dialect

SQLGlot dialects like Snowflake are **SQL with quirks** - they override a few functions and operators. The base Parser handles 95% of the work.

ASQL is **a completely different language** that happens to compile to SQL:
- FROM-first syntax (not SELECT-first)
- Pipeline transforms (`per`, `cohort`, `deduplicate`, `extend`, `stash`)
- Custom join operators (`&`, `&?`, `?&`, `?&?`, `*`)
- Inline aggregates in GROUP BY: `group by region (sum(amount))`
- List comprehensions: `[x * 2 for x in array]`
- Natural date syntax: `30 days ago`, `last month`
- Underscore function shorthands: `days_since_created_at`
- WHEN expressions with complex branching
- Cohort analysis syntax
- Column operators (`except`, `rename`, `replace`)
- etc.

Each of these features requires custom parsing logic that can't be expressed as dict overrides.

### 2. SQLGlot Dialects Use Dict-Based Configuration

Snowflake's approach (25 parser methods):
```python
class Parser(parser.Parser):
    FUNCTIONS = {
        **parser.Parser.FUNCTIONS,
        "ARRAY_CONSTRUCT": lambda args: exp.Array(expressions=args),
        # ... 100+ entries
    }
    
    FUNCTION_PARSERS = {
        **parser.Parser.FUNCTION_PARSERS,
        "TRY_CAST": lambda self: self._parse_cast(safe=True),
        # ... 20+ entries
    }
    
    # Only 25 custom methods for Snowflake-specific syntax
```

ASQL's approach (84 parser methods):
```python
class ASQLParser(Parser):
    # Some dict config
    FUNCTIONS = {...}
    TRANSFORM_PARSERS = {...}
    
    # But 84 custom methods because:
    def _parse_asql_per(self, query):           # per transform
    def _parse_asql_cohort(self, query):        # cohort analysis
    def _parse_asql_stash(self, query):         # CTE syntax
    def _parse_asql_deduplicate(self, query):   # deduplication
    def _parse_when(self):                       # WHEN expressions
    def _parse_list_comprehension(self):        # [x for x in arr]
    def _parse_asql_relative_date_unary(self):  # 30 days ago
    # ... 77 more methods
```

### 3. ASQL Has Transform-Heavy Parsing

ASQL uses a `TRANSFORM_PARSERS` dict but each parser is complex:

```python
TRANSFORM_PARSERS = {
    "WHERE": "_parse_asql_where",
    "GROUP BY": "_parse_asql_group_by", 
    "ORDER BY": "_parse_asql_order_by",
    "PER": "_parse_asql_per",
    "COHORT": "_parse_asql_cohort",
    "DEDUPLICATE": "_parse_asql_deduplicate",
    "STASH": "_parse_asql_stash",
    # ... etc
}
```

Each of these methods is 30-100 lines because ASQL transforms have complex syntax.

---

## Should We Split Into Multiple Files?

### Option A: Keep Single File (Current)

**Pros:**
- Everything in one place
- Easy to search/navigate
- SQLGlot's pattern (all dialects are single files)

**Cons:**
- 3,449 lines is hard to navigate
- Hard to understand structure
- Intimidating for contributors

### Option B: Split Into `dialect/` Folder

```
asql/
  dialect/
    __init__.py          # Exports ASQL, ASQLDialect, register_asql_dialect
    tokenizer.py         # ASQLTokenizer (47 lines)
    parser.py            # ASQLParser (2,919 lines) - could split further
    generator.py         # ASQLGenerator (383 lines)
    dialect.py           # ASQL class (52 lines)
```

**Pros:**
- Clearer organization
- Easier to find specific code
- Can split parser further if needed

**Cons:**
- Different from SQLGlot pattern
- More files to manage
- Import complexity

### Option C: Split Parser Into Submodules

```
asql/
  dialect/
    __init__.py
    tokenizer.py
    generator.py
    dialect.py
    parser/
      __init__.py        # ASQLParser class definition
      transforms.py      # _parse_asql_* methods
      expressions.py     # _parse_when, _parse_comparison, etc.
      joins.py           # Join-related parsing
      dates.py           # Date literal parsing
```

**Pros:**
- Highly organized
- Each file is focused
- Easier to test

**Cons:**
- Most complexity
- Very different from SQLGlot
- May be overkill

---

## Recommendation

**Option B: Split into `dialect/` folder** is the best balance.

The parser at 2,919 lines could stay as one file initially, but be ready to split if it grows further. The key split is:

1. **`dialect/__init__.py`** - Exports
2. **`dialect/tokenizer.py`** - ASQLTokenizer
3. **`dialect/parser.py`** - ASQLParser (the big one)
4. **`dialect/generator.py`** - ASQLGenerator
5. **`dialect/dialect.py`** - ASQL class and registration

This keeps the SQLGlot-like structure (one Parser class, one Generator class) while making the codebase more navigable.

---

## Are 84 Methods a Style Difference?

**No - this is appropriate for ASQL's complexity.**

For comparison:
- SQLGlot base Parser: **345** `_parse` methods in 8,995 lines
- ASQL Parser: **67** `_parse` methods in ~2,944 lines

ASQL has *fewer* methods than SQLGlot's base parser. The methods exist because ASQL has genuinely complex syntax that SQLGlot doesn't have:

| Method | Purpose | Why Method vs Inline |
|--------|---------|---------------------|
| `_parse_list_comprehension` (146 lines) | `[x*2 for x in arr if x > 0]` | Complex bracket/token tracking |
| `_parse_when` (117 lines) | `when cond then val` with many forms | Multi-branch condition logic |
| `_parse_asql_cohort` (96 lines) | Cohort analysis DSL | Date bucketing + retention logic |
| `_parse_asql_per` (83 lines) | Window functions `per user by date` | Multiple operation types |
| `_parse_asql_recurse` (90 lines) | Recursive CTE builder | Builds anchor + recursive queries |

**Small methods (< 15 lines) could potentially be inlined:**
- `_parse_asql_ordered` (4 lines) - just calls parent
- `_parse_when_result` (5 lines) - simple wrapper
- `_parse_join_kind` (6 lines) - delegation only

But these exist for **code organization**, not complexity. SQLGlot uses the same pattern - small methods for semantic clarity.

**Verdict:** Methods are appropriate. ASQL genuinely has novel syntax.

---

## Before Splitting: What Could Be Reduced

### Analysis of Largest Methods

| Rank | Method | Lines | Reducible? |
|------|--------|-------|------------|
| 1 | `parse_set_operation` | 230 | ⚠️ Mostly SQLGlot boilerplate copy - could simplify |
| 2 | `_parse_list_comprehension` | 146 | ❌ Complex tokenization needed |
| 3 | `_parse_group_by_term` | 140 | ⚠️ Aggregate block detection duplicated |
| 4 | `_parse_bracket` | 120 | ❌ Handles 4 different syntaxes |
| 5 | `_parse_when` | 117 | ⚠️ Could extract branch parsing |

### Specific Reduction Opportunities

**1. ✅ DONE: Replace `parse_set_operation` with PRQL-style TRANSFORM_PARSERS (~77 lines saved)**

PRQL handles UNION/INTERSECT as transforms, not via `parse_set_operation`:

```python
# PRQL style (2-line lambdas!)
"APPEND": lambda self, query: query.union(_select_all(self._parse_table()), distinct=False, copy=False),
"INTERSECT": lambda self, query: query.intersect(_select_all(self._parse_table()), copy=False),
```

**Implemented in ASQL:**
```python
TRANSFORM_PARSERS = {
    ...
    "UNION": lambda self, query: self._parse_asql_union(query),
    "UNION ALL": lambda self, query: self._parse_asql_union(query, distinct=False),
    "INTERSECT": lambda self, query: self._parse_asql_intersect(query),
}
```

**Result:**
- Deleted 77-line `parse_set_operation` override
- Added ~35 lines for `_parse_asql_union` and `_parse_asql_intersect`
- **Net savings: ~42 lines**
- **Bonus: Fixed a known limitation!** Test `test_union_with_asql` was marked `xfail` - now passes!

**2. Consolidate aggregate block detection (~30 lines)**

`_looks_like_aggregate_block_at()` is called from multiple places. Some methods duplicate its logic inline. Consolidate to always use the helper.

**3. Extract `_build_pipe_cte` call sites (~20 lines)**

8 call sites to `_build_pipe_cte(query, [exp.Star()])` - could add a default:
```python
def _build_pipe_cte(self, query, expressions=None, alias=None):
    expressions = expressions or [exp.Star()]
    ...
```

**4. Move more config to `dialect_schema.py` (~50 lines)**

- `TIME_UNITS` ✅ (already moved)
- `_TOKEN_TRANSFORMS` dict could be schema-derived
- `_TRANSFORM_KEYWORDS` ✅ (already derived from schema)

**5. Reduce docstring verbosity (~100 lines)**

Many methods have 10+ line docstrings with examples. For internal methods, shorter is fine.

### Realistic Reduction Estimate

| Category | Current | Target | Savings | Status |
|----------|---------|--------|---------|--------|
| `parse_set_operation` → TRANSFORM_PARSERS | 77 | 35 | ~42 | ✅ Done |
| Docstring trimming | ~300 | ~150 | ~150 | Pending |
| Config to schema | ~80 | ~30 | ~50 | Pending |
| Duplicate logic consolidation | ~60 | ~30 | ~30 | Pending |
| **Total Parser** | **~2,944** | **~2,670** | **~270** | |

### What Should NOT Be Reduced

1. **Parser methods for novel syntax** - `_parse_when`, `_parse_list_comprehension`, etc. are genuinely needed
2. **Generator methods** - All 33 `_sql` methods are required for proper ASQL output
3. **Tokenizer** - Already minimal at 175 lines
4. **Error messages** - Keep them helpful

---

## Recommended Order of Operations

1. **Split into `dialect/` folder first** (Option B) - No code changes, just reorganization
2. **Then reduce `parse_set_operation`** - Biggest single win
3. **Trim docstrings** - Low-risk cleanup
4. **Consolidate helpers** - Only if patterns are truly duplicated

The folder split makes the codebase navigable immediately, while reductions can happen incrementally.
