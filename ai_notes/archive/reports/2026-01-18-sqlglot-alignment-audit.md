# ASQL ↔ SQLGlot Alignment Audit

**Date**: 2026-01-18  
**Goal**: Find ALL places where ASQL has built custom wrappers instead of using SQLGlot idioms.  
**End state**: Code that looks like "the SQLGlot creator wrote this."

## 🎯 EXECUTIVE SUMMARY

### Code to Delete (Confirmed Duplicates)
| File | Lines | SQLGlot Replacement | Status |
|------|-------|---------------------|--------|
| `alias_reuse.py` | 430 | `qualify_columns(expand_alias_refs=True)` | 🟡 Agent working |
| `explode_fallback.py` | 75 | Snowflake generator handles UNNEST→FLATTEN | ✅ Already deleted |
| **Total** | **505** | | |

### Code to Keep (Truly Custom)
| Category | Lines | Reason |
|----------|-------|--------|
| Parser custom features | 1082 | `when`, `cohort`, `per`, list comprehensions, etc. |
| Parser core | 2158 | Could reduce ~1000 lines with refactoring |
| Compiler transforms | 3574 | auto_spine, pivot_fallback, etc. - unique ASQL features |

### Key Findings
1. **Parser is 2x too big** - 3240 lines vs ~1500 target (Snowflake size)
2. **19 elif chains** could be dicts - minor but idiomatic
3. **Most compiler code is legitimate** - features SQLGlot doesn't provide
4. **Settings migration** - in progress on this branch

---

## Why This Audit Exists

We keep finding major gaps where we built custom systems instead of using SQLGlot:

| Date | Discovery | Impact |
|------|-----------|--------|
| 2026-01-07 | Had 7K LOC preparser wrapping SQLGlot | Deleted most of it |
| 2026-01-17 | Had separate `CompileSettings` instead of `dialect.settings` | Migrating now |
| 2026-01-18 | Found more settings not using SQLGlot system | This audit |
| ??? | What else are we missing? | **This audit will find it** |

**Root cause**: We started with wrong assumptions about what SQLGlot could do and kept adding wrappers.

**Previous investigations were point-targeted**, not systematic. This audit uses **multiple approaches** to find everything.

---

## ⚠️ 2026-01-18 UPDATE: We Missed Parser vs Generator Placement!

**The Bug**: Transforms that need OUTPUT dialect were in the Parser (which only knows INPUT dialect).

```
❌ WRONG: Parser runs transforms with extend_dialect (input dialect hack)
✅ RIGHT: api.py runs transforms with actual output dialect
```

**Why we REALLY missed it**: We didn't do a real comparative analysis. If we had:

| Dialect | Parser Lines | Imports Compiler? | Dialect-Switching? |
|---------|--------------|-------------------|-------------------|
| PRQL | 207 | ❌ NO | ❌ NO |
| DuckDB | 1431 | ❌ NO | ❌ NO |
| Snowflake | 1888 | ❌ NO | ❌ NO |
| **ASQL** | **3167** | **✅ YES** | **✅ YES** |

ASQL's parser was importing `from asql.compiler.*` - NO OTHER DIALECT DOES THIS.

**Questions we should have asked:**
1. "Does PRQL's parser import compiler modules?" → NO
2. "Does DuckDB's parser have `extend_dialect`?" → NO
3. "Does any dialect run AST transforms in the parser?" → NO

We didn't do a real line-by-line comparison. We glanced at features, not architecture.

### APPROACH 4: Pipeline Stage Audit (ADDED)

For EVERY transform/function, ask:

| Question | Answer → Location |
|----------|-------------------|
| Needs INPUT syntax knowledge? | Parser |
| Needs OUTPUT dialect knowledge? | api.py (between parse/generate) |
| Needs both? | api.py orchestration |
| Needs neither? | Either, but prefer api.py |

**Transforms Mis-Located (now fixed)**:

| Transform | Was In | Needed | Fixed Location |
|-----------|--------|--------|----------------|
| `transform_column_operators_for_dialect` | Parser | OUTPUT | api.py |
| `_apply_auto_spine` | Parser | OUTPUT | api.py |
| `apply_alias_reuse` | Parser | OUTPUT | api.py |
| List comprehension dialect check | Parser | OUTPUT | api.py |
| `transform_cohort` | Parser | Neither | Parser (ok) |
| `transform_fk_shorthand` | Parser | Neither | Parser (ok) |

