# ASQL Documentation Audit

**Date:** 2026-01-25  
**Purpose:** Inventory of all ASQL features and their documentation status

## Summary

| Category | Documented | Missing/Partial | Total |
|----------|------------|-----------------|-------|
| Functions | 35+ | 4 | ~40 |
| Transforms | 18 | 3 | 21 |
| Operators | 20+ | 0 | 20+ |
| Keywords | 30+ | 2 | 32+ |

---

## Functions

### ✅ Fully Documented

| Function | Location | Notes |
|----------|----------|-------|
| `count()`, `sum()`, `avg()`, `min()`, `max()` | `reference/functions.md` | Core aggregates |
| `total()`, `average()`, `minimum()`, `maximum()` | `reference/functions.md` | Aliases |
| `year()`, `month()`, `week()`, `day()`, `hour()`, `quarter()` | `reference/functions.md` | Date truncation |
| `day_of_week()`, `day_of_month()`, `day_of_year()` | `reference/functions.md` | Date extraction |
| `week_of_year()`, `month_of_year()`, `quarter_of_year()` | `reference/functions.md` | Date extraction |
| `days_since()`, `weeks_since()`, `months_since()`, `years_since()` | `reference/functions.md` | Time since |
| `days_until()`, `weeks_until()`, `months_until()`, `years_until()` | `reference/functions.md` | Time until |
| `hours_since()`, `minutes_since()`, `seconds_since()` | `reference/functions.md` | Time since (granular) |
| `prior()`, `next()` | `reference/functions.md` | LAG/LEAD |
| `running_sum()`, `running_avg()`, `running_count()` | `reference/functions.md` | Cumulative |
| `running_min()`, `running_max()` | `reference/functions.md` | Cumulative |
| `rolling_avg()`, `rolling_sum()` | `reference/functions.md` | Sliding window |
| `first()`, `last()` | `reference/functions.md` | Ordered first/last |
| `arg_max()`, `arg_min()` | `reference/functions.md` | Value at max/min |
| `row_number()`, `rank()`, `dense_rank()` | `reference/functions.md` | Ranking |
| `concat()`, `string_agg()` | `reference/functions.md` | String functions |
| `upper()`, `lower()`, `trim()` | `reference/functions.md` | String functions |
| `length()`, `substring()`, `replace()` | `reference/functions.md` | String functions |
| `coalesce()` / `??` | `reference/functions.md` | Null handling |
| `cast()` / `::` | `reference/functions.md` | Type conversion |
| `guarantee()` | `reference/functions.md` | *(Marked as planned)* |
| `spine()` | `reference/keywords.md` | Gap-filling |

### ❌ NOT Documented (Implemented)

| Function | Implementation | Tests | Priority |
|----------|---------------|-------|----------|
| **`bucket()`** | `asql/functions.py` | `tests/test_bucket.py` (336 lines) | **HIGH** |
| **`fill_forward()`** | `asql/functions.py` | Needs verification | MEDIUM |
| **`fill_backward()`** | `asql/functions.py` | Needs verification | MEDIUM |
| **`key()`** | `asql/dialect/parser.py` | Needs verification | MEDIUM |

### ⚠️ Partially Documented

| Function | Status | Notes |
|----------|--------|-------|
| `slugify()` | In `spec_future.md` | Implemented but marked as "future" |
| `rolling_min()`, `rolling_max()` | Missing from docs | Implemented in `ASQL_FUNCTION_REGISTRY` |
| `rolling_count()` | Missing from docs | Implemented in `ASQL_FUNCTION_REGISTRY` |

---

## Transforms (Pipeline Keywords)

### ✅ Fully Documented

| Transform | Location | Notes |
|-----------|----------|-------|
| `from` | `reference/keywords.md` | Entry point |
| `where` | `reference/keywords.md` | Filtering |
| `select` | `reference/keywords.md` | Column selection |
| `group by` | `reference/keywords.md`, `group_by.md` | Aggregation |
| `order by` | `reference/keywords.md` | Sorting |
| `limit` | `reference/keywords.md` | Row limiting |
| `offset` | Implied in `limit` | Pagination |
| `having` | `reference/keywords.md` | Post-group filter |
| `qualify` | `reference/keywords.md` | Window filter |
| `join`, `&`, `&?`, `?&`, `?&?`, `*` | `reference/operators.md`, `syntax/joins.md` | All join types |
| `except` | `reference/keywords.md` | Column exclusion |
| `rename` | `reference/keywords.md` | Column renaming |
| `replace` | `reference/keywords.md` | Column replacement |
| `sample` | `reference/keywords.md`, `syntax/sampling.md` | Random sampling |
| `pivot`, `unpivot` | `reference/keywords.md`, `syntax/pivot-unpivot.md` | Reshaping |
| `explode` | `reference/keywords.md` | Array expansion |
| `stash as` | `reference/keywords.md`, `syntax/ctes.md` | CTEs |
| `spine by` | `reference/keywords.md`, `group_by.md` | Gap-filling |
| `per ... first/last by` | `reference/keywords.md` | Window dedup |
| `number`, `rank`, `dense rank` | `reference/keywords.md` | Ranking |
| `distinct`, `distinct on` | `reference/keywords.md` | Deduplication |

