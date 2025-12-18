# Exception Handling Cleanup

Tracking progress on removing unnecessary/dangerous exception swallowing.

## Issues to Fix

### 1. `reverse_compiler.py` - `detect_dialect()` (lines 32-64)
**Status**: ✅ DONE
**Problem**: Catches `Exception` broadly while trying multiple dialects
**User feedback**: Function design seems wrong - why try/fail on each dialect?
**Analysis**: The design is intentional - it tries parsing with each dialect to find the best match. But catching all `Exception` was too broad.
**Action**: Narrowed to catch only `sqlglot.errors.ParseError`, removed outer try/except
**Result**: All 1555 tests pass

### 2. `auto_alias.py` - `_get_function_name()` (lines 287-292)
**Status**: ✅ DONE
**Problem**: `except Exception: pass` when calling `sql_name()`
**User feedback**: Remove entirely - if it errors we should know why
**Action**: Removed try/except completely
**Result**: All 1555 tests pass - exception was unnecessary

### 3. `reverse_compiler.py` - CTE parsing (lines 307-310)
**Status**: ✅ DONE
**Problem**: `except (AttributeError, TypeError): pass` silently skips CTEs
**User feedback**: Remove and see what tests catch
**Action**: Removed outer try/except (kept inner one that shows errors in comments)
**Result**: All 1555 tests pass - exception was unnecessary

### 4. `reverse_compiler.py` - `_expression_to_asql()` (lines 700-705)
**Status**: ✅ DONE
**Problem**: `except Exception: pass` when handling function expressions
**User feedback**: Remove and run tests
**Action**: Removed try/except
**Result**: All 1555 tests pass - exception was unnecessary

### 5. `compiler/api.py` - `extract_settings_from_query()` (lines 127-135)
**Status**: ✅ DONE
**Problem**: Catches all exceptions, returns defaults silently
**User feedback**: Settings errors should fail loudly, not frustrate users
**Action**: Removed try/except
**Result**: All 1555 tests pass - exception was unnecessary

### 6. `auto_alias.py` - Jinja2 fallback (lines 279-281 + fallback function)
**Status**: ✅ DONE
**Problem**: Has entire fallback implementation for when Jinja2 not installed
**User feedback**: "NO fallbacks for lib dependencies"
**Action**: Removed ~60 lines of fallback code, Jinja2 is already a required dependency
**Result**: All 1555 tests pass

### 7. `config.py` - YAML import (lines 269-271)
**Status**: ✅ DONE
**Problem**: `except ImportError` to fall back to JSON if YAML not available
**User feedback**: Use conditional check, not exception catching
**Action**: Refactored to check file extension first - JSON files use json module, YAML files use yaml module (with clear ImportError if not installed)
**Result**: All 1555 tests pass - cleaner logic, no exception-based control flow

### 8. `dialect.py` - Dialect registration (lines 214-218)
**Status**: ✅ DONE
**Problem**: `except ValueError` to check if dialect already registered
**User feedback**: Is there a better conditional check?
**Action**: Changed to `if "asql" not in Dialect._classes:` - proper conditional check
**Result**: All 1555 tests pass

### 9. `window.py` - Window size parsing (lines 308-311, 323-326)
**Status**: ✅ VALID - NO CHANGE NEEDED
**Problem**: `except ValueError` when parsing window size as int
**User feedback**: Explain more - is this right or should we error/redesign?
**Analysis**: This is VALID and intentional:
- `rolling_avg(col, 5)` → window is "5", we parse as int and compute 5-1=4
- `rolling_avg(col, @n)` → window is "@n", int() fails, we output "@n - 1" as expression
- The ValueError distinguishes between literal integers and expressions/parameters
- This is idiomatic Python for "check if string is integer literal"
**Result**: No change needed - this is legitimate exception-based type checking

---

## Summary

**All 9 issues addressed:**
- 7 fixed by removing/narrowing exception handling
- 1 already valid (window.py integer parsing)
- ~60 lines of unnecessary fallback code removed (Jinja2 fallback)

**Key changes:**
1. Removed 4 `except Exception: pass` patterns that silently swallowed errors
2. Narrowed `detect_dialect` to catch only `ParseError` instead of all exceptions
3. Removed entire Jinja2 fallback function (Jinja2 is already a required dep)
4. Replaced exception-based control flow with conditional checks where possible

**All 1572 tests pass after changes (17 new tests added to verify error surfacing).**

---

## Progress Log

### 2025-12-18
- Created this tracking doc
- Fixed #2: Removed try/except from `_get_function_name` - tests pass
- Fixed #4: Removed try/except from `_expression_to_asql` - tests pass
- Fixed #3: Removed outer try/except from CTE parsing - tests pass
- Fixed #5: Removed try/except from `get_settings_from_query` - tests pass
- Fixed #6: Removed Jinja2 fallback (~60 lines of dead code) - tests pass
- Fixed #8: Changed dialect registration to use conditional check - tests pass
- Fixed #7: Refactored config loading to check extension first - tests pass
- Fixed #1: Narrowed detect_dialect to catch only ParseError - tests pass
- Analyzed #9: Window size parsing is valid - no change needed
- Added `tests/test_exception_handling.py` with 17 tests to verify errors surface properly

### Additional "fallback" cleanup
- Fixed `reverse_compiler.py` CAST handling: was outputting `::UNKNOWN` silently, now raises error
- Fixed `reverse_compiler.py` CAST function handling: added check for missing type
- Fixed `auto_alias.py` `_get_function_name`: was returning "unknown", now raises ValueError (this path is never hit in practice - all sqlglot Func subclasses have valid sql_name())
- Replaced hardcoded dialect list with dynamic `Dialects` enum from sqlglot (6 → 31 dialects)
