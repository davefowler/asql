-- Source: dbt_google_ads
-- Model: google_ads__account_report
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_google_ads
-- File: models/google_ads__account_report.sql

with stats as (

    select *
    from stats
),

accounts as (

    select *
    from accounts
    where is_most_recent_record = True
),

fields as (

    select
        stats.source_relation,
        stats.date_day,
        accounts.account_name,
        stats.account_id,
        accounts.currency_code,
        accounts.auto_tagging_enabled,
        accounts.time_zone,
        sum(stats.spend) as spend,
        sum(stats.clicks) as clicks,
        sum(stats.impressions) as impressions,
        sum(stats.conversions) as conversions,
        sum(stats.conversions_value) as conversions_value,
        sum(stats.view_through_conversions) as view_through_conversions

    from stats
    left join accounts
        on stats.account_id = accounts.account_id
        and stats.source_relation = accounts.source_relation

)

select *
from fields