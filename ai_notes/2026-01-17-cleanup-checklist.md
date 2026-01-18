# ASQL Cleanup Checklist

**Goal**: Clean codebase with proper SQLGlot dialect, no wrapper functions.

**Status**: ALL PHASES COMPLETE ✅  
**Last Updated**: 2026-01-17  
**PR Branch**: `feature/visualasql-dialect`

---

## Overview

```
Phase 1: Quick Cleanup (delete legacy wrappers) ✅ COMPLETE
    │
    ▼
Phase 2: Folder Split ✅ COMPLETE
    │
    ▼
Phase 3: Migrate compile() → Dialect ✅ COMPLETE
    │
    ▼
Ready for production!
```

**Out of scope (separate PR later)**: Visual ASQL dialect for JSON ↔ SQL

---

## Phase 1: Quick Cleanup ✅ COMPLETE

**Goal**: Delete legacy wrapper functions and aliases.  
**Completed**: 2026-01-17  
**All 2546 tests pass!**

### 1.1 Files DELETED ✅

| File | Why | Status |
|------|-----|--------|
| `asql/reverse_compiler.py` | Use `sqlglot.transpile(..., write='asql')` instead | ✅ Done |

### 1.2 Functions REMOVED ✅

| Function | File | Replacement | Status |
|----------|------|-------------|--------|
| `normalize()` | `asql/__init__.py` | `sqlglot.transpile(q, read='asql', write='asql')` | ✅ Done |
| `get_preparsed()` | `asql/compiler/api.py` | `sqlglot.parse_one(q, dialect='asql').sql()` | ✅ Done |
| `ASQLDialect = ASQL` | `asql/dialect.py` | Just use `ASQL` | ✅ Done |

### 1.3 Imports/Exports REMOVED ✅

**`asql/__init__.py`**: All cleaned ✅  
**`asql/compiler/__init__.py`**: All cleaned ✅

### 1.4 Tests UPDATED ✅

| Test File | Status |
|-----------|--------|
| `tests/test_reverse_translation.py` | ✅ Uses `transpile()` |
| `tests/test_playground_examples.py` | ✅ Uses `transpile()` |
| `tests/test_fivetran_examples_compilation.py` | ✅ Uses `transpile()` |
| `tests/test_cast.py` | ✅ Uses `transpile()` |
| `tests/test_dialect.py` | ✅ `ASQLDialect` removed |
| `tests/quality/test_exception_handling.py` | ✅ Updated |
| `tests/quality/test_code_quality.py` | ✅ `ASQLDialect` removed |

### 1.5 Playground UPDATED ✅

| File | Status |
|------|--------|
| `playground/app.py` | ✅ Uses `sqlglot.transpile()` |

### 1.6 ASQLGenerator ADDED ✅

Added full generator implementation with:
- `cast_sql()` - generates `::` syntax
- `select_sql()` - FROM-first output
- `with_sql()` - CTEs → `stash as` 
- `join_sql()` - join symbols (`&`, `&?`, etc.)
- `from_sql()` - lowercase `from`

---

## Phase 2: Folder Split ✅ COMPLETE

**Status**: Done! 2026-01-17

Split `asql/dialect.py` (3,225 lines) into modular files:

| File | Lines | Description |
|------|-------|-------------|
| `asql/dialect/__init__.py` | 35 | Package exports |
| `asql/dialect/tokenizer.py` | 52 | ASQLTokenizer |
| `asql/dialect/parser.py` | 2,983 | ASQLParser + helpers |
| `asql/dialect/generator.py` | 152 | ASQLGenerator |
| `asql/dialect/dialect.py` | 60 | ASQL class + registration |

All 2559 tests pass!

---

## Phase 3: Migrate compile() → Dialect ✅ COMPLETE

**Goal**: Move all transforms into the dialect parser.  
**Completed**: 2026-01-17  
**All 2625 tests pass!**

### Architecture Decisions

1. **All transforms now in `ASQLParser._apply_asql_transforms()`**
   - Applied automatically during parsing when `asql_skip_transforms=False` (default)
   - `compile()` uses `asql_skip_transforms=True` to handle inline settings first

