# PRQL Dialect Approach: Should We Build ASQL on SQLGlot's PRQL Parser?

**Date:** January 6, 2026  
**Status:** Analysis/Research  
**Context:** Feedback from SQLGlot creator Toby Mao suggesting we leverage SQLGlot's PRQL parser

## Executive Summary

SQLGlot's creator suggested extending the existing PRQL dialect rather than building a custom pre-parser. This is technically feasible and could simplify some aspects of ASQL, but our current architecture has evolved for good reasons. **The recommendation is to explore a hybrid approach** - learn from the PRQL implementation and potentially integrate more tightly with SQLGlot's parser, but not to rewrite everything from scratch.

## What SQLGlot Has for PRQL

SQLGlot includes a full PRQL dialect (`sqlglot/dialects/prql.py`) that can parse pipelined queries. Here's how it works:

### Core Architecture

```python
class PRQL(Dialect):
    class Parser(parser.Parser):
        TRANSFORM_PARSERS = {
            "DERIVE": lambda self, query: self._parse_selection(query),
            "SELECT": lambda self, query: self._parse_selection(query, append=False),
            "TAKE": lambda self, query: self._parse_take(query),
            "FILTER": lambda self, query: query.where(self._parse_disjunction()),
            "APPEND": lambda self, query: query.union(...),
            "REMOVE": lambda self, query: query.except_(...),
            "INTERSECT": lambda self, query: query.intersect(...),
            "SORT": lambda self, query: self._parse_order_by(query),
            "AGGREGATE": lambda self, query: self._parse_selection(...),
        }
        
        def _parse_query(self) -> Optional[exp.Query]:
            from_ = self._parse_from()
            query = exp.select("*").from_(from_, copy=False)
            
            while self._match_texts(self.TRANSFORM_PARSERS):
                query = self.TRANSFORM_PARSERS[self._prev.text.upper()](self, query)
            
            return query
```

