# ASQL Implementation Improvements Report

**Date**: 2026-01-08

## Changes Made Today

### 1. Simplified TRANSFORM_PARSERS Join Methods

**Before** (8 separate functions, 63 lines):
```python
def _parse_asql_left_join(self, query: exp.Query) -> exp.Query:
    self._match_text_seq("JOIN") or self._match_text_seq("OUTER", "JOIN")
    return self._parse_asql_join(query, kind="LEFT")

def _parse_asql_right_join(self, query: exp.Query) -> exp.Query:
    self._match_text_seq("JOIN") or self._match_text_seq("OUTER", "JOIN")
    return self._parse_asql_join(query, kind="RIGHT")

def _parse_asql_full_join(self, query: exp.Query) -> exp.Query:
    self._match_text_seq("OUTER")
    self._match_text_seq("JOIN")
    return self._parse_asql_join(query, kind="FULL OUTER")

def _parse_asql_cross_join(self, query: exp.Query) -> exp.Query:
    self._match_text_seq("JOIN")
    return self._parse_asql_join(query, kind="CROSS")

def _parse_asql_amp_join(self, query: exp.Query, kind: str = "INNER") -> exp.Query:
    return self._parse_asql_join(query, kind=kind)

def _parse_asql_full_outer_join(self, query: exp.Query) -> exp.Query:
    prev_token = self._tokens[self._index - 1] if self._index > 0 else None
    if prev_token and prev_token.text == "?&?":
        return self._parse_asql_join(query, kind="FULL OUTER")
    return query

def _parse_asql_star_join(self, query: exp.Query) -> exp.Query:
    return self._parse_asql_join(query, kind="CROSS")
```

**After** (2 functions, 7 lines):
```python
def _parse_join_kind(self, query: exp.Query, kind: str, skip_keywords: tuple = ()) -> exp.Query:
    for kw in skip_keywords:
        self._match_text_seq(*kw.split())
    return self._parse_asql_join(query, kind=kind)

def _parse_asql_qmark_join(self, query: exp.Query) -> exp.Query:
    prev = self._tokens[self._index - 1].text if self._index > 0 else ""
    return self._parse_asql_join(query, kind="LEFT" if prev == "&?" else "RIGHT")
```

**TRANSFORM_PARSERS now use inline lambdas**:
```python
"LEFT": lambda self, query: self._parse_join_kind(query, "LEFT", ("JOIN", "OUTER JOIN")),
"RIGHT": lambda self, query: self._parse_join_kind(query, "RIGHT", ("JOIN", "OUTER JOIN")),
"FULL": lambda self, query: self._parse_join_kind(query, "FULL OUTER", ("OUTER", "JOIN")),
"CROSS": lambda self, query: self._parse_join_kind(query, "CROSS", ("JOIN",)),
```

### 2. Converted Recurse to Pure AST

**Before** (string SQL building):
```python
anchor_sql = f"SELECT *, 1 AS _level FROM {table_name} WHERE {anchor_condition}"
recursive_sql = (
    f"SELECT {table_alias}.*, {cte_name}._level + 1 "
    f"FROM {table_name} {table_alias} "
    f"JOIN {cte_name} ON {table_alias}.{fk_col_name} = {cte_name}.id "
    f"WHERE {cte_name}._level < {max_depth}"
)
cte_sql = f"{anchor_sql} UNION ALL {recursive_sql}"
cte_query = sqlglot.parse_one(cte_sql)  # String → Parse → AST
```

**After** (pure AST):
```python
anchor_query = (
    exp.select(exp.Star(), exp.Alias(this=exp.Literal.number(1), alias="_level"))
    .from_(table_name, copy=False)
    .where(anchor_condition, copy=False)
)

recursive_query = (
    exp.select(
        exp.Column(this=exp.Star(), table=table_alias),
        exp.Add(this=exp.Column(this="_level", table=cte_name), expression=exp.Literal.number(1))
    )
    .from_(exp.Table(...), copy=False)
    .join(cte_name, on=exp.EQ(...), copy=False)
    .where(exp.LT(...), copy=False)
)

cte_body = exp.Union(this=anchor_query, expression=recursive_query, distinct=False)
```

### 3. Simplified FK Shorthand

**Before**: 83 lines with lots of boilerplate
**After**: 62 lines with schema-aware intelligence

---

## Remaining String SQL Building (Priority Fix)

### `auto_spine.py` - 1,287 lines with extensive string SQL

The `auto_spine.py` file has **7 functions** that build SQL strings directly:

