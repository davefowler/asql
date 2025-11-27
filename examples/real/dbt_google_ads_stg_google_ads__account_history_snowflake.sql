-- Source: dbt_google_ads
-- Model: stg_google_ads__account_history
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_google_ads
-- File: models/staging/stg_google_ads__account_history.sql

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
        id as account_id,
        updated_at,
        currency_code,
        auto_tagging_enabled,
        time_zone,
        descriptive_name as account_name,
        row_number() over (partition by source_relation, id order by updated_at desc) = 1 as is_most_recent_record
    from fields
    where coalesce(_fivetran_active, true)
)

select *
from final
