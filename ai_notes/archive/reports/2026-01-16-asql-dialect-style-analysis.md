# ASQL Dialect Style Analysis: Deviations from SQLGlot Patterns

**Date:** 2026-01-16 (Updated: 2026-01-17)  
**Purpose:** Identify coding style and architectural differences between ASQL's dialect implementation and SQLGlot's canonical patterns.

## 🚨 CRITICAL ISSUE: `compile()` vs `transpile()` Divergence

**ASQL is NOT a proper SQLGlot dialect!** It has two different compilation paths:

1. **`sqlglot.transpile(query, read='asql', write='postgres')`** - Uses ONLY the Parser + Generator
2. **`asql.compile(query, dialect='postgres')`** - Uses Parser + **13 additional AST transforms** + Generator

These produce **DIFFERENT SQL** for many queries! See `ai_notes/2026-01-17-code-quality-review.md` for full analysis.

| Feature | `transpile()` | `compile()` |
|---------|---------------|-------------|
| FK shorthand (`on user_id`) | ❌ Incomplete | ✅ Expands |
| Underscore shorthand (`days_since_col`) | ❌ Literal | ✅ DateDiff |
| Auto-spine gap-filling | ❌ Not applied | ✅ Applied |
| Column operators | ❌ Not expanded | ✅ Expanded |

**This is the biggest issue in the codebase.** Users expect `transpile()` to work.

---

## Status

- ✅ **`reverse_compiler.py` DELETED** - was a wrapper, now uses `transpile(..., write='asql')`
- ✅ **Style guide added** to `.cursorrules` - future code follows SQLGlot patterns
- ✅ **Unified DIALECT schema created** in `dialect_schema.py` - nested classes for all syntax
- ✅ **Key `elif` chains refactored** - now use DIALECT schema lookups
- ✅ **UI files consolidated** - deleted `ui_overrides.yaml` and `ui_schema_generator.py`
- ✅ **Reusable builders added** - `build_window_offset()` for PRIOR/NEXT
- ⚠️ **`compile()` vs `transpile()` divergence** - NOT FIXED, needs major refactor

## Refactoring Completed (2026-01-17)

The following were refactored to use the new `DIALECT` schema:

| Method | Before | After |
|--------|--------|-------|
| `_build_comparison` | elif chain for 6 operators | `DIALECT.OPERATORS.COMPARISON` lookup |
| `_parse_comparison` | elif chain for 7 string operators | `DIALECT.OPERATORS.STRING` loop |
| `_parse_asql_per` | elif chain for 5 window operations | `DIALECT.PER_OPERATIONS` + helper |
| `_parse_asql_cohort` | elif chain for 3 granularities | `DIALECT.COHORT.GRANULARITIES` loop |
| `FUNCTIONS["PRIOR/NEXT"]` | inline lambdas | `build_window_offset()` factory |

**Files deleted:**
- `asql/ui_overrides.yaml` - merged into `dialect_schema.py`
- `asql/ui_schema_generator.py` - replaced by direct schema access

## Executive Summary

The ASQL dialect implementation deviates from SQLGlot's idiomatic patterns in several ways. Some deviations are **valid stylistic improvements**, while others should be fixed.

### ✅ Valid ASQL Stylistic Choice (Keep)

**Unified DIALECT schema with nested classes:** SQLGlot uses scattered module-level dicts. ASQL organizes ALL syntax definitions in `dialect_schema.py` using **nested classes** (`DIALECT.OPERATORS.COMPARISON`, `DIALECT.JOIN_TYPES.INNER`, etc.). This provides:
- Better organization (all config in one file, hierarchical)
- Type safety (IDE autocomplete, type checking)
- Single source of truth (parser, UI, docs use same definitions)
- Easier extensibility (clear where to add new entries)

**This is preferable to SQLGlot's approach and should be maintained.**

### ⏳ Remaining Issues (Lower Priority)

1. **Some inline parsing logic** - could be further decomposed
2. **Some large methods** - could be split into smaller helpers
3. **Some remaining `elif` chains** - for ASQL-specific complex parsing (acceptable)

---

## Issue 1: Procedural `elif` Chains vs Declarative Dicts

### SQLGlot Pattern (GOOD)

SQLGlot dialects define operators, functions, and parsers as **class-level dictionaries**. This is declarative, reusable, and easy to extend:

