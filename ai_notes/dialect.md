# ASQL as a SQLGlot Dialect

**Last Updated**: December 2025  
**Status**: Research/Planning  
**Priority**: High (architectural decision)

> **See also**:
> - [comments.md](comments.md) - Comment extraction and metadata API (fits with this approach)
> - [UNDERSCORE_SPACE_PRINCIPLE.md](UNDERSCORE_SPACE_PRINCIPLE.md) - Function name flexibility (pre-parse handling)
> - [WINDOW_UTILS.md](WINDOW_UTILS.md) - Window function patterns (`per`, `running_sum`, etc.)
> - [dates.md](dates.md) - Date handling, arithmetic, relative dates, timezone syntax
> - [macros.md](macros.md) - Data transformation operators (except, pivot, fill, deduplicate, etc.)

---

## 1. Executive Summary

This document explores implementing ASQL as a SQLGlot dialect rather than using a custom parser. SQLGlot's dialect system provides extension points for Tokenizer, Parser, and Generator—the same pattern used for BigQuery, Snowflake, ClickHouse, etc.

**Key Finding**: A hybrid approach is recommended:
1. **Pre-parse transformation** for syntax that fundamentally differs from SQL structure
2. **ASQL Dialect** for syntax that fits SQLGlot's extension model
3. **Post-parse AST transformation** for semantic changes

This could reduce our custom parser from ~2000 lines to a minimal pre-processor plus dialect extensions.

---

## 2. SQLGlot Dialect Architecture

### 2.1 How Dialects Work

SQLGlot dialects customize three components:

```python
from sqlglot.dialects.dialect import Dialect
from sqlglot.parser import Parser
from sqlglot.generator import Generator
from sqlglot.tokens import Tokenizer, TokenType

class CustomDialect(Dialect):
    class Tokenizer(Tokenizer):
        # Token recognition: keywords, operators, literals
        KEYWORDS = {...}
        SINGLE_TOKENS = {...}
        
    class Parser(Parser):
        # Syntax rules: statement structure, expression parsing
        STATEMENT_PARSERS = {...}
        FUNCTION_PARSERS = {...}
        
    class Generator(Generator):
        # Output: how AST nodes become SQL text
        TRANSFORMS = {...}
        TYPE_MAPPING = {...}
```

### 2.2 Extension Points Available

| Component | Extension Point | Purpose |
|-----------|----------------|---------|
| **Tokenizer** | `KEYWORDS` | Map text to token types |
| **Tokenizer** | `SINGLE_TOKENS` | Single-character operators |
| **Tokenizer** | `QUOTES` | String delimiters |
| **Parser** | `STATEMENT_PARSERS` | Top-level statement parsing |
| **Parser** | `FUNCTION_PARSERS` | Custom function syntax |
| **Parser** | `EXPRESSION_PARSERS` | Custom expression syntax |
| **Generator** | `TRANSFORMS` | AST node → SQL text |
| **Generator** | `TYPE_MAPPING` | Type name mapping |

---

## 3. ASQL Feature Analysis

### 3.1 Features by Implementation Strategy

#### ✅ **Tokenizer-Level (Easy)**

These can be handled by extending SQLGlot's Tokenizer:

| Feature | ASQL Syntax | Implementation |
|---------|-------------|----------------|
| `#` operator | `#`, `#(col)` | Add `#` to `SINGLE_TOKENS` → `TokenType.HASH` |
| `=` equality | `x = y` | Standard SQL equality (also support `==`) |
| `??` coalesce | `a ?? b` | Add `??` token → COALESCE semantics |
| Date literals | `@2025-01-10` | Add `@` recognition → parse as date |
| Keywords | `stash`, `project` | Add to `KEYWORDS` mapping |

```python
class ASQLTokenizer(Tokenizer):
    SINGLE_TOKENS = {
        **Tokenizer.SINGLE_TOKENS,
        "#": TokenType.HASH,  # COUNT(*) shorthand
        "@": TokenType.AT,    # Date literal prefix
    }
    
    # Two-character tokens
    _COMMENTS = Tokenizer._COMMENTS
    
    KEYWORDS = {
        **Tokenizer.KEYWORDS,
        "PROJECT": TokenType.SELECT,  # Alias for SELECT
        "STASH": TokenType.VAR,       # CTE keyword
    }
```

