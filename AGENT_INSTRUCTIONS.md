# Cursor Agent Instructions for ASQL Implementation

## Current Status (as of latest commit)

### ✅ Completed (Stage 1: Foundation)

1. **Project Setup**
   - ✅ Virtual environment configured
   - ✅ Dependencies installed (sqlglot, pytest, black, mypy)
   - ✅ Test framework working
   - ✅ `.cursorrules` configured for pytest usage

2. **Basic Parser Implementation**
   - ✅ Custom ASQL parser (`asql/parser.py`) - handles ASQL's unique FROM-first syntax
   - ✅ FROM clause parsing
   - ✅ WHERE clause parsing with `==` operator
   - ✅ SELECT clause parsing
   - ✅ String literal parsing
   - ✅ Basic expression parsing (equality comparisons)

3. **Compiler**
   - ✅ `compile()` function that transforms ASQL → SQL
   - ✅ SQLGlot integration for SQL generation
   - ✅ Dialect support (can target PostgreSQL, MySQL, etc.)

4. **Tests**
   - ✅ 12 tests passing
   - ✅ Tests for FROM, WHERE, SELECT combinations
   - ✅ Error handling tests

### Current Implementation Approach

**Decision**: Using custom parser approach (not SQLGlot dialect) because:
- ASQL syntax is fundamentally different (FROM-first, pipeline-based)
- SQLGlot's dialect system expects SQL-like syntax
- Custom parser gives us full control over ASQL's unique syntax

**Architecture**:
```
ASQL Text → Custom Parser (asql/parser.py) → SQLGlot AST → SQLGlot Generator → SQL String
```

### Files Created

- `asql/__init__.py` - Public API
- `asql/dialect.py` - ASQLDialect class (skeleton, not fully used)
- `asql/parser.py` - Custom ASQL parser (working!)
- `asql/compiler.py` - Compiler function
- `asql/errors.py` - Error classes
- `tests/test_basic.py` - Basic tests
- `tests/test_compiler.py` - Compiler tests (7 tests)
- `tests/test_dialect.py` - Dialect tests (placeholder)

## Implementation Plan

### Phase 1: Core Pipeline Operators (Priority: HIGH)

**Goal**: Implement all basic pipeline operators

1. **GROUP BY with aggregations** (Priority: HIGH)
   - Parse `group by country ( # as total_users )`
   - Handle `#` syntax for COUNT(*)
   - Support standard aggregations: `sum()`, `avg()`, `count()`, `min()`, `max()`
   - Generate proper SQL GROUP BY with aggregations

2. **SORT/ORDER BY** (Priority: HIGH)
   - Parse `sort -total_users` (descending)
   - Parse `sort total_users` (ascending)
   - Multiple sort columns

3. **TAKE/LIMIT** (Priority: MEDIUM)
   - Parse `take 10`
   - Generate SQL LIMIT

   - Generate SQL SELECT with computed columns
   - Handle in pipeline (becomes CTE step)

### Phase 2: Expressions & Operators (Priority: HIGH)

1. **Comparison operators**
   - `!=`, `<`, `>`, `<=`, `>=` (already have `==`)
   - `is`, `is not` (null checks)
   - `in`, `not in` (membership)

2. **Logical operators**
   - `and`, `or`, `not`
   - Multiple WHERE clauses (implicit AND)

3. **Arithmetic operators**
   - `+`, `-`, `*`, `/`, `%`
   - Function calls in expressions

4. **String matching** (Priority: MEDIUM)
   - `contains`, `starts with`, `ends with` - natural language syntax
   - `matches` for regex
   - Case-insensitive option: `ignore case`
   - See SPEC.md Section 4.5 for detailed design rationale

### Phase 3: Advanced Features (Priority: MEDIUM)

1. **JOIN** (Priority: MEDIUM)
   - Explicit: `join owners on owner_id == owners.id`
   - Automatic joins (later, requires schema resolver)

2. **SET/LET for CTEs** (Priority: MEDIUM)
   - Parse `set active_users = from users where is_active`
   - Generate SQL WITH clauses
   - Variable resolution

3. **Indentation-based syntax** (Priority: LOW)
   - Currently only handles single-line queries
   - Need to handle multi-line with indentation

### Phase 4: Natural Language & Aggregations (Priority: MEDIUM)

1. **Natural language aggregations**
   - `Sum of amount` → `SUM(amount)`
   - `Average of age` → `AVG(age)`
   - `# of Users` → `COUNT(*)`

2. **Enhanced # syntax**
   - `#` → `COUNT(*)`
   - `#(column)` → `COUNT(column)`
   - `# of distinct column` → `COUNT(DISTINCT column)`

### Phase 5: Schema Resolution (Priority: LOW - Complex)

1. **Table name resolution**
   - Plural/singular: `User.name` → `Users.name`
   - Case-insensitive matching

2. **Foreign key inference**
   - Convention-based: `Accounts.user_id` → `Users.id`
   - Automatic join inference

**Note**: This phase is complex and may require significant work. If too difficult, document why and move on.

### Phase 6: Date/Time Functions (Priority: MEDIUM)

1. **Date functions**
   - `year()`, `month()`, `day()`, `week()`, `hour()`
   - Transform to SQL dialect-specific date functions

2. **Date literals**
   - `@2025-01-10` syntax