```python
# From clickhouse.py - clean dict-based operator mapping
COLUMN_OPERATORS = parser.Parser.COLUMN_OPERATORS.copy()
COLUMN_OPERATORS.pop(TokenType.PLACEHOLDER)

# From bigquery.py - clean function registry
FUNCTIONS = {
    **parser.Parser.FUNCTIONS,
    "DATE_ADD": build_date_delta_with_interval(exp.DateAdd),
    "DATE_SUB": build_date_delta_with_interval(exp.DateSub),
    "SPLIT": lambda args: exp.Split(
        this=seq_get(args, 0),
        expression=seq_get(args, 1) or exp.Literal.string(","),
    ),
    # ... more entries
}

# From parser.py - canonical operator dicts
CONJUNCTION = {TokenType.AND: exp.And}
DISJUNCTION = {TokenType.OR: exp.Or}
EQUALITY = {TokenType.EQ: exp.EQ, TokenType.NEQ: exp.NEQ, TokenType.NULLSAFE_EQ: exp.NullSafeEQ}
COMPARISON = {TokenType.GT: exp.GT, TokenType.GTE: exp.GTE, TokenType.LT: exp.LT, TokenType.LTE: exp.LTE}
BITWISE = {TokenType.AMP: exp.BitwiseAnd, TokenType.CARET: exp.BitwiseXor, TokenType.PIPE: exp.BitwiseOr}
```

### ASQL Pattern (BAD)

ASQL uses procedural `elif` chains for logic that should be declarative:

```python
# From dialect.py lines 934-951 - procedural comparison building
def _build_comparison(
    self, left: exp.Expression, op_token: TokenType, right: exp.Expression
) -> exp.Expression:
    """Build a comparison expression from operator token."""
    if op_token == TokenType.LT:
        return exp.LT(this=left, expression=right)
    elif op_token == TokenType.GT:
        return exp.GT(this=left, expression=right)
    elif op_token == TokenType.LTE:
        return exp.LTE(this=left, expression=right)
    elif op_token == TokenType.GTE:
        return exp.GTE(this=left, expression=right)
    elif op_token == TokenType.EQ:
        return exp.EQ(this=left, expression=right)
    elif op_token == TokenType.NEQ:
        return exp.NEQ(this=left, expression=right)
    else:
        return exp.EQ(this=left, expression=right)
```

**Should be:**

```python
# Declarative dict (reuse Parser.COMPARISON or define ASQL-specific)
COMPARISON_OPS = {
    TokenType.LT: exp.LT,
    TokenType.GT: exp.GT,
    TokenType.LTE: exp.LTE,
    TokenType.GTE: exp.GTE,
    TokenType.EQ: exp.EQ,
    TokenType.NEQ: exp.NEQ,
}

def _build_comparison(self, left, op_token, right):
    op_class = self.COMPARISON_OPS.get(op_token, exp.EQ)
    return op_class(this=left, expression=right)
```

### Other `elif` Chain Violations

1. **`_parse_when` method (lines 776-891)** - 115 lines of nested `elif` chains for parsing `when` expressions
2. **`_parse_asql_per` method (lines 2038-2113)** - Multiple `elif` chains for `first/last/number/rank/dense rank`
3. **`_parse_comparison` method (lines 2534-2604)** - String matching operators (`contains`, `starts with`, etc.)

---

## Issue 2: Inline Parsing Logic vs Reusable Parser Methods

### SQLGlot Pattern (GOOD)

SQLGlot uses small, focused helper methods that are composed together:

```python
# From parser.py - composable parsing
def _parse_tokens(
    self, parse_method: t.Callable, expressions: t.Dict[TokenType, t.Type[exp.Expression]]
) -> t.Optional[exp.Expression]:
    this = parse_method()
    while self._match_set(expressions):
        this = self.expression(expressions[self._prev.token_type], this=this, expression=parse_method())
    return this

# Usage - clean and reusable
def _parse_conjunction(self) -> t.Optional[exp.Expression]:
    return self._parse_tokens(self._parse_equality, self.CONJUNCTION)
```

### ASQL Pattern (BAD)

ASQL has large monolithic methods with inline parsing logic:

