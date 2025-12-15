# Replacing dbt's Core Runtime Features with ASQL

**Purpose**: This document covers the "last 20%" of dbt replacement - the orchestration and runtime features that require deeper integration beyond SQL-shape macros.

**See also**: `macros.md` covers the 80% of dbt-utils macros (pivot, unpivot, deduplicate, union, surrogate_key, safe_cast, etc.) that are SQL-shape transformations.

**This document covers**:
- `ref()` - Model references and DAG building
- `source()` - Raw source references
- `config()` - Model configuration
- `incremental by` + `existing` - Incremental logic
- `assert` - Data quality testing

**Assumption**: ASQL has access to dbt's manifest.json, catalog.json, and schema metadata - the same context dbt has.

---

## 1. `ref()` - Model References

### The Problem

dbt requires wrapping every model reference in `ref()`:

```sql
-- dbt: ref() is required because SQL has no way to express "resolve this model name"
SELECT * FROM {{ ref('stg_customers') }}

-- Without ref(), you'd hardcode schemas which breaks across environments:
SELECT * FROM prod.stg_customers  -- 💥 Broken in dev!
```

**Why does dbt need this?**

1. **DAG Building** - dbt parses `ref()` calls to build the dependency graph, determining model execution order
2. **Schema Resolution** - Resolves to different schemas per environment:
   - Dev: `dev_dave.stg_customers`
   - CI: `ci_pr_123.stg_customers`  
   - Prod: `prod.stg_customers`
3. **Cross-Project References** - `ref('other_project', 'model')` can reference external dbt projects

**Why Jinja?** SQL has no concept of "model references" vs "literal table names". Jinja's `ref()` is a workaround to inject this metadata before SQL is generated.

---

### ASQL Solution: Automatic Model Resolution

ASQL, as a compiled language with access to dbt context, can handle this transparently. Every `from table_name` is treated as a model reference that gets resolved at compile time:

```asql
from stg_customers
  where is_active
```

**ASQL Compiler Behavior:**

1. **Parse phase**: Extract all `from` table references → build dependency DAG
2. **Resolution phase**: Apply environment-specific schema mapping from dbt config
3. **Generate phase**: Output SQL with resolved `database.schema.table`

```asql
-- You write:
from stg_customers

-- ASQL compiles (in dev) to:
SELECT * FROM dev_dave.stg_customers

-- ASQL compiles (in prod) to:
SELECT * FROM prod.stg_customers
```

**Key insight**: ASQL eliminates `ref()` entirely by making model resolution the default behavior. No more forgetting `ref()` and accidentally hardcoding schemas.

---

### Literal Table References

For cases where you DON'T want model resolution (raw tables, external tables):

```asql
-- Model reference (resolved by ASQL) - DEFAULT
from stg_customers

-- Literal table reference (not resolved, used as-is):
from literal prod.raw_customers
-- or quoted:
from "prod.raw_customers"
```

---

### Cross-Project References

```asql
-- Reference model from another dbt project
from project.other_project.shared_customers
-- or
from external other_project.shared_customers
```

---

## 2. `source()` - Raw Source References

### The Problem

dbt uses `source()` to reference raw data tables defined in sources.yml:

```sql
SELECT * FROM {{ source('stripe', 'payments') }}
```

This provides:
- Lineage tracking between raw data and models
- Source freshness monitoring
- Separation of "raw" vs "transformed" data

---

### ASQL Solution: `source` Keyword

```asql
-- Explicit source reference
from source stripe.payments
  where status == "completed"
  select id, amount, customer_id

-- Alternative: @ syntax
from @stripe.payments
```

**Behavior:**
- ASQL reads source definitions from dbt's `sources.yml`
- Resolves to the actual database/schema/table
- Tracks lineage separately from model-to-model refs

---

## 3. `config()` - Model Configuration

### The Problem

dbt uses Jinja `config()` blocks at the top of models:

```sql
{{ config(
    materialized='incremental',
    unique_key='id',
    partition_by={'field': 'created_date', 'data_type': 'date'}
) }}

SELECT * FROM {{ source('events') }}
```

---

### ASQL Solution: YAML Config Block

ASQL supports a clean config block at the top of files:

```asql
config:
  materialized: incremental
  unique_key: id
  partition_by: created_date

from source events.raw_events
  select *
```

**Alternative: Inline directives**

```asql
-- @materialized: incremental
-- @unique_key: id

from source events.raw_events
  select *
```

**Behavior:**
- Config block is parsed and passed to dbt for materialization
- ASQL compiles the query; dbt handles the materialization strategy
- Full compatibility with dbt's config options

---

## 4. `incremental by` + `existing` - Incremental Logic

### The Problem

dbt's incremental logic is verbose and conditional:

```sql
SELECT * FROM {{ source('events') }}
{% if is_incremental() %}
WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
```

**Key insight**: The query itself is ALWAYS incremental - it's the **run mode** that changes:
- 99% of runs: Incremental (scheduled, normal operation)
- 1% of runs: Full refresh (explicit `--full-refresh` flag)

The `is_incremental()` conditional exists because Jinja needs to generate different SQL. But ASQL controls SQL generation!

