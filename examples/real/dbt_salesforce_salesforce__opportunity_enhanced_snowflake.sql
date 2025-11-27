-- Source: dbt_salesforce
-- Model: salesforce__opportunity_enhanced
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_salesforce
-- File: models/salesforce/salesforce__opportunity_enhanced.sql

with opportunity as (

    select *
    from opportunity
),

salesforce_user as (

    select *
    from salesforce_user
),

-- If using user_role table, the following will be included, otherwise it will not.

account as (

    select *
    from account
),

add_fields as (

    select
        opportunity.*,
        account.account_number,
        account.account_source,
        account.industry,
        account.account_name,
        account.number_of_employees,
        account.type as account_type,
        opportunity_owner.user_id as opportunity_owner_id,
        opportunity_owner.user_name as opportunity_owner_name,
        opportunity_owner.user_role_id as opportunity_owner_role_id,
        opportunity_owner.city opportunity_owner_city,
        opportunity_owner.state as opportunity_owner_state,
        opportunity_manager.user_id as opportunity_manager_id,
        opportunity_manager.user_name as opportunity_manager_name,
        opportunity_manager.city opportunity_manager_city,
        opportunity_manager.state as opportunity_manager_state,

        -- If using user_role table, the following will be included, otherwise it will not.

        case
            when opportunity.is_won then 'Won'
            when not opportunity.is_won and opportunity.is_closed then 'Lost'
            when not opportunity.is_closed and lower(opportunity.forecast_category) in ('pipeline','forecast','bestcase') then 'Pipeline'
            else 'Other'
        end as status,
        case when is_created_this_month then amount else 0 end as created_amount_this_month,
        case when is_created_this_quarter then amount else 0 end as created_amount_this_quarter,
        case when is_created_this_month then 1 else 0 end as created_count_this_month,
        case when is_created_this_quarter then 1 else 0 end as created_count_this_quarter,
        case when is_closed_this_month then amount else 0 end as closed_amount_this_month,
        case when is_closed_this_quarter then amount else 0 end as closed_amount_this_quarter,
        case when is_closed_this_month then 1 else 0 end as closed_count_this_month,
        case when is_closed_this_quarter then 1 else 0 end as closed_count_this_quarter

        --The below script allows for pass through columns.

        -- If using user_role table, the following will be included, otherwise it will not.

    from opportunity
    left join account
        on opportunity.account_id = account.account_id
    left join salesforce_user as opportunity_owner
        on opportunity.owner_id = opportunity_owner.user_id
    left join salesforce_user as opportunity_manager
        on opportunity_owner.manager_id = opportunity_manager.user_id

    -- If using user_role table, the following will be included, otherwise it will not.

)

select *
from add_fields