```python
# From dialect.py lines 1859-2025 - 166 lines of inline parsing
def _parse_on_condition_until_join_op(self) -> t.Optional[exp.Expression]:
    """Parse ON condition, stopping at ASQL join operators."""
    # Check if the next token after the current one is a join operator
    if self._is_at_join_op_or_end(offset=1):
        return self._parse_column()
    
    has_join_op = self._scan_for_join_op_in_condition()
    
    if not has_join_op:
        return self._parse_assignment()
    
    return self._parse_on_expr_with_join_stop()

def _parse_on_expr_with_join_stop(self) -> t.Optional[exp.Expression]:
    """Parse ON expression, stopping at join operators."""
    # ... 50+ lines of manual token manipulation
    left = self._parse_term_for_join()
    while self._curr and self._index < end_index:
        if self._match(TokenType.EQ):
            right = self._parse_term_for_join()
            left = exp.EQ(this=left, expression=right)
        elif self._match(TokenType.AND) or self._match(TokenType.DAMP):
            # ... more inline logic
```

**Should be:** Use SQLGlot's existing `_parse_assignment()` with proper boundary detection, or define a clean `STOP_TOKENS` set.

---

## Issue 3: Missing Use of SQLGlot Expression Builders

### SQLGlot Pattern (GOOD)

SQLGlot provides module-level builder functions that are reused across dialects:

```python
# From parser.py - reusable builders
def build_date_delta(
    expr_type: t.Type[E], default_unit: t.Optional[str] = None, supports_timezone: bool = False
) -> t.Callable[[t.List], E]:
    def _builder(args: t.List) -> E:
        return expr_type(
            this=seq_get(args, 0),
            expression=seq_get(args, 1),
            unit=seq_get(args, 2) or (exp.var(default_unit) if default_unit else None),
            zone=seq_get(args, 3) if supports_timezone else None,
        )
    return _builder

# Usage in dialects
FUNCTIONS = {
    "DATE_ADD": build_date_delta(exp.DateAdd, default_unit=None),
    "DATE_DIFF": build_date_delta(exp.DateDiff, default_unit=None, supports_timezone=True),
}
```

### ASQL Pattern (BAD)

ASQL defines inline lambdas and methods instead of reusable builders:

```python
# From dialect.py - inline instead of builder
FUNCTIONS = {
    **Parser.FUNCTIONS,
    "TOTAL": exp.Sum.from_arg_list,
    "AVERAGE": exp.Avg.from_arg_list,
    "PRIOR": lambda args: exp.Lag(this=seq_get(args, 0), offset=seq_get(args, 1) or exp.Literal.number(1)),
    "NEXT": lambda args: exp.Lead(this=seq_get(args, 0), offset=seq_get(args, 1) or exp.Literal.number(1)),
}
```

**Should be:** Define reusable builders in `asql/functions.py`:

```python
def build_window_offset(expr_type, default_offset=1):
    def _builder(args):
        return expr_type(
            this=seq_get(args, 0),
            offset=seq_get(args, 1) or exp.Literal.number(default_offset)
        )
    return _builder

# Usage
FUNCTIONS = {
    "PRIOR": build_window_offset(exp.Lag),
    "NEXT": build_window_offset(exp.Lead),
}
```

---

## Issue 4: Inconsistent Class-Level Configuration

### SQLGlot Pattern (GOOD)

SQLGlot dialects use class-level constants for configuration:

```python
# From clickhouse.py
class ClickHouse(Dialect):
    INDEX_OFFSET = 1
    NORMALIZE_FUNCTIONS: bool | str = False
    NULL_ORDERING = "nulls_are_last"
    SUPPORTS_USER_DEFINED_TYPES = False
    SAFE_DIVISION = True
    LOG_BASE_FIRST: t.Optional[bool] = None
    FORCE_EARLY_ALIAS_REF_EXPANSION = True
    PRESERVE_ORIGINAL_NAMES = True
    NUMBERS_CAN_BE_UNDERSCORE_SEPARATED = True
    IDENTIFIERS_CAN_START_WITH_DIGIT = True
    HEX_STRING_IS_INTEGER_TYPE = True
    NORMALIZATION_STRATEGY = NormalizationStrategy.CASE_SENSITIVE
```

### ASQL Pattern (INCONSISTENT)

ASQL has some class-level config but mixes it with runtime logic:

```python
# From dialect.py - some config at class level
class ASQL(Dialect):
    DPIPE_IS_STRING_CONCAT = True
    NORMALIZE_FUNCTIONS: bool | str = False
    
    # But missing many standard configs that should be explicit:
    # - INDEX_OFFSET
    # - NULL_ORDERING
    # - NORMALIZATION_STRATEGY
    # - etc.
```

---

## Issue 5: Monolithic Methods vs Composable Helpers

### SQLGlot Pattern (GOOD)

