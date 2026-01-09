# ASQL Architecture Audit

**Date**: 2026-01-07  
**Purpose**: Review what we've built, verify placement, identify next steps

---

## ✅ Completed Work - Placement Review

### Tokenizer (ASQLTokenizer) - ✅ CORRECT

| Feature | Token Added | Status |
|---------|-------------|--------|
| `@` for date literals | `TokenType.PARAMETER` | ✅ Correct - new punctuation |
| `#` for COUNT shorthand | `TokenType.HASH` | ✅ Correct - new punctuation |
| `\|` for pipe syntax | `TokenType.PIPE_GT` | ✅ Correct - new punctuation |

### Parser (ASQLParser) - ✅ MOSTLY CORRECT

| Feature | Method/Location | Status | Notes |
|---------|-----------------|--------|-------|
| FROM-first syntax | `_parse_query()` | ✅ Correct | Syntax change |
| Pipe transforms | `_parse_query()` + helpers | ✅ Correct | Syntax change |
| Ternary `? :` | `_parse_assignment()` | ✅ Correct | Operator pattern |
| `@date` literals | `PLACEHOLDER_PARSERS` | ✅ Correct | Token-based pattern |
| `7 days ago` | `_parse_unary()` | ✅ Correct | Token-based pattern |
| `col + 7 days` | `_parse_factor()` | ✅ Correct | Token-based pattern |
| `== null` → `IS NULL` | `_parse_equality()` | ✅ Correct | Operator overload |
| `-column` → DESC | `_parse_ordered()` | ✅ Correct | Operator overload |
| `??` coalesce | Native SQLGlot | ✅ Correct | Uses DQMARK token |

### Generator (ASQLGenerator) - ✅ CORRECT

| Feature | Status | Notes |
|---------|--------|-------|
| `NORMALIZE_FUNCTIONS = False` | ✅ Correct | Preserve function casing |
| Relies on target dialect | ✅ Correct | We transpile ASQL→AST→TargetSQL |

---

## ⚠️ Items That May Be Misplaced

### In Preparser → Should Move to OPTIMIZER

These are **schema-aware** transformations that pattern-match on identifier text:

| Feature | Current Location | Should Be | Why |
|---------|------------------|-----------|-----|
| `days_since_created_at` | `preparse/dates.py` | **Optimizer** | Needs schema to verify `created_at` exists |
| `months_until_due_date` | `preparse/dates.py` | **Optimizer** | Needs schema to verify `due_date` exists |
| `sum_amount` shorthand | `preparse/aggregates.py` | **Optimizer** | Needs schema to verify `amount` exists |
| `avg_price` shorthand | `preparse/aggregates.py` | **Optimizer** | Needs schema to verify `price` exists |
| `year_of_created_at` | (if exists) | **Optimizer** | Needs schema |

**Why optimizer?** These look like column references during parsing. Only with schema can we know they're shorthands (the column doesn't exist, but the base column does).

### In Preparser → Should Stay (Complex Text Patterns)

| Feature | Location | Why Stay |
|---------|----------|----------|
| Natural aggregates (`sum amount`) | `preparse/aggregates.py` | Space-separated = hard to tokenize |
| Join operators (`&`, `<&`, `&>`) | `preparse/joins.py` | Complex multi-token patterns |
| When expressions | `preparse/when.py` | Keyword-based + indentation |
| Per commands | `preparse/per.py` | Complex syntax transformation |
| Pivot/Unpivot | `preparse/pivot.py` | Complex syntax |
| Stash as (CTEs) | `preparse/stash.py` | Block-level transformation |
| Comments extraction | `preparse/comments.py` | Protects from regex corruption |

---

## 📋 Next Steps - Prioritized

### Phase 1: Quick Wins (Token-based, no schema needed)

| Task | Effort | LOC Saved | Where to Put |
|------|--------|-----------|--------------|
| `# COUNT(*)` shorthand | Medium | ~50 | Parser - needs table context |

**Note**: `#` COUNT is tricky - it needs to know the table name to generate `COUNT(*)`. May need to stay in preparser or move to optimizer.

