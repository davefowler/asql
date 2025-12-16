# Date Handling in ASQL

This document explores how ASQL handles dates currently and proposes improvements based on common patterns across SQL dialects.

**Last Updated**: December 2025

> **See also**: [Universal Function Shorthand](universal_function_shorthand.md) - the `func column` / `func_column` pattern that applies to dates, aggregations, and other functions.

---

## Summary

Dates are one of the most important and commonly-used features in analytics SQL. Every dialect handles them differently, leading to confusion and non-portable queries. ASQL has an opportunity to provide a clean, intuitive, and portable date syntax that compiles to the right dialect-specific SQL.

**Current Status**:
- ✅ Date literals: `@2025-01-01` syntax
- ✅ Basic date functions: `month()`, `year()`, `week()`, `day()`, `hour()`
- ⚠️ `date_trunc()` passes through as function call
- ⚠️ `INTERVAL` passes through (SQL syntax)
- ❌ `DATEDIFF` / date arithmetic not cleanly handled
- ❌ `DATEADD` not cleanly handled
- ❌ No relative date literals (e.g., "7 days ago")

---

## 1. Current Date Handling in ASQL

### 1.1 Date Literals

ASQL uses the `@` prefix for date literals:

```asql
from users
  where signup_date >= @2024-01-01
```

This is clean and unambiguous. The `@` prefix distinguishes dates from strings.

### 1.2 Time Truncation Functions (Implemented)

ASQL provides simple time truncation functions for grouping:

```asql
year(created_at)      -- Returns: 2025-01-01 (truncated to year start)
month(created_at)     -- Returns: 2025-01-01 (truncated to month start)
week(created_at)      -- Returns: 2025-01-06 (truncated to week start)
day(created_at)       -- Returns: 2025-01-15 (truncated to day)
hour(created_at)      -- Returns: 2025-01-15 14:00:00 (truncated to hour)
```

These compile to `DATE_TRUNC()` and are ideal for time series grouping.

### 1.2.1 Date Part Extraction (Proposed) - NEEDS DESIGN

Extracting date parts (day of week, week of year, etc.) needs a clean syntax. The naive approach creates too many functions to remember.

---

#### The Problem

These are all distinct operations:
- `month(created_at)` → `2025-01` (truncation, for time series)
- `month of year created_at` → `1` (extraction, for "all Januaries")

We need syntax for extraction that's:
1. Easy to remember
2. Natural language feel
3. Not 20+ new functions

---

#### Option A: Natural Language Phrases ⭐ (Recommended)

Use the pattern `{part} of {whole} {column}`:

```asql
day of week created_at        -- 1-7 (which day of the week)
day of month created_at       -- 1-31 (which day of the month)
day of year created_at        -- 1-366 (which day of the year)
week of month created_at      -- 1-5 (which week of the month)
week of year created_at       -- 1-52 (which week of the year)
month of year created_at      -- 1-12 (which month)
quarter of year created_at    -- 1-4 (which quarter)
```

**Pros**:
- ✅ Reads like English: "day of week of created_at"
- ✅ Easy to remember - just combine words naturally
- ✅ Auto-generates column names: `day_of_week_created_at`
- ✅ Consistent with ASQL's natural language philosophy
- ✅ Covers all cases with one pattern

**Cons**:
- ⚠️ More complex parsing (3-word phrase before column)

**Examples**:
```asql
-- Weekend orders
from orders
  where day of week order_date in (6, 7)

-- Sales by day of week
from sales
  group by day of week sale_date (
    sum amount
  )
-- Column: day_of_week_sale_date, sum_amount

-- Q4 across all years
from revenue
  where quarter of year date == 4
```

---

#### Option B: Compound Function Names (Traditional)

The straightforward but verbose approach:

```asql
day_of_week(created_at)       -- or: dayofweek(created_at)
day_of_month(created_at)
day_of_year(created_at)
week_of_year(created_at)
month_of_year(created_at)
quarter_of_year(created_at)
```

