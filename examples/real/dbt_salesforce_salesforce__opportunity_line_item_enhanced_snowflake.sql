-- Source: dbt_salesforce
-- Model: salesforce__opportunity_line_item_enhanced
-- Dialect: snowflake
-- Repository: https://github.com/fivetran/dbt_salesforce
-- File: models/salesforce/salesforce__opportunity_line_item_enhanced.sql

--This model will only run if you have the underlying opportunity line item table.

with opportunity_line_item as (

    select *
    from opportunity_line_item
),

-- If using product_2 table, the following will be included, otherwise it will not.

final as (

    select
        oli.opportunity_line_item_id,
        oli.opportunity_line_item_name,
        oli.opportunity_line_item_description,
        oli.opportunity_id,
        row_number() over (partition by oli.opportunity_id order by oli.created_date) as line_item_index,
        count(opportunity_line_item_id) over (partition by oli.opportunity_id) as total_line_items,
        oli.created_date,
        oli.last_modified_date,
        oli.service_date,
        oli.pricebook_entry_id,
        oli.product_2_id,
        oli.list_price,
        oli.quantity,
        oli.unit_price,
        oli.total_price,
        oli.has_quantity_schedule,
        oli.has_revenue_schedule

        --The below script allows for pass through columns.

    from opportunity_line_item as oli

)

select *
from final