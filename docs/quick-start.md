# ASQL Quick Start Guide

Get started with ASQL in minutes!

## Installation

```bash
pip install -e .
```

Or with development dependencies:

```bash
pip install -e ".[dev]"
```

## Your First Query

```python
from asql import compile

# Simple query
asql = "from users"
sql = compile(asql)
print(sql)
# Output: SELECT * FROM users
```

## Basic Syntax

### FROM - Start with a table

```python
asql = "from users"
```

### WHERE - Filter rows

```python
asql = 'from users where status == "active"'
```

### SELECT - Choose columns

```python
asql = "from users select name, email"
```

### GROUP BY - Aggregate data

```python
asql = "from users group by country ( # as total_users )"
```

The `#` symbol is shorthand for `COUNT(*)`.

### SORT - Order results

```python
# Ascending
asql = "from users sort name"

# Descending (use - prefix)
asql = "from users sort -total_users"
```

### TAKE - Limit results

```python
asql = "from users take 10"
```

## Combining Operations

ASQL uses a pipeline syntax - operations flow from top to bottom:

```python
asql = """
from users
where status == "active"
group by country ( # as total_users )
sort -total_users
take 10
"""

sql = compile(asql, dialect="postgres")
```

## Comparison Operators

- `==` - equals
- `!=` - not equals
- `<`, `>`, `<=`, `>=` - comparisons
- `is null`, `is not null` - null checks

```python
asql = "from users where age >= 18 and email is not null"
```

## Logical Operators

- `and` - logical AND
- `or` - logical OR
- `not` - logical NOT

```python
asql = 'from users where status == "active" or status == "pending"'
```

## Aggregations

Supported aggregation functions:

- `#` or `count(*)` - count rows
- `sum(column)` - sum values
- `avg(column)` - average values
- `min(column)` - minimum value
- `max(column)` - maximum value

```python
asql = """
from sales 
group by region (
    sum(amount) as revenue,
    # as orders,
    avg(amount) as avg_order
)
"""
```

## Dialect Support

ASQL can generate SQL for different database dialects:

```python
# PostgreSQL
sql = compile(asql, dialect="postgres")

# MySQL
sql = compile(asql, dialect="mysql")

# BigQuery
sql = compile(asql, dialect="bigquery")
```

## Next Steps

- Check out [EXAMPLES.md](EXAMPLES.md) for comprehensive examples
- Try the [Interactive Playground](#interactive-playground)
- Read the [Language Specification](../SPEC.md)
