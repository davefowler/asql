# ASQL Architecture & Implementation Plan

## Overview

ASQL is a pipeline-based query language that transpiles to SQL. This document outlines the architecture and implementation strategy.

## Architecture

### High-Level Flow

**Option A: SQLGlot Dialect (Recommended)**
```
ASQL Text 
  → SQLGlot ASQL Dialect Parser 
  → SQLGlot AST 
  → Schema Resolver (relationship inference, plural/singular resolution)
  → Resolved SQLGlot AST (with inferred joins)
  → SQLGlot Generator 
  → SQL String
```

**Option B: Custom Parser (Fallback if dialect approach doesn't work)**
```
ASQL Text 
  → Custom Parser 
  → ASQL AST 
  → Schema Resolver (relationship inference, plural/singular resolution)
  → Resolved ASQL AST
  → Compiler (ASQL AST → SQLGlot AST)
  → SQLGlot Generator 
  → SQL String
```

**Decision**: Start with Option A (SQLGlot Dialect) as it provides:
- Built-in parsing infrastructure
- AST building
- Transpilation to all SQL dialects
- Consistent with SQLGlot's architecture
- Less code to maintain

**Schema Resolution**: Happens after parsing but before SQL generation:
- Resolve table names (plural/singular, case-insensitive)
- Infer foreign key relationships
- Inject JOIN clauses automatically
- Resolve column references with table context

### Component Breakdown

#### 1. ASQL Dialect (`asql/dialect.py`)
**Purpose**: Define ASQL as a SQLGlot dialect

**Approach: SQLGlot Dialect System**
- **Why SQLGlot Dialect?**
  - SQLGlot already has infrastructure for parsing, AST building, and transpilation
  - We can add ASQL as another dialect alongside MySQL, PostgreSQL, BigQuery, etc.
  - Leverages SQLGlot's existing Tokenizer, Parser, and Generator infrastructure
  - Automatic transpilation to all SQL dialects (PostgreSQL, MySQL, BigQuery, Snowflake, etc.)
  - Consistent architecture with other SQLGlot dialects
  - Less code to write and maintain

**SQLGlot Dialect Structure**:
```python
from sqlglot.dialects.dialect import Dialect
from sqlglot.tokens import Tokenizer, TokenType
from sqlglot.parser import Parser
from sqlglot.generator import Generator

class ASQLDialect(Dialect):
    class Tokenizer(Tokenizer):
        # Custom tokenization for ASQL syntax
        # Handle: from, where, group by, #, etc.
        KEYWORDS = {
            **Tokenizer.KEYWORDS,
            "FROM": TokenType.FROM,
            "WHERE": TokenType.WHERE,
            # ... ASQL-specific keywords
        }
    
    class Parser(Parser):
        # Custom parsing for ASQL pipeline syntax
        # Handle: indentation-based pipelines, natural language, etc.
        pass
    
    class Generator(Generator):
        # Transform ASQL AST to SQL AST
        # Handle: pipeline → CTEs, expressions, etc.
        pass
```

**Responsibilities**:
- Define ASQL-specific tokenization (keywords, operators like `==`, `#`, etc.)
- Parse ASQL pipeline syntax (`from`, `where`, `group by`, etc.)
- Handle indentation-based syntax
- Parse natural language aggregations (`#`, `Sum of`, `Average of`)
- Transform ASQL AST to SQL AST (pipeline → CTEs)
- Generate SQL using SQLGlot's generator

**Challenges**:
- ASQL syntax is quite different from SQL (pipeline-based vs SELECT-first)
- Indentation-based syntax may require custom parsing logic
- Natural language elements need special handling
- May need to extend SQLGlot's parser more than typical dialects

**Fallback Plan**:
- If SQLGlot's dialect system is too restrictive for ASQL's unique syntax:
  - Use Lark parser for ASQL → ASQL AST
  - Transform ASQL AST → SQLGlot AST
  - Use SQLGlot for SQL generation and transpilation

**Output**: SQLGlot AST (standard SQLGlot AST structure)

#### 2. AST (SQLGlot AST)
**Purpose**: Use SQLGlot's standard AST structure

**Approach**: 
- Use SQLGlot's existing AST nodes (`exp.Select`, `exp.From`, `exp.Where`, etc.)
- Extend with ASQL-specific nodes if needed (e.g., `exp.Pipeline`, `exp.GroupByAggregate`)
- Transform ASQL syntax → SQLGlot AST nodes
- Pipeline steps become CTEs (`exp.With`)

**SQLGlot AST Nodes Used**:
- `exp.Select` - SELECT statements
- `exp.From` - FROM clauses
- `exp.Where` - WHERE clauses
- `exp.Group` - GROUP BY clauses
- `exp.Order` - ORDER BY clauses
- `exp.Limit` - LIMIT clauses
- `exp.With` - CTEs (for pipeline steps)
- `exp.Join` - JOIN clauses
- `exp.Alias` - Column aliases
- `exp.Function` - Function calls
- `exp.Aggregate` - Aggregations
- And more...

**ASQL-Specific Extensions** (if needed):
- Custom expression types for pipeline operators
- Natural language aggregation nodes
- Indentation tracking nodes

#### 3. ASQL Dialect Implementation (`asql/dialect.py`)
**Purpose**: Implement ASQL as a SQLGlot dialect

**If Using SQLGlot Dialect Approach**:
- **Tokenizer**: Tokenize ASQL syntax (keywords, operators, identifiers)
- **Parser**: Parse ASQL → SQLGlot AST
  - Handle pipeline syntax (`from`, `where`, `group by`, etc.)
  - Transform pipeline steps to CTEs
  - Parse expressions with ASQL operators (`==`, `!=`, etc.)
  - Handle natural language aggregations
- **Generator**: Generate SQL from SQLGlot AST
  - Use SQLGlot's standard generator
  - Dialect transpilation handled automatically

**If Using Custom Parser Approach** (fallback):
- **Parser** (`asql/parser.py`): Parse ASQL → ASQL AST (using Lark)
- **Compiler** (`asql/compiler.py`): Transform ASQL AST → SQLGlot AST
  - Walk ASQL AST
  - Build SQLGlot AST nodes programmatically
  - Handle pipeline semantics (each step becomes a CTE)
  - Transform ASQL expressions to SQL expressions

**Key Transformations** (same for both approaches):
- Pipeline steps → CTEs (`WITH step1 AS (...), step2 AS (...)`)
- ASQL expressions → SQL expressions (`==` → `=`, `#` → `COUNT(*)`)
- Natural language → SQL functions (`Sum of amount` → `SUM(amount)`)
- Date functions → SQL dialect-specific date functions
- SQL passthrough → Direct SQL embedding (via SQLGlot parsing)

**SQLGlot Usage**:
- Use `sqlglot.expressions.*` to build AST nodes
- Use `sqlglot.parse_one()` for parsing SQL expressions (both for passthrough and validation)
- Use `sqlglot.dialects` for dialect-specific SQL generation
- Parse raw SQL blocks using SQLGlot and embed in AST
- Register ASQL dialect: `sqlglot.dialects.register(ASQLDialect)`

#### 4. Expression Handling (in Parser/Generator)
**Purpose**: Handle ASQL expressions within SQLGlot dialect

**If Using SQLGlot Dialect**:
- Expression parsing handled in `ASQLDialect.Parser`
- Expression generation handled in `ASQLDialect.Generator`
- Operator transformations (`==` → `=`) in Generator

**If Using Custom Parser**:
- Expression transformer (`asql/expressions.py`) converts ASQL expressions → SQLGlot expressions

**Handles**:
- Binary operators (`==`, `!=`, `<`, `>`, `<=`, `>=`, `and`, `or`)
- Unary operators (`-`, `not`)
- Function calls (`year()`, `month()`, `sum()`, etc.)
- Identifiers (table.column, column)
- Literals (strings, numbers, dates)
- Aggregations

**SQL Passthrough Support**:
- **Raw SQL blocks**: `sql("...")` syntax for embedding raw SQL expressions
- **Unrecognized functions**: If a function isn't recognized as ASQL, pass it through as SQL (e.g., BigQuery's `ARRAY_AGG`, PostgreSQL's `JSONB` functions)
- **SQLGlot integration**: Use SQLGlot to parse SQL expressions and embed them in the AST
- **Dialect-aware**: Allow dialect-specific SQL functions to pass through when generating SQL

**Example**:
```asql
from users
  select tags as sql("ARRAY_AGG(tag) OVER (PARTITION BY user_id)")
  group by country (
    revenue as sum(amount),
    top_tags as sql("ARRAY_AGG(tag ORDER BY count DESC LIMIT 5)")
  )
```

#### 5. Schema Resolver (`asql/resolver.py`)
**Purpose**: Schema-aware resolution and relationship inference

**Responsibilities**:
- **Schema Loading**: Load schema metadata from:
  - Database introspection (via SQLGlot or direct DB connection)
  - YAML model files (dbt `schema.yml` compatible)
  - Custom ASQL model files
- **Table Name Resolution**: Handle plural/singular table name swapping
  - `User.name` → resolves to `Users.name` (if `Users` table exists)
  - `Account.user_id` → resolves to `Accounts.user_id`
  - Case-insensitive matching
- **Foreign Key Inference**: Automatically infer relationships
  - Convention-based: `Accounts.user_id` → `Users.id` (if `{table}_id` pattern)
  - Multiple FKs: `owner_user_id`, `manager_user_id` → infer based on context
  - Model metadata: Use explicit relationships from YAML files
- **Join Inference**: Determine join conditions automatically
  - `from accounts, users` → infer join on `accounts.user_id = users.id`
  - `from accounts group by user.name` → infer join automatically
- **Default Time Field Inference**: Infer default time columns
  - Convention: `created_at` is primary time field
  - Model metadata: Explicit `default_time` field

**Inference Priority** (from SPEC):
1. **Model metadata** - Explicit relationships from YAML files
2. **Naming convention inference** - `{table}_id` pattern matching
3. **Single FK check** - If only one FK exists between tables
4. **Require explicit** - If multiple FKs or conventions don't match
5. **Fall back to explicit join** - Always allow `join ... on ...` syntax

**Convention Assumptions**:
- Foreign keys: `{referenced_table}_id` pattern (e.g., `user_id`, `owner_id`)
- Multiple FKs: `{role}_{table}_id` (e.g., `owner_user_id`, `manager_user_id`)
- Primary keys: `id` (or `{table}_id`, `pk` - configurable)
- Time fields: `created_at` (primary), `updated_at` (secondary)
- Table names: Pluralized (configurable)

**Implementation Approach**:
- **Schema Registry**: Maintain a registry of tables, columns, and relationships
- **Resolution Phase**: After parsing, resolve identifiers:
  - Resolve table names (plural/singular, case-insensitive)
  - Resolve column references (with table context)
  - Infer joins based on column references
- **Join Injection**: Automatically inject JOIN clauses based on inferred relationships
- **Validation**: Validate that inferred relationships exist and are unambiguous

**Example Flow**:
```asql
# Input ASQL
from accounts
  group by user.name ( total as sum(amount) )
```

**Resolution Process**:
1. Parse: `accounts` table, `user.name` column reference
2. Resolve table: `accounts` → `Accounts` table (case-insensitive)
3. Detect column reference: `user.name` suggests relationship to `Users` table
4. Infer FK: `Accounts.user_id` → `Users.id` (convention-based)
5. Inject join: `FROM accounts JOIN users ON accounts.user_id = users.id`
6. Resolve column: `user.name` → `users.name`

**Integration Points**:
- **Parser**: After parsing, pass AST to resolver
- **Compiler**: Resolved AST includes inferred joins and relationships
- **SQLGlot**: Generate SQL with inferred joins as standard JOIN clauses

**Configuration**:
- Schema source (database, YAML files, both)
- Naming conventions (FK patterns, PK patterns, pluralization rules)
- Inference strictness (strict vs. permissive)

#### 6. Tests (`tests/`)
**Purpose**: Comprehensive test suite using TDD

**Structure**:
- `test_parser.py` - Parser tests
- `test_compiler.py` - Compiler/transpilation tests
- `test_expressions.py` - Expression transformation tests
- `test_integration.py` - End-to-end tests

**Testing Strategy**:
- Use SQLGlot's `assert_sql_match` or similar utilities if available
- Test ASQL → SQL transformation
- Test multiple SQL dialects
- Test edge cases and error handling

## Implementation Stages

### Stage 1: Foundation (v0.1.0-alpha)
**Goal**: Basic parsing and SQL generation for simplest queries

**Tasks**:
1. ✅ Set up project structure (package, dependencies, test framework)
2. ⏳ Study SQLGlot dialect implementations (MySQL, PostgreSQL, etc.)
3. ⏳ Create `ASQLDialect` class extending `sqlglot.dialects.Dialect`
4. ⏳ Implement `ASQLDialect.Tokenizer` for ASQL keywords/operators
5. ⏳ Implement `ASQLDialect.Parser` for pipeline syntax
6. ⏳ Implement `ASQLDialect.Generator` for SQL generation
7. ⏳ Register ASQL dialect with SQLGlot
8. ⏳ Test basic queries and transpilation to other dialects
9. ⏳ Write tests for basic queries

**Research First**:
- Examine SQLGlot source code for dialect implementations
- Understand how Tokenizer, Parser, Generator work
- See if we can extend them sufficiently for ASQL's unique syntax

**Example**:
```asql
from users
  where status == "active"
  select name, email
```

**Expected SQL**:
```sql
SELECT name, email
FROM users
WHERE status = 'active'
```

### Stage 2: Core Pipeline Operators (v0.1.0-beta)
**Goal**: Support all basic pipeline operators

**Tasks**:
1. Implement `GROUP BY` with basic aggregations (`count`, `sum`, `avg`)
2. Implement `SORT` / `ORDER BY`
3. Implement `TAKE` / `LIMIT`
5. Implement pipeline CTE generation (each step becomes a CTE)
6. Write comprehensive tests

**Example**:
```asql
from users
  where status == "active"
  group by country ( total_users as # )
  order by -total_users
  limit 10
```

### Stage 3: Aggregations & Natural Language (v0.1.0)
**Goal**: Full aggregation support with natural language syntax

**Tasks**:
1. Implement `#` syntax for `COUNT(*)`
2. Implement natural language aggregations (`Sum of`, `Average of`, `Total of`)
3. Implement `distinct` aggregations
4. Handle aggregate aliases
5. Write tests for all aggregation forms

**Example**:
```asql
from sales
  group by region (
    revenue as sum(amount),
    customers as # of distinct customer_id,
    avg_order as average amount
  )
```

### Stage 4: Expressions & Operators (v0.1.1)
**Goal**: Full expression support

**Tasks**:
1. Implement all comparison operators (`==`, `!=`, `<`, `>`, `<=`, `>=`)
2. Implement logical operators (`and`, `or`, `not`)
3. Implement arithmetic operators (`+`, `-`, `*`, `/`, `%`)
4. Implement `is`, `is not`, `in`, `not in`
5. Implement function calls
6. Implement nested expressions
7. Write expression tests

### Stage 5: Joins (v0.1.2)
**Goal**: Support table joins

**Tasks**:
1. Implement explicit `JOIN ... ON` syntax
2. Basic join condition parsing
3. Multiple joins
4. Write join tests

**Example**:
```asql
from opportunities
  join owners on owner_id == owners.id
  group by owners.name ( total_pipeline as sum(amount) )
```

### Stage 6: Date/Time Functions (v0.1.3)
**Goal**: Date and time function support

**Tasks**:
1. Implement `year()`, `month()`, `day()`, `week()`, `hour()` functions
2. Transform to SQL dialect-specific date functions
3. Support date literals (`@2025-01-10`)
4. Write date function tests

**Example**:
```asql
from users
  group by month(created_at) ( signups as # )
```

### Stage 7: Variables & CTEs (v0.1.4)
**Goal**: Support `SET` / `LET` for reusable queries

**Tasks**:
1. Implement `SET` / `LET` parsing
2. Implement variable resolution
3. Generate SQL CTEs from variables
4. Write CTE tests

**Example**:
```asql
set active_users = from users
  where is_active

from active_users
  group by country ( total_users as # )
```

### Stage 8: Advanced Features (v0.2.0)
**Goal**: Advanced syntax and features

**Tasks**:
1. Implement `IF` as alias for `WHERE`
2. Implement indentation-based pipeline parsing (currently using `|`)
3. Implement case-insensitive identifier matching
4. Implement natural language shortcuts (`# of Users by country`)
5. Error handling and better error messages
6. Write comprehensive integration tests

### Stage 9: Dialect Support (v0.3.0)
**Goal**: Full SQL dialect support via SQLGlot

**Tasks**:
1. Test and verify all major dialects (PostgreSQL, MySQL, BigQuery, Snowflake, etc.)
2. Handle dialect-specific transformations
3. Date function dialect mapping
4. Write dialect-specific tests

### Stage 10: Schema Resolution & Relationship Inference (v0.4.0)
**Goal**: Schema-aware resolution and automatic relationship inference

**Tasks**:
1. Create schema registry/resolver infrastructure
2. Implement table name resolution (plural/singular, case-insensitive)
   - `User.name` → `Users.name`
   - `Account.user_id` → `Accounts.user_id`
3. Implement foreign key inference (convention-based)
   - `{table}_id` pattern matching
   - Multiple FK handling (`owner_user_id`, `manager_user_id`)
4. Implement automatic join inference
   - `from accounts, users` → infer join
   - `from accounts group by user.name` → infer join automatically
5. Implement model file parsing (YAML, dbt-compatible)
6. Implement relationship priority (model metadata > convention > explicit)
7. Implement default time field inference (`created_at` convention)
8. Write comprehensive resolver tests

**Example**:
```asql
# Input
from accounts
  group by user.name ( total as sum(amount) )

# After resolution (inferred join)
from accounts
  join users on accounts.user_id == users.id
  group by users.name ( total as sum(amount) )
```

**Schema Sources**:
- Database introspection (via SQLGlot or direct connection)
- YAML model files (dbt `schema.yml` compatible)
- Custom ASQL model files

### Stage 11: Functions (v0.5.0)
**Goal**: User-defined functions

**Tasks**:
1. Implement `func` syntax parsing
2. Implement function definition and resolution
3. Implement function expansion
4. Write function tests

### Stage 12: SQL Passthrough (v0.1.5)
**Goal**: Allow SQL expressions to pass through for dialect-specific features

**Tasks**:
1. Implement `sql("...")` syntax for raw SQL blocks
2. Implement unrecognized function passthrough (fallback to SQL if not ASQL function)
3. Use SQLGlot to parse and validate SQL passthrough blocks
4. Handle SQL passthrough in expressions and aggregates
5. Write tests for SQL passthrough

**Example**:
```asql
from users
  select tags as sql("ARRAY_AGG(tag) OVER (PARTITION BY user_id)")
  group by country (
    revenue as sum(amount),
    top_tags as sql("ARRAY_AGG(tag ORDER BY count DESC LIMIT 5)")
  )
```

**Design Decisions**:
- **When to use passthrough**: For dialect-specific functions, complex window functions, or when ASQL doesn't have equivalent syntax
- **Validation**: Use SQLGlot to parse SQL blocks and ensure they're valid SQL
- **Dialect awareness**: SQL passthrough blocks are dialect-specific, so they should be validated against the target dialect
- **Safety**: SQL passthrough is explicit (`sql("...")`) rather than implicit to avoid confusion
- **Fallback behavior**: Unrecognized function names (not in ASQL's function list) can optionally pass through as SQL

## Technical Decisions

### Why SQLGlot Dialect Approach?
- **Consistency**: Follows SQLGlot's architecture pattern (same as MySQL, PostgreSQL, BigQuery dialects)
- **Infrastructure**: Leverages SQLGlot's existing Tokenizer, Parser, Generator infrastructure
- **Transpilation**: Automatic transpilation to all SQL dialects (PostgreSQL, MySQL, BigQuery, Snowflake, etc.)
- **Less Code**: Don't need to build parser, AST, compiler from scratch
- **Maintainability**: Changes to SQLGlot benefit ASQL automatically
- **Testing**: Can use SQLGlot's testing utilities

### Implementation Strategy
1. **Primary Approach**: Implement ASQL as a SQLGlot dialect
   - Subclass `Dialect` with custom `Tokenizer`, `Parser`, `Generator`
   - Handle ASQL-specific syntax in parser
   - Transform pipeline syntax to SQL CTEs
   - Use SQLGlot's generator for SQL output

2. **Fallback Approach**: If SQLGlot's dialect system is too restrictive
   - Use Lark parser for ASQL → ASQL AST
   - Transform ASQL AST → SQLGlot AST
   - Use SQLGlot for SQL generation and transpilation

### Why Not Just SQLGlot's Standard Parser?
- ASQL syntax is fundamentally different from SQL (`from users` vs `SELECT * FROM users`)
- Pipeline-based syntax requires custom parsing
- Indentation-based syntax needs special handling
- Natural language elements need custom parsing
- But we can extend SQLGlot's parser to handle these differences

### Why SQLGlot for SQL Generation?
- Proven, well-tested SQL AST library
- Supports multiple SQL dialects
- Handles SQL generation edge cases
- Active maintenance and community
- Can parse SQL expressions for passthrough support

### Schema Resolution Strategy
**Goal**: Make ASQL schema-aware and convention-driven

**Key Features**:
1. **Table Name Resolution**
   - Plural/singular handling: `User.name` → `Users.name`
   - Case-insensitive: `user` → `Users` or `users`
   - Context-aware: Resolve based on schema

2. **Foreign Key Inference**
   - Convention-based: `Accounts.user_id` → `Users.id`
   - Pattern: `{referenced_table}_id`
   - Multiple FKs: `owner_user_id`, `manager_user_id` → infer from context
   - Model metadata: Explicit relationships override conventions

3. **Automatic Join Inference**
   - `from accounts, users` → infer join condition
   - `from accounts group by user.name` → infer join automatically
   - Priority: Model metadata > Convention > Explicit join required

4. **Implementation**
   - Schema Registry: Maintain table/column/relationship metadata
   - Resolution Phase: After parsing, resolve all identifiers
   - Join Injection: Add JOIN clauses to AST before SQL generation
   - Validation: Ensure inferred relationships are unambiguous

**Benefits**:
- Less boilerplate (no need to write joins explicitly)
- Convention-driven (follow standards, get automatic inference)
- Explicit when needed (can always use explicit joins)
- dbt-compatible (use existing `schema.yml` files)

### SQL Passthrough Strategy
**Goal**: Allow users to use dialect-specific SQL features when needed

**Approach**:
1. **Explicit passthrough**: `sql("...")` syntax for raw SQL blocks
   - Clear and explicit
   - Easy to parse and validate
   - Can use SQLGlot to parse and embed

2. **Implicit passthrough** (optional): Unrecognized functions pass through as SQL
   - More flexible but potentially confusing
   - Could be a configuration option
   - Example: `ARRAY_AGG(...)` → passes through if not recognized as ASQL function

3. **Validation**: Use SQLGlot to validate SQL passthrough blocks
   - Ensures valid SQL syntax
   - Dialect-aware validation
   - Better error messages

**Use Cases**:
- BigQuery: `ARRAY_AGG`, `STRUCT`, `UNNEST`, etc.
- PostgreSQL: `JSONB` functions, `ARRAY` constructors, etc.
- Complex window functions not yet supported in ASQL
- Dialect-specific optimizations

### AST Design
- **ASQL AST**: Custom tree structure optimized for ASQL syntax (if using custom parser)
- **SQL AST**: SQLGlot's AST (we build this programmatically)
- **Transformation**: ASQL AST → SQL AST (one-way)
- **Resolution**: Happens after parsing, before SQL generation
  - Unresolved AST → Schema Resolver → Resolved AST (with inferred joins)

### Pipeline Semantics
Each pipeline step becomes a CTE:
```asql
from users
  where status == "active"
  group by country ( # as total_users )
```

Becomes:
```sql
WITH step1 AS (
  SELECT * FROM users WHERE status = 'active'
)
SELECT country, COUNT(*) AS total_users
FROM step1
GROUP BY country
```

### Expression Handling
- Parse ASQL expressions into our AST
- Transform to SQLGlot expressions
- Handle operator differences (`==` → `=`)
- Preserve operator precedence

## File Structure

```
asql/
├── __init__.py          # Public API
├── dialect.py           # ASQL SQLGlot dialect (Tokenizer, Parser, Generator)
├── parser.py            # Custom parser (fallback if dialect approach doesn't work)
├── compiler.py          # ASQL AST → SQLGlot AST (if using custom parser)
├── expressions.py       # Expression transformation (if using custom parser)
├── resolver.py           # Schema resolution, relationship inference, plural/singular handling
├── schema.py             # Schema registry, model loading, FK inference
└── errors.py            # Error classes

tests/
├── test_parser.py      # Parser tests
├── test_compiler.py    # Compiler tests
├── test_expressions.py # Expression tests
└── test_integration.py # End-to-end tests

pyproject.toml          # Project config
README.md               # Documentation
SPEC.md                 # Language specification
ARCHITECTURE.md         # This file
```

## Dependencies

- **sqlglot**: SQL parsing, AST building, SQL generation, dialect transpilation (core dependency)
- **lark**: Parser generator (only if custom parser approach needed as fallback)
- **pytest**: Testing framework
- **pytest-cov**: Test coverage

## Testing Strategy

1. **Unit Tests**: Test each component in isolation
   - Parser: Test tokenization and AST building
   - Compiler: Test AST transformation
   - Expressions: Test expression parsing and transformation

2. **Integration Tests**: Test full ASQL → SQL transformation
   - Simple queries
   - Complex queries with multiple pipeline steps
   - Edge cases and error conditions

3. **SQLGlot Testing**: Use SQLGlot's testing utilities if available
   - Verify generated SQL is valid
   - Test dialect-specific output

4. **Regression Tests**: Test against examples from SPEC.md
   - Ensure all examples compile correctly
   - Verify SQL output matches expected patterns

## Development Tools & Playground

### SQLGlot Execution Engine
SQLGlot provides a Python execution engine (`sqlglot.executor.execute`) that can run SQL queries against in-memory Python dictionaries. This is useful for:
- Testing ASQL → SQL → execution pipeline
- Creating a playground/REPL for ASQL
- Unit testing with sample data

### Example Dataset Strategy
**For ASQL Demos & Testing**:
- **Primary**: Use SQLGlot's "sushi" example pattern (simple, clear relationships)
- **Extended**: Consider Chinook database (standard SQL demo dataset)
- **Custom**: Create ASQL-specific demo datasets that showcase:
  - Foreign key relationships (for auto-join testing)
  - Plural/singular table names (Users/User)
  - Time-based data (for date function testing)
  - Multiple FK patterns (owner_user_id, manager_user_id)

**Example Dataset Structure** (for ASQL playground):
```python
tables = {
    "users": [
        {"id": 1, "name": "Alice", "country": "US", "created_at": "2024-01-01"},
        {"id": 2, "name": "Bob", "country": "UK", "created_at": "2024-01-02"},
    ],
    "accounts": [
        {"id": 1, "user_id": 1, "amount": 100.0},
        {"id": 2, "user_id": 2, "amount": 200.0},
    ],
    "opportunities": [
        {"id": 1, "owner_id": 1, "amount": 500.0, "status": "open"},
        {"id": 2, "owner_id": 2, "amount": 300.0, "status": "closed"},
    ],
}
```

### ASQL Playground/REPL
**Plan**: Build a simple CLI/REPL for ASQL:
- Interactive query interface
- Show ASQL → SQL transformation
- Execute queries using SQLGlot's executor
- Display results
- Support multiple SQL dialects

**Implementation** (Future Stage):
- `asql repl` - Interactive REPL
- `asql compile <query>` - Show SQL output
- `asql execute <query>` - Execute and show results
- `asql playground` - Web-based playground (optional)

## Next Steps

1. Review and approve this architecture
2. Start with Stage 1: Foundation
3. Implement incrementally with TDD
4. Build playground/REPL for testing and demos
5. Iterate based on testing and feedback

