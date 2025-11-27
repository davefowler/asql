-- Source: dbt_zendesk
-- Model: int_zendesk__organization_aggregates
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_zendesk
-- File: models/intermediate/int_zendesk__organization_aggregates.sql

with organizations as (
    select *
    from organizations

--If you use organization tags, this will be included, if not it will be ignored.

--If you use using_domain_names tags this will be included, if not it will be ignored.

), final as (
    select
        organizations.*

        --If you use organization tags this will be included, if not it will be ignored.

        --If you use using_domain_names tags this will be included, if not it will be ignored.

    from organizations

    --If you use using_domain_names tags this will be included, if not it will be ignored.

    --If you use organization tags this will be included, if not it will be ignored.

)

select *
from final