"""Reverse translation examples - SQL to ASQL."""

import sqlglot
import asql as asql_dialect  # noqa: F401  # Register ASQL dialect


def reverse_compile(sql: str, source_dialect: str) -> str:
    """Convert SQL to ASQL using sqlglot.transpile."""
    return sqlglot.transpile(sql, read=source_dialect, write='asql')[0]


def example_bigquery_cte():
    """BigQuery query with CTEs."""
    sql = """
WITH active_users AS (
  SELECT 
    user_id,
    country,
    signup_date
  FROM users
  WHERE status = 'active'
    AND signup_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
),
user_orders AS (
  SELECT 
    au.user_id,
    au.country,
    COUNT(o.order_id) AS order_count,
    SUM(o.amount) AS total_spent
  FROM active_users au
  LEFT JOIN orders o ON au.user_id = o.user_id
  GROUP BY au.user_id, au.country
)
SELECT 
  country,
  COUNT(*) AS user_count,
  AVG(order_count) AS avg_orders,
  SUM(total_spent) AS total_revenue
FROM user_orders
GROUP BY country
ORDER BY total_revenue DESC
LIMIT 10
"""
    asql = reverse_compile(sql, source_dialect='bigquery')
    print("SQL (BigQuery):")
    print(sql)
    print("\nASQL:")
    print(asql)
    return sql, asql


def example_redshift_window_function():
    """Redshift query with window functions."""
    sql = """
SELECT 
  product_id,
  category,
  sale_date,
  amount,
  SUM(amount) OVER (
    PARTITION BY category 
    ORDER BY sale_date 
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS running_total
FROM sales
WHERE sale_date >= '2024-01-01'
ORDER BY category, sale_date
"""
    asql = reverse_compile(sql, source_dialect='redshift')
    print("SQL (Redshift):")
    print(sql)
    print("\nASQL:")
    print(asql)
    return sql, asql


def example_postgres_complex_join():
    """PostgreSQL query with complex joins."""
    sql = """
SELECT 
  u.user_id,
  u.email,
  COUNT(DISTINCT o.order_id) AS order_count,
  SUM(o.amount) AS total_spent,
  AVG(o.amount) AS avg_order_value
FROM users u
INNER JOIN orders o ON u.user_id = o.user_id
LEFT JOIN order_items oi ON o.order_id = oi.order_id
WHERE u.created_at >= '2024-01-01'
  AND o.status = 'completed'
GROUP BY u.user_id, u.email
HAVING COUNT(DISTINCT o.order_id) > 5
ORDER BY total_spent DESC
LIMIT 20
"""
    asql = reverse_compile(sql, source_dialect='postgres')
    print("SQL (PostgreSQL):")
    print(sql)
    print("\nASQL:")
    print(asql)
    return sql, asql


def example_bigquery_nested_cte():
    """BigQuery query with nested CTEs."""
    sql = """
WITH monthly_sales AS (
  SELECT 
    DATE_TRUNC(order_date, MONTH) AS month,
    region,
    SUM(amount) AS revenue,
    COUNT(*) AS order_count
  FROM orders
  WHERE order_date >= '2023-01-01'
  GROUP BY month, region
),
region_rankings AS (
  SELECT 
    month,
    region,
    revenue,
    order_count,
    RANK() OVER (PARTITION BY month ORDER BY revenue DESC) AS revenue_rank
  FROM monthly_sales
)
SELECT 
  month,
  region,
  revenue,
  order_count
FROM region_rankings
WHERE revenue_rank <= 3
ORDER BY month DESC, revenue DESC
"""
    asql = reverse_compile(sql, source_dialect='bigquery')
    print("SQL (BigQuery):")
    print(sql)
    print("\nASQL:")
    print(asql)
    return sql, asql


def example_redshift_date_aggregation():
    """Redshift query with date aggregations."""
    sql = """
SELECT 
  DATE_TRUNC('week', event_timestamp) AS week,
  event_type,
  COUNT(*) AS event_count,
  COUNT(DISTINCT user_id) AS unique_users
FROM events
WHERE event_timestamp >= '2024-01-01'
  AND event_type IN ('click', 'view', 'purchase')
GROUP BY week, event_type
HAVING COUNT(*) > 100
ORDER BY week DESC, event_count DESC
"""
    asql = reverse_compile(sql, source_dialect='redshift')
    print("SQL (Redshift):")
    print(sql)
    print("\nASQL:")
    print(asql)
    return sql, asql


def example_bigquery_unnest():
    """BigQuery query with UNNEST."""
    sql = """
SELECT 
  user_id,
  tag,
  COUNT(*) AS tag_count
FROM users,
UNNEST(tags) AS tag
WHERE status = 'active'
GROUP BY user_id, tag
ORDER BY tag_count DESC
LIMIT 100
"""
    asql = reverse_compile(sql, source_dialect='bigquery')
    print("SQL (BigQuery):")
    print(sql)
    print("\nASQL:")
    print(asql)
    return sql, asql


def example_postgres_subquery():
    """PostgreSQL query with subqueries."""
    sql = """
SELECT 
  p.product_id,
  p.name,
  p.price,
  (SELECT AVG(price) FROM products WHERE category = p.category) AS avg_category_price
FROM products p
WHERE p.price > (
  SELECT AVG(price) 
  FROM products 
  WHERE category = p.category
)
ORDER BY p.price DESC
"""
    asql = reverse_compile(sql, source_dialect='postgres')
    print("SQL (PostgreSQL):")
    print(sql)
    print("\nASQL:")
    print(asql)
    return sql, asql


