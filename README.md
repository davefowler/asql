# ASQL: Analytic SQL

A modern, pipeline-based query language that transpiles to SQL.

## Installation

```bash
pip install -e .
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=asql --cov-report=html
```

## Usage

```python
from asql import compile

sql = compile("""
from users
  where status == "active"
  group by country ( total_users as # )
  sort -total_users
""")

print(sql)
```