**Pros**:
- ✅ Familiar from other languages (KQL, DuckDB, pandas)
- ✅ Simple parsing

**Cons**:
- ❌ Lots of functions to remember
- ❌ Verbose

---

#### Option C: Abbreviations

Short codes like SQL's EXTRACT:

```asql
dow(created_at)    -- day of week
dom(created_at)    -- day of month
doy(created_at)    -- day of year
woy(created_at)    -- week of year
moy(created_at)    -- month of year
qoy(created_at)    -- quarter of year
```

**Pros**:
- ✅ Very short
- ✅ Familiar to SQL users (DOW, DOY are EXTRACT fields)

**Cons**:
- ❌ Cryptic - need to memorize abbreviations
- ❌ Not self-documenting

---

#### Option D: Parameterized Function

Single function with parameters:

```asql
extract(day, week, created_at)      -- day of week
extract(day, month, created_at)     -- day of month
extract(week, year, created_at)     -- week of year
```

Or with strings:
```asql
part(created_at, "day of week")
part(created_at, "week of year")
```

**Pros**:
- ✅ One function to remember

**Cons**:
- ❌ Awkward syntax
- ❌ Doesn't read naturally

---

#### Option E: Method Chaining

Object-oriented style:

```asql
created_at.day.of_week
created_at.week.of_year
created_at.month.of_year
```

**Pros**:
- ✅ Familiar to programmers

**Cons**:
- ❌ Not natural language
- ❌ Different from rest of ASQL

---

#### Recommendation: Apply the Underscore/Space Principle

This follows ASQL's core principle that **spaces and underscores are interchangeable in function contexts** (see [Universal Function Shorthand](universal_function_shorthand.md)).

All of these are **equivalent**:

```asql
-- Explicit function call (most precise)
day_of_week(created_at)

-- Shorthand with underscores (pattern interpretation)  
day_of_week_created_at

-- Natural language with spaces (most readable)
day of week created_at
```

**The spectrum**:
| Style | Syntax | Who uses it |
|-------|--------|-------------|
| Programmer | `day_of_week(created_at)` | Developers, explicit |
| Shorthand | `day_of_week_created_at` | Power users, quick |
| Analyst | `day of week created_at` | Business users, readable |

**Plus abbreviations** for those who want them:
```asql
dow(created_at)    -- day of week
woy(signup_date)   -- week of year
```

All syntaxes produce the same output and auto-generate column name `day_of_week_created_at`.

---

#### Special Case: Day/Month Names

For text output (Monday, January, etc.):

```asql
weekday(created_at)        -- "Wednesday" (day name)
monthname(created_at)      -- "January" (month name)

-- Or natural language:
name of day created_at     -- "Wednesday"
name of month created_at   -- "January"
```

---

#### What Others Do

| Language | Syntax | Notes |
|----------|--------|-------|
| **KQL** | `dayofweek(date)` | Compound function names |
| **DuckDB** | `dayofweek(date)` or `extract(dow from date)` | Both supported |
| **PostgreSQL** | `EXTRACT(DOW FROM date)` | Verbose but standard |
| **pandas** | `date.dt.dayofweek` | Property access |
| **Malloy** | `day_of_week()` | Compound function |

None use natural language phrases - this would be an ASQL innovation.

---

#### Column Naming

With natural language syntax, column names auto-generate:

| Expression | Column Name |
|------------|-------------|
| `day of week created_at` | `day_of_week_created_at` |
| `week of year signup_date` | `week_of_year_signup_date` |
| `month of year order_date` | `month_of_year_order_date` |

### 1.3 Smart Column Naming

Date functions use **Universal Function Shorthand** - all of these are equivalent:

```asql
year(created_at)     -- function style → year_created_at
year created_at      -- space style → year_created_at
year_created_at      -- underscore style (ASQL interprets as year(created_at))
year of created_at   -- "of" style → year_of_created_at
```

For date functions, the "of" style is also supported: `year of created_at` produces `year_of_created_at`.

