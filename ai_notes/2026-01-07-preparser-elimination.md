# Preparser Elimination Progress - 2026-01-07

## Summary

This document records the progress made in eliminating the legacy preparser from ASQL. All ASQL syntax features have been migrated to the SQLGlot-based `asql/dialect.py`.

## Completed Migrations

### From Preparser to Dialect

| Feature | Preparser File | Now Handled By |
|---------|---------------|----------------|
| Join operators (`&`, `&?`, `?&`, `?&?`, `*`) | `joins.py` | `dialect.py` + `compiler/join_fk_shorthand.py` |
| FK shorthand (`ON user_id`) | `joins.py` | `compiler/join_fk_shorthand.py` |
| Recurse (`recurse(fk_col)`) | `recurse.py` | `dialect.py` (`TRANSFORM_PARSERS`) |
| List comprehensions (`[expr for var in arr]`) | `list_comprehension.py` | `dialect.py` (`_parse_bracket`) |
| Count shorthand (`#`, `# users`, `#(col)`) | `count.py` | `dialect.py` (`_parse_unary`) |
| Extend (`extend expr as alias`) | `extend.py` | `dialect.py` (`TRANSFORM_PARSERS`) |

### Previously Migrated (by other agents or earlier work)

- Pipeline operators (`|`, `|>`)
- When expressions
- Pivot/Unpivot/Explode
- Window functions (prior, next, running_*, rolling_*, etc.)
- Cohort analysis
- Aggregate blocks
- Column operators (except, rename, replace)
- Date expressions (@date, N days ago, etc.)
- Coalesce (`??`)
- Ternary (`? :`)

## Deleted Preparser Files

- `asql/preparse/joins.py`
- `asql/preparse/recurse.py`
- `asql/preparse/list_comprehension.py`
- `asql/preparse/count.py`
- `asql/preparse/extend.py`
- `asql/preparse/registry.py` (unused function registry)

## Current Preparser State

The preparser (`asql/preparse/preparser.py`) now only:
1. Extracts comments (for preservation)
2. Restores comments
3. No actual syntax transformations

It effectively passes through the input unchanged.

## Testing

- All 2438 tests pass
- Direct SQLGlot parsing works:

```python
import sqlglot
from asql.dialect import ASQL

dialect = ASQL()
parsed = sqlglot.parse("from users where active = true", dialect=dialect)
# Returns: SELECT * FROM users WHERE active = TRUE
```

## Key Implementation Details

### Count Shorthand (`#`)

The `#` count shorthand was tricky to implement because:
1. `HASH` token needed to be handled in the expression parsing chain
2. There were two paths: `_parse_unary` and `PRIMARY_PARSERS`
3. Solution: Unified handling in `_parse_count_shorthand_from_primary()` called from `_parse_unary`

Supported syntax:
- `#` → `COUNT(*)`
- `#*` → `COUNT(*)`
- `#(col)` → `COUNT(col)`
- `#(distinct col)` → `COUNT(DISTINCT col)`
- `# users` → `COUNT(DISTINCT user_id)`
- `# of users` → `COUNT(DISTINCT user_id)`

### List Comprehensions

Python-style list comprehensions are parsed in `_parse_bracket`:
1. Check if `[` is followed by `for ... in` pattern
2. If so, parse as list comprehension
3. Convert to `ARRAY(SELECT expr FROM UNNEST(arr) AS var [WHERE condition])`

For DuckDB, there's post-processing that converts back to native syntax.

### Recurse (Recursive CTEs)

The `recurse(fk_column [, max_depth])` syntax generates `WITH RECURSIVE` CTEs:
1. Parsed via `TRANSFORM_PARSERS["RECURSE"]`
2. Extracts table name and WHERE condition
3. Generates anchor + recursive query with level tracking

## Decisions Made

1. **Count shorthand in `_parse_unary`**: Rather than relying solely on `PRIMARY_PARSERS`, the `#` handling was added to `_parse_unary` which is called earlier in the expression parsing chain.

2. **List comprehension lookahead**: Added `_is_list_comprehension()` method that scans ahead for `for ... in` pattern to distinguish from array literals.

3. **FK shorthand as compiler transform**: Rather than trying to expand FK shorthand during parsing, it's handled as a post-parse AST transform in `compiler/join_fk_shorthand.py`.

## Final Status

✅ **Preparser elimination complete!**

The preparser now only handles comment preservation. All ASQL syntax features are implemented in:
- `asql/dialect.py` - SQLGlot-based parser with custom tokens and parsers
- `asql/functions.py` - Function registry with factory patterns
- `asql/compiler/` - AST transforms for complex features (cohort, FK shorthand, pivot fallback)

### Remaining Files in `/asql/preparse/`

- `preparser.py` - Orchestrator (only comment handling)
- `comments.py` - Comment extraction/restoration mixin
- `inference.py` - Shared join key inference utilities (used by tests)
- `__init__.py` - Module exports

**Note**: The preparser cannot be fully removed as SQLGlot doesn't preserve standalone comments in all cases. The comment handling is valuable for maintaining readable output.

## Files Modified

- `asql/dialect.py` - Main dialect implementation
- `asql/preparse/preparser.py` - Stripped to minimal comment handling
- `tests/test_recurse.py` - Updated to use `compile()` instead of `preparse_asql`
- `asql/compiler/column_operators.py` - Fixed bug with `stmt.find()` usage
