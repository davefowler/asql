# ASQL Function Syntax Audit

**Date**: 2026-01-07  
**Updated**: 2026-01-07 (all syntax variants verified working)
**Purpose**: Document which functions support which syntax variants

---

## Syntax Variants

ASQL supports **3 syntax variants** for most functions:

| Variant | Example | Description |
|---------|---------|-------------|
| **Function call** | `sum(amount)` | Standard SQL syntax |
| **Space notation** | `sum amount` | Natural language style |
| **Underscore alias** | `sum_amount` | Column alias that auto-expands |

Some functions also support:
- **"of" notation**: `sum of amount` → `sum(amount)`
- **Multi-word**: `day of week created_at` → `day_of_week(created_at)`
- **Singular/plural aliases**: `day_since` = `days_since`, `running_total` = `running_sum`

---

## ✅ Current Support Matrix (All Verified Working)

### Date Diff Functions

| Function | `func(col)` | `func col` | `func_col` | Notes |
|----------|-------------|------------|------------|-------|
| `days_since` / `day_since` | ✅ | ✅ | ✅ | Plural/singular aliases |
| `weeks_since` / `week_since` | ✅ | ✅ | ✅ | Plural/singular aliases |
| `months_since` / `month_since` | ✅ | ✅ | ✅ | Plural/singular aliases |
| `years_since` / `year_since` | ✅ | ✅ | ✅ | Plural/singular aliases |
| `hours_since` / `hour_since` | ✅ | ✅ | ✅ | Plural/singular aliases |
| `minutes_since` / `minute_since` | ✅ | ✅ | ✅ | Plural/singular aliases |
| `seconds_since` / `second_since` | ✅ | ✅ | ✅ | Plural/singular aliases |
| `days_until` / `day_until` | ✅ | ✅ | ✅ | Same for all `*_until` |

### Running Aggregates

| Function | `func(col)` | `func col` | Notes |
|----------|-------------|------------|-------|
| `running_sum` / `running_total` | ✅ | ✅ | SUM/TOTAL aliases |
| `running_avg` / `running_average` | ✅ | ✅ | AVG/AVERAGE aliases |
| `running_count` | ✅ | ✅ | |
| `running_min` / `running_minimum` | ✅ | ✅ | MIN/MINIMUM aliases |
| `running_max` / `running_maximum` | ✅ | ✅ | MAX/MAXIMUM aliases |

### Rolling Aggregates

| Function | `func(col, n)` | `func col` | Notes |
|----------|----------------|------------|-------|
| `rolling_sum` / `rolling_total` | ✅ | ✅ | SUM/TOTAL aliases |
| `rolling_avg` / `rolling_average` | ✅ | ✅ | AVG/AVERAGE aliases |
| `rolling_count` | ✅ | ✅ | |
| `rolling_min` / `rolling_minimum` | ✅ | ✅ | MIN/MINIMUM aliases |
| `rolling_max` / `rolling_maximum` | ✅ | ✅ | MAX/MAXIMUM aliases |

### Fill Functions

| Function | `func(col)` | `func col` | Notes |
|----------|-------------|------------|-------|
| `fill_forward` | ✅ | ✅ | LAST_VALUE IGNORE NULLS |
| `fill_backward` | ✅ | ✅ | FIRST_VALUE IGNORE NULLS |

### ArgMax/ArgMin

| Function | `func(val, by)` | Notes |
|----------|-----------------|-------|
| `arg_max` / `argmax` | ✅ | Underscore/no-underscore aliases |
| `arg_min` / `argmin` | ✅ | Underscore/no-underscore aliases |

### Basic Aggregates

| Function | `func(col)` | `func col` | `func_col` | Notes |
|----------|-------------|------------|------------|-------|
| `sum` / `total` | ✅ | ✅ | ⚠️ Schema* | |
| `avg` / `average` | ✅ | ✅ | ⚠️ Schema* | |
| `count` | ✅ | ✅ | ⚠️ Schema* | |
| `min` / `minimum` | ✅ | ✅ | ⚠️ Schema* | |
| `max` / `maximum` | ✅ | ✅ | ⚠️ Schema* | |

### Date Parts

| Function | `func(col)` | `func col` | `func_col` | Notes |
|----------|-------------|------------|------------|-------|
| `year` | ✅ | ✅ | ✅ | |
| `quarter` | ✅ | ✅ | ✅ | |
| `month` | ✅ | ✅ | ✅ | |
| `week` | ✅ | ✅ | ✅ | |
| `day` | ✅ | ✅ | ✅ | |
| `hour` | ✅ | ✅ | ✅ | |
| `minute` | ✅ | ✅ | ✅ | |
| `second` | ✅ | ✅ | ✅ | |
| `day_of_week` | ✅ | ✅ `day of week` | N/A | Multi-word |
| `day_of_month` | ✅ | ✅ `day of month` | N/A | Multi-word |
| `day_of_year` | ✅ | ✅ `day of year` | N/A | Multi-word |
| `week_of_year` | ✅ | ✅ `week of year` | N/A | Multi-word |
| `month_of_year` | ✅ | ✅ `month of year` | N/A | Multi-word |
| `quarter_of_year` | ✅ | ✅ `quarter of year` | N/A | Multi-word |

**⚠️ Schema***: Underscore alias like `sum_amount` requires schema-aware optimizer with actual table schema.

---

## Bugs Fixed (2026-01-07)

### 1. Singular Date Diff Underscore Parsing

**Bug**: `day_since_created_at` was incorrectly parsed as `DAY(since_created_at)` instead of `DATEDIFF(...)`.

**Cause**: The preparser's `_transform_implicit_function_aliases` saw `day_` and incorrectly expanded it as a natural aggregate.

**Fix**: Added check in `clauses.py` to exclude `unit_since/until_col` patterns from implicit function expansion.

### 2. Missing Fill Function Space Notation

**Bug**: `fill forward amount` didn't work (only `fill_forward(amount)` worked).

**Fix**: Added `fill forward`, `fill backward` to `normalize.py`'s `multi_word_funcs` list.

### 3. Missing Running/Rolling Aliases Space Notation

**Bug**: `running min`, `running max`, `running total`, etc. didn't work.

**Fix**: Added all running/rolling variants to `normalize.py`'s `multi_word_funcs` list.

---

## Documentation Examples

All of these are equivalent:

```asql
-- Date diff (all equivalent)
days_since(created_at)         -- Function call (recommended)
day_since(created_at)          -- Singular variant
days since created_at          -- Space notation
days_since_created_at          -- Underscore alias

-- Running aggregates (all equivalent)
running_sum(amount)            -- Function call (recommended)
running_total(amount)          -- Alias
running sum amount             -- Space notation
running total amount           -- Space notation alias

-- Fill functions (all equivalent)
fill_forward(amount)           -- Function call (recommended)
fill forward amount            -- Space notation

-- Basic aggregates (all equivalent)
sum(amount)                    -- Function call (recommended)
total(amount)                  -- Alias
sum amount                     -- Space notation
sum of amount                  -- "of" notation
```

**Recommendation**: Document function-call syntax as primary, space notation as the "natural" alternative.
