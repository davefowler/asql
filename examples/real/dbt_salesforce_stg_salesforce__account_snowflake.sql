-- Source: dbt_salesforce
-- Model: stg_salesforce__account
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_salesforce
-- File: models/salesforce/staging/stg_salesforce__account.sql

with fields as (

    select
        *

    from fields
),

final as (
    select
        cast(_fivetran_synced as TIMESTAMP) as _fivetran_synced,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,
        ,

    from fields
    where coalesce(_fivetran_active, true)
)

select *
from final
where not coalesce(is_deleted, false)