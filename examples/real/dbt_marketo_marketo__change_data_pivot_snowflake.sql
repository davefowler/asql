-- Source: dbt_marketo
-- Model: marketo__change_data_pivot
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_marketo
-- File: models/intermediate/marketo__change_data_pivot.sql

with lead_describe as (

    select *
    from lead_describe

), joined as (

    -- Join the column names from the describe table onto the change data table

    select
        change_data.*,
        lead_describe.rest_name_xf as primary_attribute_column
    from change_data
    left join lead_describe
        on change_data.source_relation = lead_describe.source_relation
        and change_data.primary_attribute_value_id = lead_describe.lead_describe_id

), event_order as (

    select
        *,
        row_number() over (
            partition by cast(activity_timestamp as date), lead_id, primary_attribute_value_id
            order by activity_timestamp asc, activity_id desc -- In the case that events come in the exact same time, we will rely on the activity_id to prove the order
            ) as row_num
    from joined

), filtered as (

    -- Find the first event that occurs on each day for each lead

    select *
    from event_order
    where row_num = 1

), pivots as (

    -- For each column that is in both the lead_history_columns variable and the restname of the lead_describe table,
    -- pivot out the value into it's own column. This will feed the daily slowly changing dimension model.

    select
        source_relation,
        lead_id,
        cast(activity_timestamp as date) as date_day

    from filtered
    where cast(activity_timestamp as date) < current_date
    group by 1,2,3

), surrogate_key as (

    select
        *,
        concat(lead_id, '_', date_day) as lead_day_id
    from pivots

)

select *
from surrogate_key
