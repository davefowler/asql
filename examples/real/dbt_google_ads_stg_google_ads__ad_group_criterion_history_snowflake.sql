-- Source: dbt_google_ads
-- Model: stg_google_ads__ad_group_criterion_history
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_google_ads
-- File: models/staging/stg_google_ads__ad_group_criterion_history.sql

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
        id as criterion_id,
        cast(ad_group_id as VARCHAR) as ad_group_id,
        base_campaign_id,
        updated_at,
        type,
        status,
        keyword_match_type,
        keyword_text,
        row_number() over (partition by source_relation, id order by updated_at desc) = 1 as is_most_recent_record
    from fields
    where coalesce(_fivetran_active, true)
)

select *
from final
