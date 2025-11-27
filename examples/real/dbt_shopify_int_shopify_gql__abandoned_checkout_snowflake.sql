-- Source: dbt_shopify
-- Model: int_shopify_gql__abandoned_checkout
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_shopify
-- File: models/graphql/intermediate/base/int_shopify_gql__abandoned_checkout.sql

with abandoned_checkout as (

    select *
    from abandoned_checkout
),

customer as (

    select *
    from customer
),

add_customer_email as (

    select
        abandoned_checkout.*,
        customer.email
    from abandoned_checkout
    left join customer
        on abandoned_checkout.customer_id = customer.customer_id
        and abandoned_checkout.source_relation = customer.source_relation
)

select *
from add_customer_email