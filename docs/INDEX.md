# Welcome to ASQL

**ASQL: Analytic SQL** - A modern, pipeline-based query language that transpiles to SQL.

ASQL uses a FROM-first, pipeline-based syntax that makes complex analytics queries more readable and intuitive.

## Quick Start

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

**Output:**
```sql
SELECT country, COUNT(*) AS total_users 
FROM users 
WHERE status = 'active' 
GROUP BY country 
ORDER BY total_users DESC 
LIMIT 10
```

## Features

- 🚀 **Pipeline-based syntax** - Queries flow naturally from top to bottom
- 🔄 **SQL Dialect Support** - Generate SQL for PostgreSQL, MySQL, BigQuery, Snowflake, and more
- 📊 **Powerful Aggregations** - GROUP BY with multiple aggregations
- 🎯 **Expressive Filtering** - Rich WHERE clause with logical operators
- 📈 **Sorting & Limiting** - Easy SORT and TAKE operations

## Documentation

- 📖 [Quick Start Guide](quick-start.md) - Get started in minutes
- 📚 [Examples](examples.md) - Extensive examples with SQL output
- 🎮 [Interactive Playground](interactive-playground.md) - Try ASQL in your browser
- 📋 [Language Specification](spec.md) - Complete ASQL syntax reference
- 🏗️ [Architecture](architecture.md) - System design and implementation details

## Installation

```bash
pip install -e .
```

Or with development dependencies:

```bash
pip install -e ".[dev]"
```

## Next Steps

1. Read the [Getting Started Guide](getting-started.md)
2. Browse [Examples](examples.md) to see what's possible
3. Check the [Language Specification](spec.md) for complete syntax reference
4. Review [Status](status.md) for current implementation status
