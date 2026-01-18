# SQLGlot Dialect Implementation Learnings

**Date**: 2026-01-07  
**Context**: Research into how SQLGlot dialects (PRQL, BigQuery, DuckDB, ClickHouse) implement parsing to inform ASQL's preparser-to-dialect migration.

---

## SQLGlot Complete Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SQLGlot Architecture                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Input SQL String                                                           │
│         │                                                                    │
│         ▼                                                                    │
│   ┌───────────┐                                                              │
│   │ TOKENIZER │  tokens.py - Lexical analysis                               │
│   │           │  Converts text → Token stream                                │
│   └─────┬─────┘                                                              │
│         │ Token[]                                                            │
│         ▼                                                                    │
│   ┌───────────┐                                                              │
│   │  PARSER   │  parser.py - Syntax analysis                                │
│   │           │  Converts tokens → AST (Expression tree)                    │
│   └─────┬─────┘                                                              │
│         │ Expression (AST)                                                   │
│         ▼                                                                    │
│   ┌───────────┐  ┌──────────┐                                               │
│   │ OPTIMIZER │←─│  SCHEMA  │  optimizer/ + schema.py                       │
│   │           │  │          │  AST transformations with schema knowledge    │
│   │  - qualify_columns      │  - Column/table resolution                    │
│   │  - expand_stars         │  - Type annotation                            │
│   │  - pushdown_predicates  │  - Query optimization                         │
│   │  - simplify             │                                               │
│   └─────┬─────┘  └──────────┘                                               │
│         │ Optimized AST                                                      │
│         ▼                                                                    │
│   ┌───────────┐                                                              │
│   │ GENERATOR │  generator.py - Code generation                             │
│   │           │  Converts AST → SQL string (target dialect)                 │
│   └─────┬─────┘                                                              │
│         │                                                                    │
│         ▼                                                                    │
│   Output SQL String                                                          │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                         Additional Components                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌───────────┐                                                              │
│   │  DIALECT  │  dialects/*.py - Bundles customizations                     │
│   │           │  Each dialect defines: Tokenizer, Parser, Generator         │
│   │           │  Examples: postgres, mysql, bigquery, snowflake, duckdb     │
│   └───────────┘                                                              │
│                                                                              │
│   ┌───────────┐                                                              │
│   │EXPRESSIONS│  expressions.py - AST node types (~2000 classes!)           │
│   │           │  Select, Column, Table, Function, BinaryOp, etc.            │
│   └───────────┘                                                              │
│                                                                              │
│   ┌───────────┐                                                              │
│   │TRANSFORMS │  transforms.py - Reusable AST→AST functions                 │
│   │           │  Used by Generator.TRANSFORMS for dialect-specific output   │
│   └───────────┘                                                              │
│                                                                              │
│   ┌───────────┐                                                              │
│   │  PLANNER  │  planner.py - Query execution planning                      │
│   │           │  Converts AST → DAG of execution Steps                      │
│   └───────────┘                                                              │
│                                                                              │
│   ┌───────────┐                                                              │
│   │ EXECUTOR  │  executor/ - Python SQL engine!                             │
│   │           │  Actually runs SQL against Python data structures           │
│   │           │  Uses: optimize → plan → execute                            │
│   └───────────┘                                                              │
│                                                                              │
│   ┌───────────┐                                                              │
│   │  LINEAGE  │  lineage.py - Column lineage tracking                       │
│   │           │  Tracks which source columns flow to output columns         │
│   └───────────┘                                                              │
│                                                                              │
│   ┌───────────┐                                                              │
│   │   DIFF    │  diff.py - AST comparison                                   │
│   │           │  Compare two SQL statements, get Insert/Remove/Move ops     │
│   └───────────┘                                                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Summary

| Component | File(s) | Purpose | ASQL Uses? |
|-----------|---------|---------|------------|
| **Tokenizer** | `tokens.py` | Text → Tokens | ✅ Via ASQLTokenizer |
| **Parser** | `parser.py` | Tokens → AST | ✅ Via ASQLParser |
| **Expressions** | `expressions.py` | AST node types | ✅ exp.If, exp.Interval, etc. |
| **Optimizer** | `optimizer/*.py` | Schema-aware AST transforms | 🔜 Could add ASQL rules |
| **Generator** | `generator.py` | AST → SQL string | ✅ Via ASQLGenerator |
| **Dialect** | `dialects/*.py` | Bundles T+P+G | ✅ ASQL dialect class |
| **Schema** | `schema.py` | Column/table metadata | 🔜 For shorthand resolution |
| **Transforms** | `transforms.py` | Reusable AST→AST | ⚪ Not yet |
| **Planner** | `planner.py` | AST → execution DAG | ⚪ Not needed |
| **Executor** | `executor/*.py` | Run SQL in Python | ⚪ Not needed |
| **Lineage** | `lineage.py` | Column flow tracking | ⚪ Future feature? |
| **Diff** | `diff.py` | Compare SQL statements | ⚪ Debugging tool |

### Where ASQL Features Should Live

```
┌──────────────────────────────────────────────────────────────────┐
│                    ASQL Feature Placement                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  TOKENIZER (tokens)                                               │
│  └─ New punctuation: @, #, |                                      │
│                                                                   │
│  PARSER (syntax)                                                  │
│  └─ FROM-first syntax                                             │
│  └─ Pipe transforms (select, where, group, etc.)                  │
│  └─ Ternary ? :                                                   │
│  └─ @date literals                                                │
│  └─ Relative dates (7 days ago)                                   │
│  └─ Date arithmetic (col + 7 days)                                │
│  └─ == null → IS NULL                                             │
│  └─ -column → DESC                                                │
│                                                                   │
│  OPTIMIZER (schema-aware)                                         │
│  └─ days_since_created_at → DATEDIFF(...)  [FUTURE]               │
│  └─ sum_amount → SUM(amount) AS sum_amount  [FUTURE]              │
│  └─ Validate column references  [FUTURE]                          │
│                                                                   │
│  GENERATOR (output)                                               │
│  └─ Dialect-specific SQL generation (handled by target dialect)  │
│                                                                   │
│  PREPARSER (still needed for complex text patterns)               │
│  └─ Natural aggregates (sum amount)                               │
│  └─ Join operators (&, <&, &>)                                    │
│  └─ When expressions (keyword-based, indentation-sensitive)       │
│  └─ Per commands                                                  │
│  └─ Pivot/Unpivot                                                 │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## ⚠️ KEY LESSON LEARNED

> **ALWAYS RESEARCH for similar implementations in existing dialects before re-creating one!**

We initially thought ternary `? :` would be "too complex" to move to the parser (disambiguation, etc.).
Then we discovered **ClickHouse already solved it in ~10 lines**. We copied their pattern and:
- **Deleted 351 lines** of fragile regex code (ternary.py)
- **Added 15 lines** of clean parser code
- All tests pass ✅

This applies broadly: SQLGlot has **many dialects** (30+). Someone has probably solved your problem already.

---

## Date/Time Format Translation System

SQLGlot has a sophisticated system for translating date formats between dialects. This is how `STRFTIME(x, '%y-%-m-%S')` in DuckDB becomes `DATE_FORMAT(x, 'yy-M-ss')` in Hive.

### Core Components

1. **`TIME_MAPPING`** (Dialect class attribute) - Maps dialect's format codes → Python strftime codes
2. **`INVERSE_TIME_MAPPING`** (auto-generated) - Maps Python strftime → dialect's format codes
3. **`format_time()` function** (`sqlglot/time.py`) - Performs conversion using a trie for efficiency
4. **Expression classes** (`exp.TimeToStr`, `exp.StrToTime`, `exp.StrToDate`) - Store value + normalized format
5. **`build_formatted_time()`** - Helper to parse time functions and normalize formats

### Example: Hive's TIME_MAPPING

```python
TIME_MAPPING = {
    "y": "%Y",       # 4-digit year
    "Y": "%Y",
    "YYYY": "%Y",
    "yyyy": "%Y",
    "YY": "%y",      # 2-digit year
    "yy": "%y",
    "MM": "%m",      # Month with zero-padding
    "M": "%-m",      # Month without padding
    "dd": "%d",      # Day with zero-padding
    "d": "%-d",      # Day without padding
    "HH": "%H",      # 24-hour
    "H": "%-H",
    "hh": "%I",      # 12-hour
    "mm": "%M",      # Minute
    "ss": "%S",      # Second
    "SSSSSS": "%f",  # Microseconds
    # etc.
}
```

### How Translation Works

**Parsing (DuckDB → internal):**
```python
# In DuckDB's FUNCTIONS dict:
"STRFTIME": build_formatted_time(exp.TimeToStr, "duckdb"),

# build_formatted_time calls Dialect["duckdb"].format_time()
# which converts DuckDB format → Python strftime
# Result: exp.TimeToStr(this=x, format='%y-%-m-%S')
```

**Generation (internal → Hive):**
```python
# Hive's generator has:
def timetostr_sql(self, expression: exp.TimeToStr) -> str:
    return self.func("DATE_FORMAT", this, self.format_time(expression))

# self.format_time() uses INVERSE_TIME_MAPPING
# Python strftime '%y-%-m-%S' → Hive 'yy-M-ss'
```

### Key Insight

The format string is normalized to **Python strftime** as the intermediate representation. This allows N×N dialect translation with only N mappings.

### Relevance to ASQL

For ASQL's date features, we should:
1. **Use SQLGlot's existing expressions** (`exp.Interval`, `exp.DateAdd`, `exp.CurrentTimestamp`) - already doing this
2. **For any custom date formats**: Define `TIME_MAPPING` in ASQL dialect if needed
3. **Rely on target dialect's generator** - It already knows how to output dates correctly

Our current approach (converting `7 days ago` → `CURRENT_TIMESTAMP - INTERVAL '7 days'`) is correct because:
- `exp.Interval` is dialect-agnostic
- Each target dialect's generator knows how to output intervals
- No need for custom format mappings for intervals

---

## Key Findings

### 1. PRQL's Transform Pattern (Most Relevant to ASQL)

PRQL uses a clean dictionary-based approach for pipeline transforms:

```python
TRANSFORM_PARSERS = {
    "DERIVE": lambda self, query: self._parse_selection(query),
    "SELECT": lambda self, query: self._parse_selection(query, append=False),
    "TAKE": lambda self, query: self._parse_take(query),
    "FILTER": lambda self, query: query.where(self._parse_disjunction()),
    "SORT": lambda self, query: self._parse_order_by(query),
    # etc.
}

def _parse_query(self) -> t.Optional[exp.Query]:
    from_ = self._parse_from()
    if not from_:
        return None
    
    query = exp.select("*").from_(from_, copy=False)
    
    # Simple loop using _match_texts!
    while self._match_texts(self.TRANSFORM_PARSERS):
        query = self.TRANSFORM_PARSERS[self._prev.text.upper()](self, query)
    
    return query
```

**Key insight**: Use `_match_texts(dict)` to check if current token matches any key in the dict, then use `_prev.text.upper()` to get which one matched.

### 2. ClickHouse Ternary Pattern (Applied to ASQL!)

The elegant ~10 line solution that replaced 351 lines of regex:

```python
# 1. Pop PLACEHOLDER from COLUMN_OPERATORS to avoid conflicts
COLUMN_OPERATORS = Parser.COLUMN_OPERATORS.copy()
COLUMN_OPERATORS.pop(TokenType.PLACEHOLDER)

# 2. Override _parse_assignment to handle ternary
def _parse_assignment(self) -> t.Optional[exp.Expression]:
    this = super()._parse_assignment()  # Parse condition first
    
    if self._match(TokenType.PLACEHOLDER):  # Found ?
        return self.expression(
            exp.If,
            this=this,
            true=self._parse_assignment(),
            false=self._match(TokenType.COLON) and self._parse_assignment(),
        )
    
    return this
```

**Why it works:**
- `?` is checked AFTER parsing an expression, so context is clear
- Recursive `_parse_assignment()` handles nested ternaries automatically
- Parser handles operator precedence - no regex needed to find matching `:`

### 3. Built-in Lookahead Helpers

| Helper | Purpose |
|--------|---------|
| `_match(TokenType, advance=False)` | Peek at current token type |
| `_match_pair(A, B, advance=False)` | Peek at current+next tokens |
| `_match_text_seq(*texts, advance=False)` | Peek at text sequence |
| `_match_texts(texts, advance=False)` | Check if current text in set |
| `_match_set(types, advance=False)` | Check if current type in set |
| `_retreat(index)` | Return to saved position |
| `_curr`, `_next`, `_prev` | Token access properties |
| `seq_get(seq, index)` | Safe index access |

### 4. Dict Copy-and-Pop Pattern

```python
# Extend parent dict
KEYWORDS = {
    **tokens.Tokenizer.KEYWORDS,
    "DATE32": TokenType.DATE32,
}
KEYWORDS.pop("/*+")  # Remove unwanted

# Same for parser configs
COLUMN_OPERATORS = Parser.COLUMN_OPERATORS.copy()
COLUMN_OPERATORS.pop(TokenType.PLACEHOLDER)
```

### 5. Parse-Try-Retreat Pattern

```python
def _parse_extract(self) -> exp.Extract | exp.Anonymous:
    index = self._index  # Save position
    this = self._parse_bitwise()
    
    if self._match(TokenType.FROM):
        self._retreat(index)  # Go back
        return super()._parse_extract()
    
    # Alternative parsing path
    return self.expression(exp.Anonymous, ...)
```

---

## ClickHouse Dialect Deep Dive (1498 lines)

### Dialect-Level Constants

```python
class ClickHouse(Dialect):
    INDEX_OFFSET = 1                    # Array indexing starts at 1
    NORMALIZE_FUNCTIONS = False         # Preserve function case
    NULL_ORDERING = "nulls_are_last"    # Default NULL sort order
    SAFE_DIVISION = True                # x/0 = NULL not error
    NUMBERS_CAN_BE_UNDERSCORE_SEPARATED = True   # 1_000_000 syntax
    IDENTIFIERS_CAN_START_WITH_DIGIT = True
```

### Aggregate Function Combinators

ClickHouse generates ~900 function variants dynamically:

```python
AGG_FUNCTIONS = {"count", "min", "max", "sum", "avg", ...}  # ~60 functions
AGG_FUNCTIONS_SUFFIXES = ["If", "Array", "State", "Merge", ...]  # 14 suffixes

# Creates: countIf, sumArray, avgMerge, etc.
AGG_FUNC_MAPPING = (
    lambda functions, suffixes: {
        f"{f}{sfx}": (f, sfx) for sfx in (suffixes + [""]) for f in functions
    }
)(AGG_FUNCTIONS, AGG_FUNCTIONS_SUFFIXES)
```

### Query Parameter Parsing

```python
PLACEHOLDER_PARSERS = {
    **parser.Parser.PLACEHOLDER_PARSERS,
    TokenType.L_BRACE: lambda self: self._parse_query_parameter(),
}

def _parse_query_parameter(self) -> t.Optional[exp.Expression]:
    index = self._index  # Save for retreat
    this = self._parse_id_var()
    self._match(TokenType.COLON)
    kind = self._parse_types() or self._match_text_seq("IDENTIFIER") and "Identifier"
    
    if not kind:
        self._retreat(index)
        return None
    
    return self.expression(exp.Placeholder, this=this, kind=kind)
```

### QUERY_MODIFIER_PARSERS

For custom trailing clauses:

```python
QUERY_MODIFIER_PARSERS = {
    **parser.Parser.QUERY_MODIFIER_PARSERS,
    TokenType.SETTINGS: lambda self: (
        "settings",
        self._advance() or self._parse_csv(self._parse_assignment),
    ),
    TokenType.FORMAT: lambda self: ("format", self._advance() or self._parse_id_var()),
}
```

---

## Current ASQL Status (2026-01-07)

### In Dialect Parser (asql/dialect.py)

- FROM-first syntax with transforms
- `??` coalesce (SQLGlot DQMARK)
- `-column` DESC ordering
- `== null` → `IS NULL`
- Relative dates (`7 days ago`, `3 months from now`)
- Date arithmetic (`col + 7 days`)
- Pipe syntax (`|`) with GROUP BY
- **Ternary `? :`** (ClickHouse pattern - 351 LOC → 15 LOC!)
- **`@date` literals** (`@2024-01-15` → `DATE '2024-01-15'`)

### Still in Preparser (~35 transforms)

- `#` COUNT(*) shorthand
- Natural aggregates (`sum amount`)
- Join operators (`&`, `<&`, `&>`)
- Per commands
- Pivot/Unpivot
- Cohort by
- Window shorthands (prior, next, running_*, rolling_*)
- Stash as (CTEs)
- And more...

---

## SQLGlot Optimizer - Schema-Aware Transformations

### Architecture

SQLGlot has a clear separation of concerns:

```
Input SQL
    ↓
[PARSE] ← Syntax only, NO schema needed
    ↓
   AST
    ↓
[OPTIMIZE] ← Schema-aware transformations happen HERE
    ├── qualify_columns.py  ← Resolves column references
    ├── annotate_types.py   ← Adds type info from schema
    ├── pushdown_projections.py ← Removes unused columns
    ├── expand_stars.py     ← SELECT * → SELECT a, b, c
    ├── eliminate_joins.py  ← Removes unnecessary JOINs
    └── simplify.py         ← 1 = 1 → TRUE (no schema)
    ↓
Optimized AST
    ↓
[GENERATE]
    ↓
Output SQL
```

**Key insight**: Schema-aware transformations are NOT in the parser - they're in the optimizer phase. This is the conventional pattern.

### Schema API

```python
schema = {
    "users": {"id": "INT", "name": "VARCHAR", "created_at": "TIMESTAMP"},
    "orders": {"id": "INT", "user_id": "INT", "amount": "DECIMAL"}
}

# Schema methods:
schema.column_names("users")        # → ["id", "name", "created_at"]
schema.get_column_type("users", "id")  # → INT
schema.has_column("users", "email")    # → False
```

### Default Optimizer Pipeline

```python
RULES = (
    qualify,              # Normalize tables + columns with schema
    pushdown_projections, # Remove unused column projections  
    normalize,            # CNF/DNF normalization
    unnest_subqueries,    # Flatten subqueries where possible
    pushdown_predicates,  # Push WHERE clauses down
    optimize_joins,       # Reorder JOINs
    eliminate_subqueries, # Remove unnecessary subqueries
    merge_subqueries,     # Combine subqueries
    eliminate_joins,      # Remove unnecessary JOINs
    eliminate_ctes,       # Inline CTEs
    quote_identifiers,    # Add quotes
    annotate_types,       # Add type info
    canonicalize,         # Standardize expression forms
    simplify,             # Constant folding, etc.
)
```

### Relevance to ASQL

For transformations that need schema knowledge (like `days_since_created_at` → `DATEDIFF(...)`), we should add an **optimizer rule**, not parser logic:

```python
# asql/optimizer/resolve_shorthands.py
def resolve_asql_shorthands(expression, schema):
    """
    Resolve ASQL column shorthands using schema.
    
    days_since_created_at → DATEDIFF('day', created_at, NOW())
    sum_amount → SUM(amount) AS sum_amount  
    year_of_created_at → YEAR(created_at)
    """
    for col in expression.find_all(exp.Column):
        if not schema.has_column(table, col.name):
            # Column doesn't exist - try shorthand patterns
            resolved = _try_resolve_shorthand(col.name, schema)
            if resolved:
                col.replace(resolved)
    return expression

# Add to ASQL's optimizer pipeline:
ASQL_RULES = (
    resolve_asql_shorthands,  # ← ASQL-specific
    *sqlglot.optimizer.RULES, # Standard SQLGlot rules
)
```

### When to Use Parser vs Optimizer

| Feature | Use Parser | Use Optimizer |
|---------|------------|---------------|
| New syntax/tokens | ✅ | ❌ |
| Keyword transforms | ✅ | ❌ |
| Operator overloading | ✅ | ❌ |
| Identifier text patterns | ❌ | ✅ (needs schema) |
| Column existence checks | ❌ | ✅ (needs schema) |
| Type-aware transforms | ❌ | ✅ (needs schema) |

---

## Files Examined

- `/venv/lib/.../sqlglot/time.py` - Date format translation core
- `/venv/lib/.../sqlglot/dialects/prql.py` (207 lines) - Pipeline language
- `/venv/lib/.../sqlglot/dialects/bigquery.py` (1463 lines) - Pipe syntax
- `/venv/lib/.../sqlglot/dialects/duckdb.py` (1431 lines) - Modern SQL extensions
- `/venv/lib/.../sqlglot/dialects/clickhouse.py` (1498 lines) - Comprehensive dialect, ternary pattern
- `/venv/lib/.../sqlglot/dialects/hive.py` - Date format example
- `/venv/lib/.../sqlglot/dialects/dialect.py` - Base dialect with TIME_MAPPING
- `/venv/lib/.../sqlglot/parser.py` - Base parser
- `/venv/lib/.../sqlglot/schema.py` - Schema API (column_names, get_column_type, has_column)
- `/venv/lib/.../sqlglot/optimizer/optimizer.py` - Main optimizer with RULES pipeline
- `/venv/lib/.../sqlglot/optimizer/qualify.py` - Table/column qualification
- `/venv/lib/.../sqlglot/optimizer/qualify_columns.py` - Column resolution with schema
- `/venv/lib/.../sqlglot/optimizer/annotate_types.py` - Type annotation from schema
- `/venv/lib/.../sqlglot/optimizer/pushdown_projections.py` - Unused column removal