#### ⚠️ **Parser-Level (Medium)**

These require extending SQLGlot's Parser:

| Feature | ASQL Syntax | Implementation |
|---------|-------------|----------------|
| `#` as COUNT(*) | `group by x (#)` | Custom expression parser |
| `order by -col` | `order by -amount` | DESC indicator in ORDER BY parser |
| String matching | `contains`, `starts with` | Infix operator parser |

**Note**: We use standard SQL keywords (`ORDER BY`, `LIMIT`) rather than aliases (`sort`, `take`). No benefit to adding mental overhead for SQL users.

```python
class ASQLParser(Parser):
    FUNCTION_PARSERS = {
        **Parser.FUNCTION_PARSERS,
        "SUM": lambda self: self._parse_natural_aggregate(exp.Sum),
        "AVG": lambda self: self._parse_natural_aggregate(exp.Avg),
        "COUNT": lambda self: self._parse_count_shorthand(),
    }
    
    def _parse_natural_aggregate(self, agg_class):
        """Parse 'sum amount' or 'sum(amount)' or 'sum of amount'"""
        # Skip optional 'of' keyword
        if self._match_text("of"):
            pass
        # Parse argument (with or without parens)
        if self._match(TokenType.L_PAREN):
            arg = self._parse_expression()
            self._match(TokenType.R_PAREN)
        else:
            arg = self._parse_column()
        return self.expression(agg_class, this=arg)
```

#### 🔴 **Pre-Parse Required (Hard)**

These features fundamentally differ from SQL structure and need transformation BEFORE parsing:

| Feature | ASQL Syntax | Why Pre-Parse? | Transform To |
|---------|-------------|----------------|--------------|
| FROM-first | `from users where...` | SQL expects `SELECT...FROM` | Add `SELECT *` at front |
| Pipeline `\|` | `from x \| where \| order by` | Not valid SQL structure | Remove `\|` operators |
| Implicit SELECT | `from users limit 10` | SQL requires SELECT clause | Add `SELECT *` at front |
| `group by (aggs)` | `group by x (sum y)` | Non-standard aggregate block | Extract to SELECT + GROUP BY |
| `stash as name` | `... stash as foo` | Different CTE syntax | Wrap in `WITH foo AS (...)` |
| Natural aggregates | `sum amount`, `avg of x` | Not valid SQL | `sum(amount)`, `avg(x)` |
| `first by/last by` | `first by -date per user` | Custom deduplication | Window function + filter |

**Simple text transforms** (can be regex):
- `sum amount` → `sum(amount)`
- `avg of revenue` → `avg(revenue)` 
- `# of users` → `count(*)`

---

## 4. Recommended Architecture

### 4.1 Three-Stage Pipeline

```
ASQL text → Pre-Parse Transform → SQLGlot Parse (ASQL Dialect) → AST → SQL
```

**Stage 1: Pre-Parse Transform** (Minimal text manipulation)
- Reorder FROM-first to SELECT...FROM
- Convert pipeline syntax to SQL structure
- Expand aggregate blocks

**Stage 2: ASQL Dialect Parsing** (SQLGlot handles most work)
- Tokenize with ASQL-specific tokens (`#`, `@`, etc.)
- Parse with extended function/expression parsers
- Build standard SQLGlot AST

**Stage 3: Output Generation** (Standard SQLGlot)
- Use target dialect (postgres, bigquery, etc.) for final SQL

### 4.2 Pre-Parse Transformations

The pre-parser should be minimal—just structural transformations:

```python
def preparse_asql(asql: str) -> str:
    """Transform ASQL structure to SQL-like structure for SQLGlot parsing."""
    
    # 1. Handle FROM-first: Add implicit SELECT *
    # from users where x → SELECT * FROM users WHERE x
    
    # 2. Handle pipeline syntax
    # from x | where y | order by z → from x where y order by z
    
    # 3. Expand aggregate blocks
    # group by x (sum y, avg z) → group by x ... sum(y), avg(z)
    
    # 4. Handle stash as
    # ... stash as foo → WITH foo AS (...)
    
    return transformed
```

#### 4.2.1 FROM-First Transformation

