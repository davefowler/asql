-- Product analytics: Best performing products by category
-- Source: Inspired by patterns from Fivetran dbt packages
--   - https://github.com/fivetran/dbt_shopify
SELECT 
    p.category,
    p.product_name,
    COUNT(DISTINCT o.order_id) AS order_count,
    SUM(oi.quantity) AS total_quantity_sold,
    SUM(oi.quantity * oi.price) AS total_revenue,
    AVG(oi.price) AS avg_price,
    COUNT(DISTINCT o.customer_id) AS unique_customers
FROM products p
INNER JOIN order_items oi ON p.product_id = oi.product_id
INNER JOIN orders o ON oi.order_id = o.order_id
WHERE o.status = 'completed' 
    AND o.order_date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY p.category, p.product_name
HAVING COUNT(DISTINCT o.order_id) >= 5
ORDER BY p.category, total_revenue DESC;

