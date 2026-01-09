"""ASQL Playground examples.

These examples are used by both the playground frontend and tests.
Each example includes tutorial-style comments explaining the feature being showcased.

Style Guide: Examples follow docs/style_guide.md unless explicitly demonstrating alternatives.
"""

from typing import TypedDict


class Example(TypedDict):
    title: str
    desc: str
    query: str


# =============================================================================
# BASIC ASQL EXAMPLES
# =============================================================================
# These examples introduce core ASQL syntax and concepts.

ASQL_EXAMPLES: list[Example] = [
    {
        "title": "Simple FROM",
        "desc": "Basic table selection - every ASQL query starts with FROM",
        "query": """-- ASQL queries start with FROM (not SELECT)
-- This selects all columns from the users table
from users"""
    },
    {
        "title": "WHERE Filter",
        "desc": "Filter rows with conditions using WHERE",
        "query": """-- Use WHERE to filter rows
-- ASQL uses = for equality (preferred over ==)
from users
  where status = "active"

-- You can also use == (accepted but not preferred)
from users
  where status == "active\""""
    },
    {
        "title": "GROUP BY with Count",
        "desc": "Aggregate with COUNT using # shorthand",
        "query": """-- GROUP BY with aggregates in parentheses
-- # is shorthand for COUNT(*) - preferred style
from users
  group by country (
    # as total_users  -- COUNT(*) aliased as total_users
  )"""
    },
    {
        "title": "Multiple Aggregations",
        "desc": "SUM, COUNT, AVG together in one GROUP BY",
        "query": """-- Multiple aggregates separated by commas
-- Each aggregate can use function form or natural language
from sales
  group by region (
    sum_amount,           -- Underscore shorthand: sum(amount) as sum_amount
    # as orders,          -- Count of rows
    avg_amount            -- Average amount
  )"""
    },
    {
        "title": "ORDER BY Descending",
        "desc": "Sort results using - prefix for descending",
        "query": """-- Use - prefix for descending order (preferred style)
-- This is cleaner than writing DESC
from users
  group by country (
    # as total_users
  )
  order by -total_users  -- Descending: most users first"""
    },
    {
        "title": "LIMIT Results",
        "desc": "Limit the number of rows returned",
        "query": """-- LIMIT restricts the result set size
from users
  limit 10"""
    },
    {
        "title": "Complete Pipeline",
        "desc": "Full query combining filter, group, sort, limit",
        "query": """-- A complete analytics pipeline:
-- 1. Start with a table
-- 2. Filter to relevant rows
-- 3. Group and aggregate
-- 4. Sort by results
-- 5. Take top N
from sales
  where status = "completed"
    and amount > 100
  group by region (
    sum_amount,      -- Total revenue per region
    # as orders      -- Number of orders
  )
  order by -sum_amount
  limit 10"""
    },
    {
        "title": "Multiple Conditions",
        "desc": "Combine conditions with AND/OR",
        "query": """-- Multiple conditions with AND
-- Indented continuation makes complex conditions readable
from users
  where status = "active"
    and age >= 18
    and email is not null"""
    },
    {
        "title": "OR Conditions",
        "desc": "Alternative conditions with OR",
        "query": """-- OR for alternative conditions
from users
  where status = "active"
    or status = "pending\""""
    },
    {
        "title": "NULL Checks",
        "desc": "Check for NULL values with IS NULL / IS NOT NULL",
        "query": """-- NULL checking works like standard SQL
from users
  where email is not null

-- Check for NULL values
from users
  where deleted_at is null"""
    },
    {
        "title": "Comparison Operators",
        "desc": "All comparison operators: =, !=, <, >, <=, >=",
        "query": """-- Standard comparison operators
from users
  where age >= 18
    and age <= 65
    and status != "banned\""""
    },
    {
        "title": "String Matching",
        "desc": "Use contains, starts with, ends with instead of LIKE",
        "query": """-- Natural language string matching (preferred over LIKE)
from users
  where email contains "@gmail.com"

-- Other string operators
from users
  where name starts with "John"

from users
  where domain ends with ".com\""""
    },
    {
        "title": "Date Literals",
        "desc": "Use @ prefix for date literals",
        "query": """-- @ prefix for date literals (clearer than strings)
from orders
  where created_at >= @2024-01-01

-- Date range with BETWEEN
from orders
  where order_date between @2024-01-01 and @2024-12-31"""
    },
    {
        "title": "Relative Dates",
        "desc": "Natural date expressions like '7 days ago'",
        "query": """-- Natural language relative dates
from users
  where last_login >= 7 days ago

-- Future dates with 'from now'
from orders
  where estimated_delivery <= 3 days from now"""
    },
]