2. **Two APIs available**:
   - `sqlglot.transpile()` - Basic ASQL without inline settings
   - `asql.compile()` - Full features with inline `SET` statements

3. **`compile()` kept** - Handles inline settings extraction which must happen before transforms

### Step 3.1: Plumbing ✅
| Task | Status |
|------|--------|
| Add `asql_` prefixed settings to parser kwargs | ✅ Done |
| Add `asql_target_dialect` for dialect-specific transforms | ✅ Done |
| Add `asql_skip_transforms` flag for compile() | ✅ Done |

### Step 3.2: Parser Transforms ✅
| Transform | Status |
|-----------|--------|
| `apply_since_until_underscore_shorthands` | ✅ In parser |
| `apply_implicit_function_aliases` | ✅ In parser |
| `apply_auto_aliasing` | ✅ In parser |
| `transform_fk_shorthand` (when `asql_schema` provided) | ✅ In parser |
| `transform_cohort` | ✅ In parser |
| `apply_alias_reuse` | ✅ In parser |

### Step 3.3: Dialect-Specific Transforms ✅
| Transform | Condition | Status |
|-----------|-----------|--------|
| `transform_pivot_for_dialect` | When `asql_target_dialect` provided | ✅ In parser |
| `transform_explode_for_dialect` | When `asql_target_dialect` provided | ✅ In parser |
| `transform_column_operators_for_dialect` | When both schema + dialect provided | ✅ In parser |
| `_apply_auto_spine` | When `asql_auto_spine=True` + dialect | ✅ In parser |
| `auto_qualify_columns` | Always | ✅ In parser |

### Bug Fixed ✅
- **`stash as` creating TableAlias instead of Table** - Was causing `eliminate_ctes` optimizer to incorrectly remove CTEs while keeping dangling references. Fixed by passing alias name as string to `_build_pipe_cte()`.

### Summary
```
sqlglot.transpile(asql, read='asql', write='postgres')
  → Basic ASQL works automatically
  → Underscore shorthands, auto-aliasing, alias reuse all work
  → 2625 tests pass

asql.compile(asql, dialect='postgres', settings=...)
  → Full features with inline SET statements
  → Schema-aware FK shorthand, column operators
  → Auto-spine, cohort analysis, pivot fallback
```

---

## Progress Summary

| Phase | Tasks | Done | Status |
|-------|-------|------|--------|
| 1. Quick Cleanup | 25 | 25 | ✅ Complete |
| 2. Folder Split | 8 | 8 | ✅ Complete |
| 3. Migrate compile() | 16 | 16 | ✅ Complete |

**Total tests passing: 2625**

---

## What's NOT in Scope (separate PRs later)

- Visual ASQL dialect (JSON ↔ SQL)
- ~~UI Schema export~~ ✅ Done - see `asql/ui-metadata.json`
- Docstring trimming
- Further parser optimizations
- ~~Phase 2 folder split~~ ✅

---

## Visual Editor Future Improvements

**Current state**: Basic functional UI in `playground/static/visual-editor.js` (~700 lines vanilla JS)

**UI Metadata**: ✅ Complete - `asql/ui-metadata.json` has:
- All transforms with parameters
- All operators (comparison, string, null, list, logical)
- All functions (date, string, math, conditional, window, array)
- Join types, aggregates, time units, data types

**Missing features for production UI**:

| Feature | Priority | Notes |
|---------|----------|-------|
| Column autocomplete | High | Currently just text inputs - need schema awareness |
| Function picker/autocomplete | High | `functions` data exists but not used in UI |
| Syntax validation in expressions | Medium | No client-side validation |
| Drag-to-reorder transforms | Medium | Currently fixed order |
| Operator picker for expressions | Medium | Expression widget has hardcoded operators |
| Better mobile support | Low | Desktop-focused layout |
| Keyboard shortcuts | Low | All mouse-driven |
| Undo/redo | Low | No history tracking |

**Tech debt**:
- No UI framework (vanilla JS + CSS)
- No component library
- No TypeScript types (could generate from ui-metadata.json later)