---

## Investigation Approaches

We'll use four complementary approaches:

```
┌─────────────────────────────────────────────────────────────────┐
│ APPROACH 1: COMPARATIVE DIALECT ANALYSIS                        │
│ Study PRQL, DuckDB, ClickHouse line-by-line                    │
│ Compare how they solve similar problems                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ APPROACH 2: SQLGLOT FEATURE INVENTORY                           │
│ List ALL SQLGlot extension points                               │
│ Check if ASQL uses each one correctly                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ APPROACH 3: ASQL CUSTOM CODE AUDIT                              │
│ List ALL custom ASQL code                                       │
│ For each: "Does SQLGlot have this?"                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ APPROACH 4: PIPELINE STAGE AUDIT (ADDED 2026-01-18)             │
│ For each transform: Does it need INPUT or OUTPUT dialect?       │
│ Is it in the correct stage (Parser vs api.py vs Generator)?     │
└─────────────────────────────────────────────────────────────────┘
```

---

# APPROACH 1: Comparative Dialect Analysis

## 1.1 PRQL Dialect Deep-Dive

PRQL is the closest comparison - it's a pipeline query language like ASQL.

**Source**: `sqlglot/dialects/prql.py` in SQLGlot repo

### Questions to Answer

| Question | PRQL Answer | ASQL Answer | Action |
|----------|-------------|-------------|--------|
| How does it handle pipeline operators? | | | |
| How does it use TRANSFORM_PARSERS? | | | |
| How does it handle settings/config? | | | |
| How does it handle FROM-first syntax? | | | |
| Does it have custom transforms? | | | |
| How big is the parser vs ours? | | | |
| What optimizer rules does it use? | | | |
| How does it handle CTE generation? | | | |

### PRQL Checklist

- [ ] Read entire `sqlglot/dialects/prql.py` (should be ~500 lines)
- [ ] Document every class attribute it overrides
- [ ] Document every method it overrides
- [ ] Compare to our `asql/dialect/parser.py` (~3000 lines!)
- [ ] List things PRQL does that we don't
- [ ] List things we do that PRQL doesn't (and question if we should)

---

## 1.2 DuckDB Dialect Deep-Dive

DuckDB has many ASQL-like features (alias reuse, EXCLUDE, etc).

**Source**: `sqlglot/dialects/duckdb.py` in SQLGlot repo

### Questions to Answer

| Question | DuckDB Answer | ASQL Answer | Action |
|----------|---------------|-------------|--------|
| How does it handle alias reuse? | Native support | Custom CTE chain | **INVESTIGATE** |
| How does it handle EXCLUDE/EXCEPT? | Native support | Custom expand | Check if we're duplicating |
| How does it handle UNNEST/EXPLODE? | | | |
| Does it have custom optimizer rules? | | | |
| How does it handle list comprehensions? | | | |

### DuckDB Checklist

- [ ] Read entire `sqlglot/dialects/duckdb.py`
- [ ] Understand how `expand_alias_refs` works in optimizer
- [ ] Check if our `alias_reuse.py` duplicates SQLGlot functionality
- [ ] Check if our `column_operators.py` duplicates SQLGlot functionality
- [ ] Document DuckDB-specific patterns we should adopt

---

## 1.3 ClickHouse Dialect Deep-Dive

ClickHouse has custom settings handling that may be instructive.

**Source**: `sqlglot/dialects/clickhouse.py` in SQLGlot repo

### Questions to Answer

| Question | ClickHouse Answer | ASQL Answer | Action |
|----------|-------------------|-------------|--------|
| How does it handle dialect settings? | | | |
| Does it use SUPPORTED_SETTINGS? | | | |
| How are settings passed to parser/generator? | | | |

### ClickHouse Checklist

- [ ] Read settings-related code in ClickHouse dialect
- [ ] Compare to our settings implementation
- [ ] Adopt any patterns we're missing

---

## 1.4 Snowflake Dialect Deep-Dive

Snowflake has complex features (FLATTEN, PIVOT) we also handle.

**Source**: `sqlglot/dialects/snowflake.py` in SQLGlot repo

### Questions to Answer

