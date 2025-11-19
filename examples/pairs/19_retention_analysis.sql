-- Retention analysis: Monthly active users and retention
-- Source: Inspired by patterns from Fivetran dbt packages
--   - https://github.com/fivetran/dbt_shopify
--   - https://github.com/fivetran/dbt_zendesk
WITH monthly_users AS (
    SELECT 
        user_id,
        DATE_TRUNC('month', activity_date) AS activity_month
    FROM user_activities
    GROUP BY user_id, DATE_TRUNC('month', activity_date)
),
user_first_month AS (
    SELECT 
        user_id,
        MIN(activity_month) AS first_month
    FROM monthly_users
    GROUP BY user_id
)
SELECT 
    um.activity_month,
    COUNT(DISTINCT um.user_id) AS mau,
    COUNT(DISTINCT CASE WHEN ufm.first_month = um.activity_month THEN um.user_id END) AS new_users,
    COUNT(DISTINCT CASE WHEN ufm.first_month < um.activity_month THEN um.user_id END) AS returning_users,
    ROUND(COUNT(DISTINCT CASE WHEN ufm.first_month < um.activity_month THEN um.user_id END)::numeric 
        / NULLIF(COUNT(DISTINCT um.user_id), 0) * 100, 2) AS retention_rate
FROM monthly_users um
LEFT JOIN user_first_month ufm ON um.user_id = ufm.user_id
GROUP BY um.activity_month
ORDER BY um.activity_month DESC;

