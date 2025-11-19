-- Source: dbt_marketo
-- Model: marketo__email_stats__by_email_template
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_marketo
-- File: models/intermediate/marketo__email_stats__by_email_template.sql

with email_sends as (

    select *
    from {{ ref('marketo__email_sends') }}

), aggregated as (

    select
        source_relation,
        email_template_id,
        count(*) as count_sends,
        sum(count_opens) as count_opens,
        sum(count_bounces) as count_bounces,
        sum(count_clicks) as count_clicks,
        sum(count_deliveries) as count_deliveries,
        sum(count_unsubscribes) as count_unsubscribes,
        count(distinct case when was_opened = True then email_send_id end) as count_unique_opens,
        count(distinct case when was_clicked = True then email_send_id end) as count_unique_clicks
    from email_sends
    where email_template_id is not null
    group by 1, 2

)

select *
from aggregated