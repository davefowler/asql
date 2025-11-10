# ASQL Documentation and Examples Guide

This document provides an overview of all documentation, examples, and interactive resources available for ASQL.

## 📚 Documentation Structure

### Main Documentation (`docs/`)

1. **INDEX.md** - Documentation index and navigation
2. **QUICK_START.md** - Get started in minutes
3. **EXAMPLES.md** - Comprehensive examples with ASQL → SQL translations
4. **GETTING_STARTED.md** - Installation and first steps
5. **INTERACTIVE_PLAYGROUND.md** - Playground usage guide

### Examples Library (`examples/`)

1. **basic_queries.py** - Basic FROM, WHERE, SELECT examples
2. **aggregations.py** - GROUP BY and aggregation examples
3. **sorting_and_limiting.py** - SORT and TAKE examples
4. **complex_queries.py** - Complex multi-operation queries
5. **run_all.py** - Script to run all examples

### Root Documentation

- **README.md** - Main project documentation
- **EXAMPLES_SUMMARY.md** - Quick reference to all examples
- **SPEC.md** - Complete language specification
- **ARCHITECTURE.md** - System design
- **STATUS.md** - Implementation status

## 🎮 Interactive Playground

### Features

- **Real-time compilation** - See SQL as you type
- **Multiple dialects** - PostgreSQL, MySQL, BigQuery, Snowflake, Redshift
- **Example library** - 12+ pre-built examples
- **Copy functionality** - Easy copying of queries
- **Clean UI** - Split-panel interface

### Usage

```bash
# Install dependencies
pip install -e ".[playground]"

# Start playground
python playground.py

# Open http://localhost:5000
```

### API Endpoint

The playground exposes a REST API:

```bash
curl -X POST http://localhost:5000/api/compile \
  -H "Content-Type: application/json" \
  -d '{"asql": "from users", "dialect": "postgres"}'
```

## 📖 Quick Start Paths

### For Beginners

1. Read [docs/QUICK_START.md](docs/QUICK_START.md)
2. Try the [Interactive Playground](#interactive-playground)
3. Browse [docs/EXAMPLES.md](docs/EXAMPLES.md)
4. Run `python examples/run_all.py`

### For Developers

1. Read [ARCHITECTURE.md](ARCHITECTURE.md)
2. Review [SPEC.md](SPEC.md)
3. Check [STATUS.md](STATUS.md) for current features
4. Explore `examples/` code

### For Users

1. Start with [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)
2. Use the playground to experiment
3. Reference [docs/EXAMPLES.md](docs/EXAMPLES.md) for patterns
4. Check [EXAMPLES_SUMMARY.md](EXAMPLES_SUMMARY.md) for quick reference

## 📝 Example Categories

### 1. Basic Queries (8+ examples)
- Simple FROM
- WHERE filtering
- SELECT operations
- Logical operators
- Comparison operators
- NULL checks

### 2. Aggregations (7+ examples)
- GROUP BY with COUNT (#)
- SUM, AVG, MIN, MAX
- Multiple aggregations
- Multiple grouping columns

### 3. Sorting & Limiting (7+ examples)
- SORT ascending/descending
- Multiple sort columns
- TAKE/LIMIT
- Complete pipelines

### 4. Complex Queries (4+ examples)
- Analytics queries
- User analytics
- Sales reports
- Time-based analysis

**Total: 29+ comprehensive examples**

## 🔍 Finding Information

### I want to...

- **Learn ASQL syntax** → [docs/QUICK_START.md](docs/QUICK_START.md) or [SPEC.md](SPEC.md)
- **See examples** → [docs/EXAMPLES.md](docs/EXAMPLES.md) or `examples/`
- **Try it interactively** → Run `python playground.py`
- **Understand implementation** → [ARCHITECTURE.md](ARCHITECTURE.md)
- **Check what's supported** → [STATUS.md](STATUS.md)
- **Run example code** → `python examples/run_all.py`

## 🚀 Running Examples

### Run All Examples

```bash
python examples/run_all.py
```

### Run Specific Category

```bash
python examples/basic_queries.py
python examples/aggregations.py
python examples/sorting_and_limiting.py
python examples/complex_queries.py
```

### Use Programmatically

```python
from examples import basic_queries

asql, sql = basic_queries.example_from_where()
print(f"ASQL: {asql}")
print(f"SQL: {sql}")
```

## 📊 Documentation Statistics

- **Documentation Files**: 10+
- **Example Files**: 6 Python modules
- **Total Examples**: 29+
- **Documentation Pages**: 5 main docs
- **Interactive Features**: Web playground + API

## 🎯 Key Features

### Documentation
- ✅ Comprehensive examples with SQL output
- ✅ Quick start guides
- ✅ Complete language specification
- ✅ Architecture documentation
- ✅ Interactive playground guide

### Examples
- ✅ Organized by category
- ✅ Runnable Python code
- ✅ Can be imported programmatically
- ✅ Cover all major features
- ✅ Include complex use cases

### Playground
- ✅ Real-time compilation
- ✅ Multiple SQL dialects
- ✅ Pre-built examples
- ✅ Copy functionality
- ✅ REST API

## 📦 Installation

### Basic
```bash
pip install -e .
```

### With Dev Tools
```bash
pip install -e ".[dev]"
```

### With Playground
```bash
pip install -e ".[playground]"
```

### Everything
```bash
pip install -e ".[dev,playground]"
```

## 🔗 Quick Links

- [Main README](README.md)
- [Examples Summary](EXAMPLES_SUMMARY.md)
- [Documentation Index](docs/INDEX.md)
- [Quick Start](docs/QUICK_START.md)
- [Comprehensive Examples](docs/EXAMPLES.md)
- [Playground Guide](docs/INTERACTIVE_PLAYGROUND.md)
- [Language Spec](SPEC.md)
- [Architecture](ARCHITECTURE.md)

## 🎓 Learning Path

1. **Start**: Read [docs/QUICK_START.md](docs/QUICK_START.md)
2. **Try**: Use the playground (`python playground.py`)
3. **Learn**: Browse [docs/EXAMPLES.md](docs/EXAMPLES.md)
4. **Practice**: Run `python examples/run_all.py`
5. **Reference**: Keep [SPEC.md](SPEC.md) handy
6. **Build**: Create your own queries!

## 💡 Tips

- Use the playground to experiment safely
- Check examples before writing complex queries
- Reference SPEC.md for exact syntax
- Run examples to see real SQL output
- Try different dialects in the playground

## 🤝 Contributing

When adding documentation or examples:

1. **Examples**: Add to appropriate `examples/` module
2. **Documentation**: Update relevant `docs/` file
3. **Playground**: Add examples to playground if appropriate
4. **Index**: Update INDEX.md or EXAMPLES_SUMMARY.md

## ✅ Verification

All documentation and examples have been tested:

- ✅ All examples run successfully
- ✅ Documentation is complete
- ✅ Playground code is ready (requires Flask)
- ✅ Examples can be imported
- ✅ All links work

---

**Last Updated**: Documentation complete with 29+ examples, comprehensive guides, and interactive playground.
