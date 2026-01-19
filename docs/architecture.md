# Analytic SQL Architecture

**Last Updated:** January 19, 2026

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
```asql-play
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

### 3. Transpiler (`asql/transpile.py`)

The `asql.transpile()` function is the main entry point for converting ASQL to SQL.

**Key Responsibilities:**
- Accept ASQL query string and target dialect
- Handle multiple queries separated by semicolons
- Parse each query using `ASQLParser`
- Apply dialect-aware transforms (spine, alias_reuse, column_operators, list_comprehension)
- Generate SQL using SQLGlot's generator
- Format SQL output (pretty printing)

**Dialect Support:**
- Uses SQLGlot's dialect system for SQL generation
- Full ASQL feature support for primary dialects: DuckDB, PostgreSQL, MySQL, Snowflake, BigQuery, Redshift, Databricks, Trino
- Other SQLGlot dialects work for basic SQL generation (passthrough mode)
- Some features have dialect limitations (see `docs/dialect-limitations.md`)

### 4. Dialect Definition (`asql/dialect/`)

The ASQL dialect is a full SQLGlot dialect implementation in the `asql/dialect/` package:

**Components:**
- `tokenizer.py`: Token mappings (`|` → PIPE, `#` → COUNT shorthand, etc.)
- `parser.py`: Full ASQL syntax parsing with TRANSFORM_PARSERS pattern
- `generator.py`: AST to ASQL string output
- `dialect.py`: Dialect class registration with SQLGlot

**Key Features:**
- FROM-first syntax parsing
- Pipeline operators (`|`, transform chaining)
- ASQL-specific operators (`&` for joins, `#` for COUNT, `@` for dates)
- Proper CTE wrapping for pipeline semantics

**Integration:**
Use `asql.transpile()` for ASQL → SQL conversion:
```python
import asql
import sqlglot

# ASQL → PostgreSQL
asql.transpile(asql_query, write='postgres')[0]

# SQL → ASQL (use sqlglot directly)
sqlglot.transpile(sql_query, read='postgres', write='asql')[0]
```

### 5. Generator (`asql/dialect/generator.py`)

The ASQL Generator converts SQLGlot AST back to ASQL syntax. This integrates with SQLGlot's standard `transpile()` API.

**Key Methods:**
- `select_sql()`: Generates FROM-first ASQL output
- `join_sql()`: Converts SQL joins to ASQL symbols (`&`, `&?`, etc.)
- `with_sql()`: Converts CTEs to `stash as` syntax
- `cast_sql()`: Generates `::` cast syntax

**Usage:**
```python
import sqlglot
import asql  # Registers the ASQL dialect

# Convert SQL to ASQL
asql_query = sqlglot.transpile(sql, write='asql')[0]
```

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
├── __init__.py          # Public API (transpile, etc.)
├── transpile.py         # Main transpile() function
├── expressions.py       # Custom AST nodes (Spine, CohortBy)
├── dialect/             # SQLGlot dialect implementation
│   ├── __init__.py      # Package exports
│   ├── tokenizer.py     # ASQLTokenizer - token mappings
│   ├── parser.py        # ASQLParser - ASQL syntax parsing
│   ├── generator.py     # ASQLGenerator - AST to ASQL output
│   ├── dialect.py       # ASQL dialect registration
│   └── transforms/      # Parser-stage transforms (no dialect needed)
│       ├── underscore_shorthands.py  # days_since_col → DATEDIFF
│       ├── auto_alias.py             # Automatic column aliasing
│       ├── auto_qualify.py           # Column qualification in joins
│       ├── join_fk_shorthand.py      # ON user_id expansion
│       ├── join_inference.py         # FK relationship inference
│       └── cohort_transform.py       # Cohort analysis CTEs
├── compiler/            # Dialect-aware transforms (transpile stage)
│   ├── spine.py         # Spine gap-filling (explicit spine())
│   ├── alias_reuse.py   # CTE chain for alias reuse
│   ├── column_operators.py  # EXCEPT expansion
│   ├── list_comprehension.py  # DuckDB [x FOR x] conversion
│   └── auto_spine.py    # Helper functions for spine generation
├── functions.py         # Function registry
├── config.py            # Configuration classes
└── errors.py            # Error classes

tests/
├── test_parser.py       # Parser tests
├── test_compiler.py     # Compiler tests
├── test_reverse_translation.py  # SQL to ASQL tests
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
