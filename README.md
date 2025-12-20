# ASQL: Analytic SQL

> **⚠️ Work in Progress**: ASQL is under active development. The language and implementation are evolving rapidly. Do not rely on this for production use yet.

**ASQL** (pronounced "Ask-el") is a modern query language that transpiles to SQL. It's designed to make analytics queries **feel like asking questions**, not writing code.

```asql
from orders
  where order_date >= @2024-01-01
  & customers on orders.customer_id = customers.id
  group by customers.country (
    sum(amount) as revenue,
    # as order_count
  )
  order by -revenue
  limit 10
```

## Why ASQL?

| Pain Point | SQL | ASQL |
|------------|-----|------|
| **Query structure** | SELECT comes first, but you don't know columns yet | FROM-first, natural top-to-bottom flow |
| **Joins** | Verbose, repetitive | Symbolic operators (`&`, `&?`) + auto-joins via FK conventions |
| **Counting** | `COUNT(*)` everywhere | Just `#` |
| **Descending sort** | `ORDER BY x DESC` | `order by -x` |
| **Date literals** | Varies by dialect | `@2024-01-01` everywhere |
| **Relative dates** | `CURRENT_DATE - INTERVAL '7 days'` | `7 days ago` |
| **Date truncation** | `DATE_TRUNC('month', x)` | `month(x)` |
| **COALESCE** | `COALESCE(a, b, c)` | `a ?? b ?? c` |
| **Case statements** | 5+ lines of CASE WHEN | `status = "active" ? 1 : 0` |
| **String matching** | `LIKE '%pattern%'` | `contains "pattern"` |

## Before & After

**SQL (traditional):**
```sql
WITH filtered_orders AS (
  SELECT * FROM orders 
  WHERE order_date >= DATE '2024-01-01'
),
with_customers AS (
  SELECT o.*, c.country
  FROM filtered_orders o
  LEFT JOIN customers c ON o.customer_id = c.id
)
SELECT 
  country,
  SUM(amount) AS revenue,
  COUNT(*) AS order_count
FROM with_customers
GROUP BY country
ORDER BY revenue DESC
LIMIT 10;
```

**ASQL:**
```asql
from orders
  where order_date >= @2024-01-01
  &? customers on orders.customer_id = customers.id
  group by customers.country (
    sum(amount) as revenue,
    # as order_count
  )
  order by -revenue
  limit 10
```

Each pipeline step compiles to a descriptive CTE, making the generated SQL self-documenting and easy to debug.

## Key Features

### 🔗 Intuitive Joins

Join operators make the join type visually clear:

```asql
from orders & customers on ...      -- INNER JOIN (& = both required)
from orders &? customers on ...     -- LEFT JOIN  (&? = right optional)
from orders ?& customers on ...     -- RIGHT JOIN (?& = left optional)
from orders ?&? customers on ...    -- FULL OUTER (?&? = both optional)
```

**Auto-joins via FK naming conventions:**
```asql
from orders
  select orders.amount, orders.customer.name  -- auto LEFT JOIN via customer_id
```

### 📅 Clean Date Handling

```asql
from events
  where created_at >= @2024-01-01        -- Date literals with @
  where created_at >= 7 days ago         -- Relative dates
  group by month(created_at) (           -- Easy truncation
    # as event_count
  )
```

### 📊 Natural Aggregations

```asql
from sales
  group by region (
    sum(amount) as revenue,
    avg(amount) as avg_order,
    # as order_count,                    -- # = COUNT(*)
    #(distinct customer_id) as customers -- COUNT(DISTINCT)
  )
```

### 🎯 Deduplication Made Easy

```asql
-- Keep only the most recent order per customer
from orders
  per customer_id first by -order_date

-- Add row numbers per customer
from orders  
  per customer_id number by -order_date
```

### 🔄 Multi-Dialect Support

ASQL compiles to PostgreSQL, BigQuery, Snowflake, MySQL, Redshift, and more via [SQLGlot](https://github.com/tobymao/sqlglot).

```python
from asql import compile

sql = compile(asql_query, dialect="bigquery")
```

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install ASQL
pip install -e .

# Or with dev dependencies
pip install -e ".[dev]"
```

## Quick Start

```python
from asql import compile

query = """
from users
  where status = "active"
  group by country ( # as total_users )
  order by -total_users
  limit 10
"""

sql = compile(query, dialect="postgres")
print(sql)
```

## Documentation

- 📖 **[Quick Start Guide](docs/quick_start.md)** — Get started in minutes
- 📋 **[Language Specification](docs/spec.md)** — Complete syntax reference
- 📚 **[Examples](docs/examples.md)** — Real-world query patterns

### Interactive Playground

Try ASQL in your browser with real-time SQL compilation:

```bash
pip install -e ".[docs,playground]"
./serve.sh
```

Then open http://localhost:5001

## VS Code Extension

Syntax highlighting and snippets for `.asql` files. See [`vscode-extension/README.md`](vscode-extension/README.md) for installation.

## Development

```bash
# Run tests (always use venv!)
./venv/bin/pytest tests/

# Run with coverage
./venv/bin/pytest tests/ --cov=asql --cov-report=html
```

## Contributing

Contributions welcome! Please:
1. Write tests for new features
2. Follow existing code patterns  
3. Run tests before submitting


---

*ASQL is inspired by [PRQL](https://prql-lang.org/), [Malloy](https://www.malloydata.dev/), and [KQL](https://learn.microsoft.com/en-us/azure/data-explorer/kusto/query/), aiming to make SQL feel more like natural language while maintaining full SQL power.*
