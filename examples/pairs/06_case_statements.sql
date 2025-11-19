-- Case statements: Customer segmentation
-- Source: Inspired by patterns from Fivetran dbt packages
--   - https://github.com/fivetran/dbt_stripe
--   - https://github.com/fivetran/dbt_salesforce
SELECT 
    customer_id,
    customer_name,
    total_orders,
    total_spent,
    CASE 
        WHEN total_spent >= 10000 THEN 'VIP'
        WHEN total_spent >= 5000 THEN 'Premium'
        WHEN total_spent >= 1000 THEN 'Regular'
        ELSE 'New'
    END AS customer_tier,
    CASE 
        WHEN total_orders >= 20 THEN 'High Frequency'
        WHEN total_orders >= 10 THEN 'Medium Frequency'
        ELSE 'Low Frequency'
    END AS order_frequency
FROM (
    SELECT 
        c.customer_id,
        c.customer_name,
        COUNT(DISTINCT o.order_id) AS total_orders,
        COALESCE(SUM(o.total_amount), 0) AS total_spent
    FROM customers c
    LEFT JOIN orders o ON c.customer_id = o.customer_id AND o.status = 'completed'
    GROUP BY c.customer_id, c.customer_name
) customer_stats
ORDER BY total_spent DESC;

