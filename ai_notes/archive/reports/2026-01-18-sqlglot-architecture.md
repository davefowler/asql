# SQLGlot Architecture Deep Dive

**Date**: 2026-01-18
**Purpose**: Understanding SQLGlot's pipeline for ASQL integration decisions

## Core Pipeline

SQLGlot has a 3-stage pipeline, but **transpile() only uses 2 stages**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SQLGlot Pipeline                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐              │
│  │   PARSER     │ ───► │  OPTIMIZER   │ ───► │  GENERATOR   │              │
│  │              │      │  (OPTIONAL)  │      │              │              │
│  └──────────────┘      └──────────────┘      └──────────────┘              │
│                                                                             │
│   Text → AST            AST → AST             AST → Text                   │
│   dialect=READ          dialect=TARGET        dialect=WRITE                │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  transpile() uses:      PARSE ──────────────────────────► GENERATE         │
│                         (skips optimizer!)                                  │
│                                                                             │
│  Manual 3-step:         PARSE ───► OPTIMIZE ───► GENERATE                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Functions

### `sqlglot.transpile(sql, read=, write=, **opts)`

**What it does**: Parse with `read` dialect, generate with `write` dialect.

**What it DOESN'T do**: Run optimizer. No AST transforms between parse and generate.

```python
# This is the FULL implementation:
def transpile(sql, read=None, write=None, **opts):
    write = Dialect.get_or_raise(write)
    return [
        write.generate(expression, **opts)
        for expression in parse(sql, read)
    ]
```

**Parameters**:
- `sql`: SQL string to transpile
- `read`: Source dialect (e.g., "postgres", "mysql", "asql")
- `write`: Target dialect (e.g., "duckdb", "snowflake")
- `**opts`: Passed to Generator (e.g., `pretty=True`)

**No `optimize` parameter!**

---

### `sqlglot.parse(sql, dialect=)` / `sqlglot.parse_one(sql, dialect=)`

**What it does**: Convert SQL string to AST using the specified dialect's parser.

```python
ast = sqlglot.parse_one("SELECT * FROM users", dialect="postgres")
# Returns: exp.Select object
```

**The parser**:
- Handles syntax specific to the dialect
- Calls `_parse_*` methods for different SQL constructs
- Returns `exp.Expression` objects (AST nodes)

**Parser extension point**: Override `_parse_*` methods or use `TRANSFORM_PARSERS` dict.

---

### `sqlglot.optimizer.optimize(expression, schema=, dialect=, rules=)`

**What it does**: Transform AST using a sequence of optimizer rules.

**When to use**: 
- Schema-aware transformations (qualify columns, expand `SELECT *`)
- Query simplification (`1=1` → removed)
- Type annotation
- Subquery optimization

**Default rules** (14 total):
1. `qualify` - Fully qualify column/table references
2. `pushdown_projections` - Only select needed columns
3. `normalize` - Normalize boolean expressions
4. `unnest_subqueries` - Convert subqueries to joins
5. `pushdown_predicates` - Move WHERE closer to source
6. `optimize_joins` - Reorder joins
7. `eliminate_subqueries` - Remove redundant subqueries
8. `merge_subqueries` - Combine subqueries
9. `eliminate_joins` - Remove unnecessary joins
10. `eliminate_ctes` - Inline single-use CTEs
11. `quote_identifiers` - Add quotes
12. `annotate_types` - Add type info to expressions
13. `canonicalize` - Standard form
14. `simplify` - Simplify expressions

**The `dialect` parameter IS passed to rules** - they can be dialect-aware.

```python
from sqlglot.optimizer import optimize

ast = parse_one(sql, dialect="asql")
optimized = optimize(ast, dialect="postgres", schema={"users": {...}})
# Rules receive dialect="postgres"
```

---

### `Expression.sql(dialect=)` / `Dialect.generate(expression)`

**What it does**: Convert AST to SQL string for target dialect.

**Pipeline**:
```python
# Expression.sql() calls:
Dialect.get_or_raise(dialect).generate(expression)

# Dialect.generate() calls:
self.generator().generate(expression)

# Generator.generate() calls:
expression = self.preprocess(expression)  # <-- Transform hook!
return self.sql(expression)
```

**Generator extension points**:
1. `preprocess(expression)` - AST transforms before generating
2. `TRANSFORMS` dict - Map expression types to SQL generators
3. `*_sql()` methods - Per-expression-type SQL generation

---

## Dialect Architecture

Each dialect has 3 nested classes:

```python
class Postgres(Dialect):
    class Tokenizer(tokens.Tokenizer):
        # Lexer rules
        KEYWORDS = {...}
        
    class Parser(parser.Parser):
        # Parsing rules
        FUNCTIONS = {...}
        
    class Generator(generator.Generator):
        # SQL generation rules
        TRANSFORMS = {...}
        
        def preprocess(self, expression):
            # AST transforms before generating
            return super().preprocess(expression)
```

**Key insight**: `preprocess()` is the place for dialect-specific AST transforms, but **NO dialect currently overrides it** - they all use base `Generator.preprocess()`.

---

## Generator.preprocess()

**Current implementation** (same for ALL dialects):

```python
def preprocess(self, expression):
    expression = self._move_ctes_to_top_level(expression)
    if self.ENSURE_BOOLS:
        expression = ensure_bools(expression)
    return expression
```

**This is where output-dialect-specific transforms SHOULD go** per SQLGlot's architecture.

---

## TRANSFORMS Dict

Dialects use `TRANSFORMS` to map expression types to SQL generators:

```python
class Postgres(Dialect):
    class Generator(generator.Generator):
        TRANSFORMS = {
            exp.Array: lambda self, e: f"ARRAY[{self.expressions(e)}]",
            exp.JSONExtract: postgres_json_extract,
            # ... 175 transforms for Postgres
        }
```

When generating SQL, if an expression type is in TRANSFORMS, that function is called.

---

## How transpile() Actually Works

```python
sqlglot.transpile("SELECT * FROM users", read="postgres", write="duckdb")
```

1. `parse("SELECT * FROM users", dialect="postgres")`
   - Postgres.Parser tokenizes and builds AST
   - Returns `[exp.Select(...)]`

2. `DuckDB.generate(exp.Select(...), **opts)`
   - Creates `DuckDB.Generator` instance
   - Calls `generator.generate(expression)`
   - Inside generate():
     - `expression = self.preprocess(expression)` (minimal transforms)
     - `return self.sql(expression)` (walk AST, use TRANSFORMS)

**No optimizer. No custom AST transforms between parse and generate.**

---

## Where ASQL Transforms Could Go

| Transform | Needs Output Dialect? | Option A: Parser | Option B: Optimizer Rule | Option C: Generator.preprocess |
|-----------|----------------------|------------------|-------------------------|-------------------------------|
| Underscore shorthands | ❌ No | ✅ Current location | ❌ Not needed | ❌ Not needed |
| Auto-aliasing | ❌ No | ✅ Current location | ❌ Not needed | ❌ Not needed |
| Alias reuse → CTEs | ✅ Yes (DuckDB native) | ⚠️ Always use CTEs | ✅ Could be rule | ✅ Best location |
| List comprehension | ✅ Yes (DuckDB native) | ⚠️ Always expand | ✅ Could be rule | ✅ Best location |
| Auto-spine | ✅ Yes (generate_series) | ⚠️ Use postgres syntax | ✅ Could be rule | ✅ Best location |
| Column operators | ✅ Yes (EXCEPT support) | ❌ Needs schema | ✅ Needs schema | ✅ Needs schema |

---

## Options for ASQL

### Option 1: Everything in Parser (Current)
- Always generate "universal" SQL (CTEs, ARRAY(SELECT...), postgres generate_series)
- SQLGlot converts generate_series between dialects
- Pro: Works with `transpile()` directly
- Con: Suboptimal for DuckDB (uses CTEs instead of native alias reuse)

### Option 2: Custom Optimizer Rules
- Register ASQL rules with `optimize()`
- Requires 3-step API: parse → optimize → generate
- Pro: Clean separation, dialect-aware
- Con: Users can't use simple `transpile()`

### Option 3: Custom Output Dialects
- Register `asql_postgres`, `asql_duckdb`, etc.
- Each has Generator.preprocess() with ASQL transforms
- Pro: Uses SQLGlot's intended architecture
- Con: Users write `write="asql_postgres"` instead of `write="postgres"`

### Option 4: Monkey-patch Standard Dialects
- On `import asql`, patch Postgres.Generator.preprocess, etc.
- Pro: `transpile(read="asql", write="postgres")` just works
- Con: Hacky, could break other SQLGlot users

### Option 5: Contribute to SQLGlot
- Add `optimize=` parameter to `transpile()`
- Add ASQL transforms to upstream generators
- Pro: Cleanest long-term
- Con: Requires SQLGlot maintainer buy-in

---

## Recommendation

**Short term**: Option 1 (Parser) - already working, minimal disruption

**Medium term**: Option 3 (Custom Output Dialects) - proper architecture

**Long term**: Option 5 (Contribute to SQLGlot) - best for ecosystem
