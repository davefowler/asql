# Transform Stage Audit: Is Every Transform in the Right Place?

**Date**: 2026-01-18  
**Updated**: After `asql.transpile()` refactor  
**Purpose**: Systematic analysis of EVERY transform asking "is this at the right stage?"

## Current Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                          CURRENT STATE (Post-Refactor)                 │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌─────────────────┐     ┌───────────────┐     ┌────────────────────┐ │
│  │  ASQL PARSER    │ ──► │ asql.transpile│ ──► │ SQLGlot Generator  │ │
│  │                 │     │ ()            │     │ (unchanged)        │ │
│  │ _apply_asql_    │     │               │     │                    │ │
│  │ transforms()    │     │ Dialect-aware │     │ DuckDB, Postgres,  │ │
│  │ - underscore    │     │ transforms:   │     │ Snowflake, etc.    │ │
│  │ - auto_alias    │     │ - spine       │     │                    │ │
│  │ - fk_shorthand  │     │ - alias_reuse │     │                    │ │
│  │ - cohort        │     │ - column_ops  │     │                    │ │
│  │ - auto_qualify  │     │ - list_comp   │     │                    │ │
│  └─────────────────┘     └───────────────┘     └────────────────────┘ │
│                                                                        │
│  ✅ Parser only handles non-dialect-aware transforms                   │
│  ✅ asql.transpile() handles dialect-aware transforms                  │
│  ✅ Uses SQLGlot's built-in generators (no custom generators)          │
│  ✅ api.py deleted                                                     │
│  ✅ generators/ directory not needed                                   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## All Compiler Modules Analysis

### `asql/compiler/alias_reuse.py` (430 lines)

| Question | Answer |
|----------|--------|
| **What does it do?** | Creates CTE chain for alias reuse in non-DuckDB dialects |
| **Needs output dialect?** | ✅ YES - DuckDB doesn't need this |
| **Needs schema?** | ❌ No |
| **Current location** | Called from `asql/transpile.py` |
| **Correct location?** | ✅ YES |
| **Action** | None needed |

### ~~`asql/compiler/api.py`~~ (DELETED)

| Question | Answer |
|----------|--------|
| **Status** | ✅ **DELETED** |
| **Replaced by** | `asql/transpile.py` |

### `asql/compiler/auto_alias.py` (449 lines)

| Question | Answer |
|----------|--------|
| **What does it do?** | Auto-adds aliases to function calls |
| **Needs output dialect?** | ❌ No |
| **Needs schema?** | ❌ No |
| **Current location** | Called from Parser._apply_asql_transforms() |
| **Correct location?** | ✅ YES - Parser stage is correct |
| **Action** | None needed |

### `asql/compiler/auto_qualify.py` (189 lines)

| Question | Answer |
|----------|--------|
| **What does it do?** | Qualifies columns in joins (SELECT * → t1.*, t2.*) |
| **Needs output dialect?** | ❌ No |
| **Needs schema?** | ❌ No (schema-free heuristic) |
| **Current location** | Called from Parser._apply_asql_transforms() |
| **Correct location?** | ✅ YES - Parser stage is correct |
| **Action** | Optional: Consider replacing with SQLGlot's qualify_columns |

### `asql/compiler/auto_spine.py` (1308 lines) ⚠️ LEGACY

| Question | Answer |
|----------|--------|
| **What does it do?** | Original auto-detection spine logic + helper functions |
| **Status** | ⚠️ **PARTIALLY LEGACY** |
| **Used by** | `spine.py` imports helper functions |
| **Action** | ⚠️ Could refactor: extract helpers to separate file, delete auto-detection code |

### `asql/compiler/spine.py` (355 lines) ✨ NEW

| Question | Answer |
|----------|--------|
| **What does it do?** | Processes explicit `exp.Spine` nodes into gap-filling CTEs |
| **Needs output dialect?** | ✅ YES - generates dialect-specific date spine SQL |
| **Needs schema?** | ❌ No |
| **Current location** | Called from `asql/transpile.py` |
| **Correct location?** | ✅ YES |
| **Action** | None needed |

### `asql/compiler/cohort_transform.py` (372 lines)

