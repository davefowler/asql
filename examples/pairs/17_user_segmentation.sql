-- User segmentation: RFM analysis
-- Source: Inspired by patterns from Fivetran dbt packages
--   - https://github.com/fivetran/dbt_stripe
--   - https://github.com/fivetran/dbt_salesforce
WITH customer_rfm AS (
    SELECT 
        c.customer_id,
        c.customer_name,
        MAX(o.order_date) AS last_order_date,
        COUNT(DISTINCT o.order_id) AS frequency,
        SUM(o.total_amount) AS monetary_value,
        CURRENT_DATE - MAX(o.order_date) AS days_since_last_order
    FROM customers c
    LEFT JOIN orders o ON c.customer_id = o.customer_id AND o.status = 'completed'
    GROUP BY c.customer_id, c.customer_name
)
SELECT 
    customer_id,
    customer_name,
    frequency,
    monetary_value,
    days_since_last_order,
    CASE 
        WHEN days_since_last_order <= 30 THEN 'Active'
        WHEN days_since_last_order <= 90 THEN 'At Risk'
        WHEN days_since_last_order <= 180 THEN 'Churned'
        ELSE 'Lost'
    END AS recency_segment,
    CASE 
        WHEN frequency >= 10 THEN 'High'
        WHEN frequency >= 5 THEN 'Medium'
        WHEN frequency >= 1 THEN 'Low'
        ELSE 'None'
    END AS frequency_segment,
    CASE 
        WHEN monetary_value >= 5000 THEN 'High'
        WHEN monetary_value >= 1000 THEN 'Medium'
        WHEN monetary_value >= 100 THEN 'Low'
        ELSE 'None'
    END AS monetary_segment
FROM customer_rfm
ORDER BY monetary_value DESC;