> **Full details**: See [Universal Function Shorthand](universal_function_shorthand.md) for the complete pattern, which also applies to aggregations (`sum`, `avg`, etc.), math functions, and string functions.

### 1.4 What Passes Through Currently

These SQL constructs currently pass through without ASQL-specific handling:

```asql
-- Intervals (SQL syntax)
current_date - interval "7 days"

-- Date functions  
date_trunc("month", created_at)
datediff("day", start_date, end_date)
dateadd("day", 7, order_date)
```

---

## 2. Date Handling Across SQL Dialects

### 2.1 Current Date/Time

| Dialect | Function |
|---------|----------|
| PostgreSQL | `NOW()`, `CURRENT_DATE`, `CURRENT_TIMESTAMP` |
| MySQL | `NOW()`, `CURDATE()`, `CURRENT_DATE` |
| SQL Server | `GETDATE()`, `CURRENT_TIMESTAMP` |
| BigQuery | `CURRENT_DATE()`, `CURRENT_TIMESTAMP()` |
| Snowflake | `CURRENT_DATE()`, `CURRENT_TIMESTAMP()` |
| DuckDB | `NOW()`, `CURRENT_DATE`, `TODAY()` |

**ASQL Proposal**: Use `now()` and `today()` - SQLGlot handles translation.

### 2.2 Date Truncation

| Dialect | Syntax |
|---------|--------|
| PostgreSQL | `DATE_TRUNC('month', date)` |
| MySQL | `DATE_FORMAT(date, '%Y-%m-01')` or `LAST_DAY(date)` |
| SQL Server | `DATETRUNC(month, date)` (2022+) or `DATEADD(month, DATEDIFF(month, 0, date), 0)` |
| BigQuery | `DATE_TRUNC(date, MONTH)` |
| Snowflake | `DATE_TRUNC('MONTH', date)` |
| DuckDB | `DATE_TRUNC('month', date)` |

**ASQL Proposal**: ASQL's `month(created_at)` already handles this cleanly.

### 2.3 Date Arithmetic (Adding/Subtracting)

| Dialect | Adding | Subtracting |
|---------|--------|-------------|
| PostgreSQL | `date + INTERVAL '7 days'` | `date - INTERVAL '7 days'` |
| MySQL | `DATE_ADD(date, INTERVAL 7 DAY)` | `DATE_SUB(date, INTERVAL 7 DAY)` |
| SQL Server | `DATEADD(day, 7, date)` | `DATEADD(day, -7, date)` |
| BigQuery | `DATE_ADD(date, INTERVAL 7 DAY)` | `DATE_SUB(date, INTERVAL 7 DAY)` |
| Snowflake | `DATEADD('day', 7, date)` | `DATEADD('day', -7, date)` |
| DuckDB | `date + INTERVAL '7 days'` | `date - INTERVAL '7 days'` |

**ASQL Proposal**: See Section 3.2 for proposed clean syntax.

### 2.4 Date Difference

| Dialect | Syntax | Notes |
|---------|--------|-------|
| PostgreSQL | `AGE(date1, date2)` or `date1 - date2` | Returns interval |
| MySQL | `DATEDIFF(date1, date2)` | Returns days |
| SQL Server | `DATEDIFF(day, date1, date2)` | Requires unit |
| BigQuery | `DATE_DIFF(date1, date2, DAY)` | Requires unit |
| Snowflake | `DATEDIFF('day', date1, date2)` | Requires unit |
| DuckDB | `date1 - date2` or `DATE_DIFF('day', date1, date2)` | Flexible |

**ASQL Proposal**: See Section 3.3 for proposed clean syntax.

### 2.5 Interval Syntax Comparison

| Dialect | Interval Syntax |
|---------|-----------------|
| PostgreSQL | `INTERVAL '7 days'`, `INTERVAL '1 month 2 days'` |
| MySQL | `INTERVAL 7 DAY`, `INTERVAL 1 MONTH` |
| SQL Server | N/A (use `DATEADD`) |
| BigQuery | `INTERVAL 7 DAY` |
| Snowflake | N/A (use `DATEADD`) |
| DuckDB | `INTERVAL '7 days'`, `INTERVAL 7 DAY` |