| Question | Snowflake Answer | ASQL Answer | Action |
|----------|------------------|-------------|--------|
| How does it handle FLATTEN/UNNEST? | | | Compare to `explode_fallback.py` |
| How does it handle PIVOT/UNPIVOT? | | | Compare to `pivot_fallback.py` |
| How does it handle array operations? | | | |

### Snowflake Checklist

- [ ] Read FLATTEN/UNNEST handling in Snowflake dialect
- [ ] Read PIVOT handling
- [ ] Check if our fallbacks duplicate what SQLGlot does

---

# APPROACH 2: SQLGlot Feature Inventory

## 2.1 Dialect System Features

| SQLGlot Feature | Purpose | ASQL Uses? | Correctly? |
|-----------------|---------|------------|------------|
| `Dialect` base class | Register dialect | ✅ | Review |
| `SUPPORTED_SETTINGS` | Declare valid settings | ✅ | **JUST ADDED** |
| `dialect.settings` dict | Store/read settings | ✅ | **MIGRATING** |
| `Tokenizer` class | Custom tokens | ✅ | Review |
| `Parser` class | Custom parsing | ✅ | **TOO BIG - 3K lines** |
| `Generator` class | Custom output | ✅ | Review |
| `NORMALIZE_FUNCTIONS` | Function casing | ✅ | |
| `DPIPE_IS_STRING_CONCAT` | \|\| meaning | ✅ | |

### Checklist

- [ ] Review all `Dialect` class attributes
- [ ] Check we're not missing any we should use
- [ ] Verify SUPPORTED_SETTINGS is complete

---

## 2.2 Parser Features

| SQLGlot Feature | Purpose | ASQL Uses? | Notes |
|-----------------|---------|------------|-------|
| `FUNCTIONS` dict | Custom function parsing | ✅ | |
| `TRANSFORM_PARSERS` dict | Pipeline transforms | ✅ | |
| `COLUMN_OPERATORS` dict | Column operators | ❓ | Need to verify |
| `STATEMENT_PARSERS` dict | Statement types | ❓ | |
| `PROPERTY_PARSERS` dict | Property parsing | ❓ | |
| `CONSTRAINT_PARSERS` dict | Constraints | ❓ | |
| `TYPE_TOKENS` set | Type keywords | ❓ | |
| `ID_VAR_TOKENS` set | Identifier tokens | ❓ | |

### Checklist

- [ ] Read all parser class attributes in SQLGlot base `Parser`
- [ ] Document which ones ASQL uses
- [ ] Document which ones ASQL should use but doesn't

---

## 2.3 Generator Features

| SQLGlot Feature | Purpose | ASQL Uses? | Notes |
|-----------------|---------|------------|-------|
| `TRANSFORMS` dict | Expression → SQL | ❓ | |
| `TYPE_MAPPING` dict | Type names | ❓ | |
| `_*_sql()` methods | Per-expression output | ✅ | |
| `unsupported()` | Error handling | ❓ | |

### Checklist

- [ ] Read all generator class attributes
- [ ] Verify ASQL generator uses them correctly

---

## 2.4 Optimizer Features

| SQLGlot Optimizer Rule | Purpose | ASQL Uses? | Duplicated? |
|------------------------|---------|------------|-------------|
| `qualify_columns` | Add table qualifiers | ✅ (partial) | **MAYBE in auto_qualify.py** |
| `expand_alias_refs` | Reuse aliases | ❌ | **YES in alias_reuse.py!** |
| `expand_stars` | * → column list | ✅ (via qualify) | |
| `merge_subqueries` | Flatten CTEs | ❌ | |
| `eliminate_ctes` | Remove unused CTEs | ✅ | |
| `simplify` | Boolean simplification | ✅ | |
| `annotate_types` | Type inference | ✅ (partial) | |
| `optimize_joins` | Join optimization | ❌ | |
| `pushdown_predicates` | WHERE optimization | ❌ | |

### Checklist

- [ ] Read SQLGlot optimizer module completely
- [ ] Compare each rule to our custom transforms
- [ ] **Specifically check `expand_alias_refs` vs `alias_reuse.py`**
- [ ] **Specifically check `qualify_columns` vs `auto_qualify.py`**

---

## 2.5 Schema Features

| SQLGlot Feature | Purpose | ASQL Uses? | Notes |
|-----------------|---------|------------|-------|
| `MappingSchema` | Table/column schema | ❓ | We have custom `Schema` class |
| Schema in optimizer | Column resolution | ✅ | |
| Type annotations | Type tracking | ❓ | |

