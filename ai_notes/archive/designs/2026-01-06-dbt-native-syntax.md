# Investigation: Native dbt Syntax in ASQL

**Date**: January 6, 2026  
**Goal**: Explore how ASQL could simplify dbt syntax while keeping `{{ }}` familiar for variables

> **UPDATE**: After discussion, decided to keep `{{ }}` for variables (familiar to dbt users) but simplify what goes inside. See main integration doc for final approach.

---

## Background

dbt users currently write models like this:

```sql
{{ config(materialized='incremental', unique_key='id') }}

SELECT *
FROM {{ ref('stg_orders') }}
WHERE created_at > '{{ var("start_date") }}'
{% if is_incremental() %}
  AND created_at > (SELECT MAX(created_at) FROM {{ this }})
{% endif %}
```

This is verbose and mixes SQL with Jinja templating. If ASQL had native dbt support, it could look like:

```asql
config materialized=incremental, unique_key=id

from @stg_orders
  where created_at > @var:start_date
  if incremental: where created_at > (select max(created_at) from @this)
```

Much cleaner! This document investigates what's possible.

---

## Part 1: Detection Strategy

### Can we detect ASQL vs SQL automatically?

Yes, with high confidence. ASQL has distinctive patterns:

| Pattern | ASQL | SQL |
|---------|------|-----|
| Starts with `from` (no SELECT) | ✅ | Rare (subquery only) |
| Uses `&` or `&?` for joins | ✅ | ❌ Never |
| Uses `#` for count | ✅ | ❌ Never |
| Uses `@` for dates | ✅ | ❌ Never |
| Uses `-` for descending | ✅ | ❌ Never |
| Uses `??` for coalesce | ✅ | ❌ Never |
| Uses `per ... first by` | ✅ | ❌ Never |
| Uses `group by ... ()` | ✅ | ❌ Never |
| Uses `stash as` | ✅ | ❌ Never |

### Detection Algorithm

```python
def is_asql(code: str) -> bool:
    # Remove comments and whitespace
    cleaned = strip_comments(code)
    
    # Strong indicators (definitely ASQL)
    strong_indicators = [
        r'\b&\?\b',           # LEFT JOIN symbol
        r'\?\&\b',            # RIGHT JOIN symbol
        r'\bstash\s+as\b',    # stash as
        r'\bper\s+\w+\s+first\b',  # per ... first
        r'group\s+by\s+.*\(',  # group by ... (
        r'\?\?',              # coalesce
        r'#\s*\w+',           # # count shorthand
    ]
    
    for pattern in strong_indicators:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return True
    
    # Medium indicators (probably ASQL)
    # File starts with "from" (not in a subquery context)
    first_keyword = get_first_keyword(cleaned)
    if first_keyword.lower() == 'from':
        # Check it's not a dbt config block followed by SELECT
        if not re.match(r'\{\{.*\}\}\s*SELECT', cleaned, re.IGNORECASE | re.DOTALL):
            return True
    
    return False
```

### Recommendation

**Use both `.asql` extension AND auto-detection:**

1. **`.asql` files** — Always compiled as ASQL
2. **`.sql` files** — Auto-detect based on syntax patterns

This gives users the best of both worlds:
- Explicit: Use `.asql` when you want certainty
- Convenient: `.sql` files can contain ASQL if patterns match

---

## Part 2: dbt Concepts to Nativize

### 2.1 Configuration (`config()`)

**Current dbt syntax:**
```sql
{{ config(
    materialized='incremental',
    unique_key='id',
    schema='staging',
    alias='orders_v2',
    tags=['daily', 'core'],
    docs={'node_color': 'blue'}
) }}
```

**Proposed ASQL syntax:**

```asql
-- Option A: config block at top
config
  materialized: incremental
  unique_key: id
  schema: staging
  alias: orders_v2
  tags: [daily, core]

from orders ...
```

```asql
-- Option B: inline config (like shebang)
#! materialized=incremental, unique_key=id

from orders ...
```

```asql
-- Option C: SET-like syntax
SET materialized = incremental;
SET unique_key = id;
SET schema = staging;

from orders ...
```

**Recommendation**: Option C (SET-like) because:
- Consistent with ASQL's existing `SET auto_spine = false`
- Familiar SQL-like syntax
- Easy to parse