---

## 3. Proposed ASQL Date Improvements

### 3.1 Simple Relative Dates (Inspiration: KQL's `ago()`)

**Problem**: Filtering for "last 7 days" is verbose in SQL.

**Current ASQL**:
```asql
from users
  where last_login >= current_date - interval "7 days"
```

**Proposed ASQL**:
```asql
from users
  where last_login >= 7 days ago
  -- or
  where last_login >= ago(7 days)
```

**Compiles to** (PostgreSQL):
```sql
SELECT * FROM users WHERE last_login >= CURRENT_DATE - INTERVAL '7 days'
```

**More examples**:
```asql
-- Natural language style (preferred)
where created_at >= 30 days ago
where created_at >= 1 month ago
where created_at >= 3 hours ago
where updated_at <= 1 year ago

-- Function style (alternative)  
where created_at >= ago(30 days)
where created_at >= ago(1 month)
```

**Singular/Plural Flexibility**: Both singular and plural forms work identically:
```asql
-- These are all equivalent:
1 day ago
1 days ago      -- grammatically wrong, but works

-- Natural grammar:
1 month ago
3 months ago
1 year ago
5 years ago
```

This allows users to write naturally (`3 months ago`) while not breaking if someone writes `1 months ago`. The parser treats `day`/`days`, `month`/`months`, `year`/`years`, `hour`/`hours`, `week`/`weeks`, `minute`/`minutes`, `second`/`seconds` as equivalent.

**Priority**: HIGH - This is one of the most common date operations in analytics.

### 3.2 Clean Date Arithmetic

**Problem**: Adding/subtracting from dates is inconsistent across dialects.

**Current ASQL**:
```asql
order_date + interval "7 days"   -- Works but verbose
dateadd("day", 7, order_date)    -- Passes through, dialect-specific
```

**Proposed ASQL Syntax (Inline Units)**:
```asql
order_date + 7 days
order_date - 1 month
order_date + 2 weeks
signup_date + 30 days
created_at + 24 hours
updated_at - 90 minutes
```

This is clean, natural, and reads like English. Singular/plural both work:
```asql
order_date + 1 day           -- singular
order_date + 7 days          -- plural
order_date + 1 days          -- also works (flexibility)
```

**Negative values**:
```asql
order_date + -7 days         -- works but awkward
order_date - 7 days          -- preferred (use subtraction)
```

**Compiles to** (varies by dialect):
```sql
-- PostgreSQL
order_date + INTERVAL '7 days'

-- SQL Server  
DATEADD(day, 7, order_date)

-- MySQL
DATE_ADD(order_date, INTERVAL 7 DAY)
```

### 3.3 Clean Date Difference

**Problem**: Getting days/months/years between dates is verbose and inconsistent.

**Current SQL approaches**:
```sql
-- PostgreSQL
EXTRACT(EPOCH FROM (end_date - start_date)) / 86400

-- SQL Server
DATEDIFF(day, start_date, end_date)

-- MySQL  
DATEDIFF(end_date, start_date)
```

**Proposed ASQL**:
```asql
days(end_date - start_date)      -- Returns integer days
months(end_date - start_date)    -- Returns integer months
years(end_date - start_date)     -- Returns integer years
hours(end_date - start_date)     -- Returns integer hours
weeks(end_date - start_date)     -- Returns integer weeks
minutes(end_date - start_date)   -- Returns integer minutes
```

Again, singular/plural both work: `day()`, `days()`, `month()`, `months()`, etc.

**Alternative syntax** (also supported):
```asql
days_between(start_date, end_date)
months_between(start_date, end_date)
```

**Usage examples**:
```asql
from orders
  select 
    days(shipped_date - order_date) as fulfillment_days,
    months(now() - customer_since) as customer_tenure_months,
    hours(completed_at - started_at) as task_duration_hours
```

