# ASQL Dialect Limitations

This document tracks features that have inconsistent behavior or limited support across SQL dialects.

---

## Compile-Time Validation

ASQL now validates feature support at compile time, catching unsupported feature + dialect combinations before generating invalid SQL.

### Error Behavior

- **❌ Not supported** → Raises `ASQLDialectError` with helpful error message
- **⚠️ Partial support** → May raise `ASQLDialectWarning` for edge cases
- **🐛 Known bug** → Raises `ASQLDialectWarning` with issue link

### Example Error Messages

When using `except` on PostgreSQL without a schema:

```
ASQLDialectError: Column operators ('except', 'rename', 'replace') are not supported for PostgreSQL.

The 'except' operator requires EXCEPT/EXCLUDE syntax which PostgreSQL doesn't support.

Options:
  1. Provide a schema to enable automatic column enumeration (see docs/schema.md)
  2. Use explicit SELECT: 'select id, name, email from users'
  3. Use a dialect with EXCLUDE support: BigQuery, Snowflake, DuckDB

See: https://asql.dev/docs/dialect-limitations#column-operators
```

When using slice syntax `[1:5]` on PostgreSQL (known bug):

```
ASQLDialectWarning: Slice syntax '[start:end]' has known issues for PostgreSQL (Issue #77).

The generated SQL may be invalid. Use SUBSTRING() instead:
  'select substring(name, 1, 5) as prefix'

See: https://asql.dev/docs/dialect-limitations#slice-syntax
```

---

## Features with Limited Dialect Support

### 1. Column Operators (`except`, `rename`, `replace`)

**Tracking**: [Issue #80](https://github.com/davefowler/asql/issues/80) - Schema-aware fallback planned

**Features**: 
- `except col1, col2` - exclude columns from result
- `rename old as new` - rename columns  
- `replace col with expr` - replace column values
- `select *, expr as col` - column override

```asql-play
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

**Compile-time behavior**:
- **Without schema**: Raises `ASQLDialectError` for unsupported dialects (PostgreSQL, MySQL, SQLite, Redshift)
- **With schema**: Raises `ASQLDialectWarning` - ASQL attempts automatic column expansion (Issue #80)

**Workaround for unsupported dialects**: 
- Provide a schema to enable automatic column enumeration
- List columns explicitly: `select id, name, email from users`
- Use a dialect with native EXCEPT/EXCLUDE support: BigQuery, Snowflake, DuckDB

---

### 2. Pivot Syntax

**Feature**: Transform row values into columns using the `pivot` keyword.

```asql
from sales
  pivot sum(amount) by category values ('A', 'B', 'C')
```

**Behavior by Dialect**:

| Dialect | Static Pivot (with values) | Dynamic Pivot (without values) |
|---------|---------------------------|-------------------------------|
| DuckDB | ✅ Native PIVOT | ✅ Native PIVOT |
| Snowflake | ✅ Native PIVOT | ✅ Native PIVOT (ANY ORDER BY) |
| BigQuery | ✅ Native PIVOT | ❌ Error (values required) |
| PostgreSQL | ✅ CASE/WHEN fallback | ❌ Error (values required) |
| MySQL | ✅ CASE/WHEN fallback | ❌ Error (values required) |
| SQLite | ✅ CASE/WHEN fallback | ❌ Error (values required) |
| Redshift | ✅ CASE/WHEN fallback | ❌ Error (values required) |

**Static Pivot** (explicit values):
```asql
from sales
  pivot sum(amount) by category values ('A', 'B', 'C')
```

- For DuckDB/Snowflake/BigQuery: Generates native `PIVOT` syntax
- For PostgreSQL/MySQL/SQLite: Generates `CASE WHEN` expressions

**Dynamic Pivot** (database determines values at runtime):
```asql
from sales
  pivot sum(amount) by category  -- No explicit values
```

- Only supported for DuckDB, Snowflake, and BigQuery
- Other dialects require explicit values and will show a helpful error:
  ```
  ValueError: Dynamic pivot (without explicit values) is not supported for postgres.
  Please specify values explicitly:
    pivot sum(amount) by category values ('val1', 'val2', ...)
  ```

**Example Output for DuckDB**:
```sql
SELECT * FROM (PIVOT sales ON category IN ('A', 'B', 'C') USING SUM(amount)) AS __pivot__
```

**Example Output for PostgreSQL** (CASE/WHEN fallback):
```sql
SELECT SUM(CASE WHEN category = 'A' THEN amount END) AS A,
       SUM(CASE WHEN category = 'B' THEN amount END) AS B,
       SUM(CASE WHEN category = 'C' THEN amount END) AS C
FROM sales
```

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

**Compile-time behavior**: No validation errors or warnings (edge cases are handled at runtime).

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
| Native PIVOT syntax | ✅ | ✅ | ✅ | ❌ (uses CASE/WHEN) | ❌ | ❌ | ❌ |
| Dynamic pivot (no values) | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Auto-spine (basic) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Auto-spine with ROLLUP/CUBE | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ❌ | ⚠️ |
| `generate_series` for spines | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| Slice syntax `[1:5]` | 🐛 | 🐛 | ✅ | 🐛 | 🐛 | 🐛 | 🐛 |

Legend:
- ✅ Fully supported - No validation errors or warnings
- ⚠️ Partial support / edge cases - May raise `ASQLDialectWarning`
- ❌ Not supported - Raises `ASQLDialectError` (unless schema enables fallback)
- 🐛 Bug - Raises `ASQLDialectWarning` with issue link (see Known Bugs section)

---

## Known Bugs (Documented but Broken)

These features are documented in the spec but have broken implementations for certain dialects.

### 3. Slice Syntax `[start:end]` 🐛

**Tracking**: [Issue #77](https://github.com/davefowler/asql/issues/77)

**Feature**: Python-style string/array slicing

```asql
from users
  select email[1:5] as prefix
```

**Current behavior**:

| Dialect | Output | Works? |
|---------|--------|--------|
| DuckDB | `email[1 : 5]` | ✅ Native support |
| PostgreSQL | `email[1 : 5]` | ❌ Invalid (Postgres uses `[]` for arrays only) |
| Snowflake | `email[GET_PATH(1, '5')]` | ❌ Completely wrong |
| BigQuery | `email[1 : 5]` | ❌ Invalid for strings |
| MySQL | `email[1 : 5]` | ❌ Invalid syntax |

**Compile-time behavior**: Raises `ASQLDialectWarning` for all dialects except DuckDB (which has native support).

**Fix planned**: Convert to `SUBSTRING()` in preparser, let SQLGlot handle dialect-specific output.

**Workaround**: Use `SUBSTRING()` directly:

```asql
from users
  select substring(email, 1, 5) as prefix
```

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

- [x] Add compile-time warnings for features not supported by target dialect - [Issue #81](https://github.com/davefowler/asql/issues/81) ✅
- [ ] Implement column expansion fallback for dialects without `EXCEPT`/`EXCLUDE` - [Issue #80](https://github.com/davefowler/asql/issues/80)
- [ ] Add comprehensive ROLLUP/CUBE testing for auto-spine
- [ ] Document all dialect-specific SQL generation differences
