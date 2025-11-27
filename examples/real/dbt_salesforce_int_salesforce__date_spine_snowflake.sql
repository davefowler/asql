-- Source: dbt_salesforce
-- Model: int_salesforce__date_spine
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_salesforce
-- File: models/salesforce/intermediate/int_salesforce__date_spine.sql

with spine as (
    select
        dateadd(day, row_number() over (order by null) - 1, '2020-01-01'::date) as date_day
    from table(generator(rowcount => 3650))
)

select *
from spine