**Priority**: HIGH - Date differences are used in almost every analytics query.

### 3.4 Date Truncation (Already Good, Minor Improvements)

ASQL's current `month()`, `year()`, etc. are great. Potential additions:

```asql
-- Current (keep these)
month(created_at)    -- Truncate to month start
year(created_at)     -- Truncate to year start
week(created_at)     -- Truncate to week start
day(created_at)      -- Truncate to day (date only)

-- Proposed additions
quarter(created_at)  -- Truncate to quarter start
minute(created_at)   -- Truncate to minute
second(created_at)   -- Truncate to second

-- "Start of" variants (clearer intent)
start_of_month(created_at)
start_of_year(created_at)
start_of_week(created_at)
end_of_month(created_at)
end_of_year(created_at)
```

### 3.5 Date Part Extraction

Separate from truncation, sometimes you just want the numeric part:

```asql
-- Extract just the number (not truncated date)
year_of(created_at)      -- Returns: 2025 (integer)
month_of(created_at)     -- Returns: 1-12 (integer)
day_of(created_at)       -- Returns: 1-31 (integer)
weekday_of(created_at)   -- Returns: 1-7 or 0-6 (integer)
hour_of(created_at)      -- Returns: 0-23 (integer)

-- Alternative: use "num" or "number"
year_num(created_at)
month_num(created_at)
```

**Distinction**:
- `month(created_at)` → `2025-01` (for grouping/time series)
- `month_of(created_at)` → `1` (the month number)

### 3.6 Relative Date Expressions

Beyond `ago()`, support future dates and common patterns:

```asql
-- Relative past
7 days ago
1 month ago
1 year ago

-- Relative future
7 days from now
1 month from now
next_month()
next_year()

-- Common boundaries
start_of_today()
end_of_today()
start_of_month()
end_of_month()
start_of_year()
end_of_year()
start_of_week()

-- Comparison shortcuts
is_today(created_at)
is_yesterday(created_at)
is_this_month(created_at)
is_this_year(created_at)
is_last_7_days(created_at)
is_last_30_days(created_at)
```

---

## 4. Decided Syntax Summary

### Core Date Operations

| Operation | ASQL Syntax | Example |
|-----------|-------------|---------|
| Date literal | `@YYYY-MM-DD` | `@2025-01-15` |
| Relative past | `N unit ago` | `7 days ago`, `1 month ago` |
| Date arithmetic | `date + N unit` | `order_date + 7 days` |
| Date difference | `unit(date1 - date2)` | `days(end - start)` |
| Truncation | `unit(col)` / `unit col` / `unit_col` | `month(created_at)` |
| "of" style | `unit of col` | `year of created_at` → `year_of_created_at` |

### Date Part Extraction (Syntax TBD - See Section 1.2.1)

Recommended: Natural language phrases with optional function equivalents:

| Natural Language | Function | Returns |
|------------------|----------|---------|
| `day of week col` | `day_of_week(col)` | 1-7 |
| `day of month col` | `day_of_month(col)` | 1-31 |
| `day of year col` | `day_of_year(col)` | 1-366 |
| `week of year col` | `week_of_year(col)` | 1-52 |
| `month of year col` | `month_of_year(col)` | 1-12 |
| `quarter of year col` | `quarter_of_year(col)` | 1-4 |

**Singular/plural equivalence**: `day`=`days`, `month`=`months`, `year`=`years`, etc.

> **Note**: Date truncation functions use [Universal Function Shorthand](universal_function_shorthand.md) - the same pattern applies to aggregations and other functions.

---

## 5. Priority Implementation Order

### Phase 1: High Value, Low Complexity
1. **Inline date arithmetic**: `date + 7 days`, `date - 1 month`
2. **Unit difference functions**: `days(end - start)`, `months(end - start)`
3. **Smart column naming**: `year(created_at)` → column `year_created_at`
4. **`quarter()` function** for quarterly truncation
5. **`today()` / `now()` functions**

