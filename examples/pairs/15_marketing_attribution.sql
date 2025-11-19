-- Marketing attribution: First-touch and last-touch attribution
-- Source: Inspired by patterns from Fivetran dbt packages
--   - https://github.com/fivetran/dbt_stripe
--   - https://github.com/fivetran/dbt_salesforce
WITH first_touch AS (
    SELECT 
        customer_id,
        campaign_id,
        touchpoint_date,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY touchpoint_date ASC) AS rn
    FROM marketing_touchpoints
),
last_touch AS (
    SELECT 
        customer_id,
        campaign_id,
        touchpoint_date,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY touchpoint_date DESC) AS rn
    FROM marketing_touchpoints
)
SELECT 
    c.campaign_name,
    COUNT(DISTINCT ft.customer_id) AS first_touch_customers,
    COUNT(DISTINCT lt.customer_id) AS last_touch_customers,
    SUM(o.total_amount) AS attributed_revenue
FROM campaigns c
LEFT JOIN first_touch ft ON c.campaign_id = ft.campaign_id AND ft.rn = 1
LEFT JOIN last_touch lt ON c.campaign_id = lt.campaign_id AND lt.rn = 1
LEFT JOIN orders o ON (o.customer_id = ft.customer_id OR o.customer_id = lt.customer_id)
    AND o.status = 'completed'
GROUP BY c.campaign_id, c.campaign_name
ORDER BY attributed_revenue DESC;