# =============================================================================
# PIPELINE EXAMPLES
# =============================================================================
# More complex multi-step query examples demonstrating ASQL's pipeline model.

PIPELINE_EXAMPLES: list[Example] = [
    {
        "title": "Multi-Step Pipeline",
        "desc": "Filter → Group → Sort → Limit pipeline",
        "query": """-- ASQL pipelines read top-to-bottom
-- Each step transforms the data from the previous step
from orders
  where status = "completed"
    and created_at >= @2024-01-01
  group by customer_id (
    sum_total,              -- Total spent per customer
    # as order_count,       -- Number of orders
    avg_total               -- Average order value
  )
  order by -sum_total       -- Highest spenders first
  limit 10                  -- Top 10 customers"""
    },
    {
        "title": "Join with Aggregation",
        "desc": "Join tables and aggregate results",
        "query": """-- Join customers with their orders
-- Use & for INNER JOIN (both sides must match)
from customers
  where signup_date >= @2023-01-01
    and is_active = true
  & orders on customers.id = orders.customer_id
  group by customers.id, customers.country (
    sum orders.total as lifetime_value,
    # as total_orders,
    max orders.created_at as last_order_date
  )
  order by -lifetime_value
  limit 50"""
    },
    {
        "title": "Left Join Pipeline",
        "desc": "Left join to include all records from left table",
        "query": """-- &? for LEFT JOIN (right side may be NULL)
-- The ? marks the optional/nullable side
from leads
  &? opportunities on leads.id = opportunities.lead_id
  &? deals on opportunities.id = deals.opportunity_id
  where leads.source = "website"
    and leads.created_at >= @2024-01-01
  group by leads.source (
    sum deals.amount as revenue,
    # as total_leads
  )
  order by -revenue"""
    },
    {
        "title": "Coalesce for NULLs",
        "desc": "Use ?? operator for null handling",
        "query": """-- ?? is the null coalesce operator (preferred over COALESCE())
-- Returns first non-null value
from users
  select
    name ?? "Unknown" as display_name,
    email ?? "no-email@example.com" as email,
    phone ?? "N/A" as phone"""
    },
    {
        "title": "Date Grouping",
        "desc": "Group by time periods using date functions",
        "query": """-- Group by time periods for time-series analysis
-- month() truncates to month start
from transactions
  where status = "completed"
    and transaction_date >= @2024-01-01
  group by month(transaction_date), region (
    sum_amount,             -- Monthly revenue
    # as transaction_count, -- Transaction count
    avg_amount              -- Average transaction
  )
  order by month_transaction_date, -sum_amount"""
    },
    {
        "title": "CTEs with stash as",
        "desc": "Create reusable CTEs inline",
        "query": """from users  -- stash as creates CTEs mid-pipeline
  where signup_date >= @2023-01-01
  group by country (# as user_count)
  stash as country_counts  -- Everything above becomes a CTE
  order by -user_count     -- Pipeline continues with the CTE"""
    },
    {
        "title": "Chained Joins",
        "desc": "Multiple joins in a single pipeline",
        "query": """-- Chain multiple joins together
-- Each join builds on the previous result
from customers
  & orders on customers.id = orders.customer_id
  & order_items on orders.id = order_items.order_id
  & products on order_items.product_id = products.id
  where orders.status = "completed"
    and orders.created_at >= @2024-01-01
  group by customers.id, customers.name (
    sum(order_items.quantity * order_items.price) as total_spent,
    # products as products_purchased
  )
  order by -total_spent
  limit 25"""
    },
]


