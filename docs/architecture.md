# Analytic SQL Architecture

**Last Updated:** November 16, 2025

This document describes the actual implementation of Analytic SQL (ASQL), a pipeline-based query language that transpiles to SQL.

## Overview

Analytic SQL is implemented as a Python library that parses ASQL syntax and generates standard SQL using SQLGlot. The system uses a custom parser to handle ASQL's unique pipeline syntax, then transforms the parsed structure into SQLGlot's AST for SQL generation.

## High-Level Flow

```
ASQL Text 
  → ASQLParser (custom parser)
  → PipelineStep objects
  → SQLGlot AST (with CTEs)
  → SQLGlot Generator
  → SQL String
```

The key insight is that ASQL's pipeline syntax is transformed into SQL Common Table Expressions (CTEs), where each pipeline step becomes a CTE that feeds into the next step.

## Core Components

### 1. Parser (`asql/parser.py`)

The `ASQLParser` class handles parsing ASQL syntax into an internal representation that can be converted to SQLGlot AST.

**Key Responsibilities:**
- Parse pipeline syntax (`from`, `where`, `group by`, `order by`, `limit`)
- Handle ASQL-specific operators (`==`, `!=`, `#` for count)
- Parse expressions and aggregations
- Handle `with` statements for CTEs
- Parse joins (`join ... on ...`)
- Convert parsed elements into `PipelineStep` objects

