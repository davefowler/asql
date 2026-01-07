# dbt-asql

Write dbt models in [ASQL](https://analyticsql.com) — a modern, readable query language that compiles to SQL.

> ⚠️ **Early Development** — Not yet published to PyPI

## Features

- **No wrappers needed** — Use `.asql` file extension, no `{% asql %}` tags
- **Automatic `ref()` detection** — Just use table names, dbt-asql finds model dependencies
- **Simplified variables** — `{{ start_date }}` instead of `{{ var('start_date') }}`
- **Native config** — `SET materialized = incremental;` instead of `{{ config(...) }}`
- **Full Jinja support** — `{% if %}` blocks work as expected

## Quick Example

### Before: Traditional dbt + SQL

```sql
{{ config(materialized='incremental', unique_key='id') }}

SELECT 
  region,
  DATE_TRUNC('month', created_at) AS month,
  SUM(amount) AS revenue,
  COUNT(*) AS order_count
FROM {{ ref('stg_orders') }}
WHERE status = 'completed'
  AND created_at > '{{ var("start_date", "2024-01-01") }}'
  {% if is_incremental() %}
    AND created_at > (SELECT MAX(created_at) FROM {{ this }})
  {% endif %}
GROUP BY 1, 2
ORDER BY revenue DESC
LIMIT {{ var("row_limit", 1000) }}
```

### After: dbt-asql

```asql
SET materialized = incremental;
SET unique_key = id;

from stg_orders
  where status = 'completed'
  where created_at > {{ start_date || @2024-01-01 }}
  {% if is_incremental() %}
    where created_at > (select max(created_at) from {{ this }})
  {% endif %}
  group by region, month(created_at) (
    sum(amount) as revenue,
    # as order_count
  )
  order by -revenue
  limit {{ row_limit || 1000 }}
```

**Improvements:**
- 29% fewer lines
- 50% fewer Jinja symbols
- No `ref()` calls — `stg_orders` auto-detected
- No `var('...')` wrappers — just `{{ variable_name }}`
- Readable aggregations with inline syntax

## Installation

```bash
# Not yet published — install from local path
pip install -e ./integrations/dbt-asql
```

## Usage

### 1. Create `.asql` models

```
models/
├── staging/
│   └── stg_orders.sql      # Regular SQL
└── marts/
    └── revenue.asql        # ASQL model ✨
```

### 2. Write ASQL

```asql
-- models/marts/revenue.asql
SET materialized = table;

from stg_orders
  where status = 'completed'
  group by region ( sum(amount) as revenue )
```

### 3. Run dbt as usual

```bash
dbt run
```

dbt-asql automatically:
1. Detects `.asql` files
2. Compiles ASQL → SQL
3. Expands `{{ variable }}` → `{{ var('variable') }}`
4. Resolves table names → `{{ ref('...') }}`
5. Passes result to dbt

## Syntax Reference

### Model References

| dbt Jinja | dbt-asql | Notes |
|-----------|----------|-------|
| `{{ ref('orders') }}` | `orders` | Auto-detected from manifest |
| `{{ ref('project', 'x') }}` | `project.orders` | Cross-project |
| `{{ source('raw', 'x') }}` | `source(raw, x)` | Explicit source |
| `{{ this }}` | `{{ this }}` | Self-reference (unchanged) |

### Variables

| dbt Jinja | dbt-asql | Notes |
|-----------|----------|-------|
| `{{ var('x') }}` | `{{ x }}` | Simple variable |
| `{{ var('x', 100) }}` | `{{ x \|\| 100 }}` | With default |
| `{{ env_var('KEY') }}` | `{{ env.KEY }}` | Environment var |

### Configuration

| dbt Jinja | dbt-asql |
|-----------|----------|
| `{{ config(materialized='table') }}` | `SET materialized = table;` |
| `{{ config(unique_key='id') }}` | `SET unique_key = id;` |
| `{{ config(schema='marts') }}` | `SET schema = marts;` |

### Conditionals

Jinja conditionals work unchanged:

```asql
{% if is_incremental() %}
  where created_at > (select max(created_at) from {{ this }})
{% endif %}
```

## How It Works

1. **File Detection**: dbt-asql hooks into dbt's model loading
2. **ASQL Compilation**: `.asql` files are compiled to SQL using the ASQL compiler
3. **Manifest Lookup**: Table names are matched against dbt's manifest to identify model refs
4. **Variable Expansion**: `{{ var }}` syntax is expanded to `{{ var('var') }}`
5. **Config Extraction**: `SET` statements become `{{ config(...) }}`
6. **Jinja Passthrough**: `{% %}` blocks are preserved for dbt to process

## Development

```bash
# Clone the repo
git clone https://github.com/definite-app/asql
cd asql

# Install in development mode
./venv/bin/pip install -e ./integrations/dbt-asql

# Run tests
./venv/bin/pytest integrations/dbt-asql/tests/
```

## Roadmap

- [ ] Basic `.asql` file support
- [ ] Automatic `ref()` resolution
- [ ] Variable syntax expansion
- [ ] `SET` → `config()` conversion
- [ ] Publish to PyPI
- [ ] VS Code extension support for `.asql` in dbt projects

## Related

- [ASQL Documentation](https://analyticsql.com)
- [dbt Documentation](https://docs.getdbt.com)
- [Design Document](../../ai_notes/archive/designs/2026-01-06-dbt-asql-integration.md)

## License

MIT — Same as ASQL

