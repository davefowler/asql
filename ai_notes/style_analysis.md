# ASQL Default Style Settings Analysis

**Date**: 2025-01-XX  
**Status**: Analysis report (may become outdated)

## Default "Pretty" Settings

Based on `asql/config.py` `StyleConfig` class (default preset):

| Setting | Default | Meaning | Example |
|---------|---------|---------|---------|
| **equality** | `"single"` | Use `=` not `==` | `where status = "active"` |
| **count** | `"hash"` | Use `#` not `count(*)` | `# as total` |
| **coalesce** | `"operator"` | Use `??` not `coalesce()` | `name ?? "Unknown"` |
| **descending** | `"prefix"` | Use `-col` not `col DESC` | `order by -created_at` |
| **cast** | `"double_colon"` | Use `::` not `CAST()` | `created_at::DATE` |
| **quotes** | `"double"` | Use `"` not `'` | `where status = "active"` |

## Other Preferred Syntax Patterns (Beyond "Pretty" Settings)

These are syntax choices that represent preferred ASQL patterns:

### Conditional Expressions: `when` over `CASE WHEN`
- **Preferred**: `when status is "active" then 1 otherwise 0`
- **Avoid**: `CASE WHEN status = 'active' THEN 1 ELSE 0 END`
- **Rationale**: `when` is ASQL's primary conditional syntax, more concise and readable

### Equality in `when`: `is` over `=`
- **Preferred**: `when status is "active" then 1`
- **Alternative**: `when status = "active" then 1` (also works)
- **Rationale**: `is` reads more naturally: "when status is active"

### Default Clause: `otherwise` over `else`
- **Preferred**: `otherwise "Unknown"`
- **Alternative**: `else "Unknown"` (also accepted)
- **Rationale**: `otherwise` is more explicit

### CTEs: `stash as` over `WITH ... AS`
- **Preferred**: `stash as active_users` (inline CTEs)
- **Alternative**: `WITH ... AS` (SQL style, also accepted)
- **Rationale**: `stash as` fits ASQL's pipeline model better

### Filtering: `where` over `if`
- **Preferred**: `where status = "active"`
- **Alternative**: `if status = "active"` (syntactic sugar)
- **Rationale**: `where` is more familiar and standard

### Pipeline Style: Indentation over Pipe Operator
- **Preferred**: Indentation-based pipelines
- **Alternative**: Pipe operator `|` (also supported)
- **Rationale**: Indentation is cleaner and more natural

### String Matching: Natural operators over `LIKE`
- **Preferred**: `contains`, `starts with`, `ends with`
- **Alternative**: `LIKE` with wildcards (SQL style)
- **Rationale**: Natural language operators are more readable

## Violations Found

### 1. Equality Operator: `==` vs `=`

**Default**: `=` (single)

**Found**: 235+ instances of `==` in docs

**Analysis**:
- ✅ **Keep as-is**: Many instances are in:
  - "Coming from" guides showing comparisons (R, pandas, etc.)
  - Documentation explicitly explaining both work: `docs/spec.md:123` says "Both `=` and `==` work for equality. `=` is preferred..."
  - Code examples demonstrating alternatives
  - JavaScript/TypeScript code blocks (not ASQL)
  
- ⚠️ **Should review**:
  - `docs/quick_start.md:43,50` - Uses `==` in main examples (should probably use `=`)
  - `docs/integrating.md:63,68,154,162,198,300,376,471,613` - Uses `==` with single quotes (double violation)
  - `docs/spec.md:217,391,528,674,987,991,1057,1058,1089,1460,1471,1578,2015,2030,2181,2228,2312` - Uses `==` in examples
  - `docs/examples.md` - Multiple instances of `==` in examples

