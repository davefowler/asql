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

### Option 1: CLI Preprocessor (Recommended)

The CLI approach compiles `.asql` files to `.sql` before running dbt.

**1. Create `.asql` models**

```
models/
├── staging/
│   └── stg_orders.sql      # Regular SQL
└── marts/
    └── revenue.asql        # ASQL model ✨
```

**2. Write ASQL**

```asql
-- models/marts/revenue.asql
SET materialized = table;

from stg_orders
  where status = 'completed'
  group by region ( sum(amount) as revenue )
```

**3. Compile and run**

```bash
# Compile .asql → .sql
dbt-asql compile

# Run dbt as usual
dbt run
```

**CLI Commands:**

```bash
# Compile all .asql files to .sql
dbt-asql compile

# Compile with specific dialect
dbt-asql compile --dialect snowflake

# Clean generated .sql files
dbt-asql clean

# Show help
dbt-asql --help
```

### Option 2: Jinja Extension

For inline ASQL in `.sql` files, use the `{% asql %}` tags:

```sql
-- models/marts/revenue.sql

{% asql %}
SET materialized = table;

from stg_orders
  where status = 'completed'
  group by region ( sum(amount) as revenue )
{% endasql %}
```

This approach works automatically when dbt-asql is installed.

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

### CLI Preprocessor

1. **File Discovery**: Scans `models/` for `.asql` files
2. **ASQL Compilation**: Compiles each file to SQL using the ASQL compiler
3. **Manifest Lookup**: Reads `target/manifest.json` to identify model refs
4. **Variable Expansion**: `{{ var }}` → `{{ var('var') }}`
5. **Config Extraction**: `SET` statements → `{{ config(...) }}`
6. **Output**: Creates `.sql` file alongside each `.asql` file

### Jinja Extension

1. **Environment Patch**: Adds `{% asql %}` tag to dbt's Jinja environment
2. **Block Parsing**: Captures content between `{% asql %}` and `{% endasql %}`
3. **Compilation**: Compiles ASQL → SQL inline
4. **Passthrough**: Returns SQL for dbt to process

## Technical Notes

### Why a CLI instead of native dbt plugin?

dbt's current plugin API (`dbtPlugin`) is designed for injecting nodes into the DAG, not for custom file extensions. The file extension handling is hardcoded in `dbt/parser/read_files.py` and only supports `.sql` and `.py` for models.

We've explored three approaches:

1. **CLI Preprocessor** ✅ — Works with any dbt version, no patches needed
2. **Jinja Extension** ✅ — Requires `{% asql %}` wrappers, but works automatically
3. **dbt Core PR** ⏳ — Feature request for plugin hooks for custom extensions

See the [research document](../../ai_notes/2026-01-07-dbt-plugin-api-research.md) for details.

## Development

```bash
# Clone the repo
git clone https://github.com/definite-app/asql
cd asql

# Install in development mode
./venv/bin/pip install -e ./integrations/dbt-asql

# Run tests
./venv/bin/pytest integrations/dbt-asql/tests/ -v
```

## Roadmap

- [x] Basic ASQL → SQL compilation
- [x] Automatic `ref()` resolution from manifest
- [x] Variable syntax expansion (`{{ x }}` → `{{ var('x') }}`)
- [x] `SET` → `config()` conversion
- [x] CLI preprocessor (`dbt-asql compile`)
- [x] Jinja extension (`{% asql %}...{% endasql %}`)
- [ ] Publish to PyPI
- [ ] VS Code extension support for `.asql` in dbt projects
- [ ] Watch mode for auto-compilation

## Related

- [ASQL Documentation](https://analyticsql.com)
- [dbt Documentation](https://docs.getdbt.com)
- [Design Document](../../ai_notes/archive/designs/2026-01-06-dbt-asql-integration.md)

## License

MIT — Same as ASQL
