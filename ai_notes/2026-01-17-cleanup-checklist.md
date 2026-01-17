# ASQL Cleanup Checklist

**Goal**: Clean codebase with proper SQLGlot dialect, no wrapper functions.

**Status**: Phase 1 Complete ✅  
**Last Updated**: 2026-01-17  
**PR Branch**: `cleanup-dialect-wrappers`

---

## Overview

```
Phase 1: Quick Cleanup (delete legacy wrappers) ✅ COMPLETE
    │
    ▼
Phase 2: Folder Split (DEFERRED - low priority)
    │
    ▼
Phase 3: Migrate compile() → Dialect (in progress)
    │
    ▼
Phase 4: PR & Code Review
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

## Phase 3: Migrate compile() → Dialect

**Goal**: Move all 11 transforms from `compile()` into the dialect, delete `compile()`.  
**Time**: ~4-6 hours  
**Risk**: Medium (logic changes, need careful testing)  
**Plan**: [ai_notes/2026-01-17-compile-to-dialect-migration.md](./2026-01-17-compile-to-dialect-migration.md)

### Step 3.1: Plumbing
| Task | Status |
|------|--------|
| Add dialect options support for ASQL settings | ⬜ TODO |
| Ensure schema accessible in Generator | ⬜ TODO |

### Step 3.2: Parser Transforms
| Transform | File | Status |
|-----------|------|--------|
| `apply_implicit_function_aliases` | compiler/implicit_aliases.py | ⬜ TODO |
| `apply_auto_aliasing` | compiler/auto_aliasing.py | ⬜ TODO |
| `apply_since_until_underscore_shorthands` | compiler/underscore_shorthands.py | ⬜ TODO |
| `apply_alias_reuse` | compiler/alias_reuse.py | ⬜ TODO |
| `transform_fk_shorthand` (schema-aware) | compiler/join_fk_shorthand.py | ⬜ TODO |

### Step 3.3: Generator Transforms
| Transform | File | Status |
|-----------|------|--------|
| `transform_column_operators_for_dialect` | compiler/column_operators.py | ⬜ TODO |
| `auto_qualify_columns` | compiler/qualify.py | ⬜ TODO |
| `transform_pivot_for_dialect` | compiler/pivot.py | ⬜ TODO |
| `transform_explode_for_dialect` | compiler/explode.py | ⬜ TODO |

### Step 3.4: Complex Transforms
| Transform | File | Status |
|-----------|------|--------|
| `transform_cohort` | compiler/cohort.py | ⬜ TODO |
| `_apply_auto_spine` | compiler/auto_spine.py | ⬜ TODO |

### Step 3.5: Cleanup
| Task | Status |
|------|--------|
| Delete `asql.compile()` | ⬜ TODO |
| Delete/archive `asql/compiler/` folder | ⬜ TODO |
| Update all tests to use `transpile()` | ⬜ TODO |
| Update docs | ⬜ TODO |

**After Phase 3**: `sqlglot.transpile(query, read='asql', write='postgres')` is the ONLY API needed.

---

## Phase 4: PR & Code Review

**Goal**: Create PR, get reviews, iterate on feedback.

| Task | Status |
|------|--------|
| Commit all changes | ⬜ TODO |
| Create branch `cleanup-dialect-wrappers` | ⬜ TODO |
| Push to GitHub | ⬜ TODO |
| Create PR with summary | ⬜ TODO |
| Address code reviews | ⬜ TODO |
| Merge PR | ⬜ TODO |

---

## Progress Summary

| Phase | Tasks | Done | Status |
|-------|-------|------|--------|
| 1. Quick Cleanup | 25 | 25 | ✅ Complete |
| 2. Folder Split | 8 | 8 | ✅ Complete |
| 3. Migrate compile() | 16 | 0 | ⬜ TODO |
| 4. PR & Code Review | 6 | 0 | ⬜ TODO |

---

## What's NOT in Scope (separate PRs later)

- Visual ASQL dialect (JSON ↔ SQL)
- UI Schema export
- Docstring trimming
- Further parser optimizations
- ~~Phase 2 folder split~~ ✅
