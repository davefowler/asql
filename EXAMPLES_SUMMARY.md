# ASQL Examples Summary

This document provides a quick reference to all available ASQL examples and resources.

## Quick Access

- **📚 Comprehensive Examples**: [docs/EXAMPLES.md](docs/EXAMPLES.md)
- **🎮 Interactive Playground**: Run `python playground.py` (requires Flask)
- **🐍 Python Examples**: `examples/` directory
- **📖 Quick Start**: [docs/QUICK_START.md](docs/QUICK_START.md)

## Example Categories

### 1. Basic Queries (`examples/basic_queries.py`)

- Simple FROM clauses
- WHERE filtering with various operators
- SELECT operations
- Combining operations
- Logical operators (AND, OR, NOT)
- Comparison operators (==, !=, <, >, <=, >=)
- NULL checks (IS NULL, IS NOT NULL)

**Run**: `python examples/basic_queries.py`

### 2. Aggregations (`examples/aggregations.py`)

- GROUP BY with COUNT (#)
- GROUP BY with SUM, AVG, MIN, MAX
- Multiple aggregations
- Multiple grouping columns
- GROUP BY with WHERE filters

**Run**: `python examples/aggregations.py`

### 3. Sorting and Limiting (`examples/sorting_and_limiting.py`)

- SORT ascending/descending
- Multiple sort columns
- TAKE/LIMIT
- Complete pipelines with all operations

**Run**: `python examples/sorting_and_limiting.py`

### 4. Derived Columns (`examples/derived_columns.py`)

- Simple DERIVE
- DERIVE with WHERE
- Multiple DERIVE clauses

**Run**: `python examples/derived_columns.py`

### 5. Complex Queries (`examples/complex_queries.py`)

- Complex analytics queries
- User analytics
- Sales reports
- Time-based analysis

**Run**: `python examples/complex_queries.py`

## Running All Examples

```bash
python examples/run_all.py
```

## Using Examples Programmatically

```python
from examples import basic_queries, aggregations

# Run a specific example
asql, sql = basic_queries.example_from_where()
print(f"ASQL: {asql}")
print(f"SQL: {sql}")

# Run aggregation examples
aggregations.example_group_by_sum()
```

## Interactive Playground

The playground provides a web-based interface with:

- Real-time ASQL → SQL compilation
- Pre-built example queries
- Multiple SQL dialect support
- Copy-to-clipboard functionality

**Start**: `python playground.py` (requires `pip install -e ".[playground]"`)

## Documentation Examples

The [docs/EXAMPLES.md](docs/EXAMPLES.md) file contains:

- All examples with ASQL and SQL side-by-side
- Organized by category
- Ready to copy and paste
- Includes PostgreSQL dialect examples

## Example Count

- **Basic Queries**: 8+ examples
- **Aggregations**: 7+ examples
- **Sorting & Limiting**: 7+ examples
- **Derived Columns**: 3+ examples
- **Complex Queries**: 4+ examples

**Total**: 29+ comprehensive examples

## Contributing Examples

When adding new examples:

1. Add to the appropriate module in `examples/`
2. Follow the naming convention: `example_<description>()`
3. Include a docstring
4. Return `(asql, sql)` tuple
5. Update [docs/EXAMPLES.md](docs/EXAMPLES.md) if adding a new category
6. Add to playground examples if appropriate

## Example Structure

Each example function:

```python
def example_description():
    """Brief description of what this demonstrates."""
    asql = "from users where ..."
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql
```

## Next Steps

1. **Try Examples**: Run `python examples/run_all.py`
2. **Read Documentation**: Check [docs/EXAMPLES.md](docs/EXAMPLES.md)
3. **Use Playground**: Start with `python playground.py`
4. **Experiment**: Modify examples to learn ASQL