### ❌ NOT Documented (Implemented)

| Transform | Implementation | Notes | Priority |
|-----------|---------------|-------|----------|
| **`extend`** | `_parse_asql_extend` | Add computed columns (like `select *, expr`) | **HIGH** |
| **`deduplicate by`** | `_parse_asql_deduplicate` | Sugar for `per ... first by` | MEDIUM |
| **`recurse()`** | `_parse_asql_recurse` | Recursive CTEs | MEDIUM |

---

## Operators

### ✅ Fully Documented

All operators are documented in `reference/operators.md`:

- Comparison: `=`, `==`, `!=`, `<`, `>`, `<=`, `>=`
- Null: `is null`, `is not null`
- Membership: `in`, `not in`
- Logical: `and`, `or`, `not`, `&&`
- Arithmetic: `+`, `-`, `*`, `/`, `%`
- Null coalescing: `??`
- Type cast: `::`, `::type?`
- Join symbols: `&`, `&?`, `?&`, `?&?`, `*`
- Order: `-column` (descending)
- Count: `#`, `#(col)`, `#(distinct col)`
- String: `contains`, `icontains`, `starts with`, `ends with`, `matches`
- Date: `@2024-01-01`, `+ N days`, `- N weeks`, `N days ago`

---

## Syntax Features

### ✅ Documented

| Feature | Location |
|---------|----------|
| Pipeline syntax (indentation & `\|`) | `syntax/pipe.md` |
| Aggregation blocks `group by ... (aggs)` | `syntax/aggregations.md` |
| Window functions | `syntax/window-functions.md` |
| Date syntax | `syntax/dates.md` |
| Joins | `syntax/joins.md` |
| CTEs | `syntax/ctes.md` |
| Cohort analysis | `syntax/cohorts.md` |
| Expressions/conditionals | `syntax/expressions.md` |
| Sampling | `syntax/sampling.md` |
| Pivot/Unpivot | `syntax/pivot-unpivot.md` |

### ⚠️ Needs Improvement

| Feature | Status | Notes |
|---------|--------|-------|
| Underscore shorthands | Partial | `sum_amount`, `month_created_at` - mentioned but not comprehensive |
| Natural language syntax | Partial | `days since col`, `sum of amount` - scattered across docs |
| Auto-aliasing | Has dedicated page | `reference/auto-aliasing.md` exists |

---

## Action Items

### Immediate (HIGH Priority)

1. **Add `bucket()` documentation** to `reference/functions.md`
   - Boundary-based: `bucket(score, [0, 60, 70, 80, 90, 100], ['F', 'D', 'C', 'B', 'A'])`
   - Width-based: `bucket(value, start=0, end=100, width=10)`
   - Auto-labels: `bucket(amount, [0, 100, 500, 1000])`

2. **Add `extend` documentation** to `reference/keywords.md`
   - Syntax: `extend expr as alias`
   - Use case: Adding computed columns without listing all existing

### Medium Priority

3. **Add `fill_forward()` / `fill_backward()` documentation**
   - Gap-filling for time series
   - Propagates last/next non-null value

4. **Add `deduplicate by` documentation**
   - Syntax: `deduplicate by col1, col2 order by -date`
   - Sugar for `per col1, col2 first by -date`

5. **Add `key()` documentation**
   - Surrogate key generation
   - Syntax: `key(col1, col2, ...)`

6. **Add `recurse()` documentation**
   - Recursive CTEs for hierarchical data
   - Syntax: `recurse(fk_column [, max_depth])`

### Low Priority

7. **Update `slugify()` status** - move from future to implemented if working
8. **Add missing rolling functions** - `rolling_min`, `rolling_max`, `rolling_count`
9. **Consolidate natural language syntax examples** into dedicated reference

---

## Notes

- The `bucket()` function has 336 lines of tests but zero documentation - highest priority fix
- `extend` is a useful feature that's fully implemented but only mentioned in future docs
- Many "future" features in `spec_future.md` may actually be implemented - need verification pass
