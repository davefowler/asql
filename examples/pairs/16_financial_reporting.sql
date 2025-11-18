-- Financial reporting: Monthly P&L summary
-- Source: Inspired by patterns from Fivetran dbt packages
--   - https://github.com/fivetran/dbt_stripe
SELECT 
    DATE_TRUNC('month', transaction_date) AS month,
    SUM(CASE WHEN transaction_type = 'revenue' THEN amount ELSE 0 END) AS total_revenue,
    SUM(CASE WHEN transaction_type = 'cost' THEN amount ELSE 0 END) AS total_costs,
    SUM(CASE WHEN transaction_type = 'expense' THEN amount ELSE 0 END) AS total_expenses,
    SUM(CASE WHEN transaction_type = 'revenue' THEN amount ELSE 0 END) 
        - SUM(CASE WHEN transaction_type = 'cost' THEN amount ELSE 0 END)
        - SUM(CASE WHEN transaction_type = 'expense' THEN amount ELSE 0 END) AS net_profit,
    LAG(SUM(CASE WHEN transaction_type = 'revenue' THEN amount ELSE 0 END)) 
        OVER (ORDER BY DATE_TRUNC('month', transaction_date)) AS prev_month_revenue
FROM financial_transactions
WHERE transaction_date >= '2024-01-01'
GROUP BY DATE_TRUNC('month', transaction_date)
ORDER BY month DESC;

