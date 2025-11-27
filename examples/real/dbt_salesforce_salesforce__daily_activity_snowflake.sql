-- Source: dbt_salesforce
-- Model: salesforce__daily_activity
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_salesforce
-- File: models/salesforce/salesforce__daily_activity.sql

with date_spine as (

    select
        date_day
    from date_spine
),

opportunity as (

    select
        opportunity_id,
        created_date,
        account_id,
        close_date,
        is_closed,
        is_deleted,
        is_won,
        owner_id,
        stage_name,
        type,
        amount,
        case
            when is_won then 'Won'
            when not is_won and is_closed then 'Lost'
            when not is_closed and lower(forecast_category) in ('pipeline','forecast','bestcase') then 'Pipeline'
            else 'Other'
        end as status
    from daily_activity
),

opportunities_created as (

    select
        created_date,
        count(opportunity_id) as opportunities_created,
        round(sum(amount)) as opportunities_created_amount
    from opportunity
    group by 1
),

opportunities_closed as (

    select
        close_date,
        count(case when status = 'Won' then opportunity_id else null end) as opportunities_won,
        round(sum(case when status = 'Won' then amount else 0 end)) as opportunities_won_amount,
        count(case when status = 'Lost' then opportunity_id else null end) as opportunities_lost,
        round(sum(case when status = 'Lost' then amount else null end)) as opportunities_lost_amount,
        round(sum(case when status = 'Pipeline' then amount else null end)) as pipeline_amount
    from opportunity
    group by 1
)

select
    date_spine.date_day,

    opportunities_created.opportunities_created,
    opportunities_created.opportunities_created_amount,
    opportunities_closed.opportunities_won,
    opportunities_closed.opportunities_won_amount,
    opportunities_closed.opportunities_lost,
    opportunities_closed.opportunities_lost_amount,
    opportunities_closed.pipeline_amount
from date_spine

left join opportunities_created
    on date_spine.date_day = opportunities_created.created_date
left join opportunities_closed
    on date_spine.date_day = opportunities_closed.close_date
