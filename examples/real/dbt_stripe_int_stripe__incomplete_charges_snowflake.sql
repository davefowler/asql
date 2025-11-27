-- Source: dbt_stripe
-- Model: int_stripe__incomplete_charges
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_stripe
-- File: models/intermediate/int_stripe__incomplete_charges.sql

with charge as (

    select *
    from charge

)

select
  balance_transaction_id,
  created_at,
  customer_id,
  connected_account_id,
  amount,
  source_relation
from charge
where not is_captured