| Question | Answer |
|----------|--------|
| **What does it do?** | Expands `exp.CohortBy` AST to CTEs and JOINs |
| **Needs output dialect?** | ❌ No |
| **Needs schema?** | ❌ No |
| **Current location** | Called from Parser._apply_asql_transforms() |
| **Correct location?** | ✅ YES - Parser stage (pure syntax expansion) |
| **Action** | None needed |

### `asql/compiler/column_operators.py` (61 lines)

| Question | Answer |
|----------|--------|
| **What does it do?** | Expands EXCEPT to explicit columns for non-native dialects |
| **Needs output dialect?** | ✅ YES - DuckDB supports native EXCEPT |
| **Needs schema?** | ✅ Yes - needs column list |
| **Current location** | Called from `asql/transpile.py` |
| **Correct location?** | ✅ YES |
| **Action** | None needed |

### `asql/compiler/join_fk_shorthand.py` (98 lines)

| Question | Answer |
|----------|--------|
| **What does it do?** | Expands `ON user_id` to full join condition |
| **Needs output dialect?** | ❌ No |
| **Needs schema?** | ✅ Yes - needs FK relationships |
| **Current location** | Called from Parser._apply_asql_transforms() |
| **Correct location?** | ✅ YES - Parser stage (syntax sugar) |
| **Action** | None needed |

### `asql/compiler/join_inference.py` (219 lines)

| Question | Answer |
|----------|--------|
| **What does it do?** | Resolves join conditions from schema/conventions |
| **Needs output dialect?** | ❌ No |
| **Needs schema?** | ✅ Yes |
| **Current location** | Utility module, called by join_fk_shorthand |
| **Correct location?** | ✅ YES - Support library |
| **Action** | None needed |

### `asql/compiler/list_comprehension.py` (66 lines)

| Question | Answer |
|----------|--------|
| **What does it do?** | Converts ARRAY(SELECT...) back to DuckDB's native [x FOR x] syntax |
| **Needs output dialect?** | ✅ YES - only DuckDB supports native syntax |
| **Current location** | Called from `asql/transpile.py` (text-based post-processing) |
| **Correct location?** | ✅ YES |
| **Action** | None needed |

### `asql/compiler/sqlglot_schema_adapter.py` (62 lines)

| Question | Answer |
|----------|--------|
| **What does it do?** | Converts ASQL Schema to SQLGlot MappingSchema |
| **Needs output dialect?** | ❌ No |
| **Current location** | Utility module |
| **Correct location?** | ✅ YES - Support library |
| **Action** | None needed |

### `asql/compiler/underscore_shorthands.py` (195 lines)

| Question | Answer |
|----------|--------|
| **What does it do?** | Expands `days_since_col` to DATEDIFF |
| **Needs output dialect?** | ❌ No |
| **Needs schema?** | ✅ Yes - validates column exists |
| **Current location** | Called from Parser._apply_asql_transforms() |
| **Correct location?** | ✅ YES - Parser stage (syntax sugar) |
| **Action** | None needed |

---

## Summary Table

| Module | Lines | Needs Dialect? | Stage | Correct? | Action |
|--------|-------|----------------|-------|----------|--------|
| `alias_reuse.py` | 430 | ✅ YES | transpile() | ✅ | None |
| ~~`api.py`~~ | - | - | DELETED | ✅ | Done |
| `auto_alias.py` | 449 | ❌ | Parser | ✅ | None |
| `auto_qualify.py` | 189 | ❌ | Parser | ✅ | Optional review |
| `auto_spine.py` | 1308 | ✅ YES | Legacy | ⚠️ | Could refactor |
| `spine.py` | 355 | ✅ YES | transpile() | ✅ | None |
| `cohort_transform.py` | 372 | ❌ | Parser | ✅ | None |
| `column_operators.py` | 61 | ✅ YES | transpile() | ✅ | None |
| `join_fk_shorthand.py` | 98 | ❌ | Parser | ✅ | None |
| `join_inference.py` | 219 | ❌ | Library | ✅ | None |
| `list_comprehension.py` | 66 | ✅ YES | transpile() | ✅ | None |
| `sqlglot_schema_adapter.py` | 62 | ❌ | Library | ✅ | None |
| `underscore_shorthands.py` | 195 | ❌ | Parser | ✅ | None |

