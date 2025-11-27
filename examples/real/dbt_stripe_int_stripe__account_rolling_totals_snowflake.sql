-- Source: dbt_stripe
-- Model: int_stripe__account_rolling_totals
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_stripe
-- File: models/intermediate/int_stripe__account_rolling_totals.sql

with date_spine as (

    select *
    from date_spine

), account_daily_balances_by_type as (

    select *
    from account_daily_balances_by_type

), account_rolling_totals as (

    select
        *,
        sum(amount) over (order by date_day rows unbounded preceding) as rolling_amount

    from account_daily_balances_by_type

), final as (

    select
        date_spine.account_id,
        date_spine.date_day,
        date_spine.date_week,
        date_spine.date_month,
        date_spine.date_year,
        coalesce(round(account_rolling_totals.amount,2),0) as amount,
        case when account_rolling_totals.amount is null and date_index = 1
            then 0
            else coalesce(round(account_rolling_totals.amount,2),0)
            end as rolling_amount,
        date_spine.date_index,
        account_rolling_totals.source_relation

    from date_spine
    left join account_rolling_totals
        on account_rolling_totals.date_day = date_spine.date_day
        and account_rolling_totals.account_id = date_spine.account_id
        and account_rolling_totals.source_relation = date_spine.source_relation
)

select *
from final
