# ASQL Examples Library

This directory contains comprehensive examples of ASQL queries organized by category.

## Running Examples

### Run All Examples

```bash
python examples/run_all.py
```

### Run Specific Example Modules

```python
from examples import basic_queries

basic_queries.example_from_where()
```

### Import and Use in Your Code

```python
from examples.basic_queries import example_from_where

asql, sql = example_from_where()
print(f"ASQL: {asql}")
print(f"SQL: {sql}")
```

## Example Categories

### Basic Queries (`basic_queries.py`)

- Simple FROM clauses
- WHERE filtering
- SELECT operations
- Combining FROM, WHERE, SELECT
- Multiple WHERE conditions
- OR conditions
- NOT operator
- Comparison operators

### Aggregations (`aggregations.py`)

- GROUP BY with COUNT (#)
- GROUP BY with SUM
- GROUP BY with AVG
- Multiple aggregations
- Multiple grouping columns
- GROUP BY with WHERE
- All aggregation functions

### Sorting and Limiting (`sorting_and_limiting.py`)

- SORT ascending
- SORT descending
- Multiple sort columns
- TAKE/LIMIT
- GROUP BY + SORT
- Complete pipelines
- Top N queries

### Derived Columns (`derived_columns.py`)

- Simple DERIVE
- DERIVE with WHERE
- Multiple DERIVE clauses

### Complex Queries (`complex_queries.py`)

- Complex analytics queries
- User analytics
- Sales reports
- Time-based analysis

## Example Structure

Each example function:
- Returns a tuple of `(asql_query, sql_output)`
- Prints the ASQL and SQL for demonstration
- Can be imported and used programmatically

## Contributing Examples

When adding new examples:

1. Add the example function to the appropriate module
2. Follow the naming convention: `example_<description>()`
3. Include a docstring describing what the example demonstrates
4. Return `(asql, sql)` tuple
5. Update this README if adding a new category
