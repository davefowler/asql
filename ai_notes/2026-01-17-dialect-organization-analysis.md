# Dialect Configuration Organization Analysis

**Date:** 2026-01-17  
**Question:** Where should dialect configuration live - centralized schema, colocated in classes, or collected from classes?

## The Three Options

### Option A: Centralized Source of Truth (Current Partial Implementation)

```
dialect_schema.py (SOURCE)
├── DIALECT.TRANSFORMS.all_keywords() → frozenset
├── DIALECT.TIME_UNITS → frozenset
├── DIALECT.OPERATORS.COMPARISON → dict
└── ...

dialect.py (CONSUMER)
├── _TRANSFORM_KEYWORDS = DIALECT.TRANSFORMS.all_keywords()
├── TIME_UNITS = DIALECT.TIME_UNITS
└── uses DIALECT.OPERATORS in _build_comparison()
```

**Pros:**
- Single source of truth
- Easy to find all syntax definitions
- UI/docs/JSON schema have direct access

**Cons:**
- Definitions far from usage
- Parser must import schema
- Two-way dependency risk (schema defines, parser consumes)
- Awkward when parser needs TokenType mappings (schema doesn't know about TokenType)

---

### Option B: Colocated in Classes (SQLGlot Pattern)

```
dialect.py (SOURCE)
├── ASQLParser._TRANSFORM_KEYWORDS = frozenset{...}
├── ASQLParser.TIME_UNITS = frozenset{...}
├── ASQLParser.COMPARISON_OPS = {TokenType.GT: exp.GT, ...}
└── ASQLParser.TRANSFORM_PARSERS = {...}

dialect_schema.py (doesn't exist or minimal)
```

**Pros:**
- Follows SQLGlot's established pattern
- Definitions next to usage
- Clear ownership (parser owns parser config)
- No import dependencies

**Cons:**
- UI/docs must import parser to get metadata
- Information scattered across methods/classes
- Parser classes get cluttered with UI metadata (icons, descriptions)

---

### Option C: Collector Pattern (User's Suggestion) ⭐

```
dialect.py (SOURCE - parser-centric definitions)
├── ASQLParser._TRANSFORM_KEYWORDS = frozenset{...}
├── ASQLParser.TIME_UNITS = frozenset{...}
├── ASQLParser.TRANSFORM_PARSERS = {
│       "WHERE": {"parser": lambda..., "icon": "🔍", "description": "..."},
│       ...
│   }
└── ASQLParser.COMPARISON_OPS = {TokenType.GT: {"expr": exp.GT, "symbol": ">"}, ...}

dialect_schema.py (COLLECTOR - aggregates for UI/docs)
├── def get_all_transforms() → collects from ASQLParser.TRANSFORM_PARSERS
├── def get_all_operators() → collects from ASQLParser.COMPARISON_OPS
├── def get_json_schema() → builds schema from parser definitions
└── class DIALECT (convenience wrapper)
```

**Pros:**
- Definitions stay close to usage (SQLGlot pattern)
- Parser is authoritative (no two-way sync)
- Schema is derived, not duplicated
- UI metadata lives WITH the parser function it describes
- Easy to add new transforms (one place)

**Cons:**
- Parser classes include UI metadata (mixed concerns?)
- Schema module depends on parser (but that's natural direction)

---

### Option D: Parallel with Validation ⭐⭐

**Key Insight:** Keep code and metadata separate, but VALIDATE they stay in sync.

```
dialect.py (PARSER CODE ONLY - clean)
├── TRANSFORM_PARSERS = {
│       "WHERE": lambda self, query: ...,
│       "SELECT": lambda self, query: ...,
│   }
└── No UI metadata - just parser functions

dialect_schema.py (UI METADATA + VALIDATION)
├── TRANSFORM_METADATA = {
│       "WHERE": {"icon": "🔍", "keywords": [...], ...},
│       "SELECT": {"icon": "📋", "keywords": [...], ...},
│   }
├── _validate_sync()  # Errors if keys don't match!
└── DIALECT class merges both for consumers
```

**Implementation:**

```python
# dialect_schema.py
from asql.dialect import ASQLParser

TRANSFORM_METADATA = {
    "WHERE": {"keywords": ["WHERE", "FILTER"], "icon": "🔍", "label": "where"},
    "SELECT": {"keywords": ["SELECT", "PROJECT"], "icon": "📋", "label": "select"},
    # ...
}

def _validate_sync():
    parser_keys = set(ASQLParser.TRANSFORM_PARSERS.keys())
    schema_keys = set(TRANSFORM_METADATA.keys())
    
    if parser_keys != schema_keys:
        missing_metadata = parser_keys - schema_keys
        extra_metadata = schema_keys - parser_keys
        raise ValueError(
            f"Transform sync error!\n"
            f"  Missing metadata for: {missing_metadata}\n"
            f"  Extra metadata for: {extra_metadata}"
        )

_validate_sync()  # Runs at import time - fail fast!

# Convenience merged view
class DIALECT:
    @staticmethod
    def get_transforms():
        return {name: TRANSFORM_METADATA[name] for name in ASQLParser.TRANSFORM_PARSERS}
```

**Pros:**
- Clean separation (parser = code, schema = UI/docs)
- Parser stays pure - no UI clutter (follows SQLGlot pattern)
- **Fail-fast validation** catches drift immediately
- Schema can add extra metadata without polluting parser
- Each file has single responsibility
- Explicit contract between parser and schema

**Cons:**
- Two places to update (but you KNOW immediately if you forget)
- Import-time validation (minimal overhead)

**Why This Might Be Best:**
- Option C mixes concerns (UI metadata in parser code)
- Option D keeps them separate but ENFORCED to match
- The validation turns "silent drift" into "loud error"
- Adding a transform = add to parser + add metadata (both required)

---

## Analysis: What Goes Where?

### Things That MUST Live in Parser

| Item | Why |
|------|-----|
| `TRANSFORM_PARSERS` | Contains lambda functions |
| `_TOKEN_TRANSFORMS` | Maps TokenType → string (TokenType is parser concept) |
| `_JOIN_OPERATOR_TOKENS` | TokenType set for boundary detection |
| `FUNCTIONS` | Maps string → builder functions |

### Things That COULD Live Either Place

| Item | Option A (Schema) | Option B (Parser) | Option C (Parser + Collect) |
|------|-------------------|-------------------|----------------------------|
| `_TRANSFORM_KEYWORDS` | Derived from schema | Hardcoded frozenset | Derived from TRANSFORM_PARSERS keys |
| `TIME_UNITS` | Defined in schema | Defined in parser | Defined in parser, collected |
| Operator metadata | Separate from expr_class | Combined with expr_class | Combined, collected |
| Icons/descriptions | In schema only | In parser dicts | In parser dicts, collected |

---

## Option C: Detailed Design

### Step 1: Enrich Parser Definitions

```python
# dialect.py - Parser is source of truth
class ASQLParser(Parser):
    
    # Transform keywords derived from TRANSFORM_PARSERS
    @classmethod
    def _get_transform_keywords(cls) -> frozenset[str]:
        return frozenset(cls.TRANSFORM_PARSERS.keys())
    
    _TRANSFORM_KEYWORDS = property(lambda self: self._get_transform_keywords())
    
    # Or simpler: just use TRANSFORM_PARSERS.keys() directly
    
    TIME_UNITS = frozenset({
        'day', 'days', 'week', 'weeks', ...
    })
    
    # Enrich TRANSFORM_PARSERS with metadata
    TRANSFORM_PARSERS = {
        "WHERE": {
            "parse": lambda self, query: query.where(self._parse_assignment(), copy=False),
            "keywords": ["WHERE", "FILTER", "IF"],
            "icon": "🔍",
            "category": "filter",
            "description": "Filter rows by condition",
        },
        "SELECT": {
            "parse": lambda self, query: self._parse_asql_select(query),
            "keywords": ["SELECT", "PROJECT"],
            "icon": "📋",
            "category": "select",
            "description": "Choose columns to return",
        },
        # ...
    }
    
    # Comparison operators with metadata
    COMPARISON_OPS: dict[TokenType, dict] = {
        TokenType.GT: {"expr_class": exp.GT, "symbol": ">", "label": ">", "description": "Greater than"},
        TokenType.LT: {"expr_class": exp.LT, "symbol": "<", "label": "<", "description": "Less than"},
        # ...
    }
```

### Step 2: Schema Collects from Parser

```python
# dialect_schema.py - Collector/aggregator
from asql.dialect import ASQLParser

class DIALECT:
    """Collected dialect metadata for UI/docs/JSON schema."""
    
    @staticmethod
    def get_transforms() -> dict:
        """Collect transform metadata from parser."""
        return {
            name: {k: v for k, v in spec.items() if k != "parse"}
            for name, spec in ASQLParser.TRANSFORM_PARSERS.items()
        }
    
    @staticmethod
    def get_operators() -> dict:
        """Collect operator metadata from parser."""
        return {
            "comparison": {
                spec["symbol"]: {k: v for k, v in spec.items() if k != "expr_class"}
                for spec in ASQLParser.COMPARISON_OPS.values()
            },
            # ...
        }
    
    @staticmethod
    def get_transform_keywords() -> frozenset[str]:
        """Get all keywords that trigger transforms."""
        keywords = set()
        for spec in ASQLParser.TRANSFORM_PARSERS.values():
            keywords.update(spec.get("keywords", []))
        return frozenset(keywords)


def generate_json_schema() -> dict:
    """Generate JSON schema from parser definitions."""
    return {
        "transforms": DIALECT.get_transforms(),
        "operators": DIALECT.get_operators(),
        # ...
    }
```

### Step 3: Parser Uses Its Own Definitions

```python
# dialect.py - Parser uses its own enriched dicts
class ASQLParser(Parser):
    
    def _build_comparison(self, left, op_token, right):
        """Build comparison using COMPARISON_OPS dict."""
        if op_token in self.COMPARISON_OPS:
            expr_class = self.COMPARISON_OPS[op_token]["expr_class"]
            return expr_class(this=left, expression=right)
        return exp.EQ(this=left, expression=right)
    
    def _match_transform(self):
        """Match transforms using TRANSFORM_PARSERS."""
        for name, spec in self.TRANSFORM_PARSERS.items():
            for keyword in spec.get("keywords", [name]):
                if self._match_text_seq(keyword):
                    return name
        return None
```

---

## Comparison Matrix

| Criterion | Option A (Central) | Option B (Colocated) | Option C (Collect) | Option D (Parallel+Validate) |
|-----------|-------------------|---------------------|-------------------|------------------------------|
| Single source of truth | ✅ Schema | ✅ Parser | ✅ Parser | ⚠️ Split (validated) |
| Definitions near usage | ❌ Far | ✅ Close | ✅ Close | ✅ Close |
| Follows SQLGlot pattern | ❌ No | ✅ Yes | ⚠️ Modified | ✅ Yes |
| UI can access metadata | ✅ Direct | ⚠️ Import parser | ✅ Via collector | ✅ Via merger |
| No duplication | ⚠️ Risk of drift | ✅ No | ✅ No | ⚠️ Intentional (validated) |
| Parser stays clean | ❌ Imports schema | ✅ Self-contained | ❌ Has UI metadata | ✅ Pure code |
| Catches drift | ❌ Silent | N/A | N/A | ✅ Fails fast |
| Add new transform | 2 places (silent) | 1 place | 1 place | 2 places (error if forget) |

---

## Recommendation

**Option D (Parallel with Validation)** might be best because:

1. **Clean separation** - Parser has code, schema has metadata (single responsibility)
2. **Parser stays pure** - No UI clutter, follows SQLGlot pattern exactly
3. **Fail-fast validation** - Can't accidentally drift, error on import
4. **Explicit contract** - Parser and schema MUST agree on keys
5. **Natural ownership** - Parser owns "what exists", schema owns "how to display"
6. **Easy to review** - See all UI metadata in one file, all parser code in another

**Trade-off acknowledged:** You update two places, but the validation ensures you can't forget. This is like type checking - it's extra work that prevents bugs.

**vs Option C:** Option C keeps metadata WITH the parser function. This is convenient but mixes concerns. Option D keeps them separate but ENFORCES the connection.

### Migration Path (Option D)

1. Keep `TRANSFORM_PARSERS` as pure functions (remove any metadata if added)
2. Create `TRANSFORM_METADATA` dict in schema with icons/labels/keywords
3. Add `_validate_sync()` function that compares keys
4. Create merged `DIALECT.get_transforms()` for consumers
5. `_TRANSFORM_KEYWORDS` derived from `TRANSFORM_METADATA.keywords`

### What Changes

**Before (Current - Option A partial):**
```
dialect_schema.py defines metadata → dialect.py imports and uses
(but TRANSFORM_PARSERS in dialect.py has authoritative list)
```

**After (Option D):**
```
dialect.py has TRANSFORM_PARSERS (code only)
dialect_schema.py has TRANSFORM_METADATA (UI only)
_validate_sync() ensures keys match at import time
DIALECT class merges both for UI/docs consumers
```

### Example Workflow with Option D

**Adding a new transform:**
```python
# 1. Add to dialect.py
TRANSFORM_PARSERS = {
    ...
    "NEW_THING": lambda self, query: self._parse_new_thing(query),
}

# 2. Run tests or import → IMMEDIATE ERROR:
# ValueError: Missing metadata for: {'NEW_THING'}

# 3. Add to dialect_schema.py
TRANSFORM_METADATA = {
    ...
    "NEW_THING": {"icon": "✨", "label": "new thing", "keywords": ["NEW_THING"]},
}

# 4. Now validation passes ✅
```

---

## Questions to Consider

1. **Is the two-places update acceptable?** - Option D requires updating both parser and schema. But the validation makes this explicit and safe. It's like adding a function and its type signature - both are required.

2. **What about non-parser syntax?** - Things like join symbols (`&`, `&?`) live in tokenizer. Could use same pattern: `TOKENIZER_SYMBOLS` in tokenizer, `SYMBOL_METADATA` in schema, validated.

3. **Performance?** - Validation runs once at import time. Negligible. Merged views could be cached as module-level constants.

4. **Backwards compatibility?** - Current code uses `DIALECT.TRANSFORMS.WHERE["keywords"]`. Would need to update to `DIALECT.get_transforms()["WHERE"]["keywords"]` or keep compatibility wrapper.

5. **Could validation be stricter?** - Could also validate that metadata has required fields (icon, label, description). Schema-as-contract.

## Summary

| If you want... | Choose... |
|----------------|-----------|
| UI metadata with parser code | Option C |
| Clean separation + enforced sync | Option D |
| SQLGlot purity (no schema) | Option B |
| Current approach (schema defines) | Option A |

**Option D** gives you the benefits of separation (clean parser, focused schema) with the safety of validation (can't drift silently). The trade-off is explicit: two updates required, but you can't forget.