**Recommendation**: Keep most as-is (they're demonstrating alternatives), but consider updating main tutorial/quickstart examples to use `=` to match defaults.

---

### 2. Count: `count(*)` vs `#`

**Default**: `#` (hash)

**Found**: 92+ instances of `count(*)` in docs

**Analysis**:
- ✅ **Keep as-is**: Many instances are:
  - `count(distinct col)` - No shorthand exists, must use function form
  - `running_count(*)` - Different function, not the same as `#`
  - Documentation explaining alternatives: `docs/syntax/aggregations.md:87` shows both options
  - SQL output examples (correct)
  
- ⚠️ **Should review**:
  - `docs/group_by.md:13,96,109` - Uses `count(*)` in ASQL examples (could use `#`)
  - `docs/concepts/guaranteed-groups.md:79,105,125,229,239` - Uses `count(*)` (could use `#`)
  - `docs/spec.md:760,907` - Uses `count(*)` in examples (could use `#`)
  - `docs/syntax/aggregations.md:193,204` - Uses `count(*)` in examples (could use `#`)

**Recommendation**: Most are correct (distinct counts, running counts, or showing alternatives). Review simple `count(*)` cases that could be `#`.

---

### 3. Coalesce: `coalesce()` vs `??`

**Default**: `??` (operator)

**Found**: 21 instances of `coalesce()` in docs

**Analysis**:
- ✅ **Keep as-is**: Most instances are:
  - In "coming from" guides showing SQL equivalents
  - Documentation explaining the operator: `docs/reference/operators.md:88` says "Compiles to `COALESCE()`"
  - SQL output examples (correct)
  
- ⚠️ **Should review**:
  - `docs/reference/functions.md:389` - Shows `coalesce()` in function reference (should probably show `??`)
  - `docs/concepts/shorthand.md:115` - Uses `coalesce()` in example (could use `??`)
  - `docs/spec.md:224,241` - Uses `coalesce()` in examples (could use `??`)
  - `docs/syntax/expressions.md:109` - Uses `coalesce()` (could use `??`)

**Recommendation**: Most are correct (showing SQL equivalents). Review ASQL examples that could use `??`.

---

### 4. Descending: `DESC` vs `-col`

**Default**: `-col` (prefix)

**Found**: 32 instances of `DESC` in docs

**Analysis**:
- ✅ **Keep as-is**: Most instances are:
  - In SQL output examples (correct - SQL uses `DESC`)
  - In window function `order by` clauses within `OVER()` (correct - that's SQL syntax)
  - Documentation explaining the mapping: `docs/coming-from/sql.md:25` shows `ORDER BY x DESC` → `order by -x`
  
- ⚠️ **Should review**:
  - `docs/spec.md:2194,2411` - Shows SQL output with `DESC` (this is correct - it's SQL, not ASQL)
  - All instances appear to be in SQL output or window function contexts, which is correct

**Recommendation**: All instances appear correct (they're SQL output or window function syntax, not ASQL).

---

### 5. Cast: `CAST()` vs `::`

**Default**: `::` (double_colon)

**Found**: 14 instances of `CAST()` in docs

**Analysis**:
- ✅ **Keep as-is**: All instances are:
  - In SQL output examples (correct)
  - In "coming from" guides showing SQL equivalents
  - Documentation explaining the mapping: `docs/spec.md:400` says "`CAST(... AS ...)` expressions are automatically converted to `::` syntax"
  - In SQL code blocks (not ASQL)

**Recommendation**: All instances are correct (they're SQL, not ASQL).

---

### 6. Quotes: Single `'` vs Double `"`

**Default**: `"` (double)

**Found**: 41 instances of single quotes in docs

**Analysis**:
- ✅ **Keep as-is**: Many instances are:
  - In SQL code blocks (SQL often uses single quotes)
  - In Python code examples (Python uses single quotes)
  - In YAML/config examples
  - In SQL output examples
  
- ⚠️ **Should review**:
  - `docs/integrating.md:63,68,154,162,198,300,376,471,613` - Uses single quotes in ASQL examples (should use `"`)
  - `docs/coming-from/r.md:47,164,165,166,258` - Uses single quotes in ASQL examples (should use `"`)
  - `docs/coming-from/dbt.md:25,132,336,341` - Uses single quotes in ASQL examples (should use `"`)

**Recommendation**: Review ASQL code blocks that use single quotes - they should use double quotes per default style.

---


## Summary of Recommended Changes

### High Priority (Main Examples/Tutorials)
1. **`docs/quick_start.md`**: Change `==` to `=` in main examples (lines 43, 50)
2. **`docs/integrating.md`**: Change single quotes to double quotes and `==` to `=` in ASQL examples

### Medium Priority (Reference Docs)
3. **`docs/reference/functions.md`**: Consider showing `??` instead of `coalesce()` in examples
4. **`docs/concepts/shorthand.md`**: Consider using `??` instead of `coalesce()` in examples
5. **`docs/spec.md`**: Review `==` usage - some examples could use `=` to match defaults

### Low Priority (Coming-From Guides)
6. **Coming-from guides**: These intentionally show alternatives, so changes are optional. However, if updating, prefer default style.

### No Changes Needed
- `DESC` usage (all in SQL output or window functions - correct)
- `CAST()` usage (all in SQL output - correct)
- `count(*)` usage (most are `count(distinct)` or `running_count()` - correct)
- `sort` keyword (not found, all use `order by` - correct)
