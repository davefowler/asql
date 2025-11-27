-- Source: dbt_zendesk
-- Model: int_zendesk__schedule_holiday
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_zendesk
-- File: models/intermediate/int_zendesk__schedule_holiday.sql

with schedule as (
    select *
    from schedule

), schedule_holiday as (
    select *
    from schedule_holiday

-- Converts holiday_start_date_at and holiday_end_date_at into daily timestamps and finds the week starts/ends using week_start.
), schedule_holiday_ranges as (
    select
        source_relation,
        holiday_name,
        schedule_id,
        cast(holiday_start_date_at as TIMESTAMP) as holiday_valid_from,
        cast(holiday_end_date_at as TIMESTAMP) as holiday_valid_until,
        cast(holiday_start_date_at as TIMESTAMP) as holiday_starting_sunday,
        cast(holiday_end_date_at as TIMESTAMP) as holiday_ending_sunday,
        -- Since the spine is based on weeks, holidays that span multiple weeks need to be broken up in to weeks. First step is to find those holidays.
        datediff('week', holiday_start_date_at, holiday_end_date_at) + 1 as holiday_weeks_spanned
    from schedule_holiday

-- Creates a record for each week of multi-week holidays. Update valid_from and valid_until in the next cte.
), expanded_holidays as (
    select
        schedule_holiday_ranges.*,
        cast(week_numbers.generated_number as INT) as holiday_week_number
    from schedule_holiday_ranges
    -- Generate a sequence of numbers from 0 to the max number of weeks spanned, assuming a holiday won't span more than 52 weeks
    cross join (select row_number() over (order by null) - 1 as generated_number from table(generator(rowcount => 52))) as week_numbers
    where schedule_holiday_ranges.holiday_weeks_spanned > 1
    and week_numbers.generated_number <= schedule_holiday_ranges.holiday_weeks_spanned

-- Define start and end times for each segment of a multi-week holiday.
), split_multiweek_holidays as (

    -- Business as usual for holidays that fall within a single week.
    select
        source_relation,
        holiday_name,
        schedule_id,
        holiday_valid_from,
        holiday_valid_until,
        holiday_starting_sunday,
        holiday_ending_sunday,
        holiday_weeks_spanned
    from schedule_holiday_ranges
    where holiday_weeks_spanned = 1

    union all

    -- Split holidays by week that span multiple weeks since the schedule spine is based on weeks.
    select
        source_relation,
        holiday_name,
        schedule_id,
        case
            when holiday_week_number = 1 -- first week in multiweek holiday
            then holiday_valid_from
            -- We have to use days in case warehouse does not truncate to Sunday.
            else dateadd('day', (holiday_week_number - 1) * 7, holiday_starting_sunday)
        end as holiday_valid_from,
        case
            when holiday_week_number = holiday_weeks_spanned -- last week in multiweek holiday
            then holiday_valid_until
            -- We have to use days in case warehouse does not truncate to Sunday.
            else dateadd('day', holiday_week_number * 7 - 1, holiday_starting_sunday) -- saturday
        end as holiday_valid_until,
        case
            when holiday_week_number = 1 -- first week in multiweek holiday
            then holiday_starting_sunday
            -- We have to use days in case warehouse does not truncate to Sunday.
            else dateadd('day', (holiday_week_number - 1) * 7, holiday_starting_sunday)
        end as holiday_starting_sunday,
        case
            when holiday_week_number = holiday_weeks_spanned -- last week in multiweek holiday
            then holiday_ending_sunday
            -- We have to use days in case warehouse does not truncate to Sunday.
            else dateadd('day', holiday_week_number * 7 - 1, holiday_starting_sunday)
        end as holiday_ending_sunday,
        holiday_weeks_spanned
    from expanded_holidays
    where holiday_weeks_spanned > 1

-- Create a record for each the holiday start and holiday end for each week to use downstream.
), split_holidays as (
    -- Creates a record that will be used for the time before a holiday
    select
        split_multiweek_holidays.*,
        holiday_valid_from as holiday_date,
        '0_gap' as holiday_start_or_end
    from split_multiweek_holidays

    union all

    -- Creates another record that will be used for the holiday itself
    select
        split_multiweek_holidays.*,
        holiday_valid_until as holiday_date,
        '1_holiday' as holiday_start_or_end
    from split_multiweek_holidays
)

select *
from split_holidays