# =============================================================================
# SAMPLING EXAMPLES
# =============================================================================
# Examples for random sampling data.

SAMPLING_EXAMPLES: list[Example] = [
    {
        "title": "Random Sample",
        "desc": "Get N random rows from a table",
        "query": """-- sample N returns N random rows
-- Useful for data exploration and testing
from orders
  sample 100"""
    },
    {
        "title": "Percentage Sample",
        "desc": "Get approximately N% of rows",
        "query": """-- sample N% returns roughly N percent of rows
-- The exact count varies (it's probabilistic)
from orders
  sample 10%"""
    },
    {
        "title": "Stratified Sample",
        "desc": "N random rows per category",
        "query": """-- sample N per column: stratified sampling
-- Gets N random rows for each distinct value of the column
from products
  sample 100 per category"""
    },
    {
        "title": "Sample with Filter",
        "desc": "Sample from filtered data",
        "query": """-- Combine filtering with sampling
-- Filter first, then sample from the results
from orders
  where status = "completed"
  sample 500"""
    },
]


# =============================================================================
# DATA RESHAPING EXAMPLES
# =============================================================================
# Pivot, unpivot, and explode operations.

RESHAPING_EXAMPLES: list[Example] = [
    {
        "title": "Pivot Rows to Columns",
        "desc": "Transform row values into columns",
        "query": """-- pivot transforms row values into columns
-- Syntax: pivot aggregate by column values (list of values)
from orders
  pivot sum(amount) by status values ("pending", "shipped", "delivered")
  group by customer_id"""
    },
    {
        "title": "Unpivot Columns to Rows",
        "desc": "Transform columns into rows",
        "query": """-- unpivot turns columns into rows
-- Useful for normalizing wide tables
from quarterly_metrics
  unpivot q1, q2, q3, q4 into quarter, value"""
    },
    {
        "title": "Explode Array",
        "desc": "Expand array column into multiple rows",
        "query": """-- explode expands array elements into rows
-- Each array element becomes a separate row
from posts
  explode tags as tag
  select post_id, title, tag"""
    },
    {
        "title": "Explode and Aggregate",
        "desc": "Explode then count occurrences",
        "query": """-- Common pattern: explode then aggregate
-- Find most used tags across all posts
from posts
  explode tags as tag
  group by tag (
    # as post_count
  )
  order by -post_count"""
    },
]


# =============================================================================
# COLUMN OPERATOR EXAMPLES
# =============================================================================
# except, rename, replace column operations.

COLUMN_OPERATOR_EXAMPLES: list[Example] = [
    {
        "title": "Exclude Columns",
        "desc": "Remove columns with EXCEPT",
        "query": """-- except removes columns from SELECT *
-- Useful for hiding sensitive data
from users
  except password_hash, internal_notes"""
    },
    {
        "title": "Rename Columns",
        "desc": "Rename columns inline",
        "query": """-- rename changes column names
-- Can rename multiple columns at once
from users
  rename id as user_id, name as full_name"""
    },
    {
        "title": "Replace Column Values",
        "desc": "Transform column values inline",
        "query": """-- replace transforms column values
-- The column keeps its name but gets new values
from users
  replace name with upper(name), email with lower(email)"""
    },
    {
        "title": "Combined Column Ops",
        "desc": "Use except, rename, and replace together",
        "query": """-- Combine column operators in a pipeline
-- They execute in order: except, rename, replace
from customers
  except internal_id
  rename name as customer_name
  replace email with lower(email)"""
    },
]


# =============================================================================
# COHORT ANALYSIS EXAMPLES
# =============================================================================
# Cohort-based analytics.

