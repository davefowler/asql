-- Multi-table join: Orders with customers and products
-- Source: Inspired by patterns from Fivetran dbt packages
--   - https://github.com/fivetran/dbt_shopify
--   - https://github.com/fivetran/dbt_stripe
SELECT 
    o.order_id,
    o.order_date,
    c.customer_name,
    c.email,
    p.product_name,
    p.category,
    oi.quantity,
    oi.price,
    (oi.quantity * oi.price) AS line_total
FROM orders o
INNER JOIN customers c ON o.customer_id = c.customer_id
INNER JOIN order_items oi ON o.order_id = oi.order_id
INNER JOIN products p ON oi.product_id = p.product_id
WHERE o.status = 'completed'
ORDER BY o.order_date DESC;

