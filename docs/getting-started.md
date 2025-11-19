# Getting Started with ASQL

Welcome to ASQL! This guide will help you get started quickly.

## Installation

### Basic Installation

```bash
pip install -e .
```

### With Development Tools

```bash
pip install -e ".[dev]"
```

### With Playground

```bash
pip install -e ".[playground]"
```

Or install everything:

```bash
pip install -e ".[dev,playground]"
```

## Your First Query

Create a file `example.py`:

```python
from asql import compile

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

Run it:

```bash
python example.py
```

## Next Steps

1. **Try Examples**: Run `python examples/run_all.py` to see all examples
2. **Read Documentation**: Check out [Examples](examples.md) for comprehensive examples
3. **Use Playground**: Start the interactive playground with `python playground.py`
4. **Read Spec**: See [Language Specification](spec.md) for complete language reference

## Interactive Playground

The playground provides a web-based interface to try ASQL:

```bash
# Install playground dependencies first
pip install -e ".[playground]"

# Start the playground
python playground.py
```

Then open http://localhost:5000 in your browser.

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=asql --cov-report=html

# Run specific test file
pytest tests/test_compiler.py
```

## Common Patterns

### Basic Query

```python
from asql import compile

sql = compile("from users")
```

### With Filtering

```python
sql = compile('from users where status == "active"')
```

### With Aggregation

```python
sql = compile("from users group by country ( # as total_users )")
```

### Complete Pipeline

```python
sql = compile("""
from users
where status == "active"
group by country ( # as total_users )
sort -total_users
take 10
""")
```

## Resources

- 📖 [Quick Start Guide](quick-start.md)
- 📚 [Examples](examples.md)
- 🎮 [Interactive Playground](interactive-playground.md)
- 📋 [Language Specification](spec.md)
- 🏗️ [Architecture](architecture.md)

## Getting Help

- Check the [Examples](EXAMPLES.md) for common patterns
- Review the [Language Specification](../SPEC.md) for syntax details
- Try the [Interactive Playground](INTERACTIVE_PLAYGROUND.md) to experiment
- See [STATUS.md](../STATUS.md) for known limitations
