-- Funnel analysis: Conversion rates through stages
-- Source: Inspired by patterns from Fivetran dbt packages
--   - https://github.com/fivetran/dbt_shopify
--   - https://github.com/fivetran/dbt_stripe
WITH funnel_stages AS (
    SELECT 'viewed' AS stage, COUNT(DISTINCT user_id) AS users FROM page_views WHERE page = 'product'
    UNION ALL
    SELECT 'added_to_cart', COUNT(DISTINCT user_id) FROM cart_items
    UNION ALL
    SELECT 'started_checkout', COUNT(DISTINCT user_id) FROM checkout_sessions WHERE status = 'started'
    UNION ALL
    SELECT 'completed_purchase', COUNT(DISTINCT user_id) FROM orders WHERE status = 'completed'
)
SELECT 
    stage,
    users,
    LAG(users) OVER (ORDER BY 
        CASE stage
            WHEN 'viewed' THEN 1
            WHEN 'added_to_cart' THEN 2
            WHEN 'started_checkout' THEN 3
            WHEN 'completed_purchase' THEN 4
        END
    ) AS previous_stage_users,
    ROUND(users::numeric / FIRST_VALUE(users) OVER (ORDER BY 
        CASE stage
            WHEN 'viewed' THEN 1
            WHEN 'added_to_cart' THEN 2
            WHEN 'started_checkout' THEN 3
            WHEN 'completed_purchase' THEN 4
        END
    ) * 100, 2) AS conversion_rate
FROM funnel_stages
ORDER BY 
    CASE stage
        WHEN 'viewed' THEN 1
        WHEN 'added_to_cart' THEN 2
        WHEN 'started_checkout' THEN 3
        WHEN 'completed_purchase' THEN 4
    END;