SQLGlot uses small, focused methods that compose:

```python
# From prql.py - clean, focused methods
def _parse_query(self) -> t.Optional[exp.Query]:
    from_ = self._parse_from()
    if not from_:
        return None
    
    query = exp.select("*").from_(from_, copy=False)
    
    while self._match_texts(self.TRANSFORM_PARSERS):
        query = self.TRANSFORM_PARSERS[self._prev.text.upper()](self, query)
    
    return query

def _parse_take(self, query: exp.Query) -> t.Optional[exp.Query]:
    num = self._parse_number()
    return query.limit(num) if num else None
```

### ASQL Pattern (BAD)

ASQL has many large methods (100+ lines):

| Method | Lines | Issue |
|--------|-------|-------|
| `_parse_when` | 115 | Should be split into `_parse_simple_case`, `_parse_searched_case` |
| `_parse_list_comprehension` | 100 | Should use helper for token scanning |
| `_parse_asql_per` | 75 | Should use dict-based dispatch |
| `_parse_asql_cohort` | 95 | Should use builder pattern |
| `_parse_bracket` | 85 | Should delegate to slice-specific helper |

---

## Issue 6: Token Scanning Instead of Parser Primitives

### SQLGlot Pattern (GOOD)

SQLGlot uses parser primitives like `_match`, `_match_set`, `_match_texts`:

```python
# From prql.py - clean token matching
def _parse_ordered(self, parse_method=None):
    asc = self._match(TokenType.PLUS)
    desc = self._match(TokenType.DASH) or (asc and False)
    term = super()._parse_ordered(parse_method=parse_method)
    if term and desc:
        term.set("desc", True)
    return term
```

### ASQL Pattern (BAD)

ASQL manually scans tokens in several places:

```python
# From dialect.py lines 1039-1071 - manual token scanning
def _is_list_comprehension(self) -> bool:
    """Check if we're at the start of a list comprehension."""
    if not self._match(TokenType.L_BRACKET, advance=False):
        return False
    
    bracket_depth = 0
    found_for = False
    found_in = False
    
    i = self._index
    while i < len(self._tokens):
        tok = self._tokens[i]
        
        if tok.token_type == TokenType.L_BRACKET:
            bracket_depth += 1
        elif tok.token_type == TokenType.R_BRACKET:
            bracket_depth -= 1
            if bracket_depth == 0:
                break
        elif bracket_depth == 1:
            if tok.token_type == TokenType.FOR or (tok.token_type == TokenType.VAR and tok.text.upper() == "FOR"):
                found_for = True
            elif found_for and (tok.token_type == TokenType.IN or ...):
                found_in = True
                break
        i += 1
    
    return found_for and found_in
```

**Should be:** Use `_try_parse` with a lookahead pattern, or define a `LOOKAHEAD_PATTERNS` dict.

---

## Issue 7: Missing Type Annotations

### SQLGlot Pattern (GOOD)

SQLGlot has comprehensive type annotations:

```python
# From parser.py
def _parse_tokens(
    self, 
    parse_method: t.Callable, 
    expressions: t.Dict[TokenType, t.Type[exp.Expression]]
) -> t.Optional[exp.Expression]:
```

### ASQL Pattern (INCONSISTENT)

Many ASQL methods lack type annotations:

```python
# From dialect.py - missing return type
def _looks_like_aggregate_block_at(self, paren_idx: int) -> bool:  # OK
def _parse_group_by_term(self):  # Missing return type
def _parse_on_expr_with_join_stop(self):  # Missing return type
```

---

## Issue 8: Hardcoded Strings Instead of Constants

### SQLGlot Pattern (GOOD)

SQLGlot uses constants and enums:

```python
# From clickhouse.py
TIMESTAMP_TRUNC_UNITS = {
    "MICROSECOND", "MILLISECOND", "SECOND", "MINUTE", 
    "HOUR", "DAY", "MONTH", "QUARTER", "YEAR",
}
```

### ASQL Pattern (BAD)

ASQL has hardcoded strings scattered throughout:

```python
# From dialect.py - hardcoded strings
sql_keywords = {
    'as', 'from', 'where', 'group', 'by', 'order', 'limit', 'having',
    'select', 'join', 'on', 'and', 'or', 'not', 'in', 'is', 'null',
    'true', 'false', 'union', 'except', 'intersect', 'with', 'stash'
}

# Should be a class constant:
SQL_KEYWORDS = frozenset({...})
```

