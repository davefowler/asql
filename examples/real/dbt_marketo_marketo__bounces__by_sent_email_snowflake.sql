-- Source: dbt_marketo
-- Model: marketo__bounces__by_sent_email
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_marketo
-- File: models/intermediate/marketo__bounces__by_sent_email.sql

with activity as (

    select *
    from activity

), aggregate as (

    select
        source_relation,
        email_send_id,
        count(*) as count_bounces
    from activity
    group by 1, 2

)

select *
from aggregate
