-- Source: dbt_stripe
-- Model: int_stripe__account_partitions
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_stripe
-- File: models/intermediate/int_stripe__account_partitions.sql

with account_rolling_totals as (

    select *
    from account_rolling_totals
),

final as (

    select
        *,
        sum(case when amount is null
            then 0
            else 1
                end) over (order by date_day rows unbounded preceding) as amount_partition
    from account_rolling_totals
)

select *
from final