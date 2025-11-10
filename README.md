# ASQL: Analytic SQL

A modern, pipeline-based query language that transpiles to SQL. ASQL uses a FROM-first, pipeline-based syntax that makes complex analytics queries more readable and intuitive.

## Features

- 🚀 **Pipeline-based syntax** - Queries flow naturally from top to bottom
- 🔄 **SQL Dialect Support** - Generate SQL for PostgreSQL, MySQL, BigQuery, Snowflake, and more
- 📊 **Powerful Aggregations** - GROUP BY with multiple aggregations
- 🎯 **Expressive Filtering** - Rich WHERE clause with logical operators
- 📈 **Sorting & Limiting** - Easy SORT and TAKE operations
- 🧮 **Derived Columns** - DERIVE for computed columns
- 🎨 **Interactive Playground** - Try ASQL in your browser

## Installation

```bash
pip install -e .
```

Or with development dependencies:

```bash
pip install -e ".[dev]"
```

## Quick Start

```python
from asql import compile

# Simple query
asql = """
from users
where status == "active"
group by country ( # as total_users )
sort -total_users
take 10
"""

sql = compile(asql, dialect="postgres")
print(sql)
```

**Output:**
```sql
SELECT country, COUNT(*) AS total_users 
FROM users 
WHERE status = 'active' 
GROUP BY country 
ORDER BY total_users DESC 
LIMIT 10
```

## Documentation

- 📖 [Quick Start Guide](docs/QUICK_START.md) - Get started in minutes
- 📚 [Comprehensive Examples](docs/EXAMPLES.md) - Extensive examples with SQL output
- 🏗️ [Architecture](ARCHITECTURE.md) - System design and implementation details
- 📋 [Language Specification](SPEC.md) - Complete ASQL syntax reference

## Interactive Playground

Try ASQL in your browser! The playground lets you write ASQL queries and see the generated SQL in real-time.

### Start the Playground

```bash
# Install playground dependencies
pip install -e ".[playground]"

# Run the playground
python playground.py
```

Then open http://localhost:5000 in your browser.

**Note**: The playground requires Flask. Install it with `pip install -e ".[playground]"` or `pip install flask`.

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
sort -total_users            # Sort descending
take 10                      # Limit results
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

- `sort column` - ascending
- `sort -column` - descending (use `-` prefix)

```asql
from users sort -total_users, name
```

### Limiting

```asql
from users take 10
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=asql --cov-report=html

# Run specific test file
pytest tests/test_compiler.py
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
├── playground.py      # Interactive web playground
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


## Status

See [STATUS.md](STATUS.md) for current implementation status and known limitations.
