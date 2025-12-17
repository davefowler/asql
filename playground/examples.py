"""ASQL Playground examples.

These examples are used by both the playground frontend and tests.
"""

from typing import TypedDict


class Example(TypedDict):
    title: str
    desc: str
    query: str


# Basic ASQL examples
ASQL_EXAMPLES: list[Example] = [
    {
        "title": "Simple FROM",
        "desc": "Basic table selection",
        "query": "from users"
    },
    {
        "title": "WHERE Filter",
        "desc": "Filter with conditions",
        "query": 'from users\nwhere status == "active"'
    },
    {
        "title": "GROUP BY",
        "desc": "Aggregate with COUNT",
        "query": "from users\ngroup by country ( # as total_users )"
    },
    {
        "title": "Multiple Aggregations",
        "desc": "SUM, COUNT, AVG together",
        "query": """from sales
group by region ( 
    sum(amount) as revenue, 
    # as orders, 
    avg(amount) as avg_order 
)"""
    },
    {
        "title": "SORT Descending",
        "desc": "Order by descending",
        "query": """from users
group by country ( # as total_users )
order by -total_users"""
    },
    {
        "title": "TAKE/LIMIT",
        "desc": "Limit results",
        "query": "from users\nlimit 10"
    },
    {
        "title": "Complex Query",
        "desc": "Full pipeline example",
        "query": """from sales
where status == "completed" and amount > 100
group by region ( 
    sum(amount) as revenue, 
    # as orders 
)
order by -revenue
limit 10"""
    },
    {
        "title": "Multiple Conditions",
        "desc": "AND/OR operators",
        "query": """from users
where status == "active" 
    and age >= 18 
    and email is not null"""
    },
    {
        "title": "OR Conditions",
        "desc": "Multiple OR conditions",
        "query": """from users
where status == "active" 
    or status == "pending\""""
    },
    {
        "title": "NULL Checks",
        "desc": "IS NULL / IS NOT NULL",
        "query": "from users\nwhere email is not null"
    },
    {
        "title": "Comparisons",
        "desc": "All comparison operators",
        "query": "from users\nwhere age >= 18 and age <= 65"
    },
]

# Pipeline examples (multi-step queries)
PIPELINE_EXAMPLES: list[Example] = [
    {
        "title": "Multi-Step Pipeline",
        "desc": "Filter → Group → Sort → Limit (creates multiple CTEs)",
        "query": """from orders
where status == "completed" 
    and created_at >= "2024-01-01"
group by customer_id ( 
    sum(total) as total_spent, 
    # as order_count,
    avg(total) as avg_order_value 
)
order by -total_spent
limit 10"""
    },
    {
        "title": "Customer Analytics Pipeline",
        "desc": "Complex multi-step customer analysis",
        "query": """from customers
where signup_date >= "2023-01-01"
    and is_active == true
join orders on customers.id == orders.customer_id
group by customers.id, customers.country ( 
    sum(orders.total) as lifetime_value,
    # as total_orders,
    max(orders.created_at) as last_order_date 
)
order by -lifetime_value
limit 50"""
    },
    {
        "title": "Sales Funnel Analysis",
        "desc": "Multi-stage sales pipeline with joins",
        "query": """from leads
join opportunities on leads.id == opportunities.lead_id
join deals on opportunities.id == deals.opportunity_id
where leads.source == "website"
    and leads.created_at >= "2024-01-01"
    and opportunities.stage != "lost"
    and deals.status == "closed"
group by leads.source, deals.region ( 
    sum(deals.amount) as revenue,
    # as closed_deals,
    avg(deals.amount) as avg_deal_size 
)
order by -revenue"""
    },
    {
        "title": "Product Performance Pipeline",
        "desc": "Product analysis with multiple filters and aggregations",
        "query": """from products
join order_items on products.id == order_items.product_id
join orders on order_items.order_id == orders.id
where products.category == "electronics"
    and products.in_stock == true
    and orders.status == "completed"
    and orders.created_at >= "2024-01-01"
group by products.id, products.name ( 
    sum(order_items.quantity) as units_sold,
    sum(order_items.price * order_items.quantity) as revenue,
    # as order_count 
)
order by -revenue
limit 20"""
    },
    {
        "title": "User Engagement Pipeline",
        "desc": "User activity analysis with aggregation and filtering",
        "query": """from users
join events on users.id == events.user_id
where users.created_at >= "2023-01-01"
    and events.event_type == "purchase"
    and events.timestamp >= "2024-01-01"
group by users.id, users.country ( 
    # as purchase_count,
    sum(events.value) as total_spent,
    max(events.timestamp) as last_purchase_date 
)
order by -total_spent
limit 100"""
    },
    {
        "title": "Time-Series Aggregation Pipeline",
        "desc": "Date-based grouping with multiple aggregations",
        "query": """from transactions
where status == "completed"
    and transaction_date >= "2024-01-01"
group by date_trunc(transaction_date, "month"), region ( 
    sum(amount) as monthly_revenue,
    # as transaction_count,
    avg(amount) as avg_transaction,
    min(amount) as min_transaction,
    max(amount) as max_transaction 
)
order by transaction_date desc, -monthly_revenue"""
    },
    {
        "title": "Cohort Analysis Pipeline",
        "desc": "User cohort analysis with complex joins",
        "query": """from users
join orders on users.id == orders.user_id
where users.signup_date >= "2023-01-01"
    and orders.status == "completed"
group by date_trunc(users.signup_date, "month"), users.country ( 
    date_trunc(users.signup_date, "month") as cohort_month,
    # as users_in_cohort,
    sum(orders.total) as cohort_revenue,
    avg(orders.total) as avg_order_value 
)
order by cohort_month desc, -cohort_revenue"""
    },
    {
        "title": "Multi-Table Join Pipeline",
        "desc": "Complex joins across multiple tables",
        "query": """from customers
join orders on customers.id == orders.customer_id
join order_items on orders.id == order_items.order_id
join products on order_items.product_id == products.id
where orders.status == "completed"
    and orders.created_at >= "2024-01-01"
group by customers.id, customers.name ( 
    sum(order_items.quantity * order_items.price) as total_spent,
    # as products_purchased,
    count(distinct products.category) as categories_bought 
)
order by -total_spent
limit 25"""
    },
]