### Phase 2: High Value, Medium Complexity
6. **Relative dates**: `7 days ago` syntax
7. **Column name interpretation**: Parse `month_created_at` as `month(created_at)`
8. **Space syntax**: `month created_at` as alternative to `month(created_at)`
9. **`start_of_*` / `end_of_*` functions**

### Phase 3: Nice to Have
10. **Boolean date checks**: `is_today()`, `is_this_month()`
11. **Timezone handling**: `at_timezone(timestamp, "America/New_York")`
12. **Natural language dates**: `"last Monday"`, `"first day of month"`

---

## 6. Examples: Before and After

### Example 1: User Retention Query

**SQL (PostgreSQL)**:
```sql
SELECT 
    DATE_TRUNC('month', signup_date) AS month_signup_date,
    COUNT(*) AS signups,
    COUNT(CASE WHEN last_login >= CURRENT_DATE - INTERVAL '7 days' THEN 1 END) AS active_7d,
    AVG(EXTRACT(EPOCH FROM (last_login - signup_date)) / 86400) AS avg_days_to_login
FROM users
WHERE signup_date >= '2024-01-01'
GROUP BY DATE_TRUNC('month', signup_date);
```

**ASQL (Clean)**:
```asql
from users
  where signup_date >= @2024-01-01
  group by month signup_date (
    count(*) as signups,
    count(case when last_login >= 7 days ago then 1 end) as active_7d,
    avg(days(last_login - signup_date)) as avg_days_to_login
  )
-- Note: month signup_date automatically becomes column month_signup_date
```

**Alternative using column name pattern**:
```asql
from users
  where signup_date >= @2024-01-01
  group by month_signup_date (
    count(*) as signups,
    count(case when last_login >= 7 days ago then 1 end) as active_7d,
    avg(days(last_login - signup_date)) as avg_days_to_login
  )
-- ASQL interprets month_signup_date as month(signup_date)
```

### Example 2: Time-Series Grouping

**SQL (PostgreSQL)**:
```sql
SELECT 
    DATE_TRUNC('month', created_at) AS month_created_at,
    DATE_TRUNC('year', created_at) AS year_created_at,
    COUNT(*) AS count
FROM events
GROUP BY 
    DATE_TRUNC('month', created_at),
    DATE_TRUNC('year', created_at)
```

**ASQL (using various syntax options)**:
```asql
from events
  group by month created_at, year created_at (
    count(*) as count
  )
-- Columns automatically: month_created_at, year_created_at

-- Or using underscore pattern directly:
from events  
  group by month_created_at, year_created_at (
    count(*) as count
  )
```

### Example 3: Order Fulfillment Analysis

**SQL**:
```sql
SELECT 
    order_id,
    order_date,
    shipped_date,
    DATEDIFF(day, order_date, shipped_date) AS fulfillment_days,
    DATEADD(day, 30, order_date) AS expected_delivery
FROM orders
WHERE order_date >= CURRENT_DATE - INTERVAL '90 days'
```

**ASQL**:
```asql
from orders
  where order_date >= 90 days ago
  select
    order_id,
    order_date,
    shipped_date,
    days(shipped_date - order_date) as fulfillment_days,
    order_date + 30 days as expected_delivery
```

---

## 7. Inspiration from Other Languages

### 6.1 KQL (Kusto)
```kql
// Relative time - very clean
| where timestamp > ago(7d)
| where timestamp > ago(1h)

// Time functions
| extend month = startofmonth(timestamp)
| extend week = startofweek(timestamp)

// Date arithmetic
| extend future = timestamp + 7d
```

**Takeaways**: The `ago()` function and `7d` duration literals are very intuitive.

### 6.2 DuckDB
```sql
-- Simple interval syntax
SELECT date + INTERVAL 7 DAY
SELECT date - INTERVAL '1 month'

-- Clean date functions
SELECT date_trunc('month', date)
SELECT date_part('year', date)
SELECT age(date1, date2)

-- Duration arithmetic
SELECT INTERVAL '1 year 2 months 3 days'
```

