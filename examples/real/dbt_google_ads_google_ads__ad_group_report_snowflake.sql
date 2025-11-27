-- Source: dbt_google_ads
-- Model: google_ads__ad_group_report
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_google_ads
-- File: models/google_ads__ad_group_report.sql

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

fields as (

    select
        stats.source_relation,
        stats.date_day,
        accounts.account_name,
        accounts.account_id,
        accounts.currency_code,
        campaigns.campaign_name,
        campaigns.campaign_id,
        ad_groups.ad_group_name,
        stats.ad_group_id,
        ad_groups.ad_group_status,
        ad_groups.ad_group_type,
        sum(stats.spend) as spend,
        sum(stats.clicks) as clicks,
        sum(stats.impressions) as impressions,
        sum(conversions) as conversions,
        sum(conversions_value) as conversions_value,
        sum(view_through_conversions) as view_through_conversions

    from stats
    left join ad_groups
        on stats.ad_group_id = ad_groups.ad_group_id
        and stats.source_relation = ad_groups.source_relation
    left join campaigns
        on ad_groups.campaign_id = campaigns.campaign_id
        and ad_groups.source_relation = campaigns.source_relation
    left join accounts
        on campaigns.account_id = accounts.account_id
        and campaigns.source_relation = accounts.source_relation

)

select *
from fields