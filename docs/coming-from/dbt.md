# ASQL for dbt Users

ASQL integrates naturally with dbt. The simplest way to think about it:

- **dbt still owns the project**: models, materializations, tests, docs, exposures, deployments.
- **ASQL is what you write inside a model**: a cleaner, more readable query that dbt materializes.

ASQL is also heavily inspired by the “dbt style” of analytics engineering: readable transformations, conventions, and (often) dbt_utils-style helpers to avoid repetitive SQL.

## What will feel familiar

- **Model-first workflow**: one model = one query you can reason about.
- **CTE-shaped thinking**: ASQL pipelines feel like a tidy, linear CTE stack.
- **dbt_utils patterns**: pivot/unpivot, date spines, dedupe, surrogate keys, unioning relations.

## Quick start: your first dbt model in ASQL

In a dbt model file, you generally keep the dbt control plane (config, refs, incremental logic) the same, and write the query itself in ASQL style:

```sql
-- models/orders_summary.sql
{{ config(materialized='table') }}

from {{ ref('orders') }}
where status = 'completed'
group by month(created_at) (
    sum(amount) as revenue,
    count(distinct customer_id) as customers
)
order by -month
```

If you’re used to leaning on dbt macros for common transformations, the nice surprise is:
**many of those “macro” patterns become built-in ASQL syntax/functions** (so your model query can stay pure and readable).

## Quick Reference

| dbt_utils-style macro pattern | ASQL built-in | Notes |
|-----------|------|-------|
| `{{ dbt_utils.star() }}` | Default behavior | ASQL returns all columns by default |
| `{{ dbt_utils.star(except=[...]) }}` | `except col1, col2` | Exclude columns |
| `{{ dbt_utils.generate_surrogate_key([...]) }}` | `key(col1, col2)` | **Planned** (inspired by dbt macros) |
| `{{ dbt_utils.pivot() }}` | `pivot ... values ('A', 'B')` | Rows to columns (static values list) |
| `{{ dbt_utils.unpivot() }}` | `unpivot ... into ...` | Columns to rows |
| `{{ dbt_utils.date_spine() }}` | auto-spine | Gap filling is automatic for date GROUP BYs |
| `{{ dbt_utils.deduplicate() }}` | `per id first by -date` | Remove duplicates |
| `{{ dbt_utils.union_relations() }}` | (future) | Not implemented yet |

---

## Built-in “macros” (dbt_utils-style helpers, without Jinja)

!!! note "dbt macros vs ASQL built-ins"
    You’ll still use dbt’s core Jinja macros (like `ref()`, `source()`, `this`, `var()`, `is_incremental()`) for dependency wiring and model logic.
    The point here is that many *transformation helpers* you might have reached for via dbt_utils-style macros are simply built into ASQL itself.

dbt macros are great, but they can also hide a lot of SQL and make it harder to see what a model *does*.
In ASQL, many of the most common macro-shaped transformations are **first-class language features**.

Below are the equivalents you can reach for directly in ASQL, without wrapping your query in Jinja.

### `star()` and `star(except=...)` → default select and `except`

- **Default**: ASQL returns all columns unless you narrow it with `select`.
- **Exclude columns**: use `except` to drop noisy or sensitive fields.

```asql
from users
except password_hash, ssn
```

### `generate_surrogate_key()` → `key(...)`

Use `key(col1, col2, ...)` to build a stable surrogate key from one or more columns.

**Status**: Planned (inspired by dbt macros). See the repo’s GitHub issues for the current implementation status.

```asql
from orders
select *, key(user_id, order_id) as order_key
```

**Features**:
- **Deterministic**: Same inputs always produce the same hash
- **NULL handling**: NULLs are converted to empty strings before hashing, ensuring consistent results
- **Type normalization**: All values are cast to strings before concatenation
- **Cross-dialect**: Automatically uses appropriate hash function for your SQL dialect (MD5, SHA256, etc.)

### `deduplicate()` → `per ... first by ...`

Most “latest row per key” / “one row per entity” macros are a window function pattern.
In ASQL, it’s a one-liner:

```asql
from events
per user_id, event_type first by -created_at
```

### `date_spine()` → auto-spine (default)

ASQL’s compiler already provides **auto-spine** (enabled by default) which gap-fills date group-bys when you filter to a range.

### `pivot()` / `unpivot()` → `pivot` / `unpivot`

Pivoting is intentionally terse in ASQL:

```asql
from issue_custom_fields
pivot field_value by field_name values ('priority', 'status', 'assignee')
```

And unpivoting (“pivot longer”) is equally direct:

```asql
from monthly_data
unpivot jan, feb, mar into month, value
```

### `union_relations()` → (future) `from union(...)`

**Not implemented yet**. (This is a plausible future convenience wrapper for schema-aligned unions.)

### `safe_cast()` → (future) `::type?` (and defaults with `??`)

Safe casts are **not implemented yet**. For now, use dialect-specific SQL (`TRY_CAST`, `SAFE_CAST`) directly.

### `coalesce()` → `??`

Null coalescing is an operator, so it reads left-to-right:

```asql
first_name ?? nickname ?? 'Unknown'
```

---

## star() / except

=== "dbt"
    ```sql
    SELECT
        {{ dbt_utils.star(from=ref('users'), except=['password_hash', 'ssn']) }}
    FROM {{ ref('users') }}
    ```

=== "ASQL"
    ```asql
    from users
    except password_hash, ssn
    ```

---

## Surrogate Keys

=== "dbt"
    ```sql
    SELECT
        {{ dbt_utils.generate_surrogate_key(['user_id', 'order_id']) }} as order_key,
        *
    FROM {{ ref('orders') }}
    ```

=== "ASQL"
    ```asql
    from orders
    -- Planned helper inspired by dbt_utils.generate_surrogate_key
    -- (See GitHub issues)
    select *, key(user_id, order_id) as order_key
    ```

---

## Date Spine

=== "dbt"
    ```sql
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('2020-01-01' as date)",
        end_date="current_date"
    ) }}
    ```

=== "ASQL"
    ```asql
    -- Auto-spine fills gaps automatically for date GROUP BYs
    -- when you filter to a date range.
    from orders
    where created_at >= @2024-01-01 and created_at < @2025-01-01
    group by month(created_at) (
      sum(amount) ?? 0 as revenue
    )
    ```

---

## Gap Filling Time Series

=== "dbt"
    ```sql
    -- Complex CTE pattern with date_spine and left join
    WITH spine AS (
        {{ dbt_utils.date_spine(...) }}
    ),
    data AS (
        SELECT date_trunc('month', created_at) as month, sum(amount) as revenue
        FROM {{ ref('orders') }}
        GROUP BY 1
    )
    SELECT 
        spine.date_month,
        COALESCE(data.revenue, 0) as revenue
    FROM spine
    LEFT JOIN data ON spine.date_month = data.month
    ```

=== "ASQL"
    ```asql
    # Auto-spine fills gaps automatically for date GROUP BYs
    from orders
    where created_at >= @2024-01-01 and created_at < @2025-01-01
    group by month(created_at) (
        sum(amount) ?? 0 as revenue  # ?? 0 sets default for filled rows
    )
    ```

---

## Deduplication

=== "dbt"
    ```sql
    {{ dbt_utils.deduplicate(
        relation=ref('events'),
        partition_by='user_id, event_type',
        order_by='created_at desc'
    ) }}
    ```

=== "ASQL"
    ```asql
    from events
    per user_id, event_type first by -created_at
    ```

---

## Pivot

=== "dbt"
    ```sql
    -- Fivetran dbt packages often have hundreds of lines for this
    {{ dbt_utils.pivot(
        column='field_name',
        values=['priority', 'sprint', 'story_points'],
        then_value='field_value'
    ) }}
    ```

=== "ASQL"
    ```asql
    -- Denormalize Jira/Salesforce custom fields
    from issue_custom_fields
    pivot field_value by field_name values ('priority', 'status', 'assignee')
    ```

---

## Union Relations

=== "dbt"
    ```sql
    {{ dbt_utils.union_relations(
        relations=[ref('users_2022'), ref('users_2023'), ref('users_2024')]
    ) }}
    ```

=== "ASQL"
    ```asql
    -- Not implemented yet (future convenience wrapper)
    -- from union(users_2022, users_2023, users_2024)
    ```

---

## Safe Casting

=== "dbt"
    ```sql
    -- Different per warehouse
    {{ adapter.dispatch('safe_cast', 'dbt_utils')('value', 'integer') }}
    
    -- Or manually
    TRY_CAST(value AS INTEGER)  -- Snowflake
    SAFE_CAST(value AS INT64)   -- BigQuery
    ```

=== "ASQL"
    ```asql
    -- Not implemented yet; use dialect-specific SQL for now
    -- TRY_CAST(value AS INTEGER)  -- Snowflake
    -- SAFE_CAST(value AS INT64)   -- BigQuery
    ```

---

## Incremental Models

dbt's incremental logic stays in dbt - ASQL focuses on the query:

=== "dbt + ASQL"
    ```sql
    -- models/orders_summary.sql
    {{ config(materialized='incremental') }}

    -- ASQL query here
    from orders
    where status = 'completed'
    group by month(created_at) (
        sum(amount) as revenue,
        count(distinct customer_id) as customers
    )

    {% if is_incremental() %}
    where created_at > (select max(created_at) from {{ this }})
    {% endif %}
    ```

---

## COALESCE

=== "dbt"
    ```sql
    COALESCE(first_name, nickname, 'Unknown')
    ```

=== "ASQL"
    ```asql
    first_name ?? nickname ?? 'Unknown'
    ```
