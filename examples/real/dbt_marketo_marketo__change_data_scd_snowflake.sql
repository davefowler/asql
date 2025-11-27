-- Source: dbt_marketo
-- Model: marketo__change_data_scd
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_marketo
-- File: models/intermediate/marketo__change_data_scd.sql


with change_data as (

    select *
    from change_data

), leads as (

    select *
    from leads

), details as (

    select *
    from details

), unioned as (
    -- unions together the current state of leads and their history changes.
    -- we need the current state to work backwards from to backfill the slowly changing dimension model
    select *
    from leads
    
    union all
    
    select *
    from change_data

), field_partitions as (

    select
        unioned.source_relation,
        coalesce(unioned.date_day, current_date) as valid_to,
        unioned.date_day,
        unioned.lead_id

    from unioned
    left join details
        on unioned.source_relation = details.source_relation
        and unioned.date_day = details.date_day
        and unioned.lead_id = details.lead_id

), today as (

    -- For each day where a change occurred for each lead, we backfill the values from the subsequent change, going back in time.
    -- The 'details' table is joined in for exactly this purpose. It tells us, even if a value is null, whether that null
    -- value is because no change occurred on that day, or because there was a change and the change involved the null value.

    select
        field_partitions.source_relation,
        field_partitions.valid_to,
        field_partitions.date_day,
        field_partitions.lead_id

    from field_partitions

), surrogate_key as (

    select
        *,
        concat(lead_id, '_', date_day) as lead_day_id
    from today

)

select *
from surrogate_key