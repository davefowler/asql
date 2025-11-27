-- Source: dbt_stripe
-- Model: stg_stripe__charge
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_stripe
-- File: models/staging/stg_stripe__charge.sql

with base as (

    select *
    from base

),

fields as (

    select
        *,
        'source' as source_relation

    from base
),

final as (

    select
        id as charge_id,
        balance_transaction_id,
        captured as is_captured,
        card_id,
        cast(created as TIMESTAMP) as created_at,
        connected_account_id,
        customer_id,
        currency,
        description,
        failure_code,
        failure_message,
        metadata,
        paid as is_paid,
        payment_intent_id,
        payment_method_id,
        receipt_email,
        receipt_number,
        refunded as is_refunded,
        status,
        shipping_address_city,
        shipping_address_country,
        shipping_address_line_1,
        shipping_address_line_2,
        shipping_address_postal_code,
        shipping_address_state,
        shipping_carrier,
        shipping_name,
        shipping_phone,
        shipping_tracking_number,
        source_id,
        source_transfer,
        statement_descriptor,
        invoice_id,
        calculated_statement_descriptor,
        billing_detail_address_city,
        billing_detail_address_country,
        billing_detail_address_line1,
        billing_detail_address_line2,
        billing_detail_address_postal_code,
        billing_detail_address_state,
        billing_detail_email,
        billing_detail_name,
        billing_detail_phone,
        source_relation

    from fields

)

select *
from final
