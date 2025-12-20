# ASQL: Analytic SQL

> **⚠️ Work in Progress**: ASQL is under active development. Do not rely on this for production use yet.

**ASQL** (pronounced "Ask-el") is a pipeline-based query language for analysts. It brings modern pipe syntax to every SQL database—think of it as a **polyfill for the pipe syntaxes emerging in BigQuery, Snowflake, and PostgreSQL**, but available everywhere today.

```asql
from orders
  where order_date >= @2024-01-01
  &? customers on orders.customer_id = customers.id
  group by month(order_date) (
    sum(amount) as revenue,
    # as order_count
  )
  order by -revenue
```

## Why ASQL?

ASQL is designed for **analytics and transformation** work. It takes patterns that analysts use every day—cohorts, gap-filling, deduplication, window functions—and makes them first-class language features instead of 50-line CTEs.

### Key Features

| Feature | What It Does |
|---------|--------------|
| **🔀 Pipeline Syntax** | FROM-first, top-to-bottom flow—even on databases without native pipe support |
| **📊 Guaranteed Groups** | Auto-fills gaps in time series and categorical data (no more missing months!) |
| **🧱 dbt Macros Built-In** | `pivot`, `unpivot`, `key()`, `except`, deduplication—no Jinja needed |
| **🏷️ Auto-Aliasing** | Every function gets a meaningful name: `sum(amount)` → `sum_amount` |
| **📈 Cohort Analysis** | 50 lines of SQL → 3 lines with `cohort by` |
| **📅 Intuitive Dates** | `@2024-01-01`, `7 days ago`, `month(created_at)` |
| **💬 Natural Language** | `# of users`, `sum of amount`, `contains "pattern"` |
| **🪟 Window Helpers** | `per customer first by -date` instead of ROW_NUMBER() boilerplate |

---

## Feature Highlights

### 📊 Guaranteed Groups (Auto-Spine)

SQL's dirty secret: missing data just... disappears. ASQL fills the gaps automatically:

```asql
from orders
  where order_date >= @2024-01-01 and order_date < @2024-07-01
  group by month(order_date) (
    sum(amount) ?? 0 as revenue
  )
```

All six months appear—even those with zero revenue. No date spine CTEs, no dimension tables.

### 📈 Cohort Analysis Made Simple

**SQL** requires 50+ lines and 5 CTEs for basic retention analysis.

**ASQL**:
```asql
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date)
```

Automatically generates cohort assignment, period calculation, cohort sizes, and proper ordering.

### 🧱 dbt-Style Helpers, No Jinja

| dbt Macro | ASQL Built-In |
|-----------|---------------|
| `{{ dbt_utils.deduplicate() }}` | `per user_id first by -created_at` |
| `{{ dbt_utils.pivot() }}` | `pivot value by category values ('A', 'B')` |
| `{{ dbt_utils.unpivot() }}` | `unpivot jan, feb, mar into month, value` |
| `{{ dbt_utils.date_spine() }}` | Automatic with `group by month(...)` |
| `{{ dbt_utils.star(except=[...]) }}` | `except password_hash, ssn` |
| `{{ dbt_utils.generate_surrogate_key() }}` | `key(user_id, order_id)` |

### 🪟 Window Functions Without the Pain

**SQL** (10 lines for "latest order per customer"):
```sql
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY customer_id ORDER BY order_date DESC
    ) as rn FROM orders
) WHERE rn = 1;
```

**ASQL** (1 line):
```asql
from orders
  per customer_id first by -order_date
```

Other window helpers: `number by`, `rank by`, `prior()`, `next()`, `running_sum()`, `rolling_avg()`.

### 📅 Dates That Make Sense

```asql
from events
  where created_at >= @2024-01-01        -- Date literals
  where created_at >= 7 days ago         -- Relative dates
  where created_at >= 30 days ago        -- Works across dialects
  group by month(created_at) (...)       -- Clean truncation
  select days_since_signup               -- Time since patterns
```

### 🔗 Intuitive Joins

```asql
from orders & customers on ...      -- INNER JOIN (& = both required)
from orders &? customers on ...     -- LEFT JOIN  (&? = right optional)
from orders.customer.name           -- Auto-join via FK convention
```

---

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install -e .
```

## Quick Start

```python
from asql import compile

query = """
from users
  where status = "active"
  group by country ( # as total_users )
  order by -total_users
"""

sql = compile(query, dialect="postgres")  # or bigquery, snowflake, mysql...
```

## Multi-Dialect Support

ASQL compiles to PostgreSQL, BigQuery, Snowflake, Redshift, MySQL, DuckDB, and more via [SQLGlot](https://github.com/tobymao/sqlglot). Write once, run anywhere.

---

## Documentation

- 📖 **[Quick Start](docs/quick_start.md)** — Get started in minutes
- 📋 **[Language Spec](docs/spec.md)** — Complete syntax reference  
- 📊 **[Guaranteed Groups](docs/concepts/guaranteed-groups.md)** — Auto-spine deep dive
- 📈 **[Cohort Analysis](docs/syntax/cohorts.md)** — Retention made easy
- 🪟 **[Window Functions](docs/window_functions.md)** — Simplified window patterns
- 🧱 **[Coming from dbt](docs/coming-from/dbt.md)** — Macro equivalents

### Interactive Playground

```bash
pip install -e ".[docs,playground]"
./serve.sh
```

Then open http://localhost:5001

## Development

```bash
./venv/bin/pytest tests/
./venv/bin/pytest tests/ --cov=asql
```


---

*ASQL is inspired by [PRQL](https://prql-lang.org/), [Malloy](https://www.malloydata.dev/), [KQL](https://learn.microsoft.com/en-us/azure/data-explorer/kusto/query/), and the emerging pipe syntaxes in BigQuery, Snowflake, and PostgreSQL.*