**Implementation Approach:**
- Custom recursive descent parser (not using SQLGlot's parser directly)
- Line-by-line parsing with indentation awareness
- Expression parsing using SQLGlot's expression parser where possible
- Builds `PipelineStep` objects that track each transformation step

### 2. Pipeline System (`asql/pipeline.py`)

The pipeline system manages how ASQL's sequential operations are transformed into SQL CTEs.

**PipelineStep Class:**
- Tracks a single transformation step (FROM, WHERE, GROUP BY, etc.)
- Stores SQLGlot expressions for each clause
- Supports multiple WHERE clauses and JOINs per step
- Can have a `store_name` for named CTEs

**CTE Generation:**
- `build_cte_pipeline()` converts a list of `PipelineStep` objects into a SQLGlot AST
- Each step becomes a CTE (except the final step)
- CTEs are named descriptively (e.g., `1_where_status`, `2_group_by_country`)
- The final step becomes the main SELECT statement

**Example Transformation:**
```asql
from users
where status = "active"
group by country ( # as total_users )
```

Becomes:
```sql
WITH 1_where_status AS (
  SELECT * FROM users WHERE status = 'active'
)
SELECT country, COUNT(*) AS total_users
FROM 1_where_status
GROUP BY country
```

### 3. Compiler (`asql/compiler.py`)

The `compile()` function is the main entry point for converting ASQL to SQL.

**Key Responsibilities:**
- Accept ASQL query string and target dialect
- Handle multiple queries separated by semicolons
- Parse each query using `ASQLParser`
- Extract and merge CTEs from multiple queries
- Generate SQL using SQLGlot's generator
- Format SQL output (pretty printing)

**Dialect Support:**
- Uses SQLGlot's dialect system for SQL generation
- Supports all SQLGlot dialects (PostgreSQL, MySQL, BigQuery, Snowflake, etc.)
- Dialect-specific SQL generation handled automatically by SQLGlot

### 4. Dialect Definition (`asql/dialect.py`)

The `ASQLDialect` class extends SQLGlot's `Dialect` but is currently minimal.

**Current Implementation:**
- Defines keyword mappings (IF → WHERE, PROJECT → SELECT, SORT → ORDER BY, TAKE → LIMIT)
- Mostly used for keyword recognition, not full parsing
- The actual parsing is handled by the custom `ASQLParser`

**Note:** The system primarily uses a custom parser rather than fully leveraging SQLGlot's dialect system, as ASQL's syntax is too different from SQL for direct SQLGlot parsing.

### 5. Reverse Compiler (`asql/reverse_compiler.py`)

The reverse compiler converts SQL back to ASQL syntax.

**Key Functions:**
- `reverse_compile()`: Converts SQL to ASQL
- `detect_dialect()`: Attempts to detect the SQL dialect

**Use Cases:**
- Converting existing SQL queries to ASQL
- Learning ASQL by seeing SQL equivalents
- Migration tools

### 6. Error Handling (`asql/errors.py`)

Custom exception classes for ASQL-specific errors.

**Error Types:**
- `ASQLError`: Base exception class
- `ASQLSyntaxError`: Syntax errors in ASQL queries
- `ASQLCompilationError`: Errors during compilation
- `ASQLResolutionError`: Schema resolution errors (not currently used)

## Implementation Details

### Expression Parsing

ASQL expressions are parsed using SQLGlot's expression parser where possible:
- Binary operators (`==`, `!=`, `<`, `>`, `<=`, `>=`, `and`, `or`)
- Unary operators (`-`, `not`)
- Function calls (`sum()`, `avg()`, `year()`, etc.)
- Identifiers (table.column, column)
- Literals (strings, numbers)

The parser converts ASQL operators to SQL operators:
- `==` → `=`
- `#` → `COUNT(*)`
- `-column` → `ORDER BY column DESC`

### Pipeline to CTE Transformation

Each pipeline step is converted to a CTE:
1. First step: Creates initial CTE with FROM and WHERE clauses
2. Subsequent steps: Create CTEs that SELECT from previous CTEs
3. Final step: Main SELECT statement that may include GROUP BY, ORDER BY, LIMIT

This approach ensures that:
- Each transformation step is explicit
- Complex queries remain readable
- SQL output is clear and debuggable

### Multiple Query Handling

The compiler supports multiple queries separated by semicolons:
- Each query is parsed separately
- CTEs from all queries are collected
- CTEs are merged into the final query
- Useful for defining reusable CTEs with `with` statements

### WITH Statement Support

ASQL supports `with variable = query` syntax:
- Creates a named CTE
- Can be referenced in subsequent queries
- Stored in the CTE registry for reuse

## File Structure

```
asql/
├── __init__.py          # Public API (compile, reverse_compile, etc.)
├── parser.py            # ASQLParser - custom parser for ASQL syntax
├── compiler.py          # Main compile() function
├── pipeline.py          # PipelineStep and CTE generation
├── dialect.py           # ASQLDialect (minimal, mostly keyword mappings)
├── reverse_compiler.py   # SQL to ASQL conversion
└── errors.py            # Error classes

tests/
├── test_parser.py       # Parser tests
├── test_compiler.py    # Compiler tests
├── test_pipeline_cte.py # Pipeline/CTE tests
├── test_basic.py        # Basic query tests
├── test_join.py         # Join tests
└── ...                  # Additional test files
```

## Dependencies

- **sqlglot**: Core dependency for SQL AST manipulation and SQL generation
- **pytest**: Testing framework

## Design Decisions

### Why Custom Parser?

ASQL's syntax is fundamentally different from SQL:
- Pipeline-based (`from users where ...`) vs SELECT-first (`SELECT ... FROM users`)
- Different operator syntax (`==` vs `=`)
- Count shorthand (`#` vs `COUNT(*)`)
- Indentation-based structure

SQLGlot's parser expects SQL syntax, so a custom parser was necessary to handle ASQL's unique structure.

### Why SQLGlot for SQL Generation?

SQLGlot provides:
- Proven SQL AST library
- Support for multiple SQL dialects
- Handles SQL generation edge cases
- Active maintenance

The system uses SQLGlot for:
- Expression parsing (where SQL syntax is used)
- AST building (SQLGlot AST nodes)
- SQL generation (dialect-specific SQL output)

### Pipeline to CTE Approach

Converting pipeline steps to CTEs provides:
- Clear separation of transformation steps
- Readable SQL output
- Easy debugging (each step is explicit)
- Natural mapping from ASQL's sequential syntax

## Current Limitations

- Schema resolution and relationship inference are not yet implemented
- No automatic join inference (joins must be explicit)
- No plural/singular table name resolution
- No foreign key inference

These features are planned but not yet implemented in the current version.

## Testing

The codebase includes comprehensive tests:
- Unit tests for parser, compiler, and pipeline components
- Integration tests for end-to-end ASQL → SQL conversion
- Tests for multiple SQL dialects
- Edge case and error handling tests

Tests use pytest and follow TDD principles where possible.
