-- Source: dbt_shopify
-- Model: int_shopify_gql__product_variant
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_shopify
-- File: models/graphql/intermediate/base/int_shopify_gql__product_variant.sql

with product_variants as (

    select *
    from product_variants
),

inventory_item as (

    select *
    from inventory_item
),

joined as (

    select
        product_variants.*,
        inventory_item.measurement_weight_value as weight,
        inventory_item.measurement_weight_unit as weight_unit

    from product_variants
    left join inventory_item
        on product_variants.inventory_item_id = inventory_item.inventory_item_id
)

select *
from joined