```python
def transform_from_first(text: str) -> str:
    """
    Transform FROM-first syntax to SQL structure.
    
    ASQL: from users where status = "active" limit 10
    SQL:  SELECT * FROM users WHERE status = 'active' LIMIT 10
    
    ASQL: from users select name, email
    SQL:  SELECT name, email FROM users
    """
    # If query starts with FROM and has no SELECT before it
    # Insert "SELECT *" or extract SELECT clause from later in query
    pass
```

#### 4.2.2 Pipeline Syntax Transformation

```python
def transform_pipeline(text: str) -> str:
    """
    Remove pipeline operators, normalize to SQL clause order.
    
    ASQL: from users | where active | order by -created_at | limit 10
    SQL:  SELECT * FROM users WHERE active ORDER BY created_at DESC LIMIT 10
    """
    # 1. Split on | operators (outside strings/parens)
    # 2. Identify clause types (where, order by, limit, etc.)
    # 3. Reconstruct in SQL order
    pass
```

#### 4.2.3 Aggregate Block Transformation

```python
def transform_aggregate_block(text: str) -> str:
    """
    Transform ASQL aggregate blocks to SQL SELECT + GROUP BY.
    
    ASQL: from sales group by region (sum amount as revenue, # as count)
    SQL:  SELECT region, SUM(amount) AS revenue, COUNT(*) AS count 
          FROM sales GROUP BY region
    """
    # 1. Find group by ... (...) pattern
    # 2. Extract grouping columns and aggregates
    # 3. Build SELECT clause from grouping cols + aggregates
    # 4. Build GROUP BY clause from grouping cols only
    pass
```

---

## 5. ASQL Dialect Implementation

### 5.1 Tokenizer

```python
from sqlglot.tokens import Tokenizer, TokenType

class ASQLTokenizer(Tokenizer):
    # Single character tokens
    SINGLE_TOKENS = {
        **Tokenizer.SINGLE_TOKENS,
        "#": TokenType.HASH,
    }
    
    # Two-character tokens (need special handling)
    # ?? → COALESCE (nullish coalescing, like JavaScript)
    
    # Keyword mappings
    KEYWORDS = {
        **Tokenizer.KEYWORDS,
        # Aliases
        "PROJECT": TokenType.SELECT,
        # New keywords
        "STASH": TokenType.VAR,
        "PER": TokenType.VAR,      # for first by ... per ...
        "CONTAINS": TokenType.VAR,
        "STARTS": TokenType.VAR,
        "ENDS": TokenType.VAR,
    }
    
    # Note: We use standard SQL keywords (ORDER BY, LIMIT) not aliases
    
    def _scan(self):
        """Override to handle ?? operator and @date literals."""
        # Handle ?? as COALESCE
        if self._char == "?" and self._peek == "?":
            self._advance()
            self._advance()
            return self._token(TokenType.COALESCE)
        
        # Handle @date literals
        if self._char == "@" and self._peek.isdigit():
            return self._scan_date_literal()
        
        return super()._scan()
    
    def _scan_date_literal(self):
        """Scan @YYYY-MM-DD as date literal."""
        self._advance()  # skip @
        start = self._current
        while self._peek and (self._peek.isdigit() or self._peek == "-"):
            self._advance()
        return self._token(TokenType.DATE, self._text[start:self._current])
```

### 5.2 Parser

