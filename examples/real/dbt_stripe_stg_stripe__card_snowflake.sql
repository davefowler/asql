-- Source: dbt_stripe
-- Model: stg_stripe__card
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_stripe
-- File: models/staging/stg_stripe__card.sql

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
        id as card_id,
        account_id,
        address_city as card_address_city,
        address_country as card_address_country,
        address_line_1 as card_address_line_1,
        address_line_2 as card_address_line_2,
        address_state as card_address_state,
        address_zip as card_address_postal_code,
        wallet_type,
        brand,
        country,
        cast(created as TIMESTAMP) as created_at,
        customer_id,
        name as card_name,
        recipient,
        funding,
        source_relation

    from fields
)

select *
from final
