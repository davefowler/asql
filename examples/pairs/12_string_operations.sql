-- String operations: Email domain analysis
SELECT 
    SUBSTRING(email FROM POSITION('@' IN email) + 1) AS email_domain,
    COUNT(*) AS user_count,
    COUNT(CASE WHEN status = 'active' THEN 1 END) AS active_users,
    COUNT(CASE WHEN verified = true THEN 1 END) AS verified_users
FROM users
WHERE email IS NOT NULL
GROUP BY SUBSTRING(email FROM POSITION('@' IN email) + 1)
HAVING COUNT(*) >= 10
ORDER BY user_count DESC;