### Checklist

- [ ] Compare `asql/schema.py` to `sqlglot.schema`
- [ ] Check if we should use MappingSchema directly
- [ ] Check if we can extend it for FK relationships

---

# APPROACH 3: ASQL Custom Code Audit

## 3.1 Files in `asql/compiler/`

| File | Lines | Purpose | SQLGlot Equivalent? | Action |
|------|-------|---------|---------------------|--------|
| `api.py` | 558 | Main compile entry | `transpile()` | Simplify |
| `alias_reuse.py` | 430 | Alias reference | `expand_alias_refs` | 🔴 **DELETE** |
| `auto_alias.py` | 450 | Auto-name functions | None (keep) | Keep |
| `auto_qualify.py` | 190 | Qualify columns | Schema-free heuristic | ✅ Keep |
| `auto_spine.py` | ??? | Gap-filling | None (keep) | Keep |
| `cohort_transform.py` | ??? | Cohort analysis | None (keep) | Keep |
| `column_operators.py` | ??? | EXCEPT/RENAME | Uses `qualify_columns` | ✅ Correct |
| `explode_fallback.py` | 75 | UNNEST→FLATTEN | Snowflake generator handles it | 🔴 **DELETE** |
| `join_fk_shorthand.py` | ??? | FK inference | None (keep) | Keep |
| `join_inference.py` | ??? | Join detection | None (keep) | Keep |
| `list_comprehension.py` | ??? | List comprehensions | Dialect-specific | Review |
| `pivot_fallback.py` | ??? | PIVOT→CASE | Dialect transpile? | **INVESTIGATE** |
| `sqlglot_schema_adapter.py` | 63 | Schema conversion | Thin adapter | ✅ Correct |
| `underscore_shorthands.py` | ??? | `sum_amount` expand | None (keep) | Keep |

### Checklist

For EACH file:

- [ ] Read the file completely
- [ ] Document what it does
- [ ] Search SQLGlot for equivalent functionality
- [ ] Mark as KEEP (truly custom) or INVESTIGATE (might duplicate)

---

## 3.2 Files in `asql/`

| File | Lines | Purpose | SQLGlot Equivalent? | Action |
|------|-------|---------|---------------------|--------|
| `config.py` | 437 | Settings classes | `dialect.settings` | **MIGRATING** |
| `schema.py` | 921 | Schema model | `MappingSchema`? | **INVESTIGATE** |
| `functions.py` | 551 | Function registry | `FUNCTIONS` dict | Review if redundant |
| `errors.py` | ??? | Error types | SQLGlot errors | Review |
| `dialect_features.py` | ??? | Feature detection | Dialect attributes? | Review |

### Checklist

- [ ] Audit each file for SQLGlot equivalents

---

## 3.3 `asql/dialect/parser.py` Size Analysis

Our parser is ~3000 lines. Reference dialects:

| Dialect | Parser Lines | Notes |
|---------|--------------|-------|
| PRQL | ~300? | Similar pipeline language |
| DuckDB | ~400? | Complex features |
| Snowflake | ~600? | Very complex |
| **ASQL** | **~3000** | **5-10x larger!** |

### Questions

- Why is our parser so big?
- What can we delete/simplify?
- Are we doing things in the parser that should be elsewhere?

### Checklist

- [ ] Count actual lines in reference dialects
- [ ] Identify why ASQL is bigger
- [ ] Create plan to reduce parser size

---

# High-Priority Investigations

Based on analysis, these are most likely to be duplicating SQLGlot:

## Priority 1: `alias_reuse.py` vs `expand_alias_refs`

**Hypothesis**: SQLGlot's `expand_alias_refs` in `qualify_columns` already handles alias reuse.

**Investigation steps**:

1. [ ] Read SQLGlot's `expand_alias_refs` implementation
2. [ ] Write test case showing ASQL behavior
3. [ ] Try replacing with SQLGlot's implementation
4. [ ] If equivalent, DELETE `alias_reuse.py`

**Test query**:
```sql
SELECT price * quantity AS total, total * 0.1 AS tax FROM orders
```

---

## Priority 2: `auto_qualify.py` vs `qualify_columns`

**Hypothesis**: SQLGlot's `qualify_columns` already does what `auto_qualify.py` does.

### ✅ INVESTIGATED - DIFFERENT PURPOSE

| Component | What it does | Requires Schema? |
|-----------|--------------|------------------|
| SQLGlot `qualify_columns` | Full column qualification + star expansion | **YES** |
| ASQL `auto_qualify.py` | `SELECT *` → `t1.*, t2.*` in joins only | **NO** |
| ASQL `column_operators.py` | Uses `qualify_columns` for EXCEPT etc. | YES (already using SQLGlot!) |

**Our `auto_qualify.py` is a schema-FREE heuristic:**

```sql
-- Input (no schema available)
SELECT * FROM users JOIN orders

-- auto_qualify.py output:
SELECT users.*, orders.* FROM users JOIN orders
```

SQLGlot's `qualify_columns` with `expand_stars=True` requires a schema to know actual columns.
Our heuristic just changes `*` to `t1.*, t2.*` without needing column info.

**Verdict**: ✅ KEEP - this is intentionally different (schema-free heuristic)

**Action**: 
- [ ] Add docstring explaining relationship to SQLGlot's `qualify_columns`
- [ ] Consider: should we call SQLGlot's qualify_columns WHEN schema is available?

---

## Priority 3: Schema Adapter vs MappingSchema

**Hypothesis**: We might be able to use `MappingSchema` directly.

### ✅ INVESTIGATED - ADAPTER IS THIN AND CORRECT

`asql/compiler/sqlglot_schema_adapter.py` is only **63 lines** and does:

1. If already SQLGlot Schema → return as-is
2. If dict → wrap in MappingSchema
3. If ASQL Schema → convert tables/columns to MappingSchema format

**Why we need ASQL's Schema separately:**
- SQLGlot's `MappingSchema` is table/column/type only
- ASQL's `Schema` has **FK relationships** for join inference
- The adapter extracts column info for SQLGlot, keeps relationships for ASQL

**Verdict**: ✅ CORRECT DESIGN
- Schema adapter is minimal and correct
- We use SQLGlot's MappingSchema where appropriate
- ASQL's relationship graph stays separate (SQLGlot doesn't have this)

---

## Priority 4: Pivot/Explode Fallbacks vs Dialect Transpilation

**Hypothesis**: SQLGlot might already handle PIVOT→CASE and UNNEST→FLATTEN.

### Pivot Fallback Investigation

`asql/compiler/pivot_fallback.py` (350 lines):

```python
# From the docstring:
# "SQLGlot can parse PIVOT expressions but cannot transpile them to CASE/WHEN
# for dialects that don't support native PIVOT (PostgreSQL, MySQL, SQLite)."
```

**What it does:**
- Native PIVOT dialects (DuckDB, Snowflake, BigQuery) → pass through
- Non-native dialects (Postgres, MySQL) → CASE/WHEN expansion
- UNPIVOT → UNION ALL expansion

**Investigation needed:**

- [ ] Test if SQLGlot now transpiles PIVOT (it might have been added since we wrote this)
- [ ] If not, this is a candidate for **upstream contribution**

### Explode Fallback Investigation

`asql/compiler/explode_fallback.py` (75 lines):

**What it does:**
- UNNEST → FLATTEN for Snowflake

### ✅ INVESTIGATED - SQLGLOT HANDLES THIS!

```python
# SQLGlot's Snowflake generator automatically converts UNNEST to FLATTEN:
parsed = sqlglot.parse_one('SELECT * FROM t CROSS JOIN UNNEST(t.arr) AS x')
print(parsed.sql(dialect='snowflake'))
# Output: SELECT * FROM t CROSS JOIN TABLE(FLATTEN(INPUT => t.arr)) AS x(...)
```

**Verdict**: 🔴 **DELETE `explode_fallback.py`** - SQLGlot does this automatically during generation!

---

# Tracking Progress

## Investigation Status

| Investigation | Status | Findings |
|---------------|--------|----------|
| PRQL dialect review | 🟡 IN PROGRESS | Uses `PIPE_SYNTAX_TRANSFORM_PARSERS` from base Parser! |
| DuckDB dialect review | ⬜ TODO | |
| ClickHouse dialect review | ⬜ TODO | |
| Snowflake dialect review | ⬜ TODO | |
| SQLGlot optimizer review | 🟡 IN PROGRESS | `expand_alias_refs` does alias expansion! |
| `alias_reuse.py` vs `expand_alias_refs` | ✅ DONE | **DELETE 430 lines** - use SQLGlot's `expand_alias_refs` |
| `auto_qualify.py` vs `qualify_columns` | ✅ DONE | KEEP - schema-free heuristic |
| Schema adapter vs MappingSchema | ✅ DONE | KEEP - thin 63-line adapter |
| `pivot_fallback.py` | ✅ DONE | KEEP - SQLGlot drops PIVOT, doesn't convert to CASE/WHEN |
| `explode_fallback.py` | ✅ DONE | **DELETE 75 lines** - SQLGlot Snowflake generator handles UNNEST→FLATTEN |

---

# Initial Findings (2026-01-18)

## Finding 1: SQLGlot Has `PIPE_SYNTAX_TRANSFORM_PARSERS`

The base `Parser` class in SQLGlot has `PIPE_SYNTAX_TRANSFORM_PARSERS` dict (~line 998):

```python
PIPE_SYNTAX_TRANSFORM_PARSERS = {
    "AGGREGATE": lambda self, query: self._parse_pipe_syntax_aggregate(query),
    "AS": lambda self, query: self._build_pipe_cte(query, [exp.Star()], self._parse_table_alias()),
    "EXTEND": lambda self, query: self._parse_pipe_syntax_extend(query),
    "LIMIT": lambda self, query: self._parse_pipe_syntax_limit(query),
    "ORDER BY": lambda self, query: query.order_by(self._parse_order(), append=False, copy=False),
    "PIVOT": lambda self, query: self._parse_pipe_syntax_pivot(query),
    "SELECT": lambda self, query: self._parse_pipe_syntax_select(query),
    "TABLESAMPLE": lambda self, query: self._parse_pipe_syntax_tablesample(query),
}
```

### ✅ ASQL IS USING THIS CORRECTLY!

Found in `asql/dialect/parser.py`:

```python
# Override PIPE_SYNTAX_TRANSFORM_PARSERS to add GROUP BY support
# This extends SQLGlot's BigQuery-style pipe syntax
PIPE_SYNTAX_TRANSFORM_PARSERS = Parser.PIPE_SYNTAX_TRANSFORM_PARSERS.copy()
PIPE_SYNTAX_TRANSFORM_PARSERS.update({
    "GROUP BY": lambda self, query: self._parse_asql_pipe_group_by(query),
    "HAVING": lambda self, query: query.having(self._parse_assignment(), copy=False),
    "QUALIFY": lambda self, query: query.qualify(self._parse_assignment(), copy=False),
})
```

We also have a separate `TRANSFORM_PARSERS` dict for FROM-first syntax (not using `|>`).

**Verdict**: ✅ This is done correctly - we extend SQLGlot's pattern rather than reinventing.

**BUT**: Our parser is still 3000+ lines vs ~300 for PRQL. Need to understand why.

---

## Finding 2: SQLGlot's `expand_alias_refs` vs Our `alias_reuse.py`

From SQLGlot's `qualify_columns` optimizer:

```sql
-- Input
SELECT y.foo AS bar, bar * 2 AS baz FROM y

-- With expand_alias_refs=True becomes:
SELECT y.foo AS bar, y.foo * 2 AS baz FROM y
```

### 🔴 WE SHOULD USE SQLGLOT'S APPROACH - DELETE OUR CODE

| Aspect | Our CTE Approach | SQLGlot's Expansion |
|--------|------------------|---------------------|
| **Code to maintain** | 430 lines | 0 lines (use SQLGlot) |
| **Complexity** | High (dependency graph, CTE generation) | None |
| **Output SQL** | Adds CTEs | Cleaner, no CTEs |
| **SQLGlot idioms** | No | Yes |

**Why my earlier "performance" argument was wrong:**