---

### ASQL Solution: Declarative `incremental by`

Instead of conditional logic, **declare** the incremental strategy:

```asql
from source events.raw_events
  incremental by updated_at
  select *
```

**That's it.** The ASQL compiler handles the rest:
- **Normal run**: Adds `WHERE updated_at > (SELECT MAX(updated_at) FROM existing)`
- **Full refresh** (`--full-refresh`): Skips the filter entirely

No conditionals, no Jinja, no mental overhead.

---

### Syntax Options

```asql
-- Option 1: incremental by (recommended)
from source events.raw_events
  incremental by updated_at

-- Option 2: increment with  
from source events.raw_events
  increment with updated_at

-- Option 3: natural language
from source events.raw_events
  since last_run by updated_at
```

---

### Advanced: Custom Incremental Strategies

For non-standard patterns:

```asql
-- By ID instead of timestamp
from source events.raw_events
  incremental by id

-- Composite key
from source events.raw_events
  incremental by (updated_at, id)

-- Custom expression (escape hatch)
from source events.raw_events
  incremental where updated_at > max(existing.updated_at) or id > max(existing.id)
```

---

### The `existing` Keyword

Use `existing` as a reserved table alias for the already-materialized version of this model:

```asql
-- Use any SQL function with existing.column:
incremental where updated_at > max(existing.updated_at)
incremental where id > max(existing.id)
incremental where hash not in (select hash from existing)
incremental where (date, id) > (select max(date), max(id) from existing)
```

**Why `existing` (not `this`, `OLD`, or special functions):**
- **Clear meaning**: "data that already exists in this model"
- **Not overloaded**: `OLD` in SQL triggers means something different (the row being updated)
- **Not confusing**: `this` is a dbt-ism that doesn't read naturally  
- **Composable**: Works with any SQL function - no need for `max_existing()`, `min_existing()`, etc.
- **Just a table alias**: Simple concept, powerful usage

**Complex patterns with `existing`:**

```asql
-- Merge/upsert pattern
incremental where hash not in (select hash from existing)

-- Composite watermark
incremental where (updated_at, id) > (select max(updated_at), max(id) from existing)

-- Window-based (reprocess last 3 days)
incremental where date >= (select max(date) - interval '3 days' from existing)
```

---

### Comparison: dbt vs ASQL

| Aspect | dbt | ASQL |
|--------|-----|------|
| Syntax | Jinja if/else conditional | Declarative `incremental by` |
| Mental model | "Sometimes filter, sometimes don't" | "This model is incremental" |
| Run mode | Embedded in query logic | External flag (`--full-refresh`) |
| Self-reference | `{{ this }}` | `existing` |
| Readability | Template soup | Clean SQL-like |

---

### Compile Behavior

```asql
-- You write:
from source events.raw_events
  incremental by updated_at
  select id, event_type, updated_at

-- Normal run compiles to:
SELECT id, event_type, updated_at
FROM events.raw_events
WHERE updated_at > (SELECT MAX(updated_at) FROM this_model)

-- Full refresh (--full-refresh) compiles to:
SELECT id, event_type, updated_at  
FROM events.raw_events
-- No WHERE clause
```

---

## 5. `assert` - Data Quality Testing (future?)

### The Problem

dbt-expectations and similar packages provide data quality assertions:

```sql
{{ dbt_expectations.expect_column_values_to_not_be_null(column_name='id') }}
```

These are typically separate test files, not inline with the model.

---

### ASQL Solution: Inline Assertions

```asql
from orders
  assert id is not null
  assert amount >= 0
  assert status in ('pending', 'completed', 'cancelled')
  select *
```

---

### What Do Assertions Actually DO?

This is a critical design decision. Several options:

**Option A: Generate dbt tests (RECOMMENDED)**

Assertions compile to dbt test definitions, run as separate queries after the model builds:

```asql
from orders
  assert id is not null
  assert amount >= 0
```

Compiles to model SQL (no assertions in query):
```sql
SELECT * FROM orders
```

Plus generates dbt test YAML:
```yaml
models:
  - name: this_model
    columns:
      - name: id
        tests:
          - not_null
      - name: amount
        tests:
          - dbt_utils.expression_is_true:
              expression: ">= 0"
```

**Pros**: Matches dbt workflow, tests run after model, clear pass/fail
**Cons**: Assertions aren't enforced in the SQL itself

---

**Option B: Fail on violation (strict mode)**

Wrap query in validation that errors if any row fails:

```sql
-- Compiled SQL
WITH validated AS (
  SELECT *,
    CASE WHEN NOT (id IS NOT NULL) THEN 'id must not be null'
         WHEN NOT (amount >= 0) THEN 'amount must be >= 0'
         ELSE NULL END as _validation_error
  FROM orders
)
SELECT * FROM validated
WHERE _validation_error IS NULL
  -- Plus: SELECT 1/0 FROM validated WHERE _validation_error IS NOT NULL LIMIT 1
  -- (forces error if any violations exist)
```

**Pros**: Guarantees data quality at query time
**Cons**: Requires database-specific error triggering, complex

---

**Option C: Filter out bad rows (lenient mode)**

Assertions become WHERE clauses - violating rows are silently removed:

```asql
from orders
  assert id is not null    -- becomes: WHERE id IS NOT NULL
  assert amount >= 0       -- becomes: AND amount >= 0
```

**Pros**: Simple, data is always clean
**Cons**: Silently drops data - dangerous! Where did those rows go?

---

**Option D: Add validation columns (informational)**

Add columns marking validity, don't filter:

```sql
SELECT *,
  (id IS NOT NULL) as _valid_id,
  (amount >= 0) as _valid_amount,
  (id IS NOT NULL AND amount >= 0) as _is_valid
FROM orders
```

**Pros**: Preserves all data, downstream can decide
**Cons**: Doesn't actually enforce anything, bloats schema

---

### Recommendation

**Default: Option A (generate dbt tests)**

Most intuitive for dbt users. Assertions are documentation + tests, not runtime enforcement.

```asql
from orders
  assert id is not null as "Order ID required"
  assert amount >= 0 as "Amount must be positive"
  select *
```

The assertions:
1. Are visible in the ASQL code (documentation)
2. Compile to dbt tests (run after model builds)
3. Don't affect the SQL query itself

**Optional: Strict mode flag**

For cases where you NEED runtime enforcement:

```asql
from orders
  assert strict id is not null  -- fails build if violated
  -- or
  assert filter amount >= 0     -- removes violating rows (explicit about filtering)
```

Or at the config level:
```asql
config:
  assert_mode: strict  # or: filter, test_only (default)
```

---

### Assert vs Where

Key distinction:
- `where` is for business logic filtering ("only active users")
- `assert` is for data quality ("this should never be null")

```asql
from orders
  where status == "completed"     -- Business logic: only completed orders
  assert id is not null           -- Data quality: IDs should never be null
  assert amount > 0               -- Data quality: completed orders must have amount
```

If `where` filters out rows, that's expected.
If `assert` would filter out rows, something is WRONG with the data.

---

## Complete Example: dbt vs ASQL

### dbt Version (Jinja + SQL)

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id'
) }}

WITH source AS (
    SELECT * FROM {{ source('ecommerce', 'raw_orders') }}
),

deduplicated AS (
    {{ dbt_utils.deduplicate(
        relation='source',
        partition_by='order_id',
        order_by='updated_at desc'
    ) }}
),

transformed AS (
    SELECT
        {{ dbt_utils.generate_surrogate_key(['order_id', 'customer_id']) }} as sk,
        {{ dbt_utils.star(from=ref('orders'), except=['created_at']) }},
        {{ dbt.safe_cast('amount', 'decimal(10,2)') }} as amount_decimal
    FROM deduplicated
    {% if is_incremental() %}
    WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
    {% endif %}
)

SELECT * FROM transformed
```

### ASQL Version

```asql
config:
  materialized: incremental
  unique_key: order_id

from source ecommerce.raw_orders
  deduplicate by order_id keeping -updated_at
  incremental by updated_at
  select 
    key(order_id, customer_id) as sk,
    * except (created_at),
    amount::decimal(10,2)? as amount_decimal
```

**Reduction**: ~30 lines → 10 lines. No Jinja. No CTEs. Readable.

---

## Summary: The Last 20%

This document covers the dbt features that require deeper integration:

| Feature | dbt Syntax | ASQL Syntax |
|---------|------------|-------------|
| Model refs | `{{ ref('model') }}` | `from model` (automatic) |
| Source refs | `{{ source('src', 'tbl') }}` | `from source src.tbl` |
| Config | `{{ config(...) }}` | `config:` block |
| Incremental | `{% if is_incremental() %}` | `incremental by column` |
| Self-reference | `{{ this }}` | `existing` |
| Assertions | dbt-expectations tests | `assert condition` |

**Combined with macros.md** (the 80%: deduplicate, pivot, unpivot, union, key, safe cast, etc.), ASQL can replace nearly all dbt Jinja with clean, readable syntax.

---

## Architecture: ASQL + dbt Integration

```
ASQL (Query Language)
 ├─ Model reference resolution (replaces ref)
 ├─ Source reference resolution (replaces source)
 ├─ Incremental logic compilation (replaces is_incremental)
 ├─ Config block parsing (replaces config macro)
 ├─ SQL-shape operators (from macros.md)
 └─ Deterministic SQL output
        ↓
dbt (Orchestration)
 ├─ DAG execution (ASQL provides dependency info)
 ├─ Materializations (ASQL provides config)
 ├─ Environment management
 ├─ Testing framework
 └─ Deployment
```

ASQL handles the **query language**; dbt handles the **build system**.

---

## Why This Matters

With these features, writing dbt models becomes:
- **No Jinja** - Pure ASQL syntax
- **No mental overhead** - Declare intent, not conditionals
- **No forgetting ref()** - Model resolution is automatic
- **No verbose patterns** - `incremental by updated_at` instead of 5 lines of Jinja

ASQL doesn't replace dbt - it makes dbt models **dramatically simpler to write and maintain**.
