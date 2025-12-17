# ASQL: Analytic SQL

A modern, pipeline-based query language that transpiles to SQL. ASQL uses a FROM-first, pipeline-based syntax that makes complex analytics queries more readable and intuitive.

## Features

- 🚀 **Fully Pipeline-based** - Every query is a sequence of transformations, compiled to CTEs
- 🔄 **SQL Dialect Support** - Generate SQL for PostgreSQL, MySQL, BigQuery, Snowflake, and more
- 📊 **Powerful Aggregations** - GROUP BY with multiple aggregations
- 🎯 **Expressive Filtering** - Rich WHERE clause with logical operators
- 📈 **Sorting & Limiting** - Easy SORT and TAKE operations
- 🎨 **Interactive Playground** - Try ASQL in your browser
- 🔗 **CTE-based Compilation** - Each pipeline step becomes a descriptive CTE for readability and debugging

## Installation

First, create and activate a virtual environment:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

Then install ASQL:

```bash
pip install -e .
```

Or with development dependencies:

```bash
pip install -e ".[dev]"
```

## VS Code Extension

ASQL has VS Code extension support for syntax highlighting, snippets, and language features!

📦 **Installation**: See [`vscode-extension/README.md`](vscode-extension/README.md) for installation instructions.

✨ **Features**:
- Syntax highlighting for ASQL keywords, operators, and functions
- Code snippets for common query patterns
- Smart indentation for pipeline syntax
- File association for `.asql` files

For more details, see [`vscode-extension/VSCODE_INTEGRATION.md`](vscode-extension/VSCODE_INTEGRATION.md).

## Quick Start

```python
from asql import compile

# Simple query
asql = """
from users
where status == "active"
group by country ( # as total_users )
order by -total_users
limit 10
"""

sql = compile(asql, dialect="postgres")
print(sql)
```

**Output:**
```sql
WITH 1_where_status AS (
  SELECT * FROM users WHERE status = 'active'
),
2_group_by_country AS (
  SELECT country, COUNT(*) AS total_users
  FROM 1_where_status
  GROUP BY country
)
SELECT country, total_users
FROM 2_group_by_country
ORDER BY total_users DESC
LIMIT 10
```

Each pipeline step becomes a descriptive CTE, making the generated SQL self-documenting and easy to debug!

## Documentation

The ASQL documentation is served via a web server that includes:
- 📖 Interactive documentation with dialect tabs
- 🎮 Embedded playground for trying ASQL
- 📚 Examples with live SQL compilation
- 📋 Complete language specification

### Serving the Documentation

```bash
# Install dependencies
pip install -e ".[docs,playground]"

# Start both MkDocs and Playground
./serve.sh
```

This starts:
- **Documentation (MkDocs)**: http://localhost:8000
- **Playground**: http://localhost:5001

### Documentation Features

- **Dialect Tabs**: Every ASQL code example automatically shows tabs for different SQL dialects (PostgreSQL, BigQuery, Snowflake, Redshift, etc.)
- **Embedded Playground**: Try ASQL directly in the documentation
- **Live Compilation**: See SQL output for any ASQL query
- **Navigation**: Easy navigation between docs pages with persistent sidebar

### Documentation Pages

- 📖 [Quick Start Guide](docs/quick_start.md) - Get started in minutes
- 📚 [Comprehensive Examples](docs/examples.md) - Extensive examples with SQL output
- 🎮 [Interactive Playground](docs/playground.md) - Try ASQL in your browser
- 🏗️ [Architecture](ARCHITECTURE.md) - System design and implementation details
- 📋 [Language Specification](docs/spec.md) - Complete ASQL syntax reference

## Interactive Playground

Try ASQL in your browser! The playground lets you write ASQL queries and see the generated SQL in real-time.

### Start the Playground

```bash
# Start docs + playground (recommended)
./serve.sh
```

Then open http://localhost:5001 in your browser.

**Note**: The playground runs on FastAPI + Uvicorn.

The playground features:
- ✨ Real-time ASQL → SQL compilation
- 🎨 Syntax highlighting
- 📝 Pre-built example queries
- 🔄 Multiple SQL dialect support
- 📋 Copy-to-clipboard functionality

## Examples Library

Run all examples:

```bash
python examples/run_all.py
```

Or import specific examples:

```python
from examples import basic_queries, aggregations, sorting_and_limiting

# Run basic query examples
basic_queries.example_from_where()

# Run aggregation examples
aggregations.example_group_by_sum()

# Run sorting examples
sorting_and_limiting.example_complete_pipeline()
```

## Language Overview

### Basic Syntax

ASQL uses a pipeline-based syntax where operations flow from top to bottom:

```asql
from users                    # Start with a table
where status == "active"      # Filter rows
group by country (            # Group and aggregate
    # as total_users
)
order by -total_users            # Sort descending
limit 10                      # Limit results
```

### Comparison Operators

- `==` - equals
- `!=` - not equals  
- `<`, `>`, `<=`, `>=` - comparisons
- `is null`, `is not null` - null checks

```asql
from users where age >= 18 and email is not null
```

### Logical Operators

- `and` - logical AND
- `or` - logical OR
- `not` - logical NOT

```asql
from users where status == "active" or status == "pending"
```

### Aggregations

Supported functions:
- `#` or `count(*)` - count rows
- `sum(column)` - sum values
- `avg(column)` - average values
- `min(column)` - minimum value
- `max(column)` - maximum value

```asql
from sales group by region (
    sum(amount) as revenue,
    # as orders,
    avg(amount) as avg_order
)
```

### Sorting

- `order by column` - ascending
- `order by -column` - descending (use `-` prefix)

```asql
from users order by -total_users, name
```

### Limiting

```asql
from users limit 10
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
./venv/bin/pytest tests/

# Run tests with coverage
./venv/bin/pytest tests/ --cov=asql --cov-report=html

# Run specific test file
./venv/bin/pytest tests/test_compiler.py
```

## Project Structure

```
asql/
├── asql/              # Core library
│   ├── parser.py      # ASQL parser
│   ├── compiler.py    # SQL compiler
│   ├── dialect.py     # Dialect support
│   └── errors.py     # Error handling
├── tests/             # Test suite
├── examples/          # Example queries
├── docs/              # Documentation
├── playground/        # Interactive web playground (FastAPI)
└── pyproject.toml     # Project configuration
```

## Supported SQL Dialects

- PostgreSQL
- MySQL
- BigQuery
- Snowflake
- Redshift
- SQLite
- And more (via SQLGlot)

## Contributing

Contributions are welcome! Please:

1. Write tests for new features
2. Follow the existing code style
3. Update documentation as needed
4. Run tests before submitting

## License

MIT License

## Status

See [STATUS.md](STATUS.md) for current implementation status and known limitations.