# Sampling examples
SAMPLING_EXAMPLES: list[Example] = [
    {
        "title": "Random Sample",
        "desc": "Get 100 random rows",
        "query": "from orders\nsample 100"
    },
    {
        "title": "Percentage Sample",
        "desc": "Get ~10% of rows",
        "query": "from orders\nsample 10%"
    },
    {
        "title": "Stratified Sample",
        "desc": "100 random rows per category",
        "query": "from products\nsample 100 per category"
    },
    {
        "title": "Sample with Filter",
        "desc": "Sample from filtered data",
        "query": """from orders
where status == "completed"
sample 500"""
    },
]

# Data reshaping examples (pivot, unpivot, explode)
RESHAPING_EXAMPLES: list[Example] = [
    {
        "title": "Pivot Rows to Columns",
        "desc": "Transform status values into columns",
        "query": """from orders
pivot sum(amount) by status values ('pending', 'shipped', 'delivered')
group by customer_id"""
    },
    {
        "title": "Unpivot Columns to Rows",
        "desc": "Turn quarterly columns into rows",
        "query": "from quarterly_metrics\nunpivot q1, q2, q3, q4 into quarter, value"
    },
    {
        "title": "Explode Array",
        "desc": "Expand array column into rows",
        "query": """from posts
explode tags as tag
select post_id, title, tag"""
    },
    {
        "title": "Explode and Aggregate",
        "desc": "Count items per tag",
        "query": """from posts
explode tags as tag
group by tag (
    # as post_count
)
order by -post_count"""
    },
]

# Column operator examples (except, rename, replace)
COLUMN_OPERATOR_EXAMPLES: list[Example] = [
    {
        "title": "Exclude Columns",
        "desc": "Remove sensitive columns",
        "query": "from users\nexcept password_hash, internal_notes"
    },
    {
        "title": "Rename Columns",
        "desc": "Rename for clarity",
        "query": "from users\nrename id as user_id, name as full_name"
    },
    {
        "title": "Replace Values",
        "desc": "Transform column values",
        "query": "from users\nreplace name with upper(name), email with lower(email)"
    },
    {
        "title": "Combined Column Ops",
        "desc": "Exclude, rename, and replace together",
        "query": """from customers
except internal_id
rename name as customer_name
replace email with lower(email)"""
    },
]

# Cohort analysis examples
COHORT_EXAMPLES: list[Example] = [
    {
        "title": "User Retention by Cohort",
        "desc": "Monthly active users by signup cohort",
        "query": """from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)"""
    },
    {
        "title": "Revenue Cohort Analysis",
        "desc": "Revenue by first purchase cohort",
        "query": """from orders
group by month(order_date) (sum(total) as revenue)
cohort by month(customers.first_order_date)"""
    },
    {
        "title": "Cohort Retention with Percentage",
        "desc": "Retention rate by cohort (requires helper functions)",
        "query": """from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)"""
    },
    {
        "title": "Cumulative LTV by Cohort",
        "desc": "Lifetime value over time using running_sum",
        "query": """from orders
group by month(order_date) (sum(total) as revenue)
cohort by month(customers.first_order_date)"""
    },
    {
        "title": "Weekly Activity by Cohort",
        "desc": "Weekly active users by signup cohort",
        "query": """from events
group by week(event_date) (count(distinct user_id) as active)
cohort by week(users.signup_date)"""
    },
    {
        "title": "Segmented Cohorts by Channel",
        "desc": "Cohort analysis segmented by acquisition channel",
        "query": """from events
group by month(event_date) (count(distinct user_id) as active)
cohort by users.channel, month(users.signup_date)"""
    },
    {
        "title": "Period-over-Period Change",
        "desc": "Month-over-month retention change",
        "query": """from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)"""
    },
]

