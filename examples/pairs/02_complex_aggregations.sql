-- Complex aggregations: Sales by region and month
-- Source: Inspired by patterns from Fivetran dbt packages
--   - https://github.com/fivetran/dbt_shopify
--   - https://github.com/fivetran/dbt_stripe
SELECT 
    region,
    DATE_TRUNC('month', order_date) AS month,
    COUNT(DISTINCT order_id) AS order_count,
    COUNT(DISTINCT customer_id) AS customer_count,
    SUM(amount) AS total_revenue,
    AVG(amount) AS avg_order_value,
    MIN(amount) AS min_order_value,
    MAX(amount) AS max_order_value,
    SUM(CASE WHEN status = 'refunded' THEN amount ELSE 0 END) AS refunded_amount
FROM sales
WHERE order_date >= '2024-01-01'
GROUP BY region, DATE_TRUNC('month', order_date)
HAVING SUM(amount) > 10000
ORDER BY month DESC, total_revenue DESC;