**Takeaways**: DuckDB's flexible interval syntax and `age()` function are nice.

### 6.3 PRQL
```prql
from users
filter signup_date >= @2024-01-01
derive {
  cohort = signup_date | date.month,
  tenure_days = (today - signup_date) | date.day
}
```

**Takeaways**: Method-style date extraction (`.month`, `.day`) is clean.

---

## 8. Date Literal Formats

Current ASQL uses `@2025-01-15` which is good. Consider supporting:

```asql
-- Date only (current)
@2025-01-15

-- With time
@2025-01-15T14:30:00
@2025-01-15 14:30:00

-- With timezone
@2025-01-15T14:30:00Z
@2025-01-15T14:30:00-05:00

-- Relative (proposed)
@today
@yesterday
@now
@start_of_month
@end_of_month
```

---

## 9. Implementation Notes

### 8.1 SQLGlot Integration

SQLGlot already handles date function translation between dialects. Key classes:
- `exp.DateTrunc` - for truncation
- `exp.DateAdd` - for addition
- `exp.DateDiff` - for differences
- `exp.Interval` - for interval literals
- `exp.CurrentDate`, `exp.CurrentTimestamp`

ASQL should:
1. Parse ASQL date syntax into these SQLGlot expressions
2. Let SQLGlot handle dialect-specific SQL generation

### 8.2 Parser Changes Needed (Date-Specific)

1. **Inline interval expressions**: Parse `7 days`, `1 month` after `+` or `-` operators
2. **`ago` keyword**: Parse `N units ago` as `now() - INTERVAL 'N units'`
3. **Unit functions for difference**: Parse `days(expr)` where expr is date subtraction
4. **Singular/plural normalization**: Treat `day`/`days`, `month`/`months` etc. as equivalent
5. **Date literals**: Already implemented with `@` prefix
6. **"of" style for dates**: Parse `year of col` as `year(col)` with alias `year_of_col`

> **Note**: Universal function shorthand implementation details are in [universal_function_shorthand.md](universal_function_shorthand.md).

### 8.3 Backward Compatibility

- Keep supporting `interval "7 days"` syntax
- Keep `date_trunc()`, `datediff()`, `dateadd()` pass-through
- New syntax is additive, not replacing
- Actual column names take precedence over pattern interpretation

---

## 10. Related Documentation

- `UNDERSCORE_SPACE_PRINCIPLE.md`: **Implementation plan for underscore/space flexibility** (prerequisite for date features)
- `universal_function_shorthand.md`: The `func column` / `func_column` pattern
- `SPEC.md` Section 8: Dates & Time
- `UNHANDLED_SQL_FUNCTIONS.md`: Date functions section
- `examples/pairs/05_date_time_analysis.asql`: Current date examples

> **⚠️ Dependency**: Most features in this document (especially date part extraction like `day of week`) depend on implementing the underscore/space principle first. See `UNDERSCORE_SPACE_PRINCIPLE.md` for the implementation plan.

---

## 11. Open Questions

1. **`ago` precedence**: How does `7 days ago` interact with other operators?
   - `created_at >= 7 days ago and status == "active"` - should work naturally
   - Need to ensure parser handles this correctly

2. **Week start**: Should `week()` start on Sunday or Monday?
   - Proposal: Configurable, default to ISO (Monday)
   - Alternative: `week_sunday()`, `week_monday()`

3. **Timezone handling**: How explicit should timezone support be?
   - Minimal: Just pass through `AT TIME ZONE`
   - Enhanced: `at_timezone(timestamp, "America/New_York")`

4. **Extended patterns**: Could we support `days_since_created_at` → `days(now() - created_at)`?
   - Recommendation: Start with basic patterns, expand based on user feedback

> **Note**: Open questions about function shorthand (column conflicts, multi-word columns, two-argument functions) are in [Universal Function Shorthand](universal_function_shorthand.md).

---

**End of Document**

