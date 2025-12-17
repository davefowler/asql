# ASQL Implementation Status

**Last Updated**: December 2024  
**Test Status**: ✅ 434 tests passing  
**Implementation Phase**: Core Complete

## ✅ Fully Implemented Features

### Core Pipeline Operators
- **FROM** - Query source specification
- **SELECT** - Column selection and expressions
- **WHERE** - Row filtering with all operators
- **GROUP BY** - Aggregation with block syntax `group by col ( aggregations )`
- **ORDER BY / SORT** - Sorting with `-` prefix for descending
- **LIMIT / TAKE** - Row limiting
- **JOIN** - Inner, left, right, outer joins with `on` conditions

### Expressions & Operators
- **Comparison**: `==`, `=`, `!=`, `<>`, `<`, `>`, `<=`, `>=`
- **NULL checks**: `is null`, `is not null`
- **Logical**: `and`, `or`, `not`
- **Membership**: `in`, `not in`
- **Arithmetic**: `+`, `-`, `*`, `/`, `%`
- **COALESCE**: `??` operator (`name ?? "Unknown"`)
- **Type casting**: `::` operator (`created_at::DATE`)

### Aggregation Functions
- `#` shorthand for `COUNT(*)`
- `sum()`, `avg()`, `count()`, `min()`, `max()`
- Natural language: `total`, `average` as aliases

### Date & Time Functions
- **Date literals**: `@2024-01-01`
- **Relative dates**: `7 days ago`, `3 months from now`
- **Date arithmetic**: `order_date + 7 days`
- **Date truncation**: `year()`, `month()`, `week()`, `day()`, `hour()`, `quarter()`
- **Date extraction**: `day_of_week()`, `week_of_year()`, `month_of_year()`
- **Time since/until**: `days_since_created_at`, `months_until_due_date`
- **Date spine**: `date_spine(start, end, grain)` for generating date sequences

### Window Functions
- **per command**: `per customer_id first by -order_date` (deduplication)
- **Ranking**: `per group rank by col`, `per group dense rank by col`
- **Row numbering**: `per group number by col`, `number by col`
- **QUALIFY**: Filter window function results
- **DISTINCT ON**: PostgreSQL-style deduplication
- **prior() / next()**: `LAG`/`LEAD` simplified
- **Running aggregates**: `running_sum()`, `running_avg()`, `running_count()`
- **Rolling aggregates**: `rolling_sum(col, n)`, `rolling_avg(col, n)`
- **first() / last()**: `first(col order by x)`
- **arg_max() / arg_min()**: ClickHouse-style aggregates

### Variables & CTEs
- **set**: `set active_users = from users where is_active`
- **with**: `with active_users = from users where is_active`
- **stash as**: `... stash as cte_name` for mid-pipeline CTEs

### Utility Functions
- **safe_divide()**: Returns NULL on divide-by-zero
- **key()**: Surrogate key generation

### Dialect Support
- PostgreSQL
- MySQL
- BigQuery
- Snowflake
- Redshift
- SQLite
- DuckDB
- ANSI SQL (default)

### Architecture
- **Pre-parser**: Structural transformations (FROM-first, aggregate blocks, etc.)
- **ASQL Dialect**: SQLGlot dialect for expression parsing
- **Compiler**: Full ASQL → SQL transpilation
- **Reverse Compiler**: SQL → ASQL translation

---

## ❌ Not Yet Implemented (Planned in Spec)

These features are documented in `SPEC.md` but not yet implemented:

### String Matching (Section 4.5)
- `contains "pattern"`
- `starts with "pattern"`
- `ends with "pattern"`
- `matches "regex"`
- `ignore case` modifier

**Workaround**: Use SQL `LIKE` syntax directly.

### Conditional Expressions (Section 4.7)
- `when status is "active" then 1 otherwise 0`
- `when age < 18 then "minor" otherwise "adult"`

**Workaround**: Use SQL `CASE WHEN ... THEN ... ELSE ... END`.

### Natural Language Aggregates (Section 5.5)
- `# of Users by country` (inferred FROM)
- `Sum of revenue by region`

**Workaround**: Use explicit `from table group by col ( aggregations )`.

### Automatic Joins (Section 7.2)
- Arrow syntax: `from opportunities->owners`
- FK inference from schema
- Plural/singular handling

**Workaround**: Use explicit `join` with `on` condition.

### Column Operators (Section 13.1)
- `except email, phone` - exclude columns
- `rename id as user_id` - rename columns
- `prefix user_` - prefix column names

**Workaround**: Explicitly list columns in `select`.

### Deduplicate Operator (Section 13.2)
- `deduplicate by user_id order by -created_at`

**Workaround**: Use `per group first by -col` instead.

### Pivot/Unpivot (Section 13.3)
- `pivot amount by category`
- `unpivot jan, feb, mar into month, value`

**Workaround**: Write SQL pivot queries directly.

### Fill / Gap Filling (Section 13.4)
- `fill month` - auto-fill time series gaps
- `fill month with {revenue: 0}`

**Workaround**: Join with a date spine manually.

### Safe Cast (Section 13.8)
- `value::integer?` - returns NULL on cast failure

**Workaround**: Use database-specific `TRY_CAST` or `SAFE_CAST`.

---

## Example Working Queries

```python
from asql import compile

# Basic query
compile("from users")
# → SELECT * FROM users

# Filtering with arithmetic
compile('from users where age + 5 >= 23')
# → SELECT * FROM users WHERE age + 5 >= 23

# Aggregation with block syntax
compile("from users group by country ( # as total_users, avg(age) as avg_age )")
# → SELECT country, COUNT(*) AS total_users, AVG(age) AS avg_age FROM users GROUP BY country

# JOIN (& for INNER, &? for LEFT, ?& for RIGHT, ?&? for FULL, * for CROSS)
compile("from orders & users on orders.user_id == users.id")
# → SELECT * FROM orders JOIN users ON orders.user_id = users.id

# COALESCE with ??
compile('from users select name ?? "Unknown" as display_name')
# → SELECT COALESCE(name, 'Unknown') AS display_name FROM users

# Type casting
compile("from users select created_at::DATE as signup_date")
# → SELECT CAST(created_at AS DATE) AS signup_date FROM users

# Date literal and relative date
compile("from orders where order_date >= @2024-01-01")
compile("from orders where created_at >= 7 days ago")

# Window function with per command
compile("from orders per customer_id first by -order_date")
# → Keeps most recent order per customer

# Running aggregate
compile("from transactions order by date select running_sum(amount) as cumulative")

# CTE with set
compile('set active = from users where status == "active" from active group by country ( # as total )')
```

---

## Test Coverage

- **434 tests** across 21 test files
- Covers all implemented features
- Edge cases and error handling
- Dialect-specific SQL generation
- Real-world query patterns

## Next Steps

See `SPEC.md` for planned features and `ai_notes/` for implementation notes.