| Function | Lines | Purpose |
|----------|-------|---------|
| `_build_spine_cte_sql` | ~80 | Orchestrates spine CTE building |
| `_build_date_spine_from_data_bounds_sql` | ~70 | Date range from data MIN/MAX |
| `_build_explicit_values_spine_sql` | ~25 | Explicit value list (guarantee) |
| `_build_date_spine_with_filter_sql` | ~80 | Date spine with WHERE filter |
| `_build_categorical_spine_sql` | ~10 | DISTINCT values from table |
| `_build_date_spine_sql` | ~90 | Date range from config bounds |
| `_build_date_spine_from_data_sql` | ~30 | Date spine from source data |

**Why it's complex**: Each function handles 5+ dialects (Postgres, DuckDB, BigQuery, Snowflake, default) with different syntax for:
- `generate_series()` vs `GENERATE_DATE_ARRAY` vs `GENERATOR()`
- `UNNEST(ARRAY[...])` vs `TABLE(FLATTEN(...))`
- Date casting (`::date` vs `DATE()`vs implicit)

**Recommendation**: Refactor to use SQLGlot's dialect-specific generation:
1. Build AST using generic expressions like `exp.GenerateSeries`, `exp.Unnest`
2. Let SQLGlot's dialect generators output correct syntax
3. For unsupported constructs, add custom generator transforms

---

## PRQL vs ASQL Comparison

| Metric | PRQL (SQLGlot) | ASQL |
|--------|----------------|------|
| Dialect LOC | 208 | 3,120 |
| TRANSFORM_PARSERS | 9 | 35 |
| Compiler transforms | 0 | 10+ |
| String SQL building | None | ~350 lines |

### Why ASQL is larger:

1. **More features**: ASQL has cohort analysis, auto-spine, recursive CTEs, FK shortcuts, pivot fallbacks
2. **More syntax sugar**: 3 formatting options (natural, underscore, function) for most operations
3. **Dialect fallbacks**: Manual PIVOT→CASE/WHEN, EXPLODE→FLATTEN transforms
4. **Schema awareness**: FK inference, primary key detection

### PRQL's Elegance

```python
# PRQL's entire TRANSFORM_PARSERS
TRANSFORM_PARSERS = {
    "DERIVE": lambda self, query: self._parse_selection(query),
    "SELECT": lambda self, query: self._parse_selection(query, append=False),
    "TAKE": lambda self, query: self._parse_take(query),
    "FILTER": lambda self, query: query.where(self._parse_disjunction()),
    ...
}
```

PRQL uses a single `_parse_selection` helper that handles both single expressions and `{...}` blocks. ASQL could adopt a similar pattern.

---

## Recommendations

### High Priority - ✅ COMPLETED

1. **✅ Converted `_build_explicit_values_spine_sql` to AST**
   - Created `_build_explicit_values_spine_ast()` using `exp.Array`, `exp.Unnest`, `exp.Union`
   - SQLGlot now handles dialect-specific UNNEST/ARRAY syntax automatically
   - Old function kept as wrapper for backward compatibility
   
2. **✅ Reorganized TRANSFORM_PARSERS with `dict.fromkeys()`**
   - Combined WHERE/FILTER/IF aliases
   - Combined SELECT/PROJECT aliases
   - Added logical groupings (Filtering, Selection, Joins, Column ops, Window ops, Advanced)
   - Removed redundant comments

### Medium Priority (Future)

3. **Consolidate boundary detection** - The `_find_transform_boundary_index` + `_parse_asql_expression_until_transform_boundary` pattern is ~50 lines that could be simplified

4. **~~Schema-aware transforms~~** ✅ DONE - Created shared `join_inference.py` module:
   - ✅ `resolve_join_condition()` - Unified resolution function
   - ✅ Resolution chain: explicit relationships → inferred → column/PK detection → convention
   - ✅ Used by `join_fk_shorthand.py` and `cohort_transform.py`
   - ✅ Auto-join: `from orders & users` auto-infers `ON orders.user_id = users.id`
     - Works with schema relationships (explicit or inferred)
     - Falls back to convention when `infer_join_keys=True`
   - 🔲 Infer GROUP BY columns from aggregate context (filed as #143)

### Low Priority (Nice to Have)

5. **~~Reduce cohort_transform.py~~** - Now uses shared `join_inference.py`
6. **Simplify alias_reuse.py** (430 lines) - Works well, but verbose

---

## LOC Summary

| File | Before | After | Change |
|------|--------|-------|--------|
| dialect.py | 3,170 | 3,120 | -50 |
| join_fk_shorthand.py | 83 | 53 | -30 |
| cohort_transform.py | ~20 lines `_infer_join_key` | Uses shared | -15 net |
| join_inference.py (NEW) | 0 | 158 | +158 (shared) |
| **Net change** | | | **+63 lines** |

Note: The +63 LOC is worth it because:
- Single source of truth for join resolution logic
- Better resolution (schema → inferred → convention)
- Reusable for future auto-join feature

---

## Tests

All 2,430 tests pass after today's changes.

