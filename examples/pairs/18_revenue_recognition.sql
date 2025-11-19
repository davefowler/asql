-- Revenue recognition: Deferred revenue by subscription
-- Source: Inspired by patterns from Fivetran dbt packages
--   - https://github.com/fivetran/dbt_stripe
SELECT 
    s.subscription_id,
    s.customer_id,
    s.plan_name,
    s.monthly_amount,
    s.start_date,
    s.end_date,
    COUNT(DISTINCT DATE_TRUNC('month', payment_date)) AS months_paid,
    SUM(p.amount) AS total_paid,
    SUM(p.amount) - SUM(CASE 
        WHEN payment_date <= CURRENT_DATE THEN p.amount 
        ELSE 0 
    END) AS deferred_revenue
FROM subscriptions s
INNER JOIN payments p ON s.subscription_id = p.subscription_id
WHERE s.status = 'active'
GROUP BY s.subscription_id, s.customer_id, s.plan_name, s.monthly_amount, s.start_date, s.end_date
ORDER BY deferred_revenue DESC;