### Phase 7: SQL Passthrough (Priority: LOW)

1. **Raw SQL blocks**
   - `sql("...")` syntax
   - Parse and embed SQL expressions

## Agent Instructions

### Workflow

1. **Branch Strategy**
   - Create a new branch for each phase: `phase-1-core-operators`, `phase-2-expressions`, etc.
   - If a phase is too complex, create a branch like `phase-X-documentation` with a writeup
   - Open PR against `main` (or previous phase branch if sequential)

2. **Implementation Order**
   - Start with Phase 1 (Core Pipeline Operators)
   - Work through phases sequentially
   - If a feature is too difficult, document why and move to next feature

3. **Testing**
   - **ALWAYS use `pytest` command** (not `python -m pytest` or `python test_*.py`)
   - Write tests FIRST (TDD approach)
   - Run `pytest tests/ -v` after each feature
   - Aim for high test coverage

4. **When Features Are Too Difficult**

   If a feature is too complex or doesn't work well with SQLGlot:
   
   **DO**:
   - Create a markdown document explaining:
     - Why it's difficult
     - What approaches were tried
     - What would be needed to implement it
     - Alternative approaches or workarounds
   - Save it in `docs/` directory (create if needed)
   - Move on to next feature/phase
   - Don't block on difficult features

   **Example**: If schema resolution is too complex, create `docs/schema-resolution-challenges.md` and move on.

5. **Code Style**
   - Follow `.cursorrules` guidelines
   - Use type hints
   - Run `pytest` for tests (not python command)
   - Keep code clean and well-documented

6. **Priorities**

   **Must Have (Core Functionality)**:
   - GROUP BY with aggregations
   - SORT
   - TAKE/LIMIT
   - Basic expressions (comparisons, logical operators)
   - JOIN (explicit)

   **Nice to Have**:
   - SET/LET
   - Natural language aggregations
   - Date functions

   **Complex (Document if Too Hard)**:
   - Schema resolution
   - Automatic joins
   - Indentation parsing
   - SQL passthrough

### Starting Point

**Current working code**:
- `asql/parser.py` - Custom parser (handles FROM, WHERE, SELECT)
- `asql/compiler.py` - Compiler function
- `tests/test_compiler.py` - 7 passing tests

**Next steps**:
1. Start with Phase 1: GROUP BY implementation
2. Write tests first (TDD)
3. Implement parser support for `group by country ( # as total_users )`
4. Generate proper SQL GROUP BY clauses

### Key Files to Understand

1. **`asql/parser.py`** - Main parser logic
   - `parse()` - Entry point
   - `_parse_from()`, `_parse_where()`, `_parse_select_list()` - Current implementations
   - Pattern: Parse ASQL → Build SQLGlot AST nodes

2. **`asql/compiler.py`** - Compiler
   - `compile()` - Main function
   - Uses parser to get SQLGlot AST, then generates SQL

3. **`SPEC.md`** - Language specification
   - Reference for syntax and behavior
   - Examples of what ASQL should support

4. **`ARCHITECTURE.md`** - Architecture decisions
   - Why we chose custom parser
   - How pipeline → CTEs should work
   - Schema resolution strategy

### SQLGlot Usage

- Use `sqlglot.exp` for AST nodes: `exp.Select`, `exp.From`, `exp.Where`, `exp.Group`, etc.
- Use `exp.Literal(this=value, is_string=True)` for string literals
- Use `exp.Column(this=exp.Identifier(this=name))` for column references
- Use `exp.EQ()`, `exp.NEQ()`, etc. for comparisons
- Use `.sql(dialect=...)` to generate SQL

### Example: How to Add a New Feature

**Example: Adding GROUP BY**

1. **Write test first** (`tests/test_compiler.py`):
```python
def test_compile_group_by() -> None:
    """Test compiling GROUP BY."""
    asql = "from users group by country ( # as total_users )"
    sql = compile(asql)
    assert "GROUP BY" in sql.upper()
    assert "country" in sql.lower()
    assert "COUNT(*)" in sql.upper() or "COUNT" in sql.upper()
```

2. **Add parser method** (`asql/parser.py`):
```python
def _parse_group_by(self) -> exp.Group:
    """Parse GROUP BY clause."""
    # Implementation here
```

3. **Update parse() method** to handle GROUP BY

4. **Run tests**: `pytest tests/test_compiler.py::test_compile_group_by -v`

5. **Iterate until passing**

### Success Criteria

- Each phase should have:
  - ✅ Working implementation
  - ✅ Comprehensive tests
  - ✅ Documentation of any limitations
  - ✅ PR ready for review

- If a phase is too difficult:
  - ✅ Documentation explaining why
  - ✅ Suggestions for future work
  - ✅ Move on to next phase

### Questions to Consider

- Does this work with SQLGlot's AST?
- Can we generate valid SQL?
- Are there edge cases we're missing?
- Should this be a CTE step or inline?

### Resources

- SQLGlot docs: https://sqlglot.com/sqlglot.html
- SPEC.md: Full language specification
- ARCHITECTURE.md: Design decisions
- Current tests: Examples of working code

## Good Luck! 🚀

Start with Phase 1: GROUP BY implementation. Write tests first, then implement. If you get stuck, document why and move on. The goal is to build a working ASQL compiler incrementally, not to implement everything perfectly on the first try.