```python
from sqlglot.parser import Parser
from sqlglot import exp

class ASQLParser(Parser):
    FUNCTION_PARSERS = {
        **Parser.FUNCTION_PARSERS,
        # Natural language aggregates
        "SUM": lambda self: self._parse_natural_aggregate(exp.Sum),
        "AVG": lambda self: self._parse_natural_aggregate(exp.Avg),
        "AVERAGE": lambda self: self._parse_natural_aggregate(exp.Avg),
        "TOTAL": lambda self: self._parse_natural_aggregate(exp.Sum),
        "MIN": lambda self: self._parse_natural_aggregate(exp.Min),
        "MAX": lambda self: self._parse_natural_aggregate(exp.Max),
    }
    
    def _parse_natural_aggregate(self, agg_class):
        """
        Parse natural language aggregate syntax.
        
        Supports:
        - sum(amount)      → standard
        - sum amount       → natural language
        - sum of amount    → natural language with 'of'
        """
        # Check for standard function call syntax
        if self._match(TokenType.L_PAREN):
            arg = self._parse_expression()
            self._match_r_paren()
            return self.expression(agg_class, this=arg)
        
        # Skip optional 'of' keyword
        self._match_text_seq("OF")
        
        # Parse column/expression without parens
        arg = self._parse_column()
        if not arg:
            arg = self._parse_primary()
        
        return self.expression(agg_class, this=arg)
    
    def _parse_hash_count(self):
        """
        Parse # count shorthand.
        
        Supports:
        - #           → COUNT(*)
        - # of users  → COUNT(*)  (natural language)
        - #(col)      → COUNT(col)
        """
        if self._match(TokenType.L_PAREN):
            arg = self._parse_expression()
            self._match_r_paren()
            return self.expression(exp.Count, this=arg)
        
        # Skip optional 'of' + table name
        if self._match_text_seq("OF"):
            self._parse_var()  # consume table name, treat as COUNT(*)
        
        return self.expression(exp.Count, this=exp.Star())
    
    def _parse_order(self):
        """
        Override ORDER BY parsing to handle ASQL's -column for DESC.

        ASQL: order by -created_at, name
        SQL:  ORDER BY created_at DESC, name ASC
        """
        if not self._match(TokenType.ORDER):
            return None

        self._match(TokenType.BY)  # 'BY' keyword
        
        expressions = []
        while True:
            # Check for - prefix (descending)
            desc = self._match(TokenType.DASH)
            
            expr = self._parse_expression()
            if not expr:
                break
            
            if desc:
                expr = self.expression(exp.Ordered, this=expr, desc=True)
            else:
                expr = self.expression(exp.Ordered, this=expr, desc=False)
            
            expressions.append(expr)
            
            if not self._match(TokenType.COMMA):
                break
        
        return self.expression(exp.Order, expressions=expressions)
```

### 5.3 Generator (Not Needed for ASQL)

Since ASQL is a **source** language (we read it, not write it), we don't need a Generator. We use the target dialect's Generator (postgres, bigquery, etc.) for output.

### 5.4 Complete Dialect Class

```python
from sqlglot.dialects.dialect import Dialect

class ASQL(Dialect):
    """
    ASQL (Analytic SQL) dialect for SQLGlot.
    
    ASQL is a human-readable query language that transpiles to SQL.
    This dialect handles ASQL-specific syntax that can be tokenized
    and parsed within SQLGlot's framework.
    
    Note: Some ASQL features require pre-parsing (see preparse_asql()).
    """
    
    class Tokenizer(ASQLTokenizer):
        pass
    
    class Parser(ASQLParser):
        pass
    
    # No Generator - we output to target dialects (postgres, bigquery, etc.)
```

---

## 6. Feature Implementation Matrix

