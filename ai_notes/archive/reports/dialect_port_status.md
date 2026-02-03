# ASQL Preparser → Dialect Migration Status

**Goal**: Move ASQL syntax handling from regex preparser to SQLGlot's parser infrastructure.

**Status**: ✅ COMPLETE - Preparser eliminated entirely!

## Final Results

| Metric | Value |
|--------|-------|
| **Lines deleted from preparser** | 6,485 |
| **Net lines removed** | 1,302 |
| **Python insertions** | 6,027 |
| **Python deletions** | 7,329 |
| **Tests passing** | 2,429 |

The entire `asql/preparse/` directory and `asql/preparser.py` have been deleted.

## What Was Eliminated

All 19 preparser files totaling ~6,485 lines:

```
asql/preparse/
├── __init__.py          (178 lines)
├── aggregates.py        (225 lines)
├── bucket.py            (351 lines)
├── clauses.py           (974 lines)
├── coalesce.py          (115 lines)
├── cohort.py            (273 lines)
├── comments.py          (93 lines)
├── count.py             (107 lines)
├── dates.py             (95 lines)
├── extend.py            (101 lines)
├── inference.py         (75 lines)
├── joins.py             (368 lines)
├── key.py               (178 lines)
├── list_comprehension.py (194 lines)
├── multistatement.py    (127 lines)
├── normalize.py         (91 lines)
├── order.py             (79 lines)
├── pipeline.py          (68 lines)
├── pivot.py             (432 lines)
├── preparser.py         (153 lines)
├── recurse.py           (202 lines)
├── registry.py          (67 lines)
├── settings.py          (56 lines)
├── slice.py             (148 lines)
├── slugify.py           (125 lines)
├── stash.py             (57 lines)
├── ternary.py           (351 lines)
├── when.py              (~100 lines)
├── window.py            (404 lines)
└── with_cte.py          (133 lines)

asql/preparser.py        (8 lines - compatibility shim)
```

## New Architecture

```
ASQL Query
    ↓
_split_multistatement_blocks()     # Split on blank lines + FROM/WITH/SELECT
    ↓
sqlglot.parse(dialect="asql")      # ASQLParser handles ALL ASQL syntax
    ↓
Compiler transforms                 # FK shorthand, PIVOT/UNPIVOT fallback, cohort, etc.
    ↓
sqlglot.sql(dialect=target)        # Generate SQL for target dialect
```

## Feature Location Summary

| Feature | Now In |
|---------|--------|
| `??` coalesce | SQLGlot native DQMARK |
| `? :` ternary | `dialect.py` `_parse_assignment` |
| `@date` literals | `dialect.py` PLACEHOLDER_PARSERS |
| `7 days ago`, `from now` | `dialect.py` `_parse_unary` |
| `col + 7 days` | `dialect.py` `_parse_factor` |
| `days_since(col)`, `days since col` | `dialect.py` + `functions.py` |
| `\|` pipeline | ASQLTokenizer maps `\|` → PIPE_GT |
| `sum amount`, `sum of amount` | `dialect.py` `_parse_unary` |
| `#`, `#(col)`, `# users` | `dialect.py` `_parse_count_shorthand_from_primary` |
| `key(...)`, `slugify(...)` | `dialect.py` FUNCTION_PARSERS |
| `col[1:5]` slices | `dialect.py` `_parse_bracket` |
| `[x for x in arr]` | `dialect.py` `_parse_list_comprehension` |
| `*_since_*` / `*_until_*` | `compiler/underscore_shorthands.py` |
| `SET ...` normalization | `compiler/api.py` |
| PIVOT→CASE/WHEN fallback | `compiler/pivot_fallback.py` |
| `explode` | `dialect.py` + `compiler/explode_fallback.py` |
| `stash as` | `dialect.py` `_parse_asql_stash` |
| `running_*`, `rolling_*` | `functions.py` factory patterns |
| `fill_forward/backward` | `functions.py` |
| `arg_max`, `arg_min` | `functions.py` |
| `cohort by` | `dialect.py` + `compiler/cohort_transform.py` |
| `group by (aggs)` | `dialect.py` `_parse_asql_group_by` |
| String matching ops | `dialect.py` `_parse_comparison` |
| Multiple `where` | SQLGlot `Query.where(..., append=True)` |
| Column operators | `dialect.py` + `compiler/column_operators.py` |
| Join operators (`&`, `&?`, etc.) | `dialect.py` TRANSFORM_PARSERS |
| FK shorthand (`ON user_id`) | `compiler/join_fk_shorthand.py` |
| `recurse()` | `dialect.py` TRANSFORM_PARSERS |
| `extend` | `dialect.py` TRANSFORM_PARSERS |
| `when` expressions | `dialect.py` `_parse_when` |
| Comment preservation | SQLGlot native `comments=True/False` |
| Multi-statement splitting | `compiler/api.py` `_split_multistatement_blocks` |

## Benefits

1. **No regex parsing** - All syntax handled by proper parser
2. **Better error messages** - SQLGlot's error reporting
3. **Easier maintenance** - Single source of truth for syntax
4. **Type-safe AST** - Work with `exp.Expression` objects, not strings
5. **1,302 fewer lines** - Simpler codebase
