-- Source: dbt_marketo
-- Model: marketo__deliveries__by_sent_email
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_marketo
-- File: models/intermediate/marketo__deliveries__by_sent_email.sql

with activity as (

    select *
    from {{ ref('stg_marketo__activity_email_delivered') }}

), aggregate as (

    select
        source_relation,
        email_send_id,
        count(*) as count_deliveries
    from activity
    group by 1, 2

)

select * 
from aggregate

