# Underscore/Space Interchangeability Principle

Implementation plan for ASQL's core syntactic flexibility feature.

**Last Updated**: December 2025  
**Status**: Planning  
**Priority**: High (foundational for other features)

---

## 1. The Principle

In function and keyword contexts, **underscores and spaces are interchangeable**:

```asql
-- All equivalent:
day_of_week(created_at)      -- Explicit function call
day_of_week_created_at       -- Shorthand pattern  
day of week created_at       -- Natural language
```

**The boundary**: Column names are literal and must match exactly.
- ✅ `sum_revenue` → interprets as `sum(revenue)` (function pattern)
- ✅ `created_at` → matches column `created_at`
- ❌ `created at` → does NOT match column `created_at`

---

## 2. Where This Principle Applies

### 2.1 Function Names

Multi-word function names can use underscores or spaces:

```asql
-- These are equivalent:
day_of_week(col)
day of week(col)

date_trunc(col, "month")
date trunc(col, "month")

row_number() over (...)
row number() over (...)
```

### 2.2 Function Shorthand (Pattern Interpretation)

The `{function}_{column}` pattern works with underscores or spaces:

```asql
-- All equivalent, all produce column sum_amount:
sum(amount)
sum_amount
sum amount
```

### 2.3 Multi-Word Functions + Shorthand

Combines both principles:

```asql
-- All equivalent, produce column day_of_week_created_at:
day_of_week(created_at)
day_of_week_created_at
day of week created_at
day of week(created_at)
day_of_week created_at
```

### 2.4 Keywords (Future)

Some keywords could also allow this flexibility:

```asql
-- Potentially equivalent:
group_by region (...)
group by region (...)

order_by name
order by name

left_join users on ...
left join users on ...
```

**Note**: Standard SQL keywords (`group by`, `order by`) should probably stay as-is for familiarity. This flexibility is most valuable for function names.

---

## 3. What This Does NOT Apply To

### 3.1 Column Names

Column names are always literal:

```asql
-- If table has column "created_at":
select created_at        -- ✅ Matches
select created at        -- ❌ Does NOT match (would be parse error or two tokens)

-- If table has column "total amount" (quoted):
select "total amount"    -- ✅ Matches (requires quotes)
select total_amount      -- ❌ Different column
```

### 3.2 String Literals

Strings are always literal:

```asql
where status == "pending_review"    -- ✅ Exact string
where status == "pending review"    -- Different string, no conversion
```

### 3.3 Table Names

Table names are literal:

```asql
from user_accounts       -- ✅ Matches table user_accounts
from user accounts       -- ❌ Parse error (two tokens)
```

---

## 4. Implementation Strategy

### 4.1 Architecture Overview

```
                    ┌─────────────────────┐
                    │   Raw ASQL Input    │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │      Tokenizer      │
                    │  (space-aware)      │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Function Registry  │
                    │  (pattern matcher)  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │       Parser        │
                    │  (context-aware)    │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │    SQLGlot AST      │
                    └─────────────────────┘
```

### 4.2 Key Components

#### A. Function Registry

A registry of known functions that can be invoked with underscore/space flexibility:

```python
FUNCTION_REGISTRY = {
    # Single-word functions (no underscore/space conversion needed)
    'sum', 'avg', 'max', 'min', 'count',
    'year', 'month', 'week', 'day', 'hour', 'quarter',
    'upper', 'lower', 'length', 'trim',
    'abs', 'round', 'floor', 'ceil',
    
    # Multi-word functions (underscore/space interchangeable)
    'day_of_week', 'day_of_month', 'day_of_year',
    'week_of_year', 'month_of_year', 'quarter_of_year',
    'date_trunc', 'date_add', 'date_diff',
    'row_number', 'dense_rank',
    'string_agg', 'array_agg',
    # ... etc
}

# Aliases - natural language alternatives that map to SQL functions
FUNCTION_ALIASES = {
    'total': 'sum',      # total_revenue → sum(revenue)
    'average': 'avg',    # average_price → avg(price)
    'maximum': 'max',    # maximum_amount → max(amount)
    'minimum': 'min',    # minimum_amount → min(amount)
}

# Extended patterns - special compound patterns
EXTENDED_PATTERNS = {
    # {unit}_since_{column} → {unit}(now() - column)
    'days_since': lambda col: f'days(now() - {col})',
    'weeks_since': lambda col: f'weeks(now() - {col})',
    'months_since': lambda col: f'months(now() - {col})',
    'years_since': lambda col: f'years(now() - {col})',
    'hours_since': lambda col: f'hours(now() - {col})',
    'minutes_since': lambda col: f'minutes(now() - {col})',
    'seconds_since': lambda col: f'seconds(now() - {col})',
}

# Normalized form (underscores) for matching
def normalize_function_name(name: str) -> str:
    """Convert 'day of week' to 'day_of_week'"""
    return name.replace(' ', '_').lower()
```

#### B. Pattern Matcher

Identifies function patterns in identifiers:

