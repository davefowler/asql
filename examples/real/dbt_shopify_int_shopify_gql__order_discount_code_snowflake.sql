-- Source: dbt_shopify
-- Model: int_shopify_gql__order_discount_code
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_shopify
-- File: models/graphql/intermediate/base/int_shopify_gql__order_discount_code.sql

with order_discount_code as (

    select *
    from order_discount_code
),

discount_application as (

    select *
    from discount_application
),

joined as (

    select
        order_discount_code.*,
        discount_application.value_type as type,
        discount_application.value_amount,
        discount_application.value_currency_code,
        discount_application.value_percentage,
        discount_application.target_type,
        discount_application.target_selection,
        discount_application.allocation_method

    from order_discount_code
    left join discount_application
        on order_discount_code.order_id = discount_application.order_id
        and order_discount_code.code = discount_application.code
        and order_discount_code.source_relation = discount_application.source_relation
)

select *
from joined