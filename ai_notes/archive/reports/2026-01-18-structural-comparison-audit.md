# Structural Comparison Audit: ASQL vs SQLGlot Dialects

**Date**: 2026-01-18  
**Purpose**: Ask the questions we SHOULD have asked - structural/architectural comparisons, not just feature comparisons.

## The 10 Questions

| # | Question | Finding |
|---|----------|---------|
| Q1 | Does parser import external modules? | ASQL imports `asql.compiler.*` - others don't |
| Q2 | How many class constants? | Similar (~11-19) |
| Q3 | Dialect param usage? | Similar |
| Q4 | Post-parse transforms? | **ASQL: YES, Others: NO** |
| Q5 | Entry point size? | Similar |
| Q6 | Settings/config references? | **ASQL: 35, Others: 0** |
| Q7 | Generator size? | ASQL smaller (306 vs 1000+) |
| Q8 | Generator TRANSFORMS dict? | **ASQL: NO, Others: YES (100+ mappings)** |
| Q9 | Schema references in parser? | Similar |
| Q10 | Custom error handling? | **ASQL: 52, Others: 0-3** |

---

## Detailed Findings

### Q1: External Imports in Parser

```
PRQL: 0 external imports
DuckDB: 1 external imports  
Snowflake: 0 external imports
BigQuery: 2 external imports
ASQL: 9 imports from asql.compiler.*
```

**🔴 RED FLAG**: ASQL parser imports compiler modules. NO other dialect does this.

```python
# ASQL parser imports (should NOT exist):
from asql.compiler.underscore_shorthands import ...
from asql.compiler.auto_alias import apply_auto_aliasing
from asql.compiler.auto_qualify import auto_qualify_columns
from asql.compiler.join_fk_shorthand import transform_fk_shorthand
from asql.compiler.cohort_transform import transform_cohort
```

---

### Q4: Post-Parse Transforms

```
PRQL: False (no _apply_* functions)
DuckDB: False
Snowflake: False
BigQuery: False
ASQL: True (_apply_asql_transforms)
```

**🔴 RED FLAG**: ASQL has a post-parse transform hook. Others don't.

---

### Q6: Settings/Config References in Parser

```
PRQL: 0 settings/config references
DuckDB: 0 settings/config references
Snowflake: 0 settings/config references
BigQuery: 0 settings/config references
ASQL: 35 settings/config references
```

**🔴 HUGE RED FLAG**: ASQL parser references settings 35 times. Others: ZERO.

This explains why ASQL's parser is doing things it shouldn't - it's reading config to decide behavior, which is a compile-time concern, not parse-time.

---

### Q8: Generator TRANSFORMS Dict

```
PRQL: No TRANSFORMS dict
DuckDB: TRANSFORMS dict with ~114 expression mappings
Snowflake: TRANSFORMS dict with ~140 expression mappings  
BigQuery: TRANSFORMS dict with ~109 expression mappings
ASQL: No TRANSFORMS dict
```

**🔴 RED FLAG**: ASQL's generator doesn't use SQLGlot's primary extension point.

DuckDB example:
```python
class Generator(generator.Generator):
    TRANSFORMS = {
        **generator.Generator.TRANSFORMS,
        exp.AnyValue: _anyvalue_sql,
        exp.ApproxDistinct: approx_count_distinct_sql,
        exp.Array: ...,
        # 100+ more mappings
    }
```

ASQL should be using TRANSFORMS for dialect-specific output, not custom code in the parser.

---

### Q10: Error Handling

```
PRQL: 3 raise/raise_error calls
DuckDB: 0 raise/raise_error calls
Snowflake: 1 raise/raise_error calls
BigQuery: 0 raise/raise_error calls
ASQL: 52 raise/raise_error calls
```

**🔴 RED FLAG**: ASQL has 52 custom error raises. Others have 0-3.

This suggests ASQL is doing validation/checking that should either:
1. Not exist (let SQLGlot handle it)
2. Happen elsewhere (optimizer, generator)

---

## Summary: Architectural Misalignments

| Area | SQLGlot Pattern | ASQL Pattern | Fix |
|------|-----------------|--------------|-----|
| Parser imports | No compiler imports | Imports `asql.compiler.*` | Move transforms to api.py |
| Post-parse hooks | None | `_apply_asql_transforms` | Remove, use api.py |
| Settings in parser | 0 references | 35 references | Settings belong in compile() |
| Generator TRANSFORMS | 100+ mappings | 0 mappings | Add TRANSFORMS dict |
| Error handling | 0-3 raises | 52 raises | Review each, remove most |

---

## Action Items

### ✅ DONE
- [x] Move dialect-specific transforms from parser to api.py (TEMPORARY)
- [x] Create `asql/generators/` module with ASQL-aware target generators
- [x] Move dialect transforms to `Generator.preprocess()`

### Immediate (Still TODO)
- [ ] **DELETE `api.py`** - see `ai_notes/2026-01-18-api-migration-plan.md`
- [ ] **DELETE `list_comprehension.py`** - duplicated in generators/base.py
- [ ] Move parser transforms from `asql/compiler/` to `asql/dialect/transforms.py`
- [ ] Remove `from asql.compiler.*` imports from parser
- [ ] Reduce 35 settings references to ~0

### Full Transform Analysis
See: `ai_notes/2026-01-18-transform-stage-audit.md`

### Investigation Needed
- [ ] How to register ASQL generators when `transpile()` is called
- [ ] Review 52 error raises - which are needed?
- [ ] Should `auto_qualify.py` be replaced with SQLGlot's `qualify_columns`?

---

## Lesson Learned

**We should have run these queries FIRST**, not after finding bugs.

A simple grep revealing "35 settings references vs 0" would have immediately shown the parser was doing compile-time work.

**Future audits must include structural comparison:**
```bash
# Count settings references
grep -c "settings\|config" dialect/parser.py  # Should be ~0

# Check for compiler imports  
grep "from.*compiler" dialect/parser.py  # Should be empty

# Verify TRANSFORMS dict exists
grep "TRANSFORMS = {" dialect/generator.py  # Should exist
```