```python
def parse_function_pattern(identifier: str) -> Optional[Tuple[str, str]]:
    """
    Parse 'sum_revenue' or 'day_of_week_created_at' into (function, column).
    Returns None if no pattern matches.
    """
    normalized = normalize_function_name(identifier)
    
    # Try longest function names first
    for func in sorted(FUNCTION_REGISTRY, key=len, reverse=True):
        if normalized.startswith(func + '_'):
            column = normalized[len(func) + 1:]
            return (func, column)
    
    return None
```

#### C. Context-Aware Parser

The parser needs to know when to apply this principle:

```python
class ParserContext(Enum):
    SELECT_EXPRESSION = "select"      # Apply function patterns
    GROUP_BY = "group_by"             # Apply function patterns
    WHERE_CLAUSE = "where"            # Apply function patterns
    COLUMN_REFERENCE = "column"       # Literal only
    TABLE_NAME = "table"              # Literal only
    STRING_LITERAL = "string"         # Literal only
```

### 4.3 Parsing Strategy

**Option A: Eager Tokenization**

Tokenize first, then identify function patterns:

```
Input: "day of week created_at"
Tokens: ["day", "of", "week", "created_at"]
→ Recognize "day of week" as function
→ Result: Function("day_of_week", Column("created_at"))
```

**Option B: Lookahead Parsing**

Parse with lookahead to detect multi-word functions:

```
At token "day":
  - Lookahead: "of" "week" 
  - Check registry: "day_of_week" is a function
  - Consume all three tokens as function name
  - Parse next token as argument
```

**Option C: Two-Pass**

First pass: identify all potential function names
Second pass: parse with knowledge of function boundaries

**Recommendation**: Option B (Lookahead) - most flexible and handles edge cases well.

---

## 5. Implementation Phases

### Phase 1: Foundation (Do First)

1. **Create Function Registry**
   - Define initial set of recognized functions
   - Include single-word and multi-word functions
   - Make it extensible for future additions

2. **Implement normalize_function_name()**
   - Convert spaces to underscores
   - Handle case normalization

3. **Implement parse_function_pattern()**
   - Match `{function}_{column}` patterns
   - Return (function, column) tuples

4. **Update parser to use registry**
   - Check if identifier is in registry before treating as column
   - Apply pattern matching in select/group by contexts

### Phase 2: Function Shorthand

5. **Shorthand in SELECT**
   ```asql
   select sum_amount, avg_price
   -- Interpreted as sum(amount), avg(price)
   ```

6. **Shorthand in GROUP BY**
   ```asql
   group by month_created_at (...)
   -- Interpreted as group by month(created_at)
   ```

7. **Auto-generated column names**
   ```asql
   select sum(amount)
   -- Auto-alias: sum_amount
   ```

### Phase 3: Space Syntax

8. **Space syntax for single-word functions**
   ```asql
   select sum amount, avg price
   ```

9. **Space syntax for multi-word functions**
   ```asql
   select day of week created_at
   group by month of year signup_date
   ```

### Phase 4: Date Functions (Depends on This)

10. **Date part extraction**
    ```asql
    day of week created_at
    week of year signup_date
    ```

11. **Date arithmetic**
    ```asql
    created_at + 7 days
    30 days ago
    ```

---

## 6. Edge Cases to Handle

### 6.1 Ambiguous Patterns

What if `sum_revenue` is an actual column AND a pattern?

```asql
-- Table has actual column "sum_revenue"
select sum_revenue  -- Column or pattern?
```

**Resolution**: Schema takes precedence
1. If schema available, check if column exists
2. If column exists, use it
3. If not, interpret as pattern

### 6.2 Multi-Word Column Names

```asql
-- Table has column "day_of_week" 
select day_of_week  -- Column or pattern looking for column "week"?
```

**Resolution**: Same as above - actual columns win.

### 6.3 Nested Patterns

```asql
sum_avg_amount  -- sum(avg_amount) or sum_avg(amount)?
```

**Resolution**: Greedy function matching from start
- `sum` matches, so interpret as `sum(avg_amount)`
- If `avg_amount` is not a column, recursively interpret as `sum(avg(amount))`

### 6.4 Function That Looks Like Column

```asql
select count  -- Function count() or column "count"?
```

**Resolution**: 
- Bare `count` without `()` or `_column` → treat as column
- `count()` or `count_users` → function

---

## 7. Testing Strategy

### 7.1 Unit Tests

```python
def test_normalize_function_name():
    assert normalize_function_name("day of week") == "day_of_week"
    assert normalize_function_name("DAY_OF_WEEK") == "day_of_week"
    assert normalize_function_name("dayOfWeek") == "dayofweek"

def test_parse_function_pattern():
    assert parse_function_pattern("sum_amount") == ("sum", "amount")
    assert parse_function_pattern("day_of_week_created_at") == ("day_of_week", "created_at")
    assert parse_function_pattern("just_a_column") == None  # "just" not a function

def test_space_syntax():
    result = compile("from users select sum amount")
    assert "SUM(amount) AS sum_amount" in result
```

### 7.2 Integration Tests

```python
def test_equivalence():
    """All these should produce identical SQL"""
    queries = [
        "from users select sum(amount)",
        "from users select sum_amount",
        "from users select sum amount",
    ]
    results = [compile(q) for q in queries]
    assert len(set(results)) == 1  # All identical
```

### 7.3 Edge Case Tests

```python
def test_schema_precedence():
    """Actual column names take precedence over patterns"""
    # With schema that has sum_revenue column
    result = compile("from sales select sum_revenue", schema=schema_with_sum_revenue)
    assert "sum_revenue" in result  # Literal column, not SUM(revenue)

def test_ambiguous_resolution():
    """Ensure consistent behavior with ambiguous patterns"""
    # ... tests for edge cases
```

---

## 8. Configuration & Style Enforcement

### 8.1 Philosophy

By default, ASQL is **permissive** - underscores and spaces are interchangeable. However, teams may want to enforce consistency for readability and code review.

We support **three levels of enforcement**:

| Level | Behavior | Use Case |
|-------|----------|----------|
| `flexible` (default) | All styles accepted | Learning, rapid prototyping |
| `strict` (compiler) | Only one style compiles | Hard enforcement, CI gates |
| `lint` (separate tool) | Warnings, no breakage | Gradual adoption, suggestions |

### 8.2 Compiler Configuration

```python
from asql import compile, CompilerConfig

# Default: flexible (all styles work)
compile("from users select sum amount")  # ✅
compile("from users select sum_amount")  # ✅

# Strict mode: enforce underscores
config = CompilerConfig(syntax_style='underscores')
compile("from users select sum_amount", config=config)  # ✅
compile("from users select sum amount", config=config)  # ❌ SyntaxError

# Strict mode: enforce spaces  
config = CompilerConfig(syntax_style='spaces')
compile("from users select sum amount", config=config)   # ✅
compile("from users select sum_amount", config=config)   # ❌ SyntaxError
```

**Configuration Options:**

```python
class CompilerConfig:
    syntax_style: Literal['flexible', 'underscores', 'spaces'] = 'flexible'
    # 'flexible' - accept both (default)
    # 'underscores' - only underscore style allowed
    # 'spaces' - only space style allowed
```

### 8.3 Independent Linter (Recommended for Teams)

A separate `asql-lint` tool provides style checking without breaking compilation:

```bash
# Check files for style violations
asql-lint queries/ --style=underscores

# Auto-fix to preferred style
asql-lint queries/ --style=underscores --fix

# CI integration (exit code 1 on violations)
asql-lint queries/ --style=underscores --strict
```

**Linter Configuration (`.asqlrc` or `pyproject.toml`):**

```toml
# pyproject.toml
[tool.asql-lint]
style = "underscores"  # or "spaces" or "flexible"
check_consistency = true  # warn if mixed styles in same file
auto_fix = false
ignore_paths = ["examples/", "tests/fixtures/"]
```

```yaml
# .asqlrc
style: underscores
check_consistency: true
rules:
  prefer-explicit-parens: warn  # sum(amount) vs sum_amount
  prefer-shorthand: off         # sum_amount vs sum(amount)
```

**Linter Output Example:**

```
queries/sales.asql:5:8 warning: Use underscore style for consistency
  5 | select sum amount, avg price
              ^^^^^^^^^^
  Auto-fix: sum_amount, avg_price

queries/sales.asql:12:3 warning: Mixed styles in same file
  12 | group by day_of_week_created_at
  Previously used space style on line 5
```

### 8.4 Why Both Compiler + Linter?

| Scenario | Use Compiler Strict | Use Linter |
|----------|---------------------|------------|
| Hard CI gate, block merges | ✅ | |
| Gradual migration to consistent style | | ✅ |
| Auto-fix existing codebase | | ✅ |
| Warning without breaking builds | | ✅ |
| Maximum strictness | ✅ | ✅ (both) |
| Learning/exploring | neither | |

**Recommendation**: Start with the linter for existing projects, use compiler strict mode for new projects or after migration.

### 8.5 Implementation Priority

1. **Phase 1**: Compiler `flexible` mode (current behavior)
2. **Phase 2**: Compiler `strict` modes (`underscores`, `spaces`)
3. **Phase 3**: Standalone `asql-lint` tool with auto-fix

The linter is lower priority since it's additive and doesn't block core functionality.

---

## 9. Dependencies

### Features That Depend on This

- **dates.md**: Date part extraction (`day of week created_at`)
- **dates.md**: Date arithmetic (`order_date + 7 days`)
- **universal_function_shorthand.md**: All shorthand patterns

### Features This Depends On

- Current parser infrastructure
- Function call handling in compiler
- Column alias generation

---

## 10. Rollout Plan

1. **Phase 1**: Implement function registry and pattern matching (internal only)
2. **Phase 2**: Enable shorthand for existing functions (`sum_amount`)
3. **Phase 3**: Enable space syntax for single-word functions (`sum amount`)
4. **Phase 4**: Add multi-word functions and space syntax (`day of week`)
5. **Phase 5**: Add date-specific functions that leverage this

Each phase should be backward compatible - existing queries continue to work.

---

## 11. Related Documentation

- `SPEC.md`: Core language specification (includes this principle)
- `universal_function_shorthand.md`: The broader shorthand pattern
- `dates.md`: Date features that depend on this principle

---

**End of Document**

