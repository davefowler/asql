# Unified Dialect Schema Refactor Plan

## Goal
Create ONE declarative schema that serves both the parser AND the visual editor, using nested classes instead of magic strings.

---

## Part 1: What We're Changing

### Current State (Problems)
```text
dialect.py (2600 lines)
├── if/elif chains (hard to introspect)
├── _build_comparison() - duplicates COMPARISON dict logic
├── _parse_comparison() - hard-coded string operator checks
└── TRANSFORM_PARSERS dict - functions, not data

ui_schema_generator.py
├── Auto-generates from TRANSFORM_PARSERS
└── Guesses icons/categories with heuristics

ui_overrides.yaml
├── Manual metadata for UI
└── DUPLICATES info from dialect (join types, operators, etc.)

dialect_schema.py (NEW - but dict-based)
└── Organized dicts with string keys (magic strings)
```

**Problem**: Information scattered across 4 files, lots of duplication, magic strings

### Target State (Solution)
```text
dialect_schema.py (ONE FILE - nested classes)
└── class DIALECT:
    ├── class OPERATORS (for parser + UI)
    ├── class JOIN_TYPES (for parser + UI)
    ├── class AGGREGATES (for parser + UI)
    └── class TRANSFORMS (for parser + UI)

dialect.py (refactored)
├── Uses DIALECT.OPERATORS.COMPARISON (no if/elif)
├── Uses DIALECT.JOIN_TYPES.INNER (no if/elif)
└── Parser logic only, no metadata

ui_schema.py (simplified)
└── Reads directly from DIALECT (no YAML, no generator)
```

**Solution**: ONE source of truth, type-safe, no duplication

---

## Part 2: Auto-Generated vs Manual

### ✅ Can Be Auto-Generated (from existing parser code)

| Field | Source | Example |
|-------|--------|---------|
| Operation names | `TRANSFORM_PARSERS.keys()` | "WHERE", "SELECT", "JOIN" |
| Keywords | `TRANSFORM_PARSERS.keys()` | ["WHERE", "FILTER", "IF"] |
| Token types | `Parser.COMPARISON`, `Parser.EQUALITY` | `TokenType.GT`, `TokenType.EQ` |
| Expression classes | `Parser.COMPARISON`, `Parser.EQUALITY` | `exp.GT`, `exp.EQ` |
| Join kinds | Token mappings in dialect | "INNER", "LEFT", "RIGHT" |
| Aggregate classes | `exp.AggFunc` subclasses | `exp.Count`, `exp.Sum` |
| Parameter names | Function signatures, arg_types | "condition", "table", "columns" |
| Required/optional | `arg_types` metadata | `required: True` |

**Percentage**: ~60% of metadata can be auto-discovered

### ❌ Must Be Manual (UI/documentation specific)

| Field | Why Manual | Example |
|-------|------------|---------|
| Icons | Visual/UX decision | 🔍, 📋, 🔗 |
| Labels | User-facing strings | "where", "join type" |
| Descriptions | Documentation | "Filter rows by condition" |
| Help text | User guidance | "Leave empty to infer from schema" |
| Placeholders | UX hints | "table_name", "column_name" |
| Categories | UI grouping | "filter", "join", "aggregate" |
| Widget types | Rendering decision | "text", "dropdown", "expression" |
| Dropdown labels | User-facing format | "inner (&)", "left (&?)" |

**Percentage**: ~40% needs human input

---

## Part 3: Unified Schema Structure

### Design: Every entry has BOTH parser fields AND UI fields

```python
class DIALECT:
    class OPERATORS:
        COMPARISON = {
            TokenType.GT: {
                # Parser fields (required by parser)
                "token": TokenType.GT,
                "expr_class": exp.GT,
                "symbol": ">",

                # UI fields (ignored by parser, used by visual editor)
                "label": ">",
                "description": "Greater than",
            },
            TokenType.LT: {
                "token": TokenType.LT,
                "expr_class": exp.LT,
                "symbol": "<",
                "label": "<",
                "description": "Less than",
            },
        }

        STRING = {
            "contains": {
                # Parser fields
                "tokens": ("CONTAINS",),
                "wrap_pattern": ("%", "%"),
                "case_sensitive": True,

                # UI fields
                "label": "contains",
                "description": "String contains (case-sensitive)",
            },
        }

    class JOIN_TYPES:
        INNER = {
            # Parser fields
            "symbols": ["&"],
            "keywords": ["JOIN", "INNER JOIN"],
            "kind": "INNER",

            # UI fields
            "label": "inner (&)",
            "description": "Inner join - only matching rows",
            "default": True,
        }

    class TRANSFORMS:
        WHERE = {
            # Parser fields
            "keywords": ["WHERE", "FILTER", "IF"],
            "parser_method": "_parse_asql_where",  # Optional, for reference

            # UI fields
            "label": "where",
            "icon": "🔍",
            "category": "filter",
            "description": "Filter rows by condition",

            # Parameter schema (used by BOTH parser hints AND UI generation)
            "parameters": {
                "condition": {
                    # Parser hints
                    "type": "expression",
                    "required": True,

                    # UI fields
                    "label": "condition",
                    "widget": "expression",
                    "description": "Boolean expression to filter rows",
                    "operators": ["=", "!=", "<", ">", "<=", ">=", "contains"],
                },
            },
        }
```

### Benefits of This Approach

1. **Single Source of Truth**: Everything in ONE place
2. **Type Safe**: No magic strings, IDE autocomplete everywhere
3. **Parser Uses It**: Replace if/elif with dict lookups
4. **UI Uses It**: Generate forms directly from schema
5. **Documentation Uses It**: Generate docs from same schema
6. **LSP Uses It**: Autocomplete from same schema
7. **Flexible**: Parser ignores UI fields, UI uses all fields
8. **Maintainable**: Change in one place, updates everywhere

---

## Part 4: Migration Path

### Phase 1: Refactor dialect_schema.py (nested classes)
- Convert dict-based to class-based
- Add UI fields alongside parser fields
- Keep backward compat (export dicts for current code)

### Phase 2: Update parser to use schema
- Refactor `_build_comparison()` to use `DIALECT.OPERATORS.COMPARISON`
- Refactor `_parse_comparison()` to loop over `DIALECT.OPERATORS.STRING`
- Update join parsing to use `DIALECT.JOIN_TYPES`

### Phase 3: Update UI to use schema directly
- Remove `ui_schema_generator.py` (no longer needed)
- Remove `ui_overrides.yaml` (data moved to dialect_schema.py)
- Simplify `ui_schema.py` to just read from DIALECT

### Phase 4: Add remaining operations
- Fill in all 34 transforms with full metadata
- Add window functions, CTEs, etc.

---

## Part 5: What Still Needs Manual Work

### After Auto-Generation, Human Must Add:

1. **Icons** (1 per operation) - ~34 operations = 34 emojis to pick
2. **Descriptions** (1 per operation) - ~34 short sentences
3. **Help text** (1-2 per parameter) - ~100 short hints
4. **Placeholders** (1 per text field) - ~50 example values
5. **Categories** (assign each operation) - ~34 category assignments
6. **Widget types** (1 per parameter) - ~100 widget decisions
7. **Dropdown labels** (format with symbols) - ~20 formatted strings

**Total manual effort**: ~400 small pieces of metadata to write

**BUT**: These are all in ONE file, easy to edit, and only need to be done once

---

## Part 6: Example Usage After Refactor

### Parser Usage (type-safe, no if/elif)
```python
from asql.dialect_schema import DIALECT

# Old way (BAD):
if op_token == TokenType.LT:
    return exp.LT(this=left, expression=right)
elif op_token == TokenType.GT:
    return exp.GT(this=left, expression=right)
# ... 10 more lines

# New way (GOOD):
op_spec = DIALECT.OPERATORS.COMPARISON[op_token]
return op_spec["expr_class"](this=left, expression=right)
```

### Visual Editor Usage (direct, no YAML)
```python
from asql.dialect_schema import DIALECT

# Old way (BAD):
# Load from YAML, merge with auto-generated, complex logic...

# New way (GOOD):
join_options = [
    {"value": name, "label": spec["label"]}
    for name, spec in vars(DIALECT.JOIN_TYPES).items()
    if not name.startswith('_')
]
```

### Documentation Generation (auto)
```python
from asql.dialect_schema import DIALECT

# Generate markdown docs
for name in dir(DIALECT.TRANSFORMS):
    transform = getattr(DIALECT.TRANSFORMS, name)
    if isinstance(transform, dict):
        print(f"## {transform['label']}")
        print(f"{transform['description']}")
        print(f"Icon: {transform['icon']}")
```

---

## Part 7: File Changes Summary

### Files to Create
- ✅ `asql/dialect_schema.py` (refactor to nested classes)

### Files to Modify
- `asql/dialect.py` - use DIALECT instead of if/elif
- `asql/ui_schema.py` - read from DIALECT instead of YAML

### Files to Delete (eventually)
- `asql/ui_schema_generator.py` - no longer needed
- `asql/ui_overrides.yaml` - data moved to dialect_schema.py

### Net Result
- **Before**: 4 files, scattered metadata, duplication
- **After**: 1 unified schema file, clean separation

---

## Part 8: Validation

### How to Verify It Works

1. **Parser still works**: All tests pass
2. **UI still works**: Visual editor renders correctly
3. **No duplication**: All metadata in ONE place
4. **Type safe**: IDE autocomplete everywhere
5. **Maintainable**: Add new operation = update ONE dict

### Success Criteria
- [ ] Parser uses DIALECT for all operator/join/transform lookups
- [ ] Visual editor reads directly from DIALECT
- [ ] No YAML files needed
- [ ] No if/elif chains for operators/joins
- [ ] IDE autocompletes all DIALECT.* references
- [ ] All existing tests pass
- [ ] Can add new operation by editing ONE dict entry

---

## Summary

**Current**: 4 files, dicts with magic strings, duplication
**Target**: 1 file, nested classes, single source of truth

**Auto-generated**: 60% (from existing parser metadata)
**Manual**: 40% (UI/docs specific - icons, help text, etc.)

**Strategy**: Include ALL metadata (parser + UI) in unified schema
**Benefit**: Parser, UI, docs, LSP all use same definitions

**Next Steps**:
1. Refactor `dialect_schema.py` to nested classes
2. Add UI fields to all entries
3. Update parser to use it
4. Update UI to read from it
5. Delete redundant files
