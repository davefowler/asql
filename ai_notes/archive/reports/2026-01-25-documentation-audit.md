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

### ✅ Recently Documented (2026-01-25)

| Function | Location | Notes |
|----------|----------|-------|
| `bucket()` | `reference/functions.md` | Binning/discretization |
| `fill_forward()` | `reference/functions.md` | Gap-filling (LOCF) |
| `fill_backward()` | `reference/functions.md` | Gap-filling (reverse) |
| `key()` | `reference/functions.md` | Surrogate key generation |
| `slugify()` | `reference/functions.md` | URL-safe string conversion |
| `rolling_min()` | `reference/functions.md` | Moving minimum |
| `rolling_max()` | `reference/functions.md` | Moving maximum |
| `rolling_count()` | `reference/functions.md` | Moving count |

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

### ✅ Recently Documented (2026-01-25)

| Transform | Location | Notes |
|-----------|----------|-------|
| `extend` | `reference/keywords.md` | Add computed columns |
| `deduplicate by` | `reference/keywords.md` | Sugar for `per ... first by` |
| `recurse()` | `reference/keywords.md` | Recursive CTEs for hierarchical data |

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

### ✅ Completed (2026-01-25)

1. ✅ **`bucket()` documentation** added to `reference/functions.md`
2. ✅ **`extend` documentation** added to `reference/keywords.md`
3. ✅ **`fill_forward()` / `fill_backward()` documentation** added
4. ✅ **`deduplicate by` documentation** added
5. ✅ **`key()` documentation** added
6. ✅ **`recurse()` documentation** added
7. ✅ **`slugify()` documentation** added (was implemented, now documented)
8. ✅ **Rolling functions** (`rolling_min`, `rolling_max`, `rolling_count`) documented
9. ✅ **dbt.md updated** with `fill_forward`, `slugify`, and `key()` status

### Remaining (Low Priority)

- Consolidate natural language syntax examples into dedicated reference
- Add tests for `fill_forward`/`fill_backward` (implemented but untested)

---

## Notes

- All major documentation gaps have been filled as of 2026-01-25
- `fill_forward`/`fill_backward` work correctly but have no tests - consider adding test coverage
- `slugify()` was listed in spec_future.md but is actually implemented - docs now reflect this
- dbt.md updated to mark `key()` as implemented (was incorrectly marked "Planned")
