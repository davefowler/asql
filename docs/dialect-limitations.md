# ASQL Dialect Limitations

This document tracks features that have inconsistent behavior or limited support across SQL dialects.

---

## Features with Limited Dialect Support

### 1. Column Operators (`except`, `rename`, `replace`)

**Features**: 
- `except col1, col2` - exclude columns from result
- `rename old as new` - rename columns  
- `replace col with expr` - replace column values
- `select *, expr as col` - column override

```asql
from users
  except password
  rename id as user_id
  replace name with upper(name)
```

**Compiles to**:
- BigQuery: `SELECT * EXCEPT(password, id, name), id AS user_id, upper(name) AS name FROM users` ✅
- Snowflake: `SELECT * EXCLUDE(...), ... FROM users` ✅
- DuckDB: `SELECT * EXCLUDE(...), ... FROM users` ✅
- PostgreSQL: ❌ **Not supported** - no `EXCEPT`/`EXCLUDE` syntax
- MySQL: ❌ **Not supported**
- SQLite: ❌ **Not supported**
- Redshift: ❌ **Not supported**

**Workaround for unsupported dialects**: List columns explicitly instead of using `*`.

---

## Features with Known Edge Cases

### 2. Auto-Spine with GROUPING SETS / ROLLUP / CUBE

**Feature**: ASQL automatically adds gap-filling spines for date truncations in GROUP BY.

**Issue**: Auto-spine may produce unexpected results with advanced grouping operations:

```asql
# This may not work correctly
from sales
group by rollup(year(date), month(date)) (
  sum(amount) ?? 0 as revenue
)
```

**Problem**: 
- ROLLUP/CUBE produce NULL values with special meaning (subtotals, grand totals)
- Auto-spine's date range detection may not account for these NULL patterns
- The cross-join of spine values with ROLLUP patterns can produce invalid combinations

**Current behavior**: Auto-spine attempts to handle ROLLUP/CUBE by including NULL in spines and filtering invalid patterns, but this is not fully tested with all edge cases.

**Workaround**: Disable auto-spine for queries using GROUPING SETS:

```asql
SET auto_spine = false;
from sales
group by rollup(year(date), month(date)) (
  sum(amount) as revenue
)
```

---

## Dialect Feature Matrix

| Feature | BigQuery | Snowflake | DuckDB | PostgreSQL | MySQL | SQLite | Redshift |
|---------|----------|-----------|--------|------------|-------|--------|----------|
| Column operators (`except`, `rename`, `replace`) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Auto-spine (basic) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Auto-spine with ROLLUP/CUBE | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ❌ | ⚠️ |
| `generate_series` for spines | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |

Legend:
- ✅ Fully supported
- ⚠️ Partial support / edge cases
- ❌ Not supported

---

## Reporting Issues

If you encounter dialect-specific issues:

1. Note which dialect you're using
2. Provide the ASQL query
3. Show the generated SQL
4. Describe the expected vs actual behavior

Open an issue at: https://github.com/davefowler/asql/issues

---

## Future Improvements

- [ ] Add compile-time warnings for features not supported by target dialect
- [ ] Implement column expansion fallback for dialects without `EXCEPT`/`EXCLUDE`
- [ ] Add comprehensive ROLLUP/CUBE testing for auto-spine
- [ ] Document all dialect-specific SQL generation differences
