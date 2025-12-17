# Task: Implement ASQL as SQLGlot Dialect

**Created**: December 2025  
**Status**: ✅ COMPLETE (434/434 tests passing)  
**Priority**: Done

---

## Implementation Status (December 2025)

### All Features Complete ✓

**Pre-parser (`asql/preparser.py`)** - ~1000 lines
- FROM-first transformation
- Pipeline operators (|)
- Aggregate blocks with function calls in GROUP BY
- Stash as (CTEs) with continuation support
- Natural aggregates (sum amount, avg of price, etc.)
- Date expressions (N days ago, date arithmetic)
- Sort → ORDER BY, Take → LIMIT
- Coalesce operator (??)
- DESC prefix (-column)
- Count shorthand (#)
- WITH/SET CTE syntax
- Comment preservation
- Underscore/space normalization for functions
- Multiple WHERE clause combination
- DISTINCT ON support
- QUALIFY clause support
- Window functions:
  - prior(col) / prior(col, n) → LAG
  - next(col) / next(col, n) → LEAD
  - running_sum, running_avg, running_count
  - rolling_avg, rolling_sum with window size
  - first(col order by ...) / last(col order by ...)
  - arg_max / arg_min
  - per ... first/last/number/rank/dense rank by
  - Standalone rank by, dense rank by, number by

**ASQL Dialect (`asql/dialect.py`)** - ~200 lines
- Custom tokenizer for ASQL keywords
- Parser extensions for ASQL functions
- Generator stub (uses target dialect)

**Updated compiler (`asql/compiler.py`)**
- Three-stage pipeline: preparse → SQLGlot parse → generate
- Error handling with context

**New tests**
- `tests/test_preparser.py` - 40 tests
- `tests/test_dialect.py` - 37 tests

### Test Results
- **434 passed, 0 failed**
- All test suites passing

---

## Context

ASQL is a pipeline-based query language that transpiles to SQL. We've finalized the language spec in `docs/spec.md` and now need to rewrite the parser to use SQLGlot's dialect system instead of our custom parser.

**Key files to read first:**
- `ai_notes/dialect.md` - Full implementation plan with code examples
- `docs/spec.md` - The language specification (source of truth)
- `asql/parser.py` - Current custom parser (to be replaced)

## Goal

Replace the ~2000 line custom parser with:
1. A **pre-parser** (~300 lines) for structural transformations
2. An **ASQL SQLGlot Dialect** (~300 lines) for expression parsing

---

## Steps

### Step 1: Create Pre-Parser (`asql/preparser.py`)

Create a new file that transforms ASQL structure to SQL-like structure before SQLGlot parsing.

**Transformations needed (see dialect.md Section 8.2):**

1. **FROM-first → SELECT-FROM**
   - `from users where active` → `SELECT * FROM users WHERE active`
   - If `select` clause exists later, move it to front

2. **Pipeline operators**
   - `from x | where y | order by z` → `SELECT * FROM x WHERE y ORDER BY z`
   - Remove `|` operators, preserve clause order

3. **Aggregate blocks**
   - `group by region (sum amount as revenue, #)` → 
   - `SELECT region, SUM(amount) AS revenue, COUNT(*) FROM ... GROUP BY region`

4. **Stash as (CTEs)**
   - `from users where active stash as active_users` →
   - `WITH active_users AS (SELECT * FROM users WHERE active) SELECT * FROM active_users`

5. **Natural aggregates**
   - `sum amount` → `sum(amount)`
   - `avg of revenue` → `avg(revenue)`
   - `# of users` → `count(*)`

6. **Underscore/space normalization** (see spec.md Section 4.13)
   - `sum_amount` → `sum(amount)`
   - `day of week created_at` → `day_of_week(created_at)`
   - `days_since_created_at` → `days(now() - created_at)`
   - See `ai_notes/UNDERSCORE_SPACE_PRINCIPLE.md` for full implementation details

7. **Window utilities (per command)**
   - `per customer_id first by -order_date` → ROW_NUMBER window + filter
   - `per department number by -salary` → ROW_NUMBER window column
   - See `ai_notes/WINDOW_UTILS.md` for full patterns

8. **Date expressions**
   - `7 days ago` → `CURRENT_DATE - INTERVAL '7 days'`
   - `order_date + 7 days` → `order_date + INTERVAL '7 days'`
   - `days(end - start)` → date difference function
   - See `ai_notes/dates.md` for full patterns

9. **Data transformation operators** (see spec.md §13, macros.md)
   - **Column operators**:
     - `except email, phone` → Explicit SELECT excluding those columns (schema-aware)
     - `rename id as user_id` → SELECT ... AS ... aliases
     - `prefix user_` → SELECT cols with prefixed names
   - **Deduplicate**:
     - `deduplicate by user_id order by -date` → ROW_NUMBER + filter (like `per` but simpler)
   - **Pivot/Unpivot**:
     - `pivot amount by category` → Native PIVOT or CASE/GROUP BY fallback
     - `unpivot jan, feb into month, value` → Native UNPIVOT or UNION fallback
   - **Gap fill**:
     - `fill month with {revenue: 0}` → LEFT JOIN with date_spine + COALESCE
   - **Table functions**:
     - `from date_spine(start='2024-01-01', end=today(), grain=day)` → generate_series or CTE
     - `from series(1, 100)` → generate_series or numbers CTE
     - `from union(t1, t2, t3)` → Schema-aligned SELECT + UNION ALL
   - **Surrogate keys**:
     - `key(user_id, order_id)` → Warehouse-specific hash function
   - **Safe casting**:
     - `value::integer?` → TRY_CAST/SAFE_CAST
     - `safe_divide(a, b)` → CASE WHEN b = 0 THEN NULL ELSE a/b END

### Step 2: Create ASQL Dialect (`asql/dialect.py`)

Create SQLGlot dialect with custom Tokenizer and Parser.

**Tokenizer additions:**
```python
from sqlglot.tokens import Tokenizer, TokenType

class ASQLTokenizer(Tokenizer):
    SINGLE_TOKENS = {
        **Tokenizer.SINGLE_TOKENS,
        "#": TokenType.HASH,  # COUNT(*) shorthand
    }
    
    def _scan(self):
        # Handle ?? as COALESCE
        if self._char == "?" and self._peek == "?":
            self._advance()
            self._advance()
            return self._token(TokenType.COALESCE)
        
        # Handle @date literals
        if self._char == "@" and self._peek.isdigit():
            return self._scan_date_literal()
        
        return super()._scan()
```

**Parser additions:**
- `order by -col` → DESC indicator
- `#` → COUNT(*)
- Natural aggregate functions (sum, avg, etc.)
- `when` conditional expressions
- `contains`, `starts with`, `ends with` operators

See `dialect.md` Section 5 for full implementation.

### Step 3: Update Main Entry Point (`asql/__init__.py`)

Wire up the new parsing pipeline:
```python
def parse(asql_text: str, dialect: str = "postgres") -> str:
    # 1. Pre-parse ASQL to SQL-like
    sql_like = preparse_asql(asql_text)
    
    # 2. Parse with ASQL dialect
    ast = sqlglot.parse_one(sql_like, dialect="asql")
    
    # 3. Generate target SQL
    return ast.sql(dialect=dialect)
```

### Step 4: Update Tests

- Keep existing test cases but update to use new parser
- Tests are in `tests/` directory
- Run `pytest tests/` to verify
- Create new test files for pre-parser and dialect

### Step 5: Clean Up

- Remove or deprecate old `parser.py` code that's replaced
- Update any imports
- Ensure all existing tests pass

---

## Key Syntax Decisions (from spec.md)

| Feature | ASQL Syntax | Notes |
|---------|-------------|-------|
| Equality | `=` (also accepts `==`) | `=` is preferred |
| COALESCE | `??` | Not `\|\|` |
| Sort | `order by -col` | `-` prefix for DESC |
| Limit | `limit 10` | Not `limit` |
| CTEs | `set x = ...` or `stash as x` | |
| Conditionals | `when status is "active" then 1 otherwise 0` | Not `case` |
| Dates | `7 days ago`, `days(end - start)` | See dates.md |
| Window | `per customer_id first by -date` | See WINDOW_UTILS.md |
| Strings | `email[1:5]` slice syntax | Python-style |
| Comparison | `max(a, b, c)` | Not `greatest()` |
| Column exclude | `except email, phone` | Schema-aware |
| Column rename | `rename id as user_id` | |
| Deduplicate | `deduplicate by user_id order by -date` | |
| Pivot | `pivot amount by category` | |
| Unpivot | `unpivot jan, feb into month, value` | |
| Fill gaps | `fill month with {revenue: 0}` | |
| Date spine | `from date_spine(start=..., end=..., grain=day)` | |
| Safe cast | `value::integer?` | TRY_CAST |
| Surrogate key | `key(user_id, order_id)` | Hash function |

---

## Testing Strategy

1. Start with pre-parser unit tests
2. Then dialect tokenizer tests  
3. Then full integration tests
4. Use existing test files as reference for expected behavior

Run tests with:
```bash
pytest tests/
pytest tests/test_preparser.py -v
pytest tests/test_dialect.py -v
```

---

## Files to Create/Modify

```
asql/
  preparser.py      # NEW - structural transformations
  dialect.py        # NEW - SQLGlot dialect
  __init__.py       # MODIFY - wire up new pipeline
  parser.py         # DEPRECATE after new system works

tests/
  test_preparser.py # NEW - pre-parser tests
  test_dialect.py   # NEW - dialect tests
```

---

## Reference Documentation

| Document | Purpose |
|----------|---------|
| `ai_notes/dialect.md` | Full implementation plan with code |
| `docs/spec.md` | Language specification (source of truth) |
| `ai_notes/WINDOW_UTILS.md` | Window function patterns |
| `ai_notes/dates.md` | Date handling patterns |
| `ai_notes/case.md` | Conditional expression design |
| `ai_notes/comments.md` | Comment handling design |
| `ai_notes/macros.md` | Data transformation operators (dbt macro replacements) |
| `ai_notes/UNDERSCORE_SPACE_PRINCIPLE.md` | Function shorthand syntax |

---

## Don't

- Don't modify `docs/spec.md` - it's the source of truth
- Don't change the language syntax - implement what's documented
- Don't try to preserve the old parser - this is a rewrite
- Don't worry about the old feature branches - they're obsolete

---

## Getting Started

1. Read `ai_notes/dialect.md` thoroughly
2. Start with Step 1 (pre-parser)
3. Write tests as you go
4. Commit frequently with clear messages

The full implementation plan with code examples is in `ai_notes/dialect.md`. Follow that document closely - it has working code snippets for most components.


