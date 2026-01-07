# ASQL User-Defined Functions: Design Document

**Date**: January 6, 2026  
**Status**: Proposal  
**Context**: Addressing the composability gap identified in PRQL comparison  
**GitHub Issue**: [#126](https://github.com/davefowler/asql/issues/126)

---

## TL;DR

Add `let` (variables) and `func` (functions) to ASQL. Use **one unified `func` keyword** for both scalar expressions and pipeline transforms — context determines behavior, just like PRQL. Technically these are compile-time macros, but we call them "functions" for user-friendliness.

---

## The Problem

PRQL's analysis of ASQL identified a critical gap:

> "ASQL has no equivalent. Their `stash as` only creates CTEs, not reusable expressions. **This is our core advantage.** ASQL users will hit a wall when they need to reuse logic across queries."

PRQL has:
```prql
func fiscal_year date -> (date + 6m) | year

let threshold = 1000

from orders
filter amount > threshold
derive fy = fiscal_year order_date
```

ASQL currently has **no way to**:
1. Define reusable expressions (`let threshold = 1000`)
2. Define reusable transformations (`func fiscal_year date -> ...`)
3. Share logic across queries without copy-paste

This limits ASQL to "convenience features" rather than being a truly composable language.

---

## Prior Art: How Others Handle This

### PRQL: Native Language Constructs

PRQL has first-class `func` and `let`:

```prql
# Variable binding
let tax_rate = 0.08

# Function definition (expression → expression)
func net_revenue amount -> amount - (amount * tax_rate)

# Function with pipeline (table → table)
func add_revenue_metrics -> (
  derive {
    gross = price * quantity,
    net = net_revenue (price * quantity)
  }
)

from orders
add_revenue_metrics
```

**Pros**: Clean, native syntax. No external dependencies.
**Cons**: Requires parser/compiler changes. Another thing to learn.

### SQLMesh: Python Macros

SQLMesh uses Python decorators:

```python
# macros/analytics.py
from sqlmesh import macro

@macro()
def fiscal_year(evaluator, date_col):
    """Returns fiscal year (starts July 1)"""
    return f"YEAR({date_col} + INTERVAL 6 MONTH)"

@macro()
def add_audit_columns(evaluator):
    return """
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    """

@macro()
def safe_divide(evaluator, numerator, denominator, default="NULL"):
    return f"CASE WHEN {denominator} = 0 THEN {default} ELSE {numerator} / {denominator} END"
```

Usage in SQL:
```sql
SELECT 
    @fiscal_year(order_date) as fy,
    @safe_divide(revenue, users, 0) as revenue_per_user
FROM orders
```

**Pros**: Full Python power. IDE support. Type hints. Testing.
**Cons**: Two languages. Requires Python knowledge.

### dbt: Jinja Macros

```jinja
{% macro safe_divide(numerator, denominator, default=0) %}
  CASE WHEN {{ denominator }} = 0 THEN {{ default }} 
       ELSE {{ numerator }} / {{ denominator }} END
{% endmacro %}
```

**Pros**: Widely adopted. Familiar to dbt users.
**Cons**: String manipulation. No type safety. Hard to debug.

### SQLGlot: Transform API

SQLGlot can transform AST nodes:

```python
import sqlglot
from sqlglot import exp

def transform_fiscal_year(node):
    """Transform fiscal_year(date) → YEAR(date + INTERVAL 6 MONTH)"""
    if isinstance(node, exp.Anonymous) and node.name == "fiscal_year":
        date_arg = node.expressions[0]
        return exp.Year(
            this=exp.Add(
                this=date_arg,
                expression=exp.Interval(this=exp.Literal.number(6), unit=exp.Var(this="MONTH"))
            )
        )
    return node

sql = "SELECT fiscal_year(order_date) FROM orders"
tree = sqlglot.parse_one(sql)
transformed = tree.transform(transform_fiscal_year)
print(transformed.sql())
# SELECT YEAR(order_date + INTERVAL 6 MONTH) FROM orders
```

**Pros**: Full AST manipulation. Type-safe transformations.
**Cons**: Requires Python. Complex for simple cases.

---

## Design Options for ASQL

### Option A: Native ASQL Syntax (PRQL-style)

Add `let` and `func` as first-class ASQL constructs:

```asql
# Variable binding
let threshold = 1000
let tax_rate = 0.08

# Expression function (returns a scalar expression)
func fiscal_year(date) = year(date + 6 months)
func net_amount(amount) = amount * (1 - tax_rate)
func safe_divide(a, b) = when b = 0 then null otherwise a / b

# Usage
from orders
where amount > threshold
select 
  order_id,
  fiscal_year(order_date) as fy,
  net_amount(amount) as net
```

**Table functions** (returns a transformation):
```asql
# Transform function (pipeline → pipeline)
func with_revenue_metrics = (
  select *,
    price * quantity as gross_revenue,
    net_amount(price * quantity) as net_revenue
)

func dedup_events = (
  deduplicate by user_id, event_type
  order by -timestamp
)

# Usage
from orders
with_revenue_metrics
order by -gross_revenue

from events
dedup_events
```

**Pros**:
- ✅ Native ASQL syntax
- ✅ Single language to learn
- ✅ Clear, concise
- ✅ Composable

**Cons**:
- ❌ Parser complexity
- ❌ Scope management
- ❌ Limited to what ASQL can express

**Implementation Complexity**: High

---

### Option B: Python Macros (SQLMesh-style)

ASQL-specific Python decorators:

```python
# asql_functions/analytics.py
from asql import func, table_func

@func
def fiscal_year(date):
    """Fiscal year starting July 1"""
    return f"year({date} + 6 months)"

@func  
def safe_divide(numerator, denominator, default=0):
    """Division that returns default instead of error on zero"""
    return f"when {denominator} = 0 then {default} otherwise {numerator} / {denominator}"

@table_func
def with_audit_columns():
    """Add standard audit columns"""
    return """
        select *,
          now() as created_at,
          now() as updated_at
    """

@table_func
def dedupe_on(*key_cols, order_by="-updated_at"):
    """Deduplicate by keys, keeping row with given ordering"""
    keys = ", ".join(key_cols)
    return f"deduplicate by {keys} order by {order_by}"
```

Usage in ASQL:
```asql
-- Uses functions from asql_functions/
from orders
select 
  order_id,
  @fiscal_year(order_date) as fy,
  @safe_divide(revenue, users) as rpu
@with_audit_columns
```

Or with Python-style call syntax:
```asql
from orders
select 
  order_id,
  fiscal_year(order_date) as fy,
  safe_divide(revenue, users) as rpu
with_audit_columns()
```

**Pros**:
- ✅ Full Python power
- ✅ IDE support (autocomplete, type hints)
- ✅ Easy testing
- ✅ Familiar to SQLMesh users
- ✅ SQLGlot native (can return AST)

**Cons**:
- ❌ Two languages
- ❌ Requires Python runtime
- ❌ Less accessible to SQL-only users

**Implementation Complexity**: Medium

---

### Option C: Hybrid Approach (Recommended)

Combine native ASQL for simple cases with Python for complex logic.

#### Level 1: Native `let` for Variables

Simple variable bindings in ASQL:

```asql
let threshold = 1000
let start_date = @2024-01-01
let tax_rate = 0.08

from orders
where amount > threshold
  and order_date >= start_date
select amount * (1 - tax_rate) as net_amount
```

**Implementation**: 
- Preparser substitutes `threshold` → `1000` before compilation
- Similar to C preprocessor `#define` but with ASQL expressions
- Scope: file-level or block-level (TBD)

#### Level 2: Native `func` for Simple Expressions

Expression-level functions in ASQL:

```asql
func fiscal_year(d) = year(d + 6 months)
func net(amount, rate) = amount * (1 - rate)

from orders
select 
  fiscal_year(order_date) as fy,
  net(amount, 0.08) as net_amount
```

**Implementation**:
- Preparser expands `fiscal_year(order_date)` → `year(order_date + 6 months)`
- Arguments are substituted positionally
- No runtime evaluation, pure text/AST substitution

#### Level 3: Python `@func` for Complex Logic

When you need conditionals, loops, or database introspection:

```python
# asql_functions/custom.py
from asql import func

@func
def fiscal_quarter(date_col):
    """Returns fiscal quarter (Q1 starts July)"""
    # Complex logic that's hard in pure ASQL
    return f"""
        when month({date_col}) >= 7 and month({date_col}) <= 9 then 'Q1'
        when month({date_col}) >= 10 and month({date_col}) <= 12 then 'Q2'
        when month({date_col}) >= 1 and month({date_col}) <= 3 then 'Q3'
        otherwise 'Q4'
    """
```

#### Level 4: Python `@table_func` for Transformations

Pipeline-level functions for reusable patterns:

```python
from asql import table_func

@table_func
def top_n_per_group(n: int, group_col: str, order_col: str):
    """Keep top N rows per group"""
    return f"""
        per {group_col} number by -{order_col} as _rank
        where _rank <= {n}
        except _rank
    """
```

Usage:
```asql
from orders
@top_n_per_group(5, "customer_id", "amount")
```

---

## Key Insight: One Unified `func` Keyword

### How PRQL and SQLMesh Handle This

Both PRQL and SQLMesh use **one keyword** for all function types. They don't require separate syntax for scalar vs table functions:

**PRQL:**
```prql
# Scalar function (returns expression)
let add_tax = rate val -> val * (1 + rate)

# Table function (returns pipeline)  
let take_latest = rel -> (
  rel
  sort {-date}
  take 1
)

# Usage - PRQL infers the type from context
from orders
derive total = (add_tax 0.08 amount)  # scalar
take_latest                            # table transform
```

**SQLMesh:**
```python
# Same @macro for everything - context determines meaning
@macro()
def safe_divide(evaluator, num, denom):
    return f"CASE WHEN {denom} = 0 THEN NULL ELSE {num}/{denom} END"

@macro()
def add_audit_columns(evaluator):
    return "created_at TIMESTAMP, updated_at TIMESTAMP"
```

### ASQL Should Follow This Pattern

**No separate `func` vs `table_func` vs `command`:**

```asql
# Scalar - body is an expression
func fiscal_year(d) = year(d + 6 months)

# Table - body is a pipeline (starts with select/where/etc)
func with_audit = (
  select *,
    now() as created_at,
    now() as updated_at
)

# Usage
from orders
select fiscal_year(order_date)   # scalar
with_audit                        # table transform
```

**The rule is simple:**
- If body is `(pipeline...)` → table function
- If body is `expression` → scalar function

### Terminology: "Functions" Not "Macros"

Technically, these are **compile-time macros** (text/AST substitution). But we call them "functions" because:

1. **User mental model**: Analysts think in functions, not macros
2. **PRQL precedent**: They call theirs `func`, it's intuitive
3. **Less intimidating**: "Macro" sounds advanced/scary
4. **Future-proof**: If we add types later, "function" fits

| What it IS | What we CALL it | Why |
|------------|-----------------|-----|
| Compile-time substitution | `func` | User-friendly |
| Variable binding | `let` | Familiar from JS/PRQL |

**For Python extension (if needed):**
```python
from asql import func  # Not "from asql.macros import macro"

@func
def safe_divide(num, denom):
    return f"when {denom} = 0 then null otherwise {num} / {denom}"
```

---

## Recommended Implementation Plan

### Phase 1: `let` Variables (Low Effort, High Value)

**Goal**: Enable reusable constants/expressions within a file.

**Syntax**:
```asql
let threshold = 1000
let active_status = 'active'
let last_year = year(today()) - 1

from users
where signup_year = last_year
  and status = active_status
  and lifetime_value > threshold
```

**Implementation**:
1. Add to preparser: detect `let name = expression` at file start
2. Build substitution map: `{name: expression}`
3. Replace all occurrences of `name` with `expression`
4. Handle scoping: file-level only (simplest)

**Edge cases**:
- `let` inside queries: Not allowed (file-level only)
- Shadowing: Later `let` overrides earlier (or error?)
- Circular references: Error

**Effort**: ~2-3 days

### Phase 2: Simple `func` (Medium Effort, High Value)

**Goal**: Enable reusable expression functions.

**Syntax**:
```asql
func fiscal_year(d) = year(d + 6 months)
func net(amount, rate = 0.08) = amount * (1 - rate)

from orders
select fiscal_year(order_date), net(amount)
```

**Implementation**:
1. Parse function definitions: `func name(args) = expression`
2. Store in function registry: `{name: (args, expression)}`
3. When parsing query, recognize function calls
4. Substitute: replace call with expression, args with actual values

**Example expansion**:
```
fiscal_year(order_date)
→ year(order_date + 6 months)

net(amount, 0.10)
→ amount * (1 - 0.10)

net(amount)  # default rate
→ amount * (1 - 0.08)
```

**Edge cases**:
- Default arguments: Support `func f(a, b = 10)`
- Nested calls: `fiscal_year(date_add(d, 1))` - substitute innermost first
- Recursion: Not supported (or limited depth?)

**Effort**: ~1 week

### Phase 3: Python `@func` Decorators (Medium Effort, High Value)

**Goal**: Enable complex functions in Python.

**Syntax**:
```python
# asql_funcs.py (or any module)
from asql.macros import func, table_func

@func
def safe_divide(num, denom, default="null"):
    return f"when {denom} = 0 then {default} otherwise {num} / {denom}"
```

```asql
-- asql.funcs = ['./asql_funcs.py']
from orders
select @safe_divide(revenue, users, 0) as rpu
```

**Implementation**:
1. Add configuration for function module paths
2. Load Python modules, discover `@func` decorated functions
3. Build function registry (same as Phase 2)
4. When parsing `@func_name(args)`, call Python function
5. Python returns ASQL snippet, which gets inserted

**Key decisions**:
- Call syntax: `@func_name()` vs `func_name()` vs `$func_name()`
- Discovery: Explicit config vs auto-discover in `asql_funcs/`
- Return type: String (ASQL) vs SQLGlot AST

**Effort**: ~1-2 weeks

### Phase 4: Table Functions (Higher Effort)

**Goal**: Enable reusable pipeline transformations.

**Syntax (native)**:
```asql
func with_metrics = (
  select *,
    sum(amount) over (partition by customer_id) as lifetime_value,
    row_number() over (partition by customer_id order by -created_at) as recency_rank
)

from orders
with_metrics
where recency_rank = 1
```

**Syntax (Python)**:
```python
@table_func
def dedupe(*keys, keep="-updated_at"):
    return f"deduplicate by {', '.join(keys)} order by {keep}"
```

```asql
from events
@dedupe("user_id", "event_type")
```

**Implementation**:
- Table functions are "pipeline snippets"
- Inserted inline where called
- Can have parameters

**Effort**: ~2 weeks

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     ASQL Query File                         │
│                                                             │
│  let threshold = 1000                                       │
│  func fy(d) = year(d + 6 months)                           │
│                                                             │
│  from orders                                                │
│  where amount > threshold                                   │
│  select fy(order_date) as fiscal_year                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Function Preprocessor                      │
│                                                             │
│  1. Extract `let` bindings                                  │
│  2. Extract `func` definitions                              │
│  3. Load Python `@func` modules                             │
│  4. Build unified function registry                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Function Expander                          │
│                                                             │
│  1. Find function calls in query                            │
│  2. Expand each call with arguments                         │
│  3. Handle nested calls (inside-out)                        │
│  4. Substitute `let` variables                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Expanded ASQL Query                        │
│                                                             │
│  from orders                                                │
│  where amount > 1000                                        │
│  select year(order_date + 6 months) as fiscal_year         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               Existing ASQL Preparser                        │
│               (transforms → SQL-like)                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               SQLGlot Compilation                            │
│               (SQL-like → target dialect)                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Does SQLGlot Support This?

**Short answer**: SQLGlot provides the building blocks, but ASQL needs to build the function system.

**What SQLGlot provides**:
1. **Custom dialects** — Can add custom functions to parser
2. **Transform API** — Can rewrite AST nodes
3. **Expression building** — Can construct SQL expressions programmatically

**What ASQL needs to build**:
1. **Function registry** — Store function definitions
2. **Expansion logic** — Replace calls with definitions
3. **Scope management** — Handle variable binding
4. **Python integration** — Load/call Python functions

**Example of SQLGlot function registration**:
```python
from sqlglot import exp
from sqlglot.dialects import Dialect

class AsqlDialect(Dialect):
    class Parser(Dialect.Parser):
        FUNCTIONS = {
            **Dialect.Parser.FUNCTIONS,
            "FISCAL_YEAR": lambda args: exp.Year(
                this=exp.Add(
                    this=args[0],
                    expression=exp.Interval(this=exp.Literal.number(6), unit="MONTH")
                )
            ),
        }
```

This approach registers `FISCAL_YEAR` as a function that SQLGlot's parser understands. However, for dynamic user-defined functions, we need the preprocessing approach described above.

---

## Open Questions

### 1. Call Syntax
How should function calls look?

| Option | Example | Pros | Cons |
|--------|---------|------|------|
| Bare | `fiscal_year(d)` | Clean, natural | Conflicts with SQL functions |
| `@` prefix | `@fiscal_year(d)` | Clear it's custom | Extra character |
| `$` prefix | `$fiscal_year(d)` | Familiar (Jinja) | Unusual in SQL |

**Recommendation**: Bare for ASQL-defined, `@` for Python-defined.

### 2. Scope Rules
Where can `let` and `func` be defined?

| Option | Description |
|--------|-------------|
| File-level only | Simplest. Defined at top, used anywhere in file. |
| Block-level | Can define inside CTEs/subqueries. More complex. |
| Global/project | Shared across files. Requires import system. |

**Recommendation**: Start with file-level only.

### 3. Import System
How do you share functions across files?

```asql
# Option A: Import statement
import "./common_funcs.asql"

# Option B: Config file
# asql.config.yaml
# function_files: ["./common/", "./team_funcs.asql"]

# Option C: Python-only for sharing
# Share Python @func modules
```

**Recommendation**: Start with Python for shared functions, add import later.

### 4. Type Safety
Should functions have type annotations?

```asql
func fiscal_year(d: date) -> int = year(d + 6 months)
```

**Recommendation**: No for v1. Add later if needed.

---

## Implementation Priority

| Phase | Feature | Effort | Value | Dependencies |
|-------|---------|--------|-------|--------------|
| **1** | `let` variables | 2-3 days | High | None |
| **2** | Simple `func` | 1 week | Very High | Phase 1 |
| **3** | Python `@func` | 1-2 weeks | High | Phase 2 |
| **4** | Table functions | 2 weeks | Medium | Phase 2 |
| **5** | Import system | 1 week | Medium | Phase 2 |

---

## Success Criteria

After implementation, this PRQL code:

```prql
func fiscal_year date -> (date + 6m) | year
let threshold = 1000

from orders
filter amount > threshold
derive fy = fiscal_year order_date
```

Should have an ASQL equivalent:

```asql
func fiscal_year(d) = year(d + 6 months)
let threshold = 1000

from orders
where amount > threshold
select *, fiscal_year(order_date) as fy
```

And the gap identified by PRQL ("ASQL users will hit a wall when they need to reuse logic") will be closed.

---

## References

- [PRQL Functions](https://prql-lang.org/book/reference/syntax/functions.html)
- [SQLMesh Macros](https://sqlmesh.readthedocs.io/en/stable/concepts/macros/)
- [SQLGlot Transform API](https://github.com/tobymao/sqlglot#rewriting-sql)
- [ASQL-PRQL Comparison](../research/2026-01-06-asql-from-prql-perspective.md)
- [ASQL Preparser Architecture](../../asql/preparse/preparser.py)