1. Database query planners optimize common subexpressions
2. CTEs can actually HURT performance (some DBs don't inline them)
3. SQLGlot team made this design choice for good reasons
4. We're maintaining 430 lines for a micro-optimization that may be negative

### Verdict: 🔴 DELETE `alias_reuse.py`, USE SQLGLOT

**Migration plan**: See `ai_notes/2026-01-18-alias-reuse-migration.md`

```python
# Replace 430 lines with:
from sqlglot.optimizer.qualify_columns import qualify_columns
stmt = qualify_columns(stmt, expand_alias_refs=True, expand_stars=False)
```

**Action**: 
- [ ] Replace `apply_alias_reuse()` call with `qualify_columns(expand_alias_refs=True)`
- [ ] Delete `asql/compiler/alias_reuse.py` (430 lines)
- [ ] Update `tests/test_alias_reuse.py` (change assertions, no more CTEs)

## Files to Delete (Confirmed Duplicates)

| File | Lines | Duplicate Of | Deleted? |
|------|-------|--------------|----------|
| `asql/compiler/alias_reuse.py` | 430 | `qualify_columns(expand_alias_refs=True)` | 🟡 Agent working |
| `asql/compiler/explode_fallback.py` | 75 | Snowflake generator auto-converts UNNEST→FLATTEN | ✅ Already deleted on branch |

**Total savings: 505 lines**

## Files to Keep (Truly Custom)

| File | Why Unique |
|------|------------|
| `auto_spine.py` | Semantic transform, no SQLGlot equivalent |
| `cohort_transform.py` | Macro expansion, no SQLGlot equivalent |
| `join_fk_shorthand.py` | FK inference, no SQLGlot equivalent |
| `underscore_shorthands.py` | ASQL-specific syntax |
| `auto_qualify.py` | Schema-free heuristic (190 lines, reasonable) |

---

# Key Findings Summary (2026-01-18)

## ✅ Things ASQL Does RIGHT

| Component | Finding |
|-----------|---------|
| `PIPE_SYNTAX_TRANSFORM_PARSERS` | ✅ Correctly extends SQLGlot's base pattern |
| `auto_qualify.py` | ✅ Schema-free heuristic (SQLGlot needs schema) |
| `sqlglot_schema_adapter.py` | ✅ Thin adapter, correct design |
| `column_operators.py` | ✅ Already uses `qualify_columns` from SQLGlot |

## 🔴 CONFIRMED DUPLICATES TO DELETE

| Component | Lines | SQLGlot Equivalent | Action |
|-----------|-------|-------------------|--------|
| `alias_reuse.py` | 430 | `qualify_columns(expand_alias_refs=True)` | **DELETE** (agent working) |
| `explode_fallback.py` | 75 | Snowflake generator does UNNEST→FLATTEN automatically | **DELETE** |

**Total: 505 lines to delete!**

## 🔶 Things to VERIFY

| Component | Question |
|-----------|----------|
| `pivot_fallback.py` | Does SQLGlot now handle PIVOT transpilation? |
| `explode_fallback.py` | Does SQLGlot now handle UNNEST→FLATTEN? |
| Parser size (3000 lines) | Why so much bigger than PRQL (~300 lines)? |

## 🔴 Things to FIX

| Component | Issue | Status |
|-----------|-------|--------|
| `config.py` | Should use `dialect.settings` | MIGRATING NOW |
| Inline settings | Should use `dialect.settings` mutation | MIGRATING NOW |

## Not Found (Yet)

These are areas we haven't found duplicates but should verify:
- Expression node types - are we creating custom ones unnecessarily?
- Error handling - are we duplicating SQLGlot's error system?
- Type annotations - are we duplicating SQLGlot's type system?

---

# Action Plan

---

## Parser Size Analysis

### Current State

| Dialect | Lines | Notes |
|---------|-------|-------|
| **ASQL** | 3240 | 15x larger than PRQL! |
| PRQL | 207 | Clean reference implementation |
| Snowflake | 1888 | Largest production dialect |
| ClickHouse | 1498 | |
| BigQuery | 1463 | |
| DuckDB | 1431 | |

### Code Breakdown

**Custom ASQL Features (1082 lines):**
- GROUP BY inline aggregations: 215 lines
- Date literals & relative dates: 170 lines  
- `when` syntax: 155 lines
- `per` window functions: 153 lines
- List comprehensions: ~~135~~ 57 lines (simplified! uses SQLGlot's `exp.Comprehension`)
- Cohort analysis: 94 lines
- Recursive CTEs sugar: 89 lines
- Count shorthand (`#`): 71 lines

**Core/Infrastructure (2158 lines):**
- Transform orchestration (`_apply_asql_transforms`): 95 lines
- Bracket parsing: 85 lines
- Comparison parsing: 77 lines
- Query parsing: 65 lines
- Plus ~60 other methods

### What ASQL Does Well ✅
- Uses `TRANSFORM_PARSERS` dict pattern (like PRQL)
- Uses `PIPE_SYNTAX_TRANSFORM_PARSERS` for pipeline
- Uses `PRIMARY_PARSERS` extension

### Improvement Opportunities 🔶

1. ~~**19 `elif self._match` chains** - Could convert to dicts:~~
   - ✅ Rank functions (`LAST`, `DENSE_RANK`, `RANK`, `NUMBER`) - **DONE: converted to `_PER_QUALIFY_OPS` and `_PER_WINDOW_OPS` dicts**
   - ✅ Date granularities - **DONE: removed hardcoded list, now parses as regular expression and extracts function name**
   - String operators already use dict pattern (`string_ops` dict in `_parse_comparison`)

2. **Large methods** - Largest 5 methods are 77-116 lines each:
   - `_parse_when`: 116 lines
   - `_parse_list_comprehension`: 102 lines
   - `_apply_asql_transforms`: 95 lines
   - `_parse_asql_cohort`: 94 lines
   - `_parse_asql_recurse`: 89 lines

3. **Missing declarative patterns** - No COMPARISON_OPS, UNARY_OPS dicts

### Realistic Target
- ASQL will always be larger than PRQL due to more features
- Target: **~1500 lines** (similar to ClickHouse/BigQuery)
- Savings: ~1700 lines (53% reduction)

---

## Compiler Files Analysis

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| `auto_spine.py` | 1308 | ✅ KEEP | SQLGlot has `GapFill` expr but NO transpilation. Our code is unique. |
| `auto_alias.py` | 449 | ✅ KEEP | Custom auto-aliasing for ASQL |
| `alias_reuse.py` | 430 | 🔴 DELETE | Replace with `expand_alias_refs` (agent working) |
| `cohort_transform.py` | 372 | ✅ KEEP | Custom cohort analysis |
| `pivot_fallback.py` | 351 | ✅ KEEP | SQLGlot drops PIVOT, doesn't convert |
| `join_inference.py` | 219 | ✅ KEEP | Custom FK inference |
| `underscore_shorthands.py` | 195 | ✅ KEEP | `days_since_x` → `DATEDIFF` |
| `auto_qualify.py` | 189 | ✅ KEEP | Schema-free star expansion |
| `api.py` | 137 | ✅ KEEP | Thin wrapper |
| `join_fk_shorthand.py` | 98 | ✅ KEEP | FK join sugar |
| `list_comprehension.py` | 66 | ✅ KEEP | Post-processing for DuckDB/Snowflake |
| `sqlglot_schema_adapter.py` | 62 | ✅ KEEP | Thin adapter for FK relationships |
| `column_operators.py` | 61 | ✅ KEEP | Uses SQLGlot's `qualify_columns` correctly |

**Total compiler code: 4004 lines**
- To delete: 430 lines (alias_reuse.py)
- Custom ASQL features: 3574 lines

---

## Immediate (This Week)

1. **Finish settings migration** - PR in progress
2. **DELETE `alias_reuse.py`** - Replace with `qualify_columns(expand_alias_refs=True)` → **-430 lines** (agent working)
3. ✅ **Test PIVOT/EXPLODE transpilation** - DONE! Results:
   - PIVOT: SQLGlot drops it, KEEP our `pivot_fallback.py`
   - EXPLODE: SQLGlot handles it → **DELETE `explode_fallback.py`** (-75 lines)
4. ✅ **DELETE `explode_fallback.py`** - Already deleted on this branch!

## Short-term

4. **Complete PRQL dialect review** - understand why it's 10x smaller
5. **Complete DuckDB dialect review** - check for other patterns
6. **Audit parser size** - why is ours 3000 lines vs ~300?

## Medium-term

7. **Systematic file audit** - go through each `asql/compiler/*.py`
8. **Consider upstream contributions** - PIVOT fallback could benefit SQLGlot community
9. **Reduce parser size** - goal: under 1000 lines

---

# How We Missed Settings Before

**Learning**: Previous investigations were feature-focused, not system-focused.

We looked at:
- "How do we do X?" (transforms, parsing, etc.)

We didn't ask:
- "What systems does SQLGlot have?" (settings, optimizer, schema)
- "Are we duplicating any SQLGlot systems?"

**Fix**: This audit takes a systems-level approach - inventory SQLGlot, then compare.
