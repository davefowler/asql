-- Window functions: Running totals and rankings
-- Source: Inspired by patterns from Fivetran dbt packages
--   - https://github.com/fivetran/dbt_stripe
--   - https://github.com/fivetran/dbt_salesforce
SELECT 
    order_id,
    customer_id,
    order_date,
    amount,
    SUM(amount) OVER (PARTITION BY customer_id ORDER BY order_date) AS running_total,
    ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) AS order_rank,
    LAG(amount) OVER (PARTITION BY customer_id ORDER BY order_date) AS previous_order_amount,
    AVG(amount) OVER (PARTITION BY customer_id ORDER BY order_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS moving_avg_3_orders
FROM orders
WHERE status = 'completed'
ORDER BY customer_id, order_date;

