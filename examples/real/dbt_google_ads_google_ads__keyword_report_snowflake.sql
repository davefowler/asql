-- Source: dbt_google_ads
-- Model: google_ads__keyword_report
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_google_ads
-- File: models/google_ads__keyword_report.sql

with stats as (

    select *
    from stats
),

accounts as (

    select *
    from accounts
    where is_most_recent_record = True
),

campaigns as (

    select *
    from campaigns
    where is_most_recent_record = True
),

ad_groups as (

    select *
    from ad_groups
    where is_most_recent_record = True
),

criterions as (

    select *
    from criterions
    where is_most_recent_record = True
),

fields as (

    select
        stats.source_relation,
        stats.date_day,
        accounts.account_name,
        stats.account_id,
        accounts.currency_code,
        campaigns.campaign_name,
        stats.campaign_id,
        ad_groups.ad_group_name,
        stats.ad_group_id,
        stats.criterion_id,
        criterions.type,
        criterions.status,
        criterions.keyword_match_type,
        criterions.keyword_text,
        sum(stats.spend) as spend,
        sum(stats.clicks) as clicks,
        sum(stats.impressions) as impressions,
        sum(conversions) as conversions,
        sum(conversions_value) as conversions_value,
        sum(view_through_conversions) as view_through_conversions

    from stats
    left join criterions
        on stats.criterion_id = criterions.criterion_id
        and stats.source_relation = criterions.source_relation
    left join ad_groups
        on stats.ad_group_id = ad_groups.ad_group_id
        and stats.source_relation = ad_groups.source_relation
    left join campaigns
        on stats.campaign_id = campaigns.campaign_id
        and stats.source_relation = campaigns.source_relation
    left join accounts
        on stats.account_id = accounts.account_id
        and stats.source_relation = accounts.source_relation

)

select *
from fields