COHORT_EXAMPLES: list[Example] = [
    {
        "title": "User Retention Cohort",
        "desc": "Track monthly active users by signup cohort",
        "query": """-- cohort by creates cohort analysis
-- Groups users by when they started, tracks activity over time
from events
  group by month(event_date) (
    #(distinct user_id) as active  -- Distinct active users
  )
  cohort by month(users.signup_date) on user_id"""
    },
    {
        "title": "Revenue Cohort",
        "desc": "Revenue by first purchase cohort",
        "query": """-- Track revenue by when customers first purchased
from orders
  group by month(order_date) (
    sum_total
  )
  cohort by month(customers.first_order_date) on customer_id"""
    },
    {
        "title": "Weekly Cohorts",
        "desc": "Weekly granularity cohort analysis",
        "query": """-- Use week() for weekly cohorts
from events
  group by week(event_date) (
    #(distinct user_id) as active
  )
  cohort by week(users.signup_date) on user_id"""
    },
    {
        "title": "Segmented Cohorts",
        "desc": "Cohort analysis by acquisition channel",
        "query": """-- Add segmentation to cohorts
-- Compare retention across different channels
from events
  group by month(event_date) (
    #(distinct user_id) as active
  )
  cohort by users.channel, month(users.signup_date) on user_id"""
    },
]


# =============================================================================
# COUNT INFERENCE EXAMPLES
# =============================================================================
# Examples showing count shorthand and inference.

COUNT_INFERENCE_EXAMPLES: list[Example] = [
    {
        "title": "Count Rows",
        "desc": "Basic COUNT(*) with # shorthand",
        "query": """-- # by itself means COUNT(*) - counts all rows
from orders
  group by status (
    # as order_count  -- COUNT(*)
  )"""
    },
    {
        "title": "Count Distinct",
        "desc": "Count distinct values with # table_name",
        "query": """-- # followed by table name = COUNT(DISTINCT primary_key)
-- ASQL infers the primary key from table name
from orders
  group by status (
    # as total_orders,      -- COUNT(*) - all rows
    # users as unique_customers  -- COUNT(DISTINCT user_id)
  )"""
    },
    {
        "title": "Multiple Entity Counts",
        "desc": "Count different entities in one query",
        "query": """-- Count multiple distinct entities
from order_items
  group by category (
    # as line_items,           -- Total line items
    # orders as unique_orders, -- Distinct orders
    # products as unique_products  -- Distinct products
  )"""
    },
    {
        "title": "Explicit Distinct Count",
        "desc": "Explicit COUNT(DISTINCT column) syntax",
        "query": """-- For explicit control, use #(distinct column)
from orders
  group by region (
    # as total_rows,
    # users as unique_users,
    #(distinct product_id) as unique_products_explicit
  )"""
    },
]


# =============================================================================
# SYNTAX STYLES EXAMPLES
# =============================================================================
# Examples showcasing different syntax styles and shorthand options.
# These demonstrate that ASQL accepts multiple equivalent syntaxes.

