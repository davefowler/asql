# PRQL vs ASQL Implementation Comparison

**Date**: 2026-01-08

## Executive Summary

| Metric | PRQL | ASQL | Notes |
|--------|------|------|-------|
| **Total compiler LOC** | 40,689 (Rust) | 11,085 (Python) | PRQL is ~3.7x larger |
| **Parser LOC** | 8,726 | 3,144 | PRQL uses Chumsky, ASQL uses SQLGlot |
| **Semantic analysis LOC** | 7,048 | ~500 | PRQL has full type system |
| **SQL backend LOC** | 7,063 | 4,385 | Similar complexity |
| **Language** | Rust | Python | Performance vs. flexibility |

## Architecture Comparison

### PRQL Pipeline (6 stages)
```
PRQL Source
    ↓ Lexer (Chumsky)
Lexer Representation (LR)
    ↓ Parser (Chumsky)
Parser Representation (PR)
    ↓ AST Expand
Pipelined Language (PL)
    ↓ Resolver (type checking, name resolution)
PL (resolved)
    ↓ Lowering
Resolved Query (RQ)
    ↓ SQL Compiler
sqlparser::ast → SQL string
```

### ASQL Pipeline (3 stages)
```
ASQL Source
    ↓ SQLGlot ASQL Dialect
SQLGlot AST
    ↓ Compiler Transforms
SQLGlot AST (transformed)
    ↓ SQLGlot Generator
SQL string
```

**Key Insight**: ASQL leverages SQLGlot's existing infrastructure, eliminating the need for:
- Custom lexer (~2,000 LOC in PRQL)
- Custom parser combinator (~6,000 LOC in PRQL)
- Full semantic analysis (~7,000 LOC in PRQL)
- Custom SQL AST (~3,000 LOC in PRQL)

## Feature-by-Feature Comparison

### 1. Parsing

| Aspect | PRQL | ASQL |
|--------|------|------|
| **Tool** | Chumsky (parser combinator) | SQLGlot (SQL parser framework) |
| **Lexer** | Custom (~2,600 LOC) | SQLGlot Tokenizer + custom tokens |
| **Parser** | Custom (~6,000 LOC) | SQLGlot Parser + TRANSFORM_PARSERS |
| **Error messages** | Custom error formatting | SQLGlot's error system |

**PRQL Approach** (lexer/mod.rs):
```rust
// Custom token definitions
pub enum TokenKind {
    NewLine,
    Ident(String),
    Keyword(String),
    Literal(Literal),
    // ... 30+ token types
}
```

**ASQL Approach** (dialect.py):
```python
class ASQLTokenizer(Tokenizer):
    KEYWORDS = {**Tokenizer.KEYWORDS, "STASH": TokenType.STASH, ...}
    SINGLE_TOKENS = {**Tokenizer.SINGLE_TOKENS, "|": TokenType.PIPE_GT, ...}
```

**Verdict**: ASQL's approach is ~75% less code by reusing SQLGlot.

### 2. Standard Library / Functions

| Aspect | PRQL | ASQL |
|--------|------|------|
| **Definition** | `std.prql` (~250 lines) | `functions.py` (~550 lines) |
| **Format** | PRQL syntax with `internal` markers | Python with SQLGlot builders |
| **Type annotations** | Yes (`-> <type>`) | No |
| **Modules** | Yes (`module math { ... }`) | No |

**PRQL Approach** (std.prql):
```prql
let sum = column <array> -> internal std.sum
let average = column <array> -> internal std.average
module math {
  let abs = column -> internal std.math.abs
  let floor = column -> <int> internal std.math.floor
}
```

**ASQL Approach** (functions.py):
```python
def build_running_agg(agg_class: type) -> Callable:
    def builder(args: list) -> exp.Expression:
        return exp.Window(this=agg_class(this=args[0]), ...)
    return builder

ASQL_FUNCTION_REGISTRY = {
    "running_sum": build_running_agg(exp.Sum),
    "running_avg": build_running_agg(exp.Avg),
}
```