# Count inference examples
COUNT_INFERENCE_EXAMPLES: list[Example] = [
    {
        "title": "Count Rows",
        "desc": "Basic COUNT(*)",
        "query": """from orders
group by status (
    # as order_count
)"""
    },
    {
        "title": "Count Distinct Users",
        "desc": "Infer primary key from table name",
        "query": """from orders
group by status (
    # as total_orders,
    # users as unique_customers
)"""
    },
    {
        "title": "Multiple Entity Counts",
        "desc": "Count different entities",
        "query": """from order_items
group by category (
    # as line_items,
    # orders as unique_orders,
    # products as unique_products
)"""
    },
    {
        "title": "Explicit vs Inferred",
        "desc": "Compare explicit and inferred counts",
        "query": """from orders
group by region (
    # as total_rows,
    # users as unique_users,
    #(distinct product_id) as unique_products_explicit
)"""
    },
]


# SQL examples for reverse compilation demos
SQL_EXAMPLES: list[dict] = [
    {
        "title": "BigQuery CTE with Joins",
        "desc": "Complex query with CTEs and aggregations",
        "dialect": "bigquery",
        "query": """WITH active_users AS (
  SELECT user_id, country, signup_date
  FROM users
  WHERE status = 'active' AND signup_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
),
user_orders AS (
  SELECT au.user_id, au.country,
    COUNT(o.order_id) AS order_count,
    SUM(o.amount) AS total_spent
  FROM active_users au
  LEFT JOIN orders o ON au.user_id = o.user_id
  GROUP BY au.user_id, au.country
)
SELECT country,
  COUNT(*) AS user_count,
  AVG(order_count) AS avg_orders,
  SUM(total_spent) AS total_revenue
FROM user_orders
GROUP BY country
ORDER BY total_revenue DESC
LIMIT 10"""
    },
    {
        "title": "Redshift Window Functions",
        "desc": "Running totals with window functions",
        "dialect": "redshift",
        "query": """SELECT product_id, category, sale_date, amount,
  SUM(amount) OVER (
    PARTITION BY category 
    ORDER BY sale_date 
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS running_total
FROM sales
WHERE sale_date >= '2024-01-01'
ORDER BY category, sale_date"""
    },
    {
        "title": "PostgreSQL Complex Join",
        "desc": "Multiple joins with HAVING clause",
        "dialect": "postgres",
        "query": """SELECT u.user_id, u.email,
  COUNT(DISTINCT o.order_id) AS order_count,
  SUM(o.amount) AS total_spent,
  AVG(o.amount) AS avg_order_value
FROM users u
INNER JOIN orders o ON u.user_id = o.user_id
LEFT JOIN order_items oi ON o.order_id = oi.order_id
WHERE u.created_at >= '2024-01-01' AND o.status = 'completed'
GROUP BY u.user_id, u.email
HAVING COUNT(DISTINCT o.order_id) > 5
ORDER BY total_spent DESC
LIMIT 20"""
    },
    {
        "title": "Simple SELECT with WHERE",
        "desc": "Basic filtering example",
        "dialect": "",
        "query": """SELECT user_id, email, status
FROM users
WHERE status = 'active' AND created_at >= '2024-01-01'
ORDER BY created_at DESC
LIMIT 100"""
    },
]


def get_all_examples() -> dict[str, list[Example]]:
    """Get all examples organized by category."""
    return {
        "asql": ASQL_EXAMPLES,
        "pipeline": PIPELINE_EXAMPLES,
        "sampling": SAMPLING_EXAMPLES,
        "reshaping": RESHAPING_EXAMPLES,
        "column_operators": COLUMN_OPERATOR_EXAMPLES,
        "count_inference": COUNT_INFERENCE_EXAMPLES,
        "cohort": COHORT_EXAMPLES,
    }


def get_all_examples_flat() -> list[tuple[str, str, str]]:
    """Get all examples as flat list of (category, title, query) tuples for testing."""
    result = []
    for category, examples in get_all_examples().items():
        for ex in examples:
            result.append((category, ex["title"], ex["query"]))
    return result
