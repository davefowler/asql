-- Source: dbt_stripe
-- Model: int_stripe__date_spine
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_stripe
-- File: models/intermediate/int_stripe__date_spine.sql

-- depends_on:
with spine as (
    select dateadd(day, row_number() over (order by null) - 1, '2020-01-01'::date) as date_day
    from table(generator(rowcount => 3650))
),

account as (
    select *
    from account
),

date_spine as (
    select
        cast(date_day as date) as date_day,
        date_trunc('week', date_day) as date_week,
        date_trunc('month', date_day) as date_month,
        date_trunc('year', date_day) as date_year,
        row_number() over (order by cast(date_day as date)) as date_index
    from spine
),

final as (
    select distinct
        account.account_id,
        account.source_relation,
        date_spine.date_day,
        date_spine.date_week,
        date_spine.date_month,
        date_spine.date_year,
        date_spine.date_index
    from account
    cross join date_spine
)

select *
from final
