# ASQL Feature Status - Complete Breakdown

**Last Updated**: December 2024  
**Total Tests**: 434 tests (all passing ✅)

## ✅ IMPLEMENTED FEATURES

### Core Pipeline Operators ✅

| Feature | Status | Tests | Notes |
|---------|--------|-------|-------|
| FROM clause | ✅ Complete | ✅ | Foundation of all queries |
| WHERE clause | ✅ Complete | ✅ | All comparison/logical operators |
| SELECT clause | ✅ Complete | ✅ | Column selection, expressions |
| GROUP BY | ✅ Complete | ✅ | Block syntax `group by col (aggs)` |
| ORDER BY / SORT | ✅ Complete | ✅ | `-` prefix for DESC |
| TAKE / LIMIT | ✅ Complete | ✅ | Row limiting |
| JOIN | ✅ Complete | ✅ | Inner, left, right, outer |

### Expressions & Operators ✅

| Feature | Status | Syntax |
|---------|--------|--------|
| Comparison | ✅ | `==`, `=`, `!=`, `<>`, `<`, `>`, `<=`, `>=` |
| NULL checks | ✅ | `is null`, `is not null` |
| Logical | ✅ | `and`, `or`, `not` |
| Membership | ✅ | `in (...)`, `not in (...)` |
| Arithmetic | ✅ | `+`, `-`, `*`, `/`, `%` |
| COALESCE | ✅ | `??` operator |
| Type casting | ✅ | `::` operator |

### Aggregation Functions ✅

| Function | Status | Alias |
|----------|--------|-------|
| `count(*)` | ✅ | `#` shorthand |
| `sum()` | ✅ | `total` |
| `avg()` | ✅ | `average` |
| `min()` | ✅ | - |
| `max()` | ✅ | - |
| `count(distinct)` | ✅ | - |

### Date & Time ✅

| Feature | Status | Example |
|---------|--------|---------|
| Date literals | ✅ | `@2024-01-01` |
| Relative dates | ✅ | `7 days ago`, `3 months from now` |
| Date arithmetic | ✅ | `order_date + 7 days` |
| Date truncation | ✅ | `year()`, `month()`, `week()`, `day()`, `quarter()` |
| Date extraction | ✅ | `day_of_week()`, `week_of_year()`, `month_of_year()` |
| Time since/until | ✅ | `days_since_created_at`, `months_until_due_date` |
| Date spine | ✅ | `date_spine(start, end, grain)` |

### Window Functions ✅

| Feature | Status | Syntax |
|---------|--------|--------|
| per command | ✅ | `per customer_id first by -order_date` |
| Ranking | ✅ | `per group rank by col`, `dense rank` |
| Row numbering | ✅ | `per group number by col` |
| QUALIFY | ✅ | `qualify row_num == 1` |
| DISTINCT ON | ✅ | `distinct on (cols)` |
| prior/next | ✅ | `prior(col)`, `next(col, n)` |
| Running aggs | ✅ | `running_sum()`, `running_avg()`, `running_count()` |
| Rolling aggs | ✅ | `rolling_sum(col, n)`, `rolling_avg(col, n)` |
| first/last | ✅ | `first(col order by x)`, `last(col order by x)` |
| arg_max/min | ✅ | `arg_max(value_col, sort_col)` |

### CTEs & Variables ✅

| Feature | Status | Syntax |
|---------|--------|--------|
| set | ✅ | `set name = query` |
| with | ✅ | `with name = query`, `with name as query` |
| stash as | ✅ | `... stash as cte_name ...` |

### Utility Functions ✅

| Function | Status | Description |
|----------|--------|-------------|
| `safe_divide()` | ✅ | NULL on divide-by-zero |
| `key()` | ✅ | Surrogate key generation |

### Dialect Support ✅

- ✅ PostgreSQL
- ✅ MySQL
- ✅ BigQuery
- ✅ Snowflake
- ✅ Redshift
- ✅ SQLite
- ✅ DuckDB
- ✅ ANSI SQL (default)

---

## ❌ NOT IMPLEMENTED (Planned)

Features documented in SPEC.md but not yet implemented:

### String Matching (Section 4.5)
- ❌ `contains "pattern"`
- ❌ `starts with "pattern"`
- ❌ `ends with "pattern"`
- ❌ `matches "regex"`
- ❌ `ignore case` modifier

### Conditional Expressions (Section 4.7)
- ❌ `when status is "active" then 1 otherwise 0`
- ❌ Multiple conditions with `is`, `<`, `>`, `in`

### Natural Language Aggregates (Section 5.5)
- ❌ `# of Users by country` (inferred FROM)
- ❌ `Sum of revenue by region`

### Automatic Joins (Section 7.2)
- ❌ Arrow syntax: `from opportunities->owners`
- ❌ FK inference from schema
- ❌ Plural/singular handling

### Column Operators (Section 13.1)
- ❌ `except email, phone`
- ❌ `rename id as user_id`
- ❌ `prefix user_`

### Deduplicate Operator (Section 13.2)
- ❌ `deduplicate by user_id order by -created_at`

### Pivot/Unpivot (Section 13.3)
- ❌ `pivot amount by category`
- ❌ `unpivot cols into name, value`

### Fill/Gap Filling (Section 13.4)
- ❌ `fill month`
- ❌ `fill month with {revenue: 0}`

### Safe Cast (Section 13.8)
- ❌ `value::integer?` (returns NULL on failure)

---

## 📊 Implementation Summary

| Category | Implemented | Not Implemented | Percentage |
|----------|-------------|-----------------|------------|
| Core Operators | 7/7 | 0 | 100% |
| Expressions | 7/7 | 0 | 100% |
| Aggregations | 5/5 | 0 | 100% |
| Date/Time | 7/7 | 0 | 100% |
| Window Functions | 10/10 | 0 | 100% |
| CTEs | 3/3 | 0 | 100% |
| Dialects | 8/8 | 0 | 100% |
| String Matching | 0/5 | 5 | 0% |
| Conditionals | 0/1 | 1 | 0% |
| Natural Lang | 0/2 | 2 | 0% |
| Auto Joins | 0/3 | 3 | 0% |
| Column Ops | 0/3 | 3 | 0% |
| Transforms | 0/4 | 4 | 0% |

**Overall**: ~75% of spec implemented (all core features complete)

---

## 🎯 Next Implementation Priority

### High Priority
1. **String Matching** - Common use case, design complete in spec
2. **Conditional Expressions** (`when`) - Needed for business logic

### Medium Priority
3. **Column Operators** (`except`, `rename`, `prefix`)
4. **Deduplicate Operator** - Though `per first by` works as alternative

### Lower Priority
5. **Pivot/Unpivot** - Complex, can use SQL directly
6. **Fill** - Can use date_spine + left join
7. **Natural Language Aggregates** - Nice-to-have syntactic sugar
8. **Automatic Joins** - Requires schema resolution infrastructure
