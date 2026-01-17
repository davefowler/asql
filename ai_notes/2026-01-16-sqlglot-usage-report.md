# Code Quality Report: Where We're Still Being Messy

**Date:** 2026-01-16  
**Context:** Post-parser rewrite audit - what else needs cleanup?

## Executive Summary

The preparser is dead 🎉. But let's be honest about what's still messy. This report covers:
1. **String SQL building** - the new preparser-lite
2. **Bare `except Exception` handlers** - hiding bugs
3. **Duplicated patterns** - DRY violations
4. **`exp.Anonymous` abuse** - avoiding proper SQLGlot types
5. **Regex that should be AST operations**

---

## 🔴 High Priority: String SQL Building in `auto_spine.py`

**The Problem:** We killed the preparser but `auto_spine.py` is basically doing the same thing - building SQL strings and parsing them back.

```python
# Lines 916-923 - This is preparser energy
final_sql = (
    f"SELECT {', '.join(select_cols)} "
    f"FROM {combined_spine_name} "
    f"LEFT JOIN {data_cte_name} ON {' AND '.join(join_conditions)}"
)
sqlglot.parse_one(final_sql.strip(), dialect=dialect)  # 🤮
```

**Why it's bad:**
- Quoting issues waiting to happen
- No type safety
- Parse errors at runtime instead of construction time
- 23 calls to `.sql()` in this file alone

**The fix:** Build AST directly:
```python
# What it should be
final_stmt = exp.Select(
    expressions=[...],
).from_(combined_spine_name).join(
    data_cte_name,
    on=exp.And(expressions=join_conditions),
    kind="LEFT",
)
```

**Effort:** Medium-high (1,308 line file, but well-documented)

---

## 🔴 High Priority: Bare `except Exception` Handlers

**The Problem:** 20 instances of `except Exception` or `except:` that swallow errors silently.

**Worst offenders:**

```python
# dialect.py:1003-1008 - Silently ignores conversion errors
try:
    start_num = int(start.to_py())
except Exception:
    start_num = None  # 🤷 who knows what went wrong

# dialect.py:1141-1145 - Nested try/except that gives up
try:
    condition_expr = sqlglot.parse_one(cond_str, dialect="asql")
except Exception:
    try:
        condition_expr = sqlglot.parse_one(cond_str)
    except Exception:
        pass  # Just... give up?
```

**Why it's bad:**
- Hides real bugs
- Makes debugging impossible
- "It works on my machine" syndrome

**The fix:** Catch specific exceptions, log warnings, or let it fail loudly.

**Effort:** Low (find/replace + add logging)

---

## 🟡 Medium Priority: `exp.Anonymous` Abuse

**The Problem:** Using `exp.Anonymous` when proper SQLGlot types exist.

```python
# cohort_transform.py:136-139
return exp.Anonymous(
    this="DATE_TRUNC",
    expressions=[exp.Literal.string(granularity), col]
)

# Should be:
return exp.DateTrunc(this=col, unit=exp.Literal.string(granularity))
```

**Why it's bad:**
- SQLGlot can't optimize or transpile properly
- Dialect-specific argument ordering breaks
- No type checking

**Where it happens:**
- `cohort_transform.py` - DATE_TRUNC, FLOOR, EXTRACT
- `functions.py` - Some date diff functions
- `auto_spine.py` - GENERATE_SERIES

**The fix:** Use proper `exp.DateTrunc`, `exp.Floor`, `exp.Extract`, etc.

**Effort:** Low-medium (straightforward replacements)

---

## 🟡 Medium Priority: Duplicated Patterns

### Pattern 1: Getting FROM table name

Three different implementations:
```python
# underscore_shorthands.py:25
def _single_from_table_name(stmt: exp.Expression) -> str | None:

# auto_qualify.py:20-27
from_expr = expression.find(exp.From)
if from_expr:
    from_table = from_expr.this
    ...

# Various inline implementations
```

### Pattern 2: Extracting alias names

```python
# alias_reuse.py:20-31
def _extract_alias_name(expr: exp.Expression) -> Optional[str]:
    if isinstance(expr, exp.Alias):
        alias = expr.alias
        if isinstance(alias, exp.Identifier):
            return alias.name
        ...

# Similar code in auto_alias.py, auto_spine.py, reverse_compiler.py
```

**The fix:** Create `asql/compiler/utils.py` with shared helpers.

**Effort:** Low (extract and consolidate)

---

## 🟡 Medium Priority: Post-Parse String Manipulation

**The Problem:** `list_comprehension.py` uses regex on generated SQL.

```python
# Lines 22-41
pattern = r'ARRAY\s*\(\s*SELECT\s+(.+?)\s+(?:AS\s+\w+\s+)?FROM\s+UNNEST...'
result = re.sub(pattern, replace_with_duckdb_syntax, sql, flags=re.IGNORECASE)
```

**Why it's bad:**
- Fragile regex on SQL
- Runs AFTER SQLGlot generation
- Edge cases will break

**The fix:** Implement `ASQLGenerator.comprehension_sql()` for DuckDB dialect.

**Effort:** Medium (need to understand SQLGlot Generator)

---

## 🟢 Low Priority: Regex That's Actually Fine

These are OK to keep:

| File | Use | Why it's fine |
|------|-----|---------------|
| `inline_settings.py` | `-- dialect: snowflake` | Pre-parse comment extraction |
| `reverse_compiler.py` | ANSI code stripping | Cosmetic error cleanup |
| `pivot_fallback.py` | Column name sanitization | Data cleanup, not SQL parsing |
| `schema.py` | dbt `ref()` parsing | External format, not our SQL |

---

## 📊 Messiness Metrics

| Category | Count | Files |
|----------|-------|-------|
| String SQL building | ~30 instances | `auto_spine.py` |
| Bare `except Exception` | 20 instances | 11 files |
| `exp.Anonymous` misuse | ~15 instances | 3 files |
| Duplicated helpers | 4 patterns | 6 files |
| Post-parse regex | 2 functions | 1 file |

---

## 🎯 Recommended Cleanup Order

### Sprint 1: Quick Wins
1. **Replace bare `except Exception`** with specific catches + logging
2. **Extract shared helpers** to `compiler/utils.py`
3. **Replace `exp.Anonymous`** with proper SQLGlot types

### Sprint 2: `auto_spine.py` Refactor
4. **Refactor string building** to AST-first construction
5. **Add tests** for edge cases the string building hides

### Sprint 3: Generator Customization
6. **Implement `ASQLGenerator`** transforms for dialect-specific output
7. **Remove `list_comprehension.py`** post-processing

---

## Files by Messiness Score

| File | Lines | Messiness | Notes |
|------|-------|-----------|-------|
| `auto_spine.py` | 1,308 | 🔴 High | String SQL building |
| `dialect.py` | 3,090 | 🟡 Medium | Bare excepts, but mostly clean |
| `cohort_transform.py` | 372 | 🟡 Medium | `exp.Anonymous` abuse |
| `reverse_compiler.py` | 827 | 🟢 Low | Mostly clean, some bare excepts |
| `alias_reuse.py` | 430 | 🟢 Low | Clean, just has duplicated patterns |

---

## Conclusion

The preparser was the worst offender and it's gone. What remains is:

1. **One big mess** (`auto_spine.py`) that needs a focused refactor
2. **Scattered small messes** (bare excepts, duplicated code) that are easy fixes
3. **Some technical debt** (`exp.Anonymous`, post-parse regex) that's annoying but not urgent

The codebase is in much better shape than before PR 149. These are polish items, not architectural problems.

---

*Report generated by honest assessment of ASQL codebase post-PR-149 merge.*
