# Fallback Pattern Audit

**Philosophy**: We want to fail immediately if something isn't right. Fallbacks hide bugs, confuse users, bloat code, and lower quality. Only keep fallbacks that are truly necessary.

## Categories

- 🔴 **REMOVE** - Silent fallback that hides bugs, should error instead
- 🟡 **REVIEW** - May be legitimate, needs closer look
- 🟢 **KEEP** - Legitimate algorithm/design pattern

---

## 1. reverse_compiler.py

### 1.1 LIMIT clause extraction (lines 457-465)
```python
elif limit_expr.expressions:
    # Fallback: try expressions list
    limit_value_expr = limit_expr.expressions[0]
    ...
else:
    # Last fallback
    limit_value = str(limit_expr.this) if limit_expr.this else "10"
```
**What it does**: If can't extract LIMIT value, defaults to "10"
**Risk**: User writes `LIMIT 50`, output says `limit 10` - SILENT DATA CORRUPTION
**Recommendation**: 🔴 **REMOVE** - Raise error if can't determine limit value
**Test needed**: Yes - verify error on malformed LIMIT

### 1.2 Expression to ASQL fallback (line 721-722)
```python
# Fallback: use SQL representation
return str(expr)
```
**What it does**: If can't convert expression to ASQL, uses raw SQL string
**Risk**: Might produce invalid ASQL, but at least preserves the original
**Recommendation**: 🟡 **REVIEW** - This is a reasonable fallback for unknown expressions
**Test needed**: No - this is intentional passthrough for unsupported expressions

### 1.3 Function shorthand fallback (lines 748-749)
```python
else:
    # Fallback to parens if unknown
    return f"{func_name}({col})"
```
**What it does**: If shorthand style is unknown, uses parens
**Risk**: User sets `function_shorthand: "foo"` and gets parens instead of error
**Recommendation**: 🔴 **REMOVE** - Should error on invalid style setting
**Test needed**: Yes - verify error on invalid function_shorthand value

---

## 2. auto_alias.py

### 2.1 Function name fallback (lines 226-243)
```python
# Fallback to this.name or this.this.name
...
raise ValueError(...)  # ALREADY FIXED
```
**Status**: ✅ Already fixed - now raises ValueError

### 2.2 Template variable fallbacks (lines 108-146)
```python
vars_dict[f"arg{i}"] = col_name or ""
vars_dict["col"] = col_name or ""
vars_dict["order_by"] = order_by_col or ""
vars_dict["partition_by"] = partition_by_col or ""
```
**What it does**: If can't extract column name, uses empty string in template
**Risk**: Template `{prefix}_{col}` becomes `sum_` instead of erroring
**Recommendation**: 🟡 **REVIEW** - Empty string might be intentional for optional parts
**Test needed**: Maybe - check if empty col should error or just omit

### 2.3 Alias generation fallback (lines 295-315)
```python
# Fallback: Simple prefix-based generation (Phase 1)
...
return None  # No column name available
```
**What it does**: Falls back to simple prefix-based generation, or None for complex expressions
**Risk**: Low - this is the designed algorithm with multiple strategies
**Recommendation**: 🟢 **KEEP** - Legitimate multi-strategy algorithm
**Test needed**: No

---

## 3. count.py

### 3.1 SQL keyword fallback (lines 79, 93)
```python
if table_name.lower() in sql_keywords:
    return 'COUNT(*)'  # Shouldn't happen due to above pattern, but safe fallback
```
**What it does**: If regex matches SQL keyword as table name, returns COUNT(*)
**Risk**: Comment says "Shouldn't happen" - this is defensive coding for impossible case
**Recommendation**: 🔴 **REMOVE** - If it shouldn't happen, raise an error to surface bugs
**Test needed**: Yes - verify error if somehow a keyword is matched

---

## 4. cohort.py

### 4.1 Activity date column fallback (line 97)
```python
if not activity_date_col:
    activity_date_col = 'created_at'  # Fallback
```
**What it does**: If can't find date column, assumes 'created_at'
**Risk**: User's table has 'event_timestamp', gets wrong column silently
**Recommendation**: 🔴 **REMOVE** - Should error: "Cannot infer activity date column, please specify"
**Test needed**: Yes - verify error when date column not found

### 4.2 Join key default (lines 60-61) ✅ FIXED
```python
else:
    raise ASQLSyntaxError("Cohort analysis requires an explicit join key...")
```
**What it did**: Assumed 'user_id' if no explicit join key
**Fix**: Now requires explicit `on <join_key>` syntax (e.g., `cohort by month(users.signup_date) on user_id`)
**Recommendation**: 🔴 **REMOVED** - Now errors with helpful message

---

## 5. config.py

### 5.1 Preset default (line 349)
```python
preset = data.get("preset", "default")
```
**What it does**: If no preset specified, uses "default"
**Risk**: Low - this is intentional default configuration
**Recommendation**: 🟢 **KEEP** - Reasonable default for optional config
**Test needed**: No