**Full config options to support:**

| dbt Config | ASQL Equivalent | Notes |
|------------|-----------------|-------|
| `materialized` | `SET materialized = table` | table, view, incremental, ephemeral |
| `unique_key` | `SET unique_key = id` | For incremental |
| `schema` | `SET schema = staging` | Target schema |
| `alias` | `SET alias = orders_v2` | Table name override |
| `tags` | `SET tags = [daily, core]` | Metadata tags |
| `enabled` | `SET enabled = false` | Disable model |
| `pre_hook` | `SET pre_hook = "..."` | Pre-run SQL |
| `post_hook` | `SET post_hook = "..."` | Post-run SQL |
| `database` | `SET database = analytics` | Target database |
| `cluster_by` | `SET cluster_by = [date, region]` | Clustering (Snowflake/BigQuery) |
| `partition_by` | `SET partition_by = date` | Partitioning |

---

### 2.2 Model References (`ref()`)

**Current dbt syntax:**
```sql
SELECT * FROM {{ ref('stg_orders') }}
```

**Proposed ASQL syntax:**

```asql
-- Option A: @ prefix (like date literals)
from @stg_orders

-- Option B: Explicit ref keyword
from ref(stg_orders)

-- Option C: Dot notation for project references
from @my_project.stg_orders
```

**Recommendation**: Option A (`@table_name`) because:
- `@` is already used for dates in ASQL, extending it is natural
- Very concise
- Visually distinct from regular table names

**Edge cases:**

```asql
-- Same-project reference
from @stg_orders

-- Cross-project reference
from @analytics.stg_orders

-- Reference with version (dbt 1.6+)
from @stg_orders:v2
```

---

### 2.3 Source References (`source()`)

**Current dbt syntax:**
```sql
SELECT * FROM {{ source('raw', 'orders') }}
```

**Proposed ASQL syntax:**

```asql
-- Option A: source() function
from source(raw, orders)

-- Option B: @ with source prefix
from @source:raw.orders

-- Option C: Double @ for sources
from @@raw.orders
```

**Recommendation**: Option B (`@source:schema.table`) because:
- Distinguishes sources from refs
- Readable
- Consistent with `@` prefix pattern

---

### 2.4 Variables (`var()`)

**Current dbt syntax:**
```sql
WHERE date > '{{ var("start_date") }}'
WHERE limit = {{ var("row_limit", 1000) }}
```

**Proposed ASQL syntax:**

```asql
-- Option A: $variable syntax (shell-like)
where date > $start_date
where limit = $row_limit ?? 1000

-- Option B: var() function
where date > var(start_date)
where limit = var(row_limit, 1000)

-- Option C: @var:name syntax
where date > @var:start_date
where limit = @var:row_limit ?? 1000
```

**Recommendation**: Option A (`$variable`) because:
- Shell/Bash familiar
- Very concise
- Clear that it's a variable, not a column

**Date variables:**
```asql
-- Variable containing a date
where created_at > @$start_date  -- @ for date, $ for variable

-- Or just let the variable be the date
where created_at > $start_date::DATE
```

---

### 2.5 Conditionals (`{% if %}`)

**Current dbt syntax:**
```sql
{% if is_incremental() %}
  WHERE created_at > (SELECT MAX(created_at) FROM {{ this }})
{% endif %}
```

**Proposed ASQL syntax:**

```asql
-- Option A: if keyword as pipeline step
from orders
  if incremental:
    where created_at > (select max(created_at) from @this)

-- Option B: Conditional block
from orders
  when incremental (
    where created_at > (select max(created_at) from @this)
  )

-- Option C: Inline condition with ?
from orders
  where created_at > (select max(created_at) from @this) ? incremental
```

**Recommendation**: Option A (`if condition:`) because:
- Python-like readability
- Clear scope (indented block)
- Natural in pipeline

**Common conditions to support:**

| dbt Condition | ASQL Syntax | Meaning |
|---------------|-------------|---------|
| `is_incremental()` | `if incremental:` | Incremental run |
| `target.name == 'prod'` | `if target = prod:` | Target environment |
| `var('enabled', true)` | `if $enabled:` | Variable-based |
| `execute` | `if execute:` | Not parsing phase |

---

### 2.6 Self-Reference (`this`)