---

## Parser Transforms (`_apply_asql_transforms`)

These are called in the parser and are all **dialect-agnostic** (don't need output dialect):

```python
# Currently in parser (asql/dialect/parser.py):
from asql.compiler.underscore_shorthands import (...)
from asql.compiler.auto_alias import apply_auto_aliasing
from asql.compiler.auto_qualify import auto_qualify_columns
from asql.compiler.join_fk_shorthand import transform_fk_shorthand
from asql.compiler.cohort_transform import transform_cohort
```

| Transform | Parser OK? | Verdict |
|-----------|------------|---------|
| `underscore_shorthands` | ✅ | Syntax sugar, no dialect needed |
| `auto_alias` | ✅ | Syntax sugar, no dialect needed |
| `auto_qualify` | ✅ | Syntax sugar, no dialect needed |
| `fk_shorthand` | ✅ | Syntax sugar, no dialect needed |
| `cohort` | ✅ | Syntax expansion, no dialect needed |

**✅ All parser transforms are correctly placed.**

---

## Transpile Transforms (`asql.transpile()`)

These are called in `asql/transpile.py` and are all **dialect-aware** (need output dialect):

```python
# In asql/transpile.py:
from asql.compiler.spine import transform_spine_expressions
from asql.compiler.alias_reuse import apply_alias_reuse
from asql.compiler.column_operators import transform_column_operators_for_dialect
from asql.compiler.list_comprehension import fix_duckdb_list_comprehensions
```

| Transform | Needs Dialect? | Verdict |
|-----------|---------------|---------|
| `spine` | ✅ YES | Generates dialect-specific date spine SQL |
| `alias_reuse` | ✅ YES | DuckDB has native support, others need CTEs |
| `column_operators` | ✅ YES | DuckDB has native EXCEPT |
| `list_comprehension` | ✅ YES | DuckDB has native [x FOR x] syntax |

**✅ All transpile transforms are correctly placed.**

---

## ✅ Completed Reorganization

### File Organization (DONE)

Parser-stage transforms have been moved to `asql/dialect/transforms/`:

```
asql/dialect/transforms/
├── __init__.py                # Package exports
├── underscore_shorthands.py   # days_since_col → DATEDIFF
├── auto_alias.py              # Automatic column aliasing
├── auto_qualify.py            # Column qualification in joins
├── join_fk_shorthand.py       # ON user_id expansion
├── join_inference.py          # FK relationship inference
└── cohort_transform.py        # Cohort analysis CTEs

asql/compiler/                 # Dialect-aware transforms (stay here)
├── spine.py                   # Explicit spine() processing
├── alias_reuse.py             # CTE chain for alias reuse
├── column_operators.py        # EXCEPT expansion
├── list_comprehension.py      # DuckDB [x FOR x] conversion
└── auto_spine.py              # Helper functions for spine generation
```

### Remaining Low-Priority Items

1. **`auto_spine.py` cleanup**: Contains helper functions used by `spine.py`. Legacy auto-detection code could be removed but works fine as-is.

---

## Action Items

### ✅ Completed
- [x] Delete `api.py` 
- [x] Move dialect-aware transforms to `asql.transpile()`
- [x] Create explicit `exp.Spine` AST node
- [x] Create explicit `exp.CohortBy` AST node
- [x] Create `spine.py` for explicit spine syntax

### ⏳ Optional (Low Priority)
- [ ] Refactor `auto_spine.py` - extract helpers, delete unused code
- [ ] Move parser transforms to `asql/dialect/transforms/` (organizational)
- [ ] Consider replacing `auto_qualify.py` with SQLGlot's `qualify_columns`

---

## Conclusion

**All transforms are now in the correct stage:**

| Stage | Location | Transforms |
|-------|----------|------------|
| Parser | `_apply_asql_transforms()` | underscore_shorthands, auto_alias, auto_qualify, fk_shorthand, cohort |
| Transpile | `asql.transpile()` | spine, alias_reuse, column_operators, list_comprehension |
| Generator | SQLGlot built-in | (no custom transforms needed) |

The architecture is clean. Remaining items are cosmetic/organizational.
