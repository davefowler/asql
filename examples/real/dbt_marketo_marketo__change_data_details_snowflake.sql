-- Source: dbt_marketo
-- Model: marketo__change_data_details
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_marketo
-- File: models/intermediate/marketo__change_data_details.sql

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

), pivots as (

    -- For each column that is in both the lead_history_columns variable and the restname of the lead_describe table,
    -- find whether a change occurred for a given column on a given day for a given lead.
    -- This will feed the daily slowly changing dimension model.

    select
        source_relation,
        lead_id,
        cast(activity_timestamp as date) as date_day

    from joined
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
