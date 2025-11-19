-- Date/time analysis: Monthly signups and retention
-- Source: Inspired by patterns from Fivetran dbt packages
--   - https://github.com/fivetran/dbt_shopify
--   - https://github.com/fivetran/dbt_zendesk
SELECT 
    DATE_TRUNC('month', signup_date) AS signup_month,
    COUNT(*) AS signups,
    COUNT(CASE WHEN last_login_date >= CURRENT_DATE - INTERVAL '7 days' THEN 1 END) AS active_last_7_days,
    COUNT(CASE WHEN last_login_date >= CURRENT_DATE - INTERVAL '30 days' THEN 1 END) AS active_last_30_days,
    AVG(EXTRACT(EPOCH FROM (last_login_date - signup_date)) / 86400) AS avg_days_to_first_login
FROM users
WHERE signup_date >= '2024-01-01'
GROUP BY DATE_TRUNC('month', signup_date)
ORDER BY signup_month DESC;