**Verdict**: PRQL's approach is cleaner for users to understand. ASQL could benefit from a declarative function definition format.

### 3. Type System

| Aspect | PRQL | ASQL |
|--------|------|------|
| **Type checking** | Full (~7,000 LOC) | None |
| **Type inference** | Yes | No |
| **Column tracking** | Yes (frames) | No |

**PRQL has**:
- Type primitives: `int`, `float`, `bool`, `text`, `date`, `time`, `timestamp`
- Generic types: `array`, `relation`, `range`, `transform`
- Type annotations on function parameters and returns
- Frame inference (tracking columns through pipeline)

**ASQL has**:
- No type system
- Relies on SQLGlot's AST types
- Runtime errors from database

**Verdict**: PRQL's type system catches errors earlier but adds significant complexity. For ASQL's target audience (analysts), runtime errors may be acceptable.

### 4. Dialect Handling

| Aspect | PRQL | ASQL |
|--------|------|------|
| **Dialect definition** | `dialect.rs` (~750 LOC) | SQLGlot's dialect system |
| **Feature flags** | Custom trait system | SQLGlot's `Dialect` class |
| **SQL generation** | `sqlparser` crate | SQLGlot generator |

**PRQL Approach** (dialect.rs):
```rust
pub trait DialectHandler: Debug + DynClone {
    fn column_exclude(&self) -> Option<ColumnExclude> { None }
    fn ident_quoting_style(&self) -> IdentQuotingStyle { ... }
    fn requires_order_by_in_window_function(&self) -> bool { false }
    // ... 15+ methods
}
```

**ASQL Approach**:
```python
# Leverages SQLGlot's existing dialect system
from sqlglot.dialects import Dialect
sql_dialect = Dialect.get_or_raise(dialect)
stmt.sql(dialect=sql_dialect)
```

**Verdict**: ASQL benefits from SQLGlot's mature dialect support (20+ dialects).

### 5. Window Functions

| Aspect | PRQL | ASQL |
|--------|------|------|
| **Syntax** | `window rows:0..-1 (derive ...)` | `running_sum(col)`, `rolling_avg(col, 7)` |
| **Implementation** | ~500 LOC in semantic + SQL | ~100 LOC in functions.py |

**PRQL Approach**:
```prql
from employees
window rows:0..0 (
  derive cumulative_salary = sum salary
)
```

**ASQL Approach**:
```sql
from employees
  select running_sum(salary) as cumulative_salary
```

**Verdict**: ASQL's function-based approach is simpler but less flexible. PRQL's `window` transform is more powerful.

### 6. Joins

| Aspect | PRQL | ASQL |
|--------|------|------|
| **Syntax** | `join side:left table (condition)` | `&? table on condition` |
| **Implementation** | ~200 LOC | ~150 LOC |

**PRQL**:
```prql
from employees
join side:left d=departments (employees.dept_id == d.id)
```

**ASQL**:
```sql
from employees
  &? departments on dept_id
```

**Verdict**: Both are concise. ASQL's symbolic operators (`&`, `&?`, `?&`) are more terse.

## What PRQL Does Better

### 1. **Declarative Standard Library**
PRQL's `std.prql` is self-documenting and user-readable. Functions are defined in PRQL syntax itself.

**Recommendation for ASQL**: Consider a declarative function definition format:
```yaml
# functions.yaml
running_sum:
  args: [column]
  returns: window(sum(column), rows: unbounded..current)
  aliases: [cumsum]
```

### 2. **Module System**
PRQL has `module math { ... }` for organizing functions.

**Recommendation for ASQL**: Group functions logically:
```python
# Instead of flat ASQL_FUNCTION_REGISTRY
MATH_FUNCTIONS = {"abs": ..., "floor": ..., "ceil": ...}
TEXT_FUNCTIONS = {"lower": ..., "upper": ..., "trim": ...}
DATE_FUNCTIONS = {"days_since": ..., "months_until": ...}
```

### 3. **Type Annotations**
PRQL functions have explicit types: `let sum = column <array> -> internal std.sum`

**Recommendation for ASQL**: Add type hints to function builders:
```python
def sum_agg(column: exp.Column) -> exp.Sum:
    """Aggregate sum of column values."""
    return exp.Sum(this=column)
```

### 4. **Comprehensive Test Snapshots**
PRQL uses snapshot testing extensively (~52,000 lines in test.rs files).

**Recommendation for ASQL**: Adopt snapshot testing for SQL output verification.

## What ASQL Does Better

### 1. **Leveraging SQLGlot**
ASQL saves ~30,000 LOC by using SQLGlot instead of building custom infrastructure.

### 2. **SQL Compatibility**
ASQL can parse and transform standard SQL, making migration easier.

### 3. **Simpler Mental Model**
No type system = less to learn for analysts.

### 4. **Symbolic Join Operators**
`&`, `&?`, `?&`, `?&?` are more concise than `join side:left/right/inner/outer`.

## Recommendations for ASQL Cleanup

### ✅ Completed (2026-01-08)

1. **Simplified TRANSFORM_PARSERS join methods**
   - Consolidated 8 functions (63 LOC) → 2 functions (7 LOC)
   - Now uses `_parse_join_kind()` helper with inline lambdas

2. **Converted recurse to pure AST**
   - Eliminated string SQL building: `f"SELECT *, 1 AS _level FROM..."` 
   - Now uses `exp.select()`, `exp.Union()`, `exp.CTE()` directly

3. **Simplified FK shorthand**
   - Reduced 83 LOC → 62 LOC
   - Added schema-aware FK/PK detection

### High Priority (Remaining)

1. **Convert `auto_spine.py` to pure AST** (1,287 LOC with ~350 lines of string SQL)
   - 7 `_build_*_sql` functions still use f-strings
   - Should use `exp.Unnest`, `exp.GenerateSeries` etc.
   - Highest LOC savings opportunity

2. **Split `dialect.py` (3,120 LOC)**
   - Extract `tokenizer.py` (~200 LOC)
   - Extract `transform_parsers.py` (~800 LOC)
   - Extract `function_parsers.py` (~500 LOC)
   - Keep core parser in `dialect.py` (~1,600 LOC)

3. **Reduce compiler transform count**
   - Current: 15+ transforms in `compile()`
   - Consider combining related transforms

### Medium Priority

4. **Add snapshot testing**
   - Create `tests/snapshots/` directory
   - Test SQL output for all playground examples

5. **Document function coverage**
   - Create matrix of functions × dialects
   - Mark unsupported combinations

6. **Simplify `_split_multistatement_blocks`**
   - Currently 50+ LOC for statement splitting
   - Consider using SQLGlot's built-in statement splitting

### Low Priority

7. **Consider declarative function definitions**
   - YAML or similar format
   - Auto-generate Python code

8. **Add optional type hints**
   - Not for runtime checking
   - For documentation and IDE support

## LOC Breakdown

### PRQL (Rust)
```
prqlc-parser/        8,726 lines
  lexer/             2,600
  parser/            6,126

prqlc/src/          31,963 lines
  semantic/          7,048
  sql/               7,063
  ir/                5,000 (estimated)
  cli/               2,000 (estimated)
  other/            10,852

Total:              40,689 lines
```

### ASQL (Python)
```
asql/               11,085 lines
  dialect.py         3,144
  compiler/          4,385
  functions.py         550
  config.py            400
  reverse_compiler.py  850
  schema.py            850
  other/               906

Total:              11,085 lines
```

## Conclusion

ASQL achieves similar functionality to PRQL with **~27% of the code** by leveraging SQLGlot. The tradeoffs are:

| PRQL Advantage | ASQL Advantage |
|----------------|----------------|
| Type safety | Simpler codebase |
| Better error messages | SQL compatibility |
| Self-documenting stdlib | Faster development |
| Module system | More dialects supported |

For ASQL's target audience (data analysts), the simpler approach is likely the right choice. The main areas for improvement are code organization (splitting `dialect.py`) and documentation (function coverage matrix).

