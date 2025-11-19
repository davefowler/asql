-- Complex filtering: Multi-condition queries
SELECT 
    o.order_id,
    o.order_date,
    c.customer_name,
    o.total_amount,
    COUNT(oi.product_id) AS item_count
FROM orders o
INNER JOIN customers c ON o.customer_id = c.customer_id
LEFT JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.status = 'completed'
    AND o.order_date >= '2024-01-01'
    AND o.total_amount >= 100
    AND c.country IN ('US', 'CA', 'UK')
    AND EXISTS (
        SELECT 1 
        FROM order_items oi2 
        WHERE oi2.order_id = o.order_id 
        AND oi2.price > 50
    )
GROUP BY o.order_id, o.order_date, c.customer_name, o.total_amount
HAVING COUNT(oi.product_id) >= 2
ORDER BY o.order_date DESC, o.total_amount DESC;

