# Re-Analysis: Structural Comparison Audit

**Date**: 2026-01-18 (Updated after `asql.transpile()` refactor)  
**Original**: `ai_notes/2026-01-18-structural-comparison-audit.md`

## Summary

After implementing `asql.transpile()` and the explicit spine syntax, many of the "red flags" from the original audit are now **by design** rather than architectural mistakes.

---

## Issue-by-Issue Analysis

### Q1: External Imports in Parser → ⚠️ ACCEPTABLE

**Current state**: 5 imports from `asql.compiler.*`

```
from asql.compiler.underscore_shorthands import ...
from asql.compiler.auto_alias import apply_auto_aliasing
from asql.compiler.auto_qualify import auto_qualify_columns
from asql.compiler.join_fk_shorthand import transform_fk_shorthand
from asql.compiler.cohort_transform import transform_cohort
```

**Why this is OK now**: These are **parser-stage transforms** that:
- ❌ Do NOT need the output dialect
- ✅ Can be applied during parsing
- ✅ Are called in `_apply_asql_transforms()` after parsing each statement

The original audit assumed all transforms should go in Generator.preprocess(), but we've since established a clearer architecture:
- **Parser transforms**: Don't need output dialect → stay in parser
- **Dialect-aware transforms**: Need output dialect → go in `asql.transpile()`

**Action**: None needed. Could reorganize files (move these to `asql/dialect/transforms/`) but not architecturally wrong.

---

### Q4: Post-Parse Transforms → ✅ BY DESIGN

**Current state**: `_apply_asql_transforms` exists in parser

**Why this is correct**: ASQL legitimately needs parser-stage transforms that don't depend on output dialect:
- Underscore shorthands (`days_since_` → `DATEDIFF`)
- Auto-aliasing (auto-generate column aliases)
- FK shorthand (`ON user_id` → `ON a.user_id = b.user_id`)
- Cohort transform (builds cohort analysis query)
- Auto-qualify (resolve ambiguous columns)

These run in the parser because they're **input-dialect concerns**, not output-dialect concerns.

**Action**: None. This is the correct pattern.

---

### Q6: Settings/Config References → ⚠️ REVIEW NEEDED

**Current state**: 38 references (was 35)

**Settings used in parser**:
| Setting | Why in Parser? | Verdict |
|---------|---------------|---------|
| `schema` | FK inference, qualify columns | ✅ Needed |
| `week_start` | Affects `week()` function parsing | ✅ Needed |
| `relative_date_type` | Affects date literal parsing | ✅ Needed |
| `alias_template/prefixes/templates` | Auto-aliasing | ✅ Needed |
| `infer_join_keys` | FK shorthand | ✅ Needed |
| `include_transpilation_comments` | Passed to transforms | ⚠️ Could move |
| `passthrough_comments` | Comment handling | ⚠️ Now in transpile() |

**Verdict**: Most settings ARE legitimately needed at parse time because they affect how syntax is interpreted. A few could potentially be moved to `asql.transpile()`.

**Action**: Low priority. Current approach is workable.

---

### Q8: Generator TRANSFORMS Dict → ✅ INTENTIONALLY SKIPPED

**Current state**: No custom generator, no TRANSFORMS dict

**Why this is correct**: We decided NOT to create custom generators because:
1. We want to use SQLGlot's generators unchanged (DuckDB, Postgres, Snowflake, etc.)
2. Dialect-aware transforms happen in `asql.transpile()`, not Generator.preprocess()
3. This keeps our code simpler and more maintainable

**The original audit suggested**: Create `ASQLGenerator(DuckDBGenerator)` with TRANSFORMS dict.  
**Our decision**: Use `asql.transpile()` as the transform layer instead.

**Action**: None. This is by design.

---

### Q10: Error Handling → ⚠️ REVIEW OPTIONAL

**Current state**: 55 raise statements (was 52)

**Why this might be OK**: ASQL has substantial custom syntax:
- Pipeline operators (`from`, `where`, `join`, `group by`, etc.)
- Date shorthands (`1 week ago`, `3 months from now`)
- Custom functions (`prior()`, `next()`, `rolling_avg()`)
- Spine syntax (`spine by`, `spine()`)
- Cohort syntax (`cohort by`)

Custom syntax = custom error messages make sense.

**Potential issues**:
- Some errors might be overly strict
- Some might duplicate SQLGlot's built-in error handling

**Action**: Low priority. Could audit which errors are actually helpful vs. redundant.

---

## Action Items Status

| Original Item | Status | Notes |
|--------------|--------|-------|
| Move dialect-specific transforms to api.py | ✅ Done | Moved to `asql.transpile()` |
| Create `asql/generators/` module | ❌ Skipped | Not needed with `asql.transpile()` design |
| Move transforms to Generator.preprocess() | ❌ Skipped | Transforms go in `asql.transpile()` instead |
| DELETE `api.py` | ✅ Done | `api.py` removed |
| DELETE `list_comprehension.py` | ❌ Not needed | Still used by `asql.transpile()` for DuckDB fixups |
| Move parser transforms to `dialect/transforms.py` | ⚠️ Optional | Could reorganize but not required |
| Remove compiler imports from parser | ⚠️ Acceptable | Parser-stage transforms need these imports |
| Reduce settings references to ~0 | ⚠️ Unnecessary | Settings are legitimately needed at parse time |
| Review 52 error raises | ⏳ Optional | Low priority, most likely valid |
| Replace auto_qualify with SQLGlot's qualify_columns | ⏳ Optional | Would need investigation |

---

## Remaining Concerns

### 1. File Organization (Cosmetic)
The `asql/compiler/` folder contains a mix of:
- Parser-stage transforms (underscore_shorthands, auto_alias, cohort_transform)
- Transpile-stage transforms (spine, alias_reuse, column_operators)

**Suggestion**: Could reorganize into:
- `asql/dialect/transforms/` - parser-stage transforms
- `asql/compiler/` - transpile-stage transforms (dialect-aware)

**Priority**: Low. Current organization works, just slightly confusing.

### 2. Error Message Quality (Optional)
55 custom errors might include:
- Overly strict validation
- Poor error messages
- Redundant checks

**Suggestion**: Could audit top 10 most common error paths and improve messages.

**Priority**: Low.

---

## Conclusion

The original audit identified real architectural concerns, but our `asql.transpile()` refactor addressed them differently than originally suggested:

| Original Suggestion | What We Did | Why |
|--------------------|-------------|-----|
| Put transforms in Generator.preprocess() | Put in `asql.transpile()` | Keeps SQLGlot generators unchanged |
| Create custom Generator classes | Use SQLGlot generators as-is | Simpler, less code to maintain |
| Remove all compiler imports from parser | Keep parser-stage imports | These transforms don't need output dialect |
| Remove all settings from parser | Keep parse-time settings | They affect syntax interpretation |

**The architecture is now clean and intentional**, even if it differs from what the original audit suggested.
