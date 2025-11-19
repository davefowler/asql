-- Union: Combined sales from multiple sources
SELECT 
    'online' AS source,
    order_date,
    amount,
    customer_id
FROM online_orders
WHERE status = 'completed'
UNION ALL
SELECT 
    'retail' AS source,
    sale_date AS order_date,
    total_amount AS amount,
    customer_id
FROM retail_sales
WHERE status = 'completed'
ORDER BY order_date DESC;

