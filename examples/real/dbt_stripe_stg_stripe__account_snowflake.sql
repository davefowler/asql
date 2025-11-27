-- Source: dbt_stripe
-- Model: stg_stripe__account
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_stripe
-- File: models/staging/stg_stripe__account.sql

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
        id as account_id,
        business_profile_mcc,
        business_profile_name,
        business_type,
        charges_enabled,
        company_address_city,
        company_address_country,
        company_address_line_1,
        company_address_line_2,
        company_address_postal_code,
        company_address_state,
        company_name,
        company_phone,
        country,
        cast(created as TIMESTAMP) as created_at,
        default_currency,
        email,
        is_deleted,
        metadata,
        payouts_enabled as is_payouts_enabled,
        type as account_type,
        source_relation

    from fields
)

select *
from final
