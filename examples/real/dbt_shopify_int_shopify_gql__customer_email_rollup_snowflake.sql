-- Source: dbt_shopify
-- Model: int_shopify_gql__customer_email_rollup
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_shopify
-- File: models/graphql/intermediate/int_shopify_gql__customer_email_rollup.sql

with customers as (

    select
        *,
        row_number() over(
            partition by email, source_relation
            order by created_timestamp desc)
            as customer_index

    from customer_email_rollup
    where email is not null -- nonsensical to include any null emails here

), customer_tags as (

    select
        *
    from customer_tags

), rollup_customers as (

    select
        -- fields to group by
        lower(customers.email) as email,
        customers.source_relation,

        -- fields to string agg together
        string_agg(cast(customers.customer_id as string), ', ') as customer_ids,
        string_agg(customers.phone, ', ') as phone_numbers,
        string_agg(customer_tags.tag, ', ') as customer_tags,

        -- fields to take aggregates of
        min(customers.created_timestamp) as first_account_created_at,
        max(customers.created_timestamp) as last_account_created_at,
        max(customers.updated_timestamp) as last_updated_at,
        max(customers.marketing_consent_updated_at) as marketing_consent_updated_at,
        max(customers._fivetran_synced) as last_fivetran_synced,

        -- take true if ever given for boolean fields
        NULL as is_tax_exempt, -- since this changes every year
        NULL as is_verified_email

        -- for all other fields, just take the latest value

    from customers
    left join customer_tags
        on customers.customer_id = customer_tags.customer_id
        and customers.source_relation = customer_tags.source_relation

    group by 1,2

)

select *
from rollup_customers