**Current dbt syntax:**
```sql
SELECT MAX(created_at) FROM {{ this }}
```

**Proposed ASQL syntax:**

```asql
-- Use @this like @ref
select max(created_at) from @this
```

Simple and consistent.

---

### 2.7 Environment Info (`target`, `env_var()`)

**Current dbt syntax:**
```sql
{% if target.name == 'prod' %}
  -- production logic
{% endif %}

{{ env_var('API_KEY') }}
```

**Proposed ASQL syntax:**

```asql
-- Target info via $ variables
if $target.name = prod:
  ...

-- Or dedicated syntax
if target = prod:
  ...

-- Environment variables
$env:API_KEY
-- or
env(API_KEY)
```

---

### 2.8 Loops (`{% for %}`)

**Current dbt syntax:**
```sql
{% for payment_method in ['credit_card', 'bank_transfer', 'gift_card'] %}
  SUM(CASE WHEN payment_method = '{{ payment_method }}' THEN amount ELSE 0 END) AS {{ payment_method }}_amount,
{% endfor %}
```

**Proposed ASQL syntax:**

```asql
-- Option A: for loop in select
from orders
  select
    for method in [credit_card, bank_transfer, gift_card]:
      sum(payment_method = method ? amount : 0) as {method}_amount

-- Option B: macro-like expansion
from orders
  select expand(
    pattern: "sum(payment_method = '{m}' ? amount : 0) as {m}_amount",
    m: [credit_card, bank_transfer, gift_card]
  )
```

**Recommendation**: This is complex. Consider NOT supporting loops natively and letting users fall back to Jinja for complex metaprogramming.

**Alternative**: ASQL's `pivot` might cover many loop use cases:

```asql
from orders
  pivot sum(amount) by payment_method values (credit_card, bank_transfer, gift_card)
```

---

## Part 3: Complete Example

### Current dbt + SQL

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    schema='marts'
) }}

WITH orders AS (
    SELECT * FROM {{ ref('stg_orders') }}
    WHERE created_at > '{{ var("start_date", "2024-01-01") }}'
    {% if is_incremental() %}
      AND created_at > (SELECT MAX(created_at) FROM {{ this }})
    {% endif %}
),
customers AS (
    SELECT * FROM {{ ref('stg_customers') }}
)
SELECT
    o.order_id,
    o.created_at,
    o.amount,
    c.customer_name
FROM orders o
LEFT JOIN customers c ON o.customer_id = c.customer_id
ORDER BY o.created_at DESC
```

### Proposed ASQL

```asql
SET materialized = incremental;
SET unique_key = order_id;
SET schema = marts;

from @stg_orders
  where created_at > $start_date ?? @2024-01-01
  if incremental:
    where created_at > (select max(created_at) from @this)
  stash as orders

from orders
  &? @stg_customers as c on orders.customer_id = c.customer_id
  select
    orders.order_id,
    orders.created_at,
    orders.amount,
    c.customer_name
  order by -orders.created_at
```

**Line count**: 29 → 16 (45% reduction)
**Jinja symbols**: 8 `{{` + 2 `{%` → 0

---

## Part 4: Implementation Approach

### Phase 1: Core Integration

1. **Model references**: `@table_name` → `{{ ref('table_name') }}`
2. **Source references**: `@source:schema.table` → `{{ source('schema', 'table') }}`
3. **Variables**: `$var_name` → `{{ var('var_name') }}`
4. **Self-reference**: `@this` → `{{ this }}`

These are simple string replacements before dbt processes the file.

### Phase 2: Configuration

1. **Parse SET statements** at the top of ASQL files
2. **Generate config block** before the compiled SQL

```python
def extract_config(asql_code: str) -> tuple[dict, str]:
    """Extract SET statements and return config dict + remaining code."""
    config = {}
    lines = []
    
    for line in asql_code.split('\n'):
        if match := re.match(r'SET\s+(\w+)\s*=\s*(.+);', line, re.IGNORECASE):
            key, value = match.groups()
            config[key.lower()] = parse_value(value)
        else:
            lines.append(line)
    
    return config, '\n'.join(lines)

def compile_with_config(asql_code: str) -> str:
    config, code = extract_config(asql_code)
    sql = compile(code)
    
    if config:
        config_str = ", ".join(f"{k}='{v}'" for k, v in config.items())
        return f"{{{{ config({config_str}) }}}}\n\n{sql}"
    return sql
```

### Phase 3: Conditionals

1. **Parse `if condition:` blocks**
2. **Generate `{% if %}` Jinja**

This is more complex because it requires understanding ASQL's indentation/scope.

### Phase 4: Passthrough

For anything we don't natively support, pass through Jinja:

```asql
-- Native ASQL with Jinja fallback
from @stg_orders
  where status in {{ var('valid_statuses') }}  -- Jinja passthrough
```

---

## Part 5: Comparison

| Feature | dbt + SQL | dbt + ASQL (proposed) | Reduction |
|---------|-----------|----------------------|-----------|
| Config block | `{{ config(...) }}` | `SET key = value;` | Cleaner |
| Model ref | `{{ ref('x') }}` | `@x` | 13 → 2 chars |
| Source ref | `{{ source('a', 'b') }}` | `@source:a.b` | 20 → 12 chars |
| Variable | `{{ var('x') }}` | `$x` | 13 → 2 chars |
| Self-ref | `{{ this }}` | `@this` | 10 → 5 chars |
| Incremental | `{% if is_incremental() %}` | `if incremental:` | 25 → 15 chars |

**Overall**: Significant reduction in visual noise.

---

## Part 6: Risks and Mitigations

### Risk: Syntax Ambiguity

**Example**: `$start_date` — is this a dbt variable or an ASQL feature?

**Mitigation**: Document clearly. `$` is ONLY for dbt variables; ASQL scalars (if added) would use different syntax.

### Risk: Incomplete Coverage

Some dbt features are too complex for native syntax (loops, complex macros).

**Mitigation**: Always allow Jinja passthrough. Native syntax is sugar, not a complete replacement.

### Risk: Upgrade Path

What happens when dbt adds new features?

**Mitigation**: Design syntax to be extensible. `$` for variables, `@` for refs can expand.

---

## Part 7: Recommendation (UPDATED)

> **Note**: After discussion, we decided to keep `{{ }}` for variables since dbt users are familiar with them. The improvement is simplifying what goes INSIDE the braces.

### Adopted Strategy

1. **File extension detection** (`.asql`) + **auto-detection** (syntax patterns)
2. **Simplified syntax**:
   - Model refs: just use table names (`orders` auto-expands to `{{ ref('orders') }}`)
   - Sources: `source(schema, table)` (no quotes needed)
   - Variables: `{{ var_name }}` expands to `{{ var('var_name') }}`
   - Defaults: `{{ var || default }}` expands to `{{ var('var', default) }}`
   - Env vars: `{{ env.NAME }}` expands to `{{ env_var('NAME') }}`
   - Config: `SET key = value;` expands to `{{ config(key='value') }}`
   - Self-ref: `{{ this }}` unchanged
3. **Keep `{% %}` for conditionals** (already familiar)
4. **Jinja passthrough** for advanced cases

### Why This Approach Wins

- **Familiar**: `{{ }}` delimiters are what dbt users know
- **Simpler**: Just drop `var('...')` wrapper, keep the rest
- **Readable**: Easy to spot injected values
- **Gradual**: Users can adopt one simplification at a time

---

## Appendix: Full Syntax Reference (UPDATED)

| dbt Jinja | dbt-asql | Expansion |
|-----------|----------|-----------|
| `{{ ref('orders') }}` | `orders` (just table name) | Auto-detected from manifest |
| `{{ ref('project', 'x') }}` | `project.x` | Cross-project ref |
| `{{ source('raw', 'orders') }}` | `source(raw, orders)` | No quotes needed |
| `{{ this }}` | `{{ this }}` | Unchanged |
| `{{ var('x') }}` | `{{ x }}` | Drop `var('...')` |
| `{{ var('x', 100) }}` | `{{ x \|\| 100 }}` | `\|\|` for defaults |
| `{{ env_var('KEY') }}` | `{{ env.KEY }}` | Dot notation |
| `{{ target.name }}` | `{{ target.name }}` | Unchanged |
| `{% if is_incremental() %}` | `{% if is_incremental() %}` | Unchanged |
| `{{ config(materialized='x') }}` | `SET materialized = x;` | Native syntax |

