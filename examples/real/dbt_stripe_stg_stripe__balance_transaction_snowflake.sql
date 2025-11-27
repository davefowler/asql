-- Source: dbt_stripe
-- Model: stg_stripe__balance_transaction
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_stripe
-- File: models/staging/stg_stripe__balance_transaction.sql

with base as (
    select *
    from base
),

fields as (
    select
        *,
        'source' as source_relation

    from base
),

final as (
    select
        id as balance_transaction_id,
        cast(available_on as TIMESTAMP) as available_on,
        cast(created as TIMESTAMP) as created_at,
        connected_account_id,
        currency,
        description,
        exchange_rate,
        reporting_category,
        source,
        status,
        type,
        source_relation
    from fields
)

select *
from final