SYNTAX_STYLES_EXAMPLES: list[Example] = [
    {
        "title": "Aggregate Shorthand Styles",
        "desc": "Three ways to write aggregates: underscore, space, parens",
        "query": """-- ASQL supports three equivalent aggregate syntaxes:
-- 1. Underscore shorthand: sum_amount (declarative, matches output column)
-- 2. Space shorthand: sum amount (natural language feel)
-- 3. Parens form: sum(amount) (explicit, required for complex expressions)
-- Each example below shows a different style:

-- Style 1: Underscore shorthand - what you write = output column name
from sales
  group by region (sum_amount, avg_price)
  order by -sum_amount;

-- Style 2: Space shorthand - natural language style
from sales
  group by region (sum amount, avg price);

-- Style 3: Parens form - required for complex expressions
from sales
  group by region (
    sum(amount * quantity) as revenue,
    avg(price / 100) as avg_cents
  )"""
    },
    {
        "title": "When to Use Each Style",
        "desc": "Guidelines for underscore vs space vs parens",
        "query": """-- UNDERSCORE: when not aliasing, want declarative continuity
-- What you write (sum_amount) = what the output column is named
from sales
  group by region (sum_amount)
  order by -sum_amount;

-- SPACE or PARENS: when using 'as' alias
from sales
  group by region (
    sum amount as revenue,
    avg(price) as avg_price
  );

-- PARENS: required for multiple arguments or complex expressions
from sales
  select
    max(price, cost) as highest,
    sum(amount * quantity) as total"""
    },
    {
        "title": "Count Shorthand Styles",
        "desc": "Different ways to write COUNT expressions",
        "query": """-- # by itself = COUNT(*) row count
from orders
  group by status (# as total);

-- # with table name = COUNT(DISTINCT primary_key)
from orders
  group by status (# users as customers);

-- Explicit parens form for full control
from orders
  group by status (#(distinct product_id) as unique_products)"""
    },
    {
        "title": "Equality Operators",
        "desc": "= (preferred) vs == (also accepted)",
        "query": """-- Single = is the preferred style (SQL standard)
from users
  where status = "active"

-- Double == also works (familiar to programmers)
from users
  where status == "active"

-- Both produce the same SQL output"""
    },
    {
        "title": "Null Coalesce Styles",
        "desc": "?? operator (preferred) vs coalesce() function",
        "query": """-- ?? operator - preferred style, more concise
from users
  select name ?? "Unknown" as display_name

-- Chains naturally for multiple fallbacks
from products
  select price ?? sale_price ?? 0 as final_price

-- coalesce() function also works
from users
  select coalesce(name, "Unknown") as display_name"""
    },
    {
        "title": "Descending Order Styles",
        "desc": "- prefix (preferred) vs DESC suffix",
        "query": """-- Minus prefix - preferred style, cleaner
from users
  group by country (# as total)
  order by -total

-- DESC suffix also works (SQL style)
from users
  group by country (# as total)
  order by total DESC

-- Mix in multi-column sorts
from users
  order by -created_at, name  -- Newest first, then alphabetical"""
    },
    {
        "title": "Conditional Styles",
        "desc": "Ternary ? : vs when expressions",
        "query": """-- Ternary for simple binary conditions (preferred)
-- Syntax: condition ? true_value : false_value
from orders
  select amount > 1000 ? "high" : "low" as tier;

-- when for multi-branch conditions (comma-separated branches)
-- More readable than SQL CASE WHEN
from users
  select
    when status
      is "active" then "Active User",
      is "pending" then "Pending",
      otherwise "Unknown"
    as status_label"""
    },
    {
        "title": "Join Styles",
        "desc": "Symbolic operators (preferred) vs SQL JOIN keywords",
        "query": """-- Symbolic operators - preferred, more concise
-- & = INNER JOIN, &? = LEFT JOIN, ?& = RIGHT JOIN
from orders
  & customers on orders.customer_id = customers.id

-- LEFT JOIN: &? (the ? marks the nullable side)
from orders
  &? customers on orders.customer_id = customers.id

-- SQL JOIN syntax also works
from orders
  LEFT JOIN customers on orders.customer_id = customers.id"""
    },
    {
        "title": "Pipeline Styles",
        "desc": "Indentation (preferred) vs pipe operator",
        "query": """-- Indentation-based pipeline - preferred, cleaner
from users
  where status = "active"
  group by country (# as total)
  order by -total

-- Explicit pipe operator also works
from users
| where status = "active"
| group by country (# as total)
| order by -total"""
    },
    {
        "title": "CTE Styles",
        "desc": "stash as (preferred) vs WITH ... AS",
        "query": """from users  -- ASQL style: stash as creates inline CTEs
  where status = "active"
  group by country (# as total)
  stash as by_country     -- Everything above becomes CTE "by_country"
  order by -total;        -- Continue pipeline with the CTE

-- SQL style WITH ... AS also works
WITH active_users AS (
  SELECT * FROM users WHERE status = "active"
)
SELECT country, COUNT(*) as total
FROM active_users
GROUP BY country"""
    },
]


# =============================================================================
# SQL EXAMPLES (for reverse compilation demos)
# =============================================================================

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
        "syntax_styles": SYNTAX_STYLES_EXAMPLES,
    }


def get_all_examples_flat() -> list[tuple[str, str, str]]:
    """Get all examples as flat list of (category, title, query) tuples for testing."""
    result = []
    for category, examples in get_all_examples().items():
        for ex in examples:
            result.append((category, ex["title"], ex["query"]))
    return result
