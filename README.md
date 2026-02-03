# ASQL: Analytic SQL

A modern, pipe-based query language that transpiles to SQL. ASQL uses a FROM-first, pipeline syntax that makes complex analytics queries more readable and intuitive.

## What is ASQL?

ASQL (Analytic SQL) transforms how you write SQL queries. Instead of the traditional nested, inside-out SQL syntax, ASQL lets you write queries as a pipeline of operations that flow top-to-bottom:

```asql
from orders
where status == "completed"
group by region ( sum(amount) as revenue )
order by -revenue
limit 10
```

This compiles to standard SQL (PostgreSQL, BigQuery, Snowflake, etc.) with each step becoming a readable CTE.

**Key Benefits:**
- **Readable** - Queries flow top-to-bottom like natural thought
- **Multi-dialect** - One query compiles to PostgreSQL, BigQuery, Snowflake, Redshift, MySQL, and more
- **Debuggable** - Each pipeline step becomes a named CTE you can inspect
- **Interactive** - Built-in playground to experiment in your browser

## Getting Started

### Prerequisites

ASQL uses [just](https://github.com/casey/just) as a command runner. Install it first:

```bash
# macOS
brew install just

# Linux
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/bin

# Or via cargo
cargo install just
```

### Installation

```bash
git clone <repo-url>
cd asql
just install
```

That's it! This creates a Python virtual environment and installs all dependencies.

### Start Developing

```bash
just serve
```

This launches:
- **Documentation**: http://localhost:8000
- **Playground**: http://localhost:5001

## Common Commands

| Command | Description |
|---------|-------------|
| `just install` | Set up virtual environment and install all dependencies |
| `just serve` | Start docs + playground servers (hot reload enabled) |
| `just test` | Run all tests |
| `just test tests/test_compiler.py` | Run a specific test file |
| `just test -k "pattern"` | Run tests matching a pattern |
| `just lint` | Run the linter |
| `just lint --fix` | Run linter and auto-fix issues |
| `just kill` | Stop any running dev servers |
| `just --list` | Show all available commands |

## Quick Example

```python
from asql import compile

asql_query = """
from users
where status == "active"
group by country ( # as total_users )
order by -total_users
limit 10
"""

sql = compile(asql_query, dialect="postgres")
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

## Language Overview

### Basic Syntax

ASQL uses a pipe syntax where operations flow from top to bottom:

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

## Project Structure

```
asql/
├── asql/              # Core library
│   ├── compiler.py    # ASQL → SQL compiler
│   ├── dialect.py     # SQL dialect support
│   ├── parser.py      # ASQL parser
│   └── schema.py      # Schema handling
├── playground/        # Interactive web playground (FastAPI)
├── docs/              # Documentation (MkDocs)
├── tests/             # Test suite
├── examples/          # Example queries
└── vscode-extension/  # VS Code syntax highlighting
```

## Supported SQL Dialects

ASQL compiles to multiple SQL dialects via [SQLGlot](https://github.com/tobymao/sqlglot):

- PostgreSQL
- BigQuery
- Snowflake
- Redshift
- MySQL
- SQLite
- DuckDB
- And more

## Documentation

- [Quick Start Guide](docs/quick_start.md) - Get started in minutes
- [Examples](docs/examples.md) - Comprehensive examples with SQL output
- [Language Specification](docs/spec.md) - Complete ASQL syntax reference
- [Architecture](ARCHITECTURE.md) - System design and implementation details

Or run `just serve` and browse the interactive docs at http://localhost:8000.

## VS Code Extension

ASQL has a VS Code extension for syntax highlighting and snippets. See [`vscode-extension/README.md`](vscode-extension/README.md) for installation.

## Contributing

1. Fork the repo and create a feature branch
2. Write tests for new features (`just test`)
3. Ensure linting passes (`just lint`)
4. Submit a pull request

## Status

See [STATUS.md](STATUS.md) for current implementation status and roadmap.
