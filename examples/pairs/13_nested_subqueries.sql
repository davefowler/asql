-- Nested subqueries: Customers who ordered above average
SELECT 
    c.customer_id,
    c.customer_name,
    c.email,
    o.order_id,
    o.order_date,
    o.total_amount
FROM customers c
INNER JOIN orders o ON c.customer_id = o.customer_id
WHERE o.total_amount > (
    SELECT AVG(total_amount) 
    FROM orders 
    WHERE status = 'completed' AND order_date >= '2024-01-01'
)
AND o.status = 'completed'
ORDER BY o.total_amount DESC;

