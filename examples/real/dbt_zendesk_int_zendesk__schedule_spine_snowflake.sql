-- Source: dbt_zendesk
-- Model: int_zendesk__schedule_spine
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_zendesk
-- File: models/intermediate/int_zendesk__schedule_spine.sql

/*
    This model generates `valid_from` and `valid_until` timestamps for each schedule start_time and stop_time,
    accounting for timezone changes, holidays, and historical schedule adjustments. The inclusion of holidays
    and historical changes is controlled by variables `using_holidays` and `using_schedule_histories`.

    !!! Important distinction for holiday ranges: A holiday remains valid through the entire day specified by
    the `valid_until` field. In contrast, schedule history and timezone `valid_until` values mark the end of
    validity at the start of the specified day.
*/

with schedule_timezones as (
    select *
    from schedule_timezones

), adjust_spillover as(
    select
        source_relation,
        schedule_id,
        valid_from,
        valid_until,
        change_type,

        -- ensure only valid start and end times are used. Spillover is accounted for in the following unions.
        greatest(start_time_utc, 0) as start_time_utc,
        least(end_time_utc, 7*24*60) as end_time_utc
    from final

    union all

    -- Handle spillover for time zones ahead of UTC.
    -- Occurs when start_time_utc < 0 after applying the local timezone offset.
    -- In these cases, there will be a gap at the end of the week and the spillover appears at the beginning.
    -- Example: a UTC 24/7 schedule spans start_time_utc = 0 and end_time_utc = 10080.
    -- After applying a +7 hour offset, the same schedule could become start_time_utc = -420 and end_time_utc = 9660.
    -- Since values < 0 exceed the valid week range, add a compensating slice to cover the gap.

    select
        source_relation,
        schedule_id,
        valid_from,
        valid_until,
        change_type,
        7*24*60 + start_time_utc as start_time_utc, -- "+" since in this case the start time would be negative
        7*24*60 as end_time_utc
    from final
    where start_time_utc < 0

    union all

    -- Handle spillover for time zones behind UTC.
    -- Occurs when end_time_utc > 10080 after applying the local timezone offset.
    -- In these cases, there will be a gap at the beginning of the week and the spillover appears at the end.
    -- Example: a UTC 24/7 schedule spans start_time_utc = 0 and end_time_utc = 10080.
    -- After applying a -5 hour offset, the same schedule could become start_time_utc = 300 and end_time_utc = 10380.
    -- Since values > 10080 exceed the valid week range, add a compensating slice to cover the gap.
    select
        source_relation,
        schedule_id,
        valid_from,
        valid_until,
        change_type,
        0 as start_time_utc,
        end_time_utc - 7*24*60 as end_time_utc
    from final
    where end_time_utc > 7*24*60
)

select *
from adjust_spillover