### Key Features
1. **FROM-first parsing**: Starts with FROM, builds query progressively
2. **Transform chain**: Each keyword (filter, derive, take) transforms the query
3. **Direct AST building**: Builds SQLGlot expressions directly (no string manipulation)
4. **Proper tokenization**: Custom tokenizer for PRQL syntax (= for alias, # for comments)

### Test of PRQL Parsing
```python
import sqlglot

prql_query = '''
from employees
filter start_date > @2021-01-01
derive gross_salary = salary + bonus
take 10
'''

result = sqlglot.transpile(prql_query, read='prql', write='postgres')
# OUTPUT: SELECT *, salary + bonus AS gross_salary 
#         FROM employees 
#         WHERE start_date > $2021 - 01 - 01 
#         LIMIT 10
```

Note: The date parsing has issues, but the core pipeline structure works.

## Current ASQL Architecture

Our current approach uses a **pre-parser pattern**:

```
ASQL Text 
  → ASQLPreParser (30+ mixins, string transformation)
  → SQL-like text
  → SQLGlot parse
  → SQLGlot AST
  → SQLGlot Generator
  → Target SQL
```

### Pre-parser Mixins (30+ transformations)
```python
class ASQLPreParser(
    CommentsMixin,        # Extract/restore comments
    SettingsMixin,        # SET statements
    PipelineMixin,        # | pipe operators
    JoinsMixin,           # left/right/inner join transformations
    CountMixin,           # # → COUNT(*)
    CoalesceMixin,        # ?? → COALESCE
    OrderMixin,           # -col → col DESC
    AggregatesMixin,      # group by x (sum y) blocks
    DatesMixin,           # @2024-01-01, 7 days ago
    PivotMixin,           # pivot value by key
    WindowMixin,          # running_*, rolling_*, prior, next
    CohortMixin,          # cohort by date
    WhenMixin,            # when x then y else z
    TernaryMixin,         # x ? y : z
    WithCTEMixin,         # with name = from ...
    UnionMixin,           # union all, intersect, except
    SlugifyMixin,         # slugify(col)
    BucketMixin,          # bucket(col, ranges)
    RecurseMixin,         # recurse(...)
    # ... and more
):
```

## Comparison: PRQL Dialect vs ASQL Pre-parser

| Aspect | PRQL Dialect Approach | ASQL Pre-parser Approach |
|--------|----------------------|--------------------------|
| **Core mechanism** | Override Parser class methods | String transformations before parsing |
| **AST building** | Direct (builds exp.* nodes) | Indirect (transform to SQL text, then parse) |
| **Error handling** | Integrated with SQLGlot errors | Custom errors + SQLGlot errors |
| **Dialect features** | Single unified dialect | Pre-parser + minimal dialect |
| **Extensibility** | Subclass and override | Add new mixin classes |
| **Complexity** | ~200 lines of code | ~4000+ lines across 30 mixins |
| **Feature coverage** | Basic (filter, derive, take, sort) | Very rich (cohorts, pivots, window functions, dates, etc.) |

## What "Extending PRQL" Would Mean

If we adopted the PRQL pattern, we'd create an ASQL dialect like:

```python
class ASQL(PRQL):
    class Tokenizer(PRQL.Tokenizer):
        SINGLE_TOKENS = {
            **PRQL.Tokenizer.SINGLE_TOKENS,
            "#": TokenType.COUNT,  # Count shorthand
            "@": TokenType.DATE,   # Date literal prefix
        }
    
    class Parser(PRQL.Parser):
        TRANSFORM_PARSERS = {
            **PRQL.Parser.TRANSFORM_PARSERS,
            "WHERE": lambda self, query: query.where(self._parse_disjunction()),
            "GROUP": lambda self, query: self._parse_group_by(query),
            "ORDER": lambda self, query: self._parse_order_by(query),
            "LIMIT": lambda self, query: self._parse_limit(query),
            "JOIN": lambda self, query: self._parse_join(query),
            "STASH": lambda self, query: self._parse_stash_cte(query),
            # ... ASQL-specific transforms
        }
        
        def _parse_date_literal(self):
            """Handle @2024-01-01 syntax."""
            ...
        
        def _parse_count_shorthand(self):
            """Handle # → COUNT(*)."""
            ...
```

## Advantages of the PRQL Approach

### 1. **Direct AST Building**
Instead of transforming strings and re-parsing, build the AST directly:
```python
# Current (pre-parser)
text = re.sub(r'#', 'COUNT(*)', text)
ast = sqlglot.parse_one(text)

# PRQL approach
return exp.Count(this=exp.Star())
```

### 2. **Better Error Messages**
Parser-level errors include line/column info and proper context:
```python
# Current: "Error parsing: unexpected token"
# PRQL approach: "Line 3, Column 5: Expected expression after 'filter'"
```

### 3. **Single Parse Pass**
No intermediate string representation means:
- Fewer edge cases with escaping/quoting
- Better handling of nested expressions
- More predictable behavior

### 4. **Built-in Feature Inheritance**
PRQL already handles:
- `from table` → SELECT * FROM table
- `filter x` → WHERE x  
- `take N` → LIMIT N
- `sort col` → ORDER BY col
- `-col` for descending
- `=` for aliasing

## Disadvantages / Challenges

### 1. **Feature Gap**
ASQL has many features PRQL doesn't:
- `group by x (sum y)` aggregate blocks
- `7 days ago`, `@2024-01-01` date literals
- `?? ` null coalescing
- `per country first by date` window operations
- `cohort by signup_date`
- `pivot value by key`
- `running_sum()`, `rolling_avg()`
- `stash as name` CTEs
- `when x then y else z` expressions
- `recurse(...)` recursive CTEs
- `bucket(col, ranges)`

Each of these would need custom parser methods.

### 2. **Learning Curve**
SQLGlot's parser internals are complex:
- Token matching with `_match()`, `_match_texts()`
- Expression building with `self.expression()`
- Lookahead with `_prev`, `_curr`, `_next`
- Error handling with `raise_error()`

### 3. **Migration Effort**
We have 4000+ lines of working pre-parser code. Rewriting would be a major effort.

### 4. **Coupling to SQLGlot Internals**
Parser internals can change between versions. Our pre-parser is more isolated.

## Recommended Hybrid Approach

Instead of fully rewriting to use the PRQL pattern, consider a hybrid:

### Phase 1: Learn from PRQL (Now)
- Study how PRQL handles core transforms
- Identify patterns we could adopt
- Use PRQL as a reference implementation

### Phase 2: Targeted Integration (Medium-term)
Move specific features from pre-parser to dialect:
1. **Count shorthand**: `#` → `COUNT(*)` in tokenizer
2. **Operator mapping**: `==` → `=` in tokenizer
3. **Date literals**: `@2024-01-01` in tokenizer + parser

### Phase 3: Consider Full Integration (Long-term)
If we find the hybrid approach works well, consider:
1. Moving more transforms into the Parser class
2. Eliminating the pre-parser for core features
3. Keeping pre-parser only for very complex transforms (pivot, cohort)

## What Toby Probably Meant

When Toby said "just extend what we have for PRQL," he likely meant:

1. **The pattern exists**: SQLGlot already handles pipelined, FROM-first syntax
2. **It's battle-tested**: PRQL dialect has been used in production
3. **Subclass and extend**: Add ASQL-specific transforms to the pattern
4. **Leverage the tokenizer**: Custom tokens for `#`, `@`, `??`, etc.

He probably didn't mean "PRQL and ASQL are the same" - they have different syntax. But the *pattern* of FROM-first parsing with transform chains is reusable.

## Concrete Next Steps

If we want to experiment with this:

### 1. Create a Proof of Concept
```python
# asql/dialect_v2.py (experimental)
from sqlglot.dialects.prql import PRQL

class ASQLv2(PRQL):
    """Experimental ASQL dialect built on PRQL patterns."""
    
    class Parser(PRQL.Parser):
        TRANSFORM_PARSERS = {
            **PRQL.Parser.TRANSFORM_PARSERS,
            "WHERE": lambda self, query: query.where(self._parse_disjunction()),
            "LIMIT": lambda self, query: query.limit(self._parse_number()),
            # ... add ASQL transforms
        }
```

### 2. Test Core Features
Test the PoC with basic ASQL queries:
- `from users where active`
- `from users order by -created_at`
- `from users limit 10`

### 3. Identify Integration Boundaries
Determine which features are easy to move to the dialect vs which need pre-parsing.

## Conclusion

Toby's suggestion is valid and worth exploring. The PRQL dialect shows that SQLGlot can handle pipelined, FROM-first syntax elegantly. However, ASQL has evolved significant complexity that would be non-trivial to port.

**The recommended path forward:**
1. Keep the current pre-parser architecture for now
2. Study the PRQL dialect as a reference implementation
3. Gradually move simple transforms into the dialect
4. Consider a larger rewrite only if the incremental approach proves valuable

The pre-parser approach isn't wrong - it's just a different trade-off. It's more explicit and easier to debug, while the dialect approach is more elegant and integrated.

## References

- SQLGlot PRQL dialect: `venv/lib/python3.13/site-packages/sqlglot/dialects/prql.py`
- ASQL pre-parser: `asql/preparse/preparser.py`
- ASQL dialect: `asql/dialect.py`
- PRQL language: https://prql-lang.org/

