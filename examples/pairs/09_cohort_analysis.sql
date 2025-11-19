-- Cohort analysis: User retention by signup month
-- Source: Inspired by patterns from Fivetran dbt packages
--   - https://github.com/fivetran/dbt_shopify
WITH user_cohorts AS (
    SELECT 
        user_id,
        DATE_TRUNC('month', signup_date) AS cohort_month,
        signup_date
    FROM users
),
monthly_activity AS (
    SELECT 
        user_id,
        DATE_TRUNC('month', activity_date) AS activity_month
    FROM user_activities
    GROUP BY user_id, DATE_TRUNC('month', activity_date)
)
SELECT 
    uc.cohort_month,
    COUNT(DISTINCT uc.user_id) AS cohort_size,
    COUNT(DISTINCT ma.user_id) AS active_users,
    ROUND(COUNT(DISTINCT ma.user_id)::numeric / COUNT(DISTINCT uc.user_id) * 100, 2) AS retention_rate
FROM user_cohorts uc
LEFT JOIN monthly_activity ma ON uc.user_id = ma.user_id 
    AND ma.activity_month = uc.cohort_month
GROUP BY uc.cohort_month
ORDER BY uc.cohort_month DESC;