| Feature | Pre-Parse | Tokenizer | Parser | Notes |
|---------|-----------|-----------|--------|-------|
| FROM-first syntax | ✅ | | | Structural transformation |
| Pipeline `\|` operators | ✅ | | | Remove, reorder clauses |
| Implicit SELECT | ✅ | | | Add SELECT * |
| `group by (aggs)` block | ✅ | | | Extract to SELECT + GROUP BY |
| `stash as name` | ✅ | | | Convert to WITH clause |
| `#` count | | ✅ | ✅ | Token + expression parser |
| `=` / `==` equality | | ✅ | | Both map to EQ |
| `??` coalesce | | ✅ | ✅ | Nullish coalescing operator |
| `project` | | ✅ | | Alias for SELECT |
| `order by -col` | | | ✅ | DESC indicator parsing |
| Natural aggregates | ✅ | | | `sum x` → `sum(x)` in pre-parse |
| `@date` literals | | ✅ | | Scan as date literal |
| `contains`, `starts with` | | ✅ | ✅ | Keyword + infix parser |
| Underscore/space flexibility | ✅ | | | Normalize before parsing |
| `if` (alias for where) | | ✅ | | Keyword alias |
| **Window Utilities** | | | | |
| `per ... first/last by` | ✅ | ✅ | ✅ | Transform to ROW_NUMBER + filter |
| `per ... number/rank by` | ✅ | ✅ | ✅ | Transform to window function |
| `prior()` / `next()` | | | ✅ | Map to LAG/LEAD |
| `running_sum/avg/count()` | | | ✅ | Cumulative window functions |
| `rolling_avg/sum()` | | | ✅ | Moving window functions |
| `arg_max()` / `arg_min()` | | | ✅ | First value by sort |
| `first()` / `last()` in GROUP BY | | | ✅ | Ordered aggregates |
| **Date Operations** | | | | |
| `N days ago` | ✅ | | | Transform to `now() - INTERVAL` |
| `N days from now` | ✅ | | | Transform to `now() + INTERVAL` |
| `date + N days` | ✅ | | | Inline interval arithmetic |
| `days(end - start)` | | | ✅ | Date difference functions |
| `days_since_col` | ✅ | | | Expand to `days(now() - col)` |
| `days_until_col` | ✅ | | | Expand to `days(col - now())` |
| `col::PST` timezone | | | ✅ | Map to AT TIME ZONE |
| `day of week col` | ✅ | | | Natural language extraction |
| `week_sunday()` | | | ✅ | Week start variant |
| **Data Transformation Operators** | | | | See spec.md §13, macros.md |
| `except col1, col2` | ✅ | ✅ | | Column exclusion (schema-aware) |
| `rename col as alias` | ✅ | ✅ | | Column renaming |
| `prefix name_` | ✅ | ✅ | | Column prefixing |
| `deduplicate by cols` | ✅ | | | Transform to ROW_NUMBER + filter |
| `pivot val by key` | ✅ | ✅ | ✅ | Native or CASE fallback |
| `unpivot cols into k, v` | ✅ | ✅ | ✅ | Native or UNION fallback |
| `fill col` | ✅ | ✅ | ✅ | Gap-fill with date_spine |
| `date_spine()` | | | ✅ | Table-valued function |
| `series()` | | | ✅ | Table-valued function |
| `union(t1, t2, t3)` | | | ✅ | Schema-aligned union |
| `key(col1, col2)` | | | ✅ | Surrogate key hash |
| `::type?` safe cast | | ✅ | ✅ | TRY_CAST / SAFE_CAST |
| `safe_divide(a, b)` | | | ✅ | NULL on divide-by-zero |

---

## 7. Comment Handling

### 7.1 SQLGlot's Built-in Comment Support

**Good news**: SQLGlot already preserves comments on AST nodes. This means comment handling comes "for free" with the dialect approach:

```python
import sqlglot

sql = '''
/* Table: monthly_signups */
SELECT 
    user_id,  -- primary key
    COUNT(*) AS user_count /* number of users */
FROM users
'''

parsed = sqlglot.parse_one(sql)

# Comments are attached to AST nodes
print(parsed.comments)  # [' Table: monthly_signups ']

# Walk AST to find all comments
for expr in parsed.walk():
    if hasattr(expr, 'comments') and expr.comments:
        print(f'{type(expr).__name__}: {expr.comments}')
```

### 7.2 Where Comments Fit in the Pipeline

```
ASQL text → Pre-Parser → SQLGlot Parse (comments preserved) → AST with comments → SQL
                                                                    ↓
                                                          Metadata Extraction API
```

**Key insight**: Comment handling is done AFTER parsing, on the AST. This means:
- Pre-parser: Must preserve comment tokens (not strip them)
- Tokenizer: SQLGlot's tokenizer already handles `--` and `/* */`
- Parser: SQLGlot attaches comments to nearest AST node
- Metadata extraction: Separate API on the final AST

### 7.3 Pre-Parser Comment Preservation

The pre-parser must be careful not to break comments when doing transformations:

```python
def transform_from_first(text: str) -> str:
    """Add SELECT * but preserve any leading comments."""
    
    # Find comments at start
    leading_comments = []
    rest = text.strip()
    
    while rest.startswith('--') or rest.startswith('/*'):
        if rest.startswith('--'):
            end = rest.find('\n')
            leading_comments.append(rest[:end+1])
            rest = rest[end+1:].strip()
        elif rest.startswith('/*'):
            end = rest.find('*/') + 2
            leading_comments.append(rest[:end])
            rest = rest[end:].strip()
    
    # Add SELECT * after comments
    if rest.lower().startswith('from '):
        return ''.join(leading_comments) + 'SELECT * ' + rest
    
    return text
```

### 7.4 Metadata Extraction (Post-Parse)

After parsing, ASQL provides an API to extract structured metadata from comments:

```python
import asql

# Parse ASQL (comments preserved in AST)
ast = asql.parse("""
/**
 * @name monthly_signups
 * @description Track user signups by month
 */
from users
group by month(created_at) (
    # as user_count  -- count of users
)
""")

# Extract structured metadata
metadata = asql.extract_metadata(ast)

print(metadata.name)         # "monthly_signups"
print(metadata.description)  # "Track user signups by month"
print(metadata.columns)      # {"user_count": ColumnMetadata(description="count of users")}

# Serialize to various formats
dbt_schema = metadata.to_dbt_schema()  # For schema.yml
sql_comments = metadata.to_sql_comments("analytics.signups")  # COMMENT ON statements
```

### 7.5 No Tokenizer/Parser Changes Needed

Comments are handled entirely by:
1. **SQLGlot's tokenizer** - Already recognizes `--` and `/* */`
2. **SQLGlot's parser** - Already attaches comments to AST nodes
3. **Our metadata API** - Post-parse extraction (see [comments.md](comments.md))

**Conclusion**: Comment handling is orthogonal to the dialect implementation. We get it for free from SQLGlot and add value through our metadata extraction API.

---

## 8. Pre-Parser Specification

### 8.1 Requirements

The pre-parser should be:
- **Minimal**: Only structural transformations, not expression parsing
- **Reversible**: Original ASQL should be reconstructable (for error messages)
- **Line-preserving**: Keep line numbers for error reporting
- **Fast**: Simple regex/string operations where possible

### 8.2 Transformations

#### T1: FROM-First to SELECT-FROM

```
Input:  from users where active limit 10
Output: SELECT * FROM users WHERE active LIMIT 10

Input:  from users select name, email where active
Output: SELECT name, email FROM users WHERE active
```

**Algorithm:**
1. If query starts with `from` (not `with` or `select`)
2. Find `select`/`project` clause if present
3. Move SELECT clause to front (or add `SELECT *`)

#### T2: Pipeline Operators

```
Input:  from users | where active | order by -date | limit 10
Output: SELECT * FROM users WHERE active ORDER BY date DESC LIMIT 10
```

**Algorithm:**
1. Split on `|` (respecting string literals and parens)
2. Classify each segment by leading keyword
3. Reconstruct in SQL clause order

#### T3: Aggregate Blocks

```
Input:  from sales group by region (sum amount as revenue, #)
Output: SELECT region, SUM(amount) AS revenue, COUNT(*) FROM sales GROUP BY region
```

**Algorithm:**
1. Find `group by <cols> (...)` pattern
2. Extract column list and aggregate list
3. Build SELECT from cols + aggs
4. Build GROUP BY from cols only

#### T4: Stash As

```
Input:  from users where active stash as active_users
Output: WITH active_users AS (SELECT * FROM users WHERE active) SELECT * FROM active_users
```

**Algorithm:**
1. Find `stash as <name>` at end of pipeline
2. Wrap preceding query in CTE
3. Add final SELECT from CTE

#### T5: Underscore/Space Normalization

```
Input:  day of week created_at
Output: day_of_week(created_at)

Input:  sum of revenue
Output: sum(revenue)
```

**Algorithm:**
1. Build function registry (known multi-word functions)
2. Scan for space-separated tokens
3. If tokens match function pattern, normalize to function call

#### T6: Window Utility Transformations

The `per` command and related window utilities need structural transformation:

```
Input:  per customer_id first by -order_date
Output: SELECT * FROM (
          SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) AS _rn
          FROM _prev
        ) WHERE _rn = 1

Input:  per department number by -salary as rank_num
Output: SELECT *, ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) AS rank_num
        FROM _prev
```

**Algorithm:**
1. Find `per <cols> <op> by <order>` pattern
2. Generate appropriate window function (ROW_NUMBER, RANK, DENSE_RANK)
3. For `first`/`last`, wrap in subquery with filter on row number
4. For `number`/`rank`, just add the window column

**Note**: `prior()`, `next()`, `running_sum()`, `rolling_avg()`, etc. can be handled by the Parser since they map directly to SQL window functions (LAG, LEAD, SUM OVER, etc.).

### 8.3 Pre-Parser Implementation Sketch

```python
import re
from typing import List, Tuple

class ASQLPreParser:
    """
    Pre-parse ASQL to SQLGlot-compatible syntax.
    
    Handles structural transformations that can't be done in SQLGlot's
    dialect extension model.
    """
    
    def __init__(self, text: str):
        self.text = text
        self.original = text
    
    def transform(self) -> str:
        """Apply all transformations and return SQL-like text."""
        result = self.text
        result = self._transform_pipeline(result)
        result = self._transform_per_commands(result)  # Window utilities
        result = self._transform_aggregate_blocks(result)
        result = self._transform_stash_as(result)
        result = self._transform_from_first(result)
        result = self._normalize_function_spaces(result)
        return result
    
    def _transform_pipeline(self, text: str) -> str:
        """Remove | operators, preserve clause structure."""
        # Split on | outside of strings/parens
        segments = self._split_pipeline(text)
        if len(segments) == 1:
            return text
        # Reconstruct without |
        return " ".join(seg.strip() for seg in segments)
    
    def _transform_from_first(self, text: str) -> str:
        """Add SELECT * if needed for FROM-first queries."""
        stripped = text.strip().lower()
        if not stripped.startswith("from "):
            return text
        
        # Check if SELECT already present
        if re.search(r'\bselect\b|\bproject\b', text, re.IGNORECASE):
            # Extract and move SELECT to front
            return self._reorder_select(text)
        
        # Add implicit SELECT *
        return "SELECT * " + text
    
    def _transform_aggregate_blocks(self, text: str) -> str:
        """
        Transform: group by x (agg1, agg2)
        To:        SELECT x, agg1, agg2 ... GROUP BY x
        """
        # Pattern: group by <cols> (<aggs>)
        pattern = r'group\s+by\s+([^(]+)\s*\(([^)]+)\)'
        
        def replace_agg_block(match):
            cols = match.group(1).strip()
            aggs = match.group(2).strip()
            # Return normalized form (will be combined with FROM clause)
            return f"GROUP BY {cols} SELECT_AGGS {cols}, {aggs}"
        
        return re.sub(pattern, replace_agg_block, text, flags=re.IGNORECASE)
    
    def _transform_stash_as(self, text: str) -> str:
        """
        Transform: ... stash as name
        To:        WITH name AS (...) SELECT * FROM name
        """
        pattern = r'^(.+?)\s+stash\s+as\s+(\w+)\s*$'
        match = re.match(pattern, text.strip(), re.IGNORECASE | re.DOTALL)
        if match:
            query = match.group(1)
            name = match.group(2)
            return f"WITH {name} AS ({query}) SELECT * FROM {name}"
        return text
    
    def _split_pipeline(self, text: str) -> List[str]:
        """Split on | respecting strings and parentheses."""
        segments = []
        current = []
        depth = 0
        in_string = None
        
        i = 0
        while i < len(text):
            char = text[i]
            
            # String handling
            if char in ('"', "'") and (i == 0 or text[i-1] != '\\'):
                if in_string == char:
                    in_string = None
                elif in_string is None:
                    in_string = char
            
            # Parentheses
            if in_string is None:
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
                elif char == '|' and depth == 0:
                    segments.append(''.join(current))
                    current = []
                    i += 1
                    continue
            
            current.append(char)
            i += 1
        
        if current:
            segments.append(''.join(current))
        
        return segments
```

---

## 9. Migration Path

### 9.1 Phase 1: Pre-Parser + Current System

1. Implement `ASQLPreParser` for structural transformations
2. Feed transformed text to current custom parser
3. Validate output matches current behavior
4. **No risk**: Old parser still works as fallback

### 9.2 Phase 2: ASQL Dialect for Expressions

1. Implement `ASQLTokenizer` for new tokens
2. Implement `ASQLParser` for expression-level parsing
3. Replace expression parsing in custom parser with SQLGlot calls
4. **Gradual**: Replace one expression type at a time

### 9.3 Phase 3: Full SQLGlot Integration

1. Pre-parser produces SQL-like text
2. SQLGlot parses with ASQL dialect
3. Custom parser eliminated
4. **Goal**: ~200 lines of pre-parser + ~300 lines of dialect

---

## 10. Benefits of This Approach

### 10.1 Code Reduction

| Component | Current | Proposed |
|-----------|---------|----------|
| Custom parser | ~2000 lines | 0 |
| Pre-parser | 0 | ~200-300 lines |
| Dialect extensions | 0 | ~200-300 lines |
| **Total** | ~2000 lines | ~400-600 lines |

### 10.2 Leveraged SQLGlot Features