### Phase 2: Schema-Aware Optimizer (New capability)

| Task | Effort | Where to Put |
|------|--------|--------------|
| Create `asql/optimizer/` module | Medium | New directory |
| Add `resolve_shorthands()` rule | Medium | `asql/optimizer/shorthands.py` |
| Move `days_since_*` / `*_until_*` | Low | Uses new optimizer |
| Move `sum_amount` / `avg_*` shorthands | Low | Uses new optimizer |
| Wire optimizer into `compile()` | Low | `asql/compiler/api.py` |

**Proposed optimizer rule:**

```python
# asql/optimizer/shorthands.py
def resolve_asql_shorthands(expression, schema):
    """
    Resolve ASQL column shorthands using schema.
    
    Only transforms columns that:
    1. Don't exist in schema
    2. Match a known pattern (days_since_*, sum_*, etc.)
    3. Have a valid base column that DOES exist
    """
    for col in expression.find_all(exp.Column):
        table = col.table or infer_table(col, expression)
        if not schema.has_column(table, col.name):
            resolved = _try_resolve_shorthand(col.name, table, schema)
            if resolved:
                col.replace(resolved)
    return expression
```

### Phase 3: Preparser Cleanup

| Task | Notes |
|------|-------|
| Remove `_transform_since_until_patterns` from dates.py | After optimizer handles it |
| Remove aggregate shorthands from aggregates.py | After optimizer handles it |
| Audit remaining preparser for any other schema-aware transforms | |

---

## 📊 Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                     ASQL Compilation Pipeline                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ASQL Query String                                               │
│         │                                                        │
│         ▼                                                        │
│   ┌──────────────┐                                               │
│   │  PREPARSER   │  Still needed for:                           │
│   │              │  - Natural aggregates (sum amount)            │
│   │              │  - Join operators                             │
│   │              │  - When expressions                           │
│   │              │  - Per/Pivot/Stash                            │
│   └──────┬───────┘                                               │
│          │                                                       │
│          ▼                                                       │
│   ┌──────────────┐                                               │
│   │  TOKENIZER   │  ASQL tokens: @, #, |                        │
│   └──────┬───────┘                                               │
│          │                                                       │
│          ▼                                                       │
│   ┌──────────────┐                                               │
│   │   PARSER     │  ASQL syntax:                                │
│   │              │  - FROM-first, pipes                          │
│   │              │  - Ternary ? :                                │
│   │              │  - @date, relative dates                      │
│   │              │  - Date arithmetic                            │
│   └──────┬───────┘                                               │
│          │ AST                                                   │
│          ▼                                                       │
│   ┌──────────────┐  ┌──────────┐                                │
│   │  OPTIMIZER   │←─│  SCHEMA  │  [NEW - Phase 2]               │
│   │              │  │          │                                 │
│   │  - Standard SQLGlot rules                                   │
│   │  - resolve_asql_shorthands [NEW]                            │
│   │    └─ days_since_*, sum_*, etc.                             │
│   └──────┬───────┘  └──────────┘                                │
│          │ Optimized AST                                         │
│          ▼                                                       │
│   ┌──────────────┐                                               │
│   │  GENERATOR   │  Target dialect (postgres, snowflake, etc.)  │
│   └──────┬───────┘                                               │
│          │                                                       │
│          ▼                                                       │
│   Target SQL String                                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Immediate Action Items

1. [ ] **Decide**: Do we want to build the optimizer integration now or later?
2. [ ] **If now**: Create `asql/optimizer/` module with `resolve_shorthands.py`
3. [ ] **If later**: File GitHub issue for "Schema-aware ASQL optimizer"
4. [ ] **Either way**: Keep `days_since_*` in preparser for now (it works)

---

## Questions to Resolve

1. **Schema availability**: When is schema available in ASQL? Always? Sometimes?
2. **Performance**: Is optimizer overhead acceptable for all queries?
3. **Error messages**: How do we handle "column doesn't exist AND isn't a valid shorthand"?