---

## Remaining `elif` Chains to Fix (as of 2026-01-16)

These `elif` chains should be converted to **typed class-level attributes** on `ASQLParser`.

> **ASQL Style Note:** Unlike SQLGlot's scattered module-level dicts, ASQL organizes configuration as typed class attributes (e.g., `_TOKEN_TRANSFORMS: dict[TokenType, str]`). This provides better organization and type safety. **Add new dispatch tables to `ASQLParser` as class attributes.**

### High Priority (Easy Wins)

| Method | Lines | Current | Add to `ASQLParser` |
|--------|-------|---------|---------------------|
| `_build_comparison` | 938-951 | 6 elifs for operators | `COMPARISON_OPS: dict[TokenType, t.Type[exp.Expression]] = {...}` |
| `_parse_asql_per` | 2065-2110 | 5 elifs for first/last/number/rank/dense | `PER_OPERATIONS: dict[str, t.Callable] = {...}` |
| `_parse_comparison` | 2572-2588 | 6 elifs for string ops | `STRING_MATCH_OPS: dict[str, tuple[str, str, bool]] = {...}` |
| `_parse_asql_cohort` | 2289-2294 | 3 elifs for granularity | `COHORT_GRANULARITIES: dict[str, str] = {...}` |

### Medium Priority (More Complex)

| Method | Lines | Add to `ASQLParser` |
|--------|-------|---------------------|
| `_parse_when` | 820-853, 909-917 | Complex - may need `WHEN_BRANCH_PARSERS` dict |
| `_parse_pivot` | 479-495 | `PIVOT_PARSERS: dict[TokenType, t.Callable]` |
| `parse_set_operation` | 247-260 | `SET_OPERATION_TYPES: dict[TokenType, t.Type[exp.SetOperation]]` |

### Acceptable `elif` Usage

Some `elif` patterns are acceptable when they involve:
- Bracket depth tracking (`L_PAREN`/`R_PAREN` pairs)
- Sequential token consumption with side effects
- Complex conditional logic that doesn't map to a simple lookup

---

## Recommendations

### Priority 1 (High Impact, Do First)

1. **Convert `_build_comparison` to use dict lookup** - 5 min fix
2. **Extract `_parse_when` into smaller methods** - 30 min refactor
3. **Define `ASQL_OPERATORS` dict for join operators** - 15 min fix
4. **Move hardcoded keyword sets to class constants** - 15 min fix

### Priority 2 (Medium Impact)

5. **Create reusable builders in `functions.py`** - 1 hour refactor
6. **Add missing type annotations** - 30 min
7. **Split large methods (>50 lines)** - 2 hours
8. **Use `_try_parse` instead of manual token scanning** - 1 hour

### Priority 3 (Lower Impact, Nice to Have)

9. **Add comprehensive class-level dialect config** - 30 min
10. **Document ASQL-specific patterns in ARCHITECTURE.md** - 1 hour

---

## Files Requiring Changes

| File | Changes Needed |
|------|----------------|
| `asql/dialect.py` | Major refactoring - convert elif chains, split methods |
| `asql/functions.py` | Add reusable builder functions |
| `docs/architecture.md` | Document ASQL-specific patterns |

---

## Conclusion

The ASQL dialect is functional but has **one critical architectural flaw** and several style issues:

### Critical Issue

**`compile()` vs `transpile()` divergence** - ASQL has 13 AST transforms that are NOT part of the dialect. This means `sqlglot.transpile()` produces different (often incorrect) SQL compared to `asql.compile()`. This violates the SQLGlot contract where dialects should be self-contained.

**Fix options:**
1. Move transforms into the dialect (Parser or Generator TRANSFORMS)
2. Document that `compile()` is required (non-standard)
3. Monkey-patch `transpile()` (fragile)

### Style Issues

1. **Procedural code where declarative dicts should be used**
2. **Large monolithic methods instead of composable helpers**
3. **Manual token scanning instead of parser primitives**
4. **Missing reusable builders and type annotations**

### Other Non-Standard Patterns

1. **`json_schema.py`** duplicates Generator logic (should use ASQLGenerator)
2. **`StyleConfig`** options not passed to Generator (can't customize output style via transpile)
3. **`register_asql_dialect()`** must be called explicitly (fixed in `__init__.py`)

Fixing these issues will make the codebase more maintainable, easier for SQLGlot-familiar developers to understand, and more aligned with upstream patterns for future updates.