- **Expression parsing**: Arithmetic, comparisons, function calls
- **Precedence handling**: Operator precedence rules
- **Nested expressions**: Parentheses, subqueries
- **Dialect output**: Automatic translation to target dialects
- **Error messages**: SQLGlot's parsing error infrastructure
- **AST manipulation**: Transform, walk, find methods

### 10.3 Maintenance Benefits

- SQLGlot updates automatically improve ASQL
- New SQL features available with minimal work
- Dialect-specific behaviors handled automatically
- Community-tested parsing infrastructure

---

## 11. Risks and Mitigations

### 11.1 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Pre-parser complexity grows | Medium | High | Keep pre-parser minimal, push complexity to dialect |
| SQLGlot API changes | Low | Medium | Pin version, gradual updates |
| Performance regression | Low | Low | Pre-parser is simple string ops |
| Feature gaps | Medium | Medium | Fallback to custom parsing for edge cases |

### 11.2 Decision Points

Before full commitment, validate:
1. Can `group by (aggs)` be cleanly transformed?
2. Can underscore/space flexibility work with SQLGlot tokenizer?
3. Can error messages map back to original ASQL?

---

## 12. Appendix: SQLGlot Dialect Examples

### BigQuery Dialect (for reference)

```python
# From sqlglot/dialects/bigquery.py
class BigQuery(Dialect):
    class Tokenizer(Tokenizer):
        KEYWORDS = {
            **Tokenizer.KEYWORDS,
            "INT64": TokenType.BIGINT,
            "FLOAT64": TokenType.DOUBLE,
            "STRUCT": TokenType.STRUCT,
        }
    
    class Parser(Parser):
        FUNCTION_PARSERS = {
            **Parser.FUNCTION_PARSERS,
            "ARRAY_AGG": lambda self: self._parse_array_agg(),
        }
```

### ClickHouse Dialect (for reference)

```python
# From sqlglot/dialects/clickhouse.py  
class ClickHouse(Dialect):
    class Tokenizer(Tokenizer):
        SINGLE_TOKENS = {
            **Tokenizer.SINGLE_TOKENS,
            "$": TokenType.PARAMETER,
        }
    
    class Parser(Parser):
        FUNCTIONS = {
            **Parser.FUNCTIONS,
            "ARGMAX": exp.ArgMax.from_arg_list,
            "ARGMIN": exp.ArgMin.from_arg_list,
        }
```

---

## 13. SPEC.md Updates ✅ COMPLETED

The following changes have been made to `docs/spec.md`:

| Change | Status |
|--------|--------|
| `=` as primary equality (also accept `==`) | ✅ Done |
| `??` for COALESCE (not `\|\|`) | ✅ Done |
| `set` for CTEs (not `with x = ...`) | ✅ Done |
| `order by` (not `sort`) | ✅ Done |
| `limit` (not `take`) | ✅ Done |

**Rationale for `??` over `||`:**
- JavaScript uses `??` for nullish coalescing (not `||`)
- `||` in SQL is string concatenation in most dialects
- `??` can also be used for safe casting: `col??int` (cast, return NULL on failure)
- Avoids confusion with logical OR

**Rationale for standard SQL keywords:**
- SQL users already know `ORDER BY` and `LIMIT`
- No value in learning `sort` and `take` aliases
- Reduces cognitive load
- `sort` would need `sort by` for consistency anyway

---

## 14. Next Steps

1. **Prototype pre-parser** for:
   - FROM-first → `SELECT * FROM ...`
   - Pipeline `|` removal
   - Natural aggregates: `sum amount` → `sum(amount)`
   - `group by (aggs)` extraction
   - `stash as` → CTE wrapping
2. **Test with existing ASQL examples** to validate transformation correctness
3. **Implement ASQLTokenizer** for `#`, `@`, `??`
4. **Implement ASQLParser** for `order by -col` DESC indicator
5. **Benchmark** against current parser for performance
6. **Gradual migration** following the phase plan

---

## 15. Open Questions

1. **Error mapping**: How to report errors in terms of original ASQL line numbers?
2. **Round-trip**: Should we support ASQL → SQL → ASQL conversion?
3. **IDE support**: Will pre-parsing affect language server features?
4. **Testing**: How to test pre-parser transformations in isolation?

---

*This document is a living analysis. Update as implementation progresses.*

