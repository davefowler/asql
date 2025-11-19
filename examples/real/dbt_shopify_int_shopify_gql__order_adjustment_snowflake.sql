-- Source: dbt_shopify
-- Model: int_shopify_gql__order_adjustment
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_shopify
-- File: models/graphql/intermediate/base/int_shopify_gql__order_adjustment.sql

{{ config(enabled=var('shopify_api', 'rest') == var('shopify_api_override','graphql')) }}

with order_adjustment as (

    select *
    from {{ ref('stg_shopify_gql__order_adjustment') }}
),

refund as (

    select *
    from {{ ref('stg_shopify_gql__refund') }}
),

joined as (

    select 
        order_adjustment.*,
        refund.order_id

    from order_adjustment
    left join refund
        on order_adjustment.refund_id = refund.refund_id
        and order_adjustment.source_relation = refund.source_relation
)

select *
from joined