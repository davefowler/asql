-- Source: dbt_google_ads
-- Model: stg_google_ads__account_stats
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_google_ads
-- File: models/staging/stg_google_ads__account_stats.sql

with base as (

    select * from stg_table
),

fields as (

    select
        *,
        'source' as source_relation

    from base
),

final as (

    select
        source_relation,
        customer_id as account_id,
        date as date_day,
        ad_network_type,
        device,
        coalesce(clicks, 0) as clicks,
        coalesce(cost_micros, 0) / 1000000.0 as spend,
        coalesce(impressions, 0) as impressions,
        coalesce(conversions, 0) as conversions,
        coalesce(conversions_value, 0) as conversions_value,
        coalesce(view_through_conversions, 0) as view_through_conversions

    from fields
)

select *
from final