### 5.2 Config file search returns None (line 259)
```python
return None  # No config file found
```
**What it does**: Returns None if no config file exists
**Risk**: Low - config is optional
**Recommendation**: 🟢 **KEEP** - Optional config file is by design
**Test needed**: No

---

## 6. window.py

### 6.1 Window alias defaults (lines 118, 146, 159, 172, 185)
```python
alias = match.group(4) or 'dense_rank'
alias = match.group(3) or 'row_num'
```
**What it does**: If no explicit alias, uses function name as alias
**Risk**: Low - sensible defaults for window functions
**Recommendation**: 🟢 **KEEP** - Standard behavior for optional aliases
**Test needed**: No

### 6.2 Rolling function without window size (lines 313-314, 328-329)
```python
else:
    return f"AVG({args}) OVER ({order_clause} ROWS UNBOUNDED PRECEDING)"
```
**What it does**: If rolling_avg has only one arg, uses UNBOUNDED PRECEDING
**Risk**: Low - documented behavior for cumulative vs rolling
**Recommendation**: 🟢 **KEEP** - Intentional API design
**Test needed**: No

---

## 7. when.py

### 7.1 Parser fallbacks returning None (many lines)
```python
return None, start_pos
return None, None, start_pos, False
```
**What it does**: Returns None when parsing fails
**Risk**: Low - parser design pattern for backtracking
**Recommendation**: 🟢 **KEEP** - Standard recursive descent parser pattern
**Test needed**: No

### 7.2 Complex condition fallback (line 350)
```python
# Fallback: searched-case / complex-condition branches...
```
**What it does**: Falls back to simpler parsing for complex WHEN conditions
**Risk**: Low - handles edge cases in WHEN clause parsing
**Recommendation**: 🟢 **KEEP** - Parser robustness
**Test needed**: No

---

## 8. compiler/auto_qualify.py

### 8.1 Table name extraction returns None (line 16) - DEAD CODE
```python
return None
```
**What it does**: Returns None if can't determine table name
**Analysis**: Function `_get_table_name` is defined but NEVER CALLED. The logic is duplicated inline in `_collect_joined_tables`.
**Recommendation**: 🟡 **DEAD CODE** - Consider removing the unused function
**Test needed**: No - it's not used

---

## 9. compiler/auto_spine.py

### 9.1 Build data spine returns None (lines 828, 832) - DEAD CODE
```python
if not source_col:
    return None
if not from_clause:
    return None
```
**What it does**: Returns None if can't build spine
**Analysis**: Function `_build_spine_select_from_data` is exported but NEVER USED or tested anywhere
**Recommendation**: 🟡 **DEAD CODE** - Consider removing the function entirely
**Test needed**: No - it's not used

---

## 10. inline_settings.py

### 10.1 Dialect extraction returns None (line 101)
```python
return None
```
**What it does**: Returns None if no dialect comment found
**Risk**: Low - dialect is optional
**Recommendation**: 🟢 **KEEP** - Optional return by design
**Test needed**: No

---

## Summary

### Items to FIX (🔴 REMOVE):

| Location | Issue | Action |
|----------|-------|--------|
| reverse_compiler.py:465 | LIMIT defaults to "10" | Raise error |
| reverse_compiler.py:749 | Unknown shorthand defaults to parens | Raise error |
| count.py:79,93 | "Shouldn't happen" fallback | Raise error |
| cohort.py:97 | Date column defaults to 'created_at' | Raise error |

### Items to REVIEW (🟡):

| Location | Issue | Decision needed |
|----------|-------|-----------------|
| cohort.py:61 | Join key defaults to 'user_id' | Convention vs explicit |
| auto_alias.py:108-146 | Template vars use empty string | May be intentional |
| reverse_compiler.py:722 | Unknown expr uses str(expr) | Passthrough vs error |

### Items to KEEP (🟢):

- Parser patterns returning None (backtracking)
- Optional config/alias defaults
- Multi-strategy algorithms with fallbacks
- Window function default aliases

---

## Progress

- [x] Fix LIMIT "10" fallback → Now raises ASQLCompilationError
- [x] Fix unknown shorthand fallback → Now raises ValueError  
- [x] Fix count.py "shouldn't happen" fallback → Now raises ValueError (bug indicator)
- [x] Fix cohort.py date column fallback → Now raises ASQLSyntaxError with helpful message
- [x] Add tests for new error cases → 2 new tests in test_exception_handling.py
- [x] Fix cohort.py join key default → Now requires explicit `on <join_key>` syntax
- [x] Review template variable empty strings → **KEEP** - intentional for optional template parts, cleanup removes double underscores
- [x] Review expression passthrough → **KEEP** - reasonable fallback for unsupported expressions, preserves original SQL
- [x] Review auto_spine.py returns None → **DEAD CODE** - function `_build_spine_select_from_data` is exported but never used or tested

**All 1575 tests pass after changes.**