def example_bigquery_multiple_ctes():
    """BigQuery query with multiple CTEs."""
    sql = """
WITH customers AS (
  SELECT DISTINCT user_id, country, signup_date
  FROM users
  WHERE status = 'active'
),
orders_summary AS (
  SELECT 
    user_id,
    COUNT(*) AS order_count,
    SUM(amount) AS total_amount
  FROM orders
  WHERE status = 'completed'
  GROUP BY user_id
),
customer_metrics AS (
  SELECT 
    c.user_id,
    c.country,
    COALESCE(o.order_count, 0) AS order_count,
    COALESCE(o.total_amount, 0) AS total_amount
  FROM customers c
  LEFT JOIN orders_summary o ON c.user_id = o.user_id
)
SELECT 
  country,
  COUNT(*) AS customer_count,
  AVG(order_count) AS avg_orders,
  SUM(total_amount) AS total_revenue
FROM customer_metrics
GROUP BY country
ORDER BY total_revenue DESC
"""
    asql = reverse_compile(sql, source_dialect='bigquery')
    print("SQL (BigQuery):")
    print(sql)
    print("\nASQL:")
    print(asql)
    return sql, asql


def example_redshift_case_statement():
    """Redshift query with CASE statements."""
    sql = """
SELECT 
  user_id,
  amount,
  CASE 
    WHEN amount < 50 THEN 'low'
    WHEN amount < 200 THEN 'medium'
    ELSE 'high'
  END AS order_tier,
  COUNT(*) AS order_count
FROM orders
WHERE order_date >= '2024-01-01'
GROUP BY user_id, amount, order_tier
ORDER BY amount DESC
LIMIT 50
"""
    asql = reverse_compile(sql, source_dialect='redshift')
    print("SQL (Redshift):")
    print(sql)
    print("\nASQL:")
    print(asql)
    return sql, asql


def example_bigquery_array_aggregation():
    """BigQuery query with array aggregations."""
    sql = """
SELECT 
  category,
  COUNT(*) AS product_count,
  ARRAY_AGG(DISTINCT brand IGNORE NULLS) AS brands,
  AVG(price) AS avg_price
FROM products
WHERE in_stock = TRUE
GROUP BY category
ORDER BY product_count DESC
"""
    asql = reverse_compile(sql, source_dialect='bigquery')
    print("SQL (BigQuery):")
    print(sql)
    print("\nASQL:")
    print(asql)
    return sql, asql


def example_postgres_json_operations():
    """PostgreSQL query with JSON operations."""
    sql = """
SELECT 
  user_id,
  metadata->>'source' AS source,
  COUNT(*) AS event_count
FROM events
WHERE metadata ? 'source'
  AND event_timestamp >= '2024-01-01'
GROUP BY user_id, metadata->>'source'
ORDER BY event_count DESC
LIMIT 100
"""
    asql = reverse_compile(sql, source_dialect='postgres')
    print("SQL (PostgreSQL):")
    print(sql)
    print("\nASQL:")
    print(asql)
    return sql, asql


def example_bigquery_time_series():
    """BigQuery query for time series analysis."""
    sql = """
WITH daily_metrics AS (
  SELECT 
    DATE(timestamp) AS date,
    event_type,
    COUNT(*) AS event_count,
    COUNT(DISTINCT user_id) AS unique_users
  FROM events
  WHERE timestamp >= TIMESTAMP('2024-01-01')
    AND timestamp < TIMESTAMP('2024-02-01')
  GROUP BY date, event_type
),
daily_totals AS (
  SELECT 
    date,
    SUM(event_count) AS total_events,
    SUM(unique_users) AS total_users
  FROM daily_metrics
  GROUP BY date
)
SELECT 
  dt.date,
  dt.total_events,
  dt.total_users,
  dm.event_type,
  dm.event_count
FROM daily_totals dt
LEFT JOIN daily_metrics dm ON dt.date = dm.date
ORDER BY dt.date DESC, dm.event_count DESC
"""
    asql = reverse_compile(sql, source_dialect='bigquery')
    print("SQL (BigQuery):")
    print(sql)
    print("\nASQL:")
    print(asql)
    return sql, asql


if __name__ == "__main__":
    print("=== Reverse Translation Examples ===\n")
    
    examples = [
        ("BigQuery CTE", example_bigquery_cte),
        ("Redshift Window Function", example_redshift_window_function),
        ("PostgreSQL Complex Join", example_postgres_complex_join),
        ("BigQuery Nested CTE", example_bigquery_nested_cte),
        ("Redshift Date Aggregation", example_redshift_date_aggregation),
        ("BigQuery UNNEST", example_bigquery_unnest),
        ("PostgreSQL Subquery", example_postgres_subquery),
        ("BigQuery Multiple CTEs", example_bigquery_multiple_ctes),
        ("Redshift CASE Statement", example_redshift_case_statement),
        ("BigQuery Array Aggregation", example_bigquery_array_aggregation),
        ("PostgreSQL JSON Operations", example_postgres_json_operations),
        ("BigQuery Time Series", example_bigquery_time_series),
    ]
    
    for title, func in examples:
        print(f"\n{'='*60}")
        print(f"Example: {title}")
        print('='*60)
        try:
            func()
        except Exception as e:
            print(f"Error: {e}")
        print("\n")
