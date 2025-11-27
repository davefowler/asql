-- Source: dbt_zendesk
-- Model: int_zendesk__schedule_history
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_zendesk
-- File: models/intermediate/int_zendesk__schedule_history.sql

with audit_logs as (
    select
        source_relation,
        cast(source_id as VARCHAR) as schedule_id,
        created_at,
        lower(change_description) as change_description
    from schedule_history
    where lower(change_description) like '%workweek changed from%'

-- the formats for change_description vary, so it needs to be cleaned
), audit_logs_enhanced as (
    select
        source_relation,
        schedule_id,
        rank() over (partition by schedule_id  order by created_at desc) as schedule_id_index,
        created_at,
        -- Clean up the change_description, sometimes has random html stuff in it
        replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(change_description,
            'workweek changed from', ''),
            '&quot;', '"'),
            'amp;', ''),
            '=&gt;', ':'), ':mon:', '"mon":'), ':tue:', '"tue":'), ':wed:', '"wed":'), ':thu:', '"thu":'), ':fri:', '"fri":'), ':sat:', '"sat":'), ':sun:', '"sun":')
            as change_description_cleaned
    from audit_logs

), split_to_from as (
    select
        source_relation,
        schedule_id,
        schedule_id_index,
        created_at,
        cast(created_at as date) as valid_from,
        -- each change_description has two parts: 1-from the old schedule 2-to the new schedule.
        NULL as schedule_change_from,
        NULL as schedule_change
    from audit_logs_enhanced

), find_same_day_changes as (
    select
        source_relation,
        schedule_id,
        schedule_id_index,
        created_at,
        valid_from,
        schedule_change_from,
        schedule_change,
        row_number() over (
            partition by schedule_id, valid_from  -- valid from is type date
            -- ordering to get the latest change when there are multiple on one day
            order by schedule_id_index, schedule_change_from -- use the length of schedule_change_from to tie break, which will deprioritize empty "from" schedules
        ) as row_number
    from split_to_from

-- multiple changes can occur on one day, so we will keep only the latest change in a day.
), consolidate_same_day_changes as (
    select
        source_relation,
        schedule_id,
        schedule_id_index,
        created_at,
        valid_from,
        lead(valid_from) over (
            partition by schedule_id  order by schedule_id_index desc) as valid_until,
        schedule_change
    from find_same_day_changes
    where row_number = 1

-- Creates a record for each day of the week for each schedule_change event.
-- This is done by iterating over the days of the week, extracting the corresponding
-- schedule data for each day, and unioning the results after each iteration.
), split_days as (
    select
        source_relation,
        schedule_id,
        schedule_id_index,
        valid_from,
        valid_until,
        schedule_change,
        'monday' as day_of_week,
        cast(1 as INT) as day_of_week_number,
        NULL as day_of_week_schedule -- Extracts the schedule data specific to the current day from the schedule_change field.
    from consolidate_same_day_changes
    -- Exclude records with a null valid_until, which indicates it is the current schedule.
    -- We will to pull in the live schedule downstream, which is necessary when not using schedule histories.
    where valid_until is not null

-- A single day may contain multiple start and stop times, so we need to generate a separate record for each.
-- The day_of_week_schedule is structured like a JSON string, requiring warehouse-specific logic to flatten it into individual records.

-- Each cleaned_unnested_schedule will have the format hh:mm:hh:mm, so we can extract each time part.
), split_times as (
    select
        split_days.*,
        cast(nullif(substring(day_of_week_schedule, 1, 2), ' ') as INT) as start_time_hh,
        cast(nullif(substring(day_of_week_schedule, 4, 2), ' ') as INT) as start_time_mm,
        cast(nullif(substring(day_of_week_schedule, 7, 2), ' ') as INT) as end_time_hh,
        cast(nullif(substring(day_of_week_schedule, 10, 2), ' ') as INT) as end_time_mm
    from split_days

-- Calculate the start_time and end_time as minutes from Sunday
), calculate_start_end_times as (
    select
        source_relation,
        schedule_id,
        schedule_id_index,
        start_time_hh * 60 + start_time_mm + 24 * 60 * day_of_week_number as start_time,
        end_time_hh * 60 + end_time_mm + 24 * 60 * day_of_week_number as end_time,
        valid_from,
        valid_until,
        day_of_week,
        day_of_week_number
    from split_times
)

select *
from calculate_start_end_times