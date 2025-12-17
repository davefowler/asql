# ASQL for dbt Users

ASQL integrates naturally with dbt. Think of ASQL as "what goes inside your dbt models" - cleaner SQL that dbt materializes.

## Quick Reference

| dbt Macro | ASQL | Notes |
|-----------|------|-------|
| `{{ dbt_utils.star() }}` | Default behavior | ASQL returns all columns by default |
| `{{ dbt_utils.star(except=[...]) }}` | `except col1, col2` | Exclude columns |
| `{{ dbt_utils.surrogate_key() }}` | `key(col1, col2)` | Generate surrogate key |
| `{{ dbt_utils.pivot() }}` | `pivot value by category` | Rows to columns |
| `{{ dbt_utils.unpivot() }}` | `unpivot ... into ...` | Columns to rows |
| `{{ dbt_utils.date_spine() }}` | `from date_spine(...)` | Generate date sequence |
| `{{ dbt_utils.deduplicate() }}` | `per id first by -date` | Remove duplicates |
| `{{ dbt_utils.union_relations() }}` | `from union(t1, t2)` | Union with alignment |

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
    from date_spine(start = '2020-01-01', end = today(), grain = day)
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
    from orders
    group by month(created_at) as month (
        sum(amount) as revenue
    )
    fill month with {revenue: 0}
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
    pivot field_value by field_name
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
    from union(users_2022, users_2023, users_2024)
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
    -- Safe cast with ? suffix (returns NULL on failure)
    select value::integer? as value_int

    -- With default
    select value::integer? ?? 0 as value_int
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
    group by month(created_at) as month (
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
