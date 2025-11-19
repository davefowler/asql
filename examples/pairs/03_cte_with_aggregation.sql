-- CTE: Active users by country with their order totals
-- Source: Inspired by patterns from Fivetran dbt packages
--   - https://github.com/fivetran/dbt_shopify
--   - https://github.com/fivetran/dbt_stripe
WITH active_users AS (
    SELECT * FROM users WHERE status = 'active' AND last_login_date >= CURRENT_DATE - INTERVAL '30 days'
),
user_orders AS (
    SELECT 
        customer_id,
        COUNT(*) AS order_count,
        SUM(total_amount) AS lifetime_value
    FROM orders
    WHERE status = 'completed'
    GROUP BY customer_id
)
SELECT 
    au.country,
    COUNT(DISTINCT au.user_id) AS active_user_count,
    AVG(COALESCE(uo.order_count, 0)) AS avg_orders_per_user,
    SUM(COALESCE(uo.lifetime_value, 0)) AS total_lifetime_value
FROM active_users au
LEFT JOIN user_orders uo ON au.user_id = uo.customer_id
GROUP BY au.country
ORDER BY active_user_count DESC;

