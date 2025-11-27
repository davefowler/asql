-- Source: dbt_marketo
-- Model: marketo__email_sends_deduped
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_marketo
-- File: models/intermediate/marketo__email_sends_deduped.sql

with base as (

    select *
    from base

), windowed as (

    select
        *,
        row_number() over (partition by email_send_id  order by activity_timestamp asc) as activity_rank
    from base

), filtered as (

    select *
    from windowed
    where activity_rank = 1

)

select *
from filtered