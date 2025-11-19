"""Real-world SQL examples from Fivetran dbt models, converted to ASQL.

These examples showcase how ASQL's pipeline syntax simplifies complex queries
from production dbt models. Original SQL from:
- https://github.com/fivetran/dbt_shopify
- https://github.com/fivetran/dbt_stripe  
- https://github.com/fivetran/dbt_zendesk

Note: For more examples, see examples/pairs/ directory which contains
20+ SQL/ASQL query pairs organized by pattern type.
"""

from asql import compile


def example_1_shopify_line_items() -> None:
    """Example 1: Shopify Line Items with Multiple Joins
    
    Original: Complex query joining orders, products, transactions, refunds, customers
    ASQL: Clean pipeline showing each transformation step
    """
    print("=" * 80)
    print("Example 1: Shopify Line Items (from dbt_shopify)")
    print("=" * 80)
    
    print("\n--- Original SQL (simplified from dbt model) ---")
    original_sql = """
WITH line_items AS (
    SELECT * FROM stg_shopify_gql__order_line
),
orders AS (
    SELECT * FROM stg_shopify_gql__order
),
transactions AS (
    SELECT order_id, kind, 
           STRING_AGG(CAST(transaction_id AS STRING), ', ') AS transaction_id,
           STRING_AGG(gateway, ', ') AS gateway
    FROM stg_shopify_gql__transaction
    WHERE kind = 'capture' AND status = 'success'
    GROUP BY order_id, kind
),
refund_transactions AS (
    SELECT order_id, SUM(amount_shop) AS total_order_refund_amount
    FROM stg_shopify_gql__transaction
    WHERE kind = 'refund'
    GROUP BY order_id
)
SELECT 
    li.order_id,
    li.order_line_id,
    o.created_timestamp AS created_at,
    o.currency,
    li.quantity,
    li.price_shop_amount AS unit_amount,
    (li.quantity * li.price_shop_amount) AS total_amount,
    t.transaction_id AS payment_id,
    t.gateway AS payment_method,
    rt.total_order_refund_amount AS refund_amount
FROM line_items li
LEFT JOIN orders o ON li.order_id = o.order_id
LEFT JOIN transactions t ON o.order_id = t.order_id
LEFT JOIN refund_transactions rt ON o.order_id = rt.order_id
"""
    print(original_sql)
    
    print("\n--- ASQL Version ---")
    # Note: This is a simplified version - ASQL doesn't yet support all features
    # but shows how the pipeline approach makes it clearer
    asql = """
from stg_shopify_gql__order_line
join stg_shopify_gql__order on order_line.order_id == order.order_id
join (
    from stg_shopify_gql__transaction
    where kind == "capture" and status == "success"
    group by order_id, kind ( 
        string_agg(transaction_id) as transaction_id,
        string_agg(gateway) as gateway
    )
) as transactions on order.order_id == transactions.order_id
join (
    from stg_shopify_gql__transaction
    where kind == "refund"
    group by order_id ( sum(amount_shop) as total_order_refund_amount )
) as refund_transactions on order.order_id == refund_transactions.order_id
select 
    order_line.order_id,
    order_line.order_line_id,
    order.created_timestamp as created_at,
    order.currency,
    order_line.quantity,
    order_line.price_shop_amount as unit_amount,
    (order_line.quantity * order_line.price_shop_amount) as total_amount,
    transactions.transaction_id as payment_id,
    transactions.gateway as payment_method,
    refund_transactions.total_order_refund_amount as refund_amount
"""
    print(asql.strip())
    print("\nNote: ASQL's pipeline syntax makes each transformation step clear!")


def example_2_stripe_customer_overview() -> None:
    """Example 2: Stripe Customer Overview with Complex Aggregations
    
    Original: Multiple CASE statements aggregating transaction types
    ASQL: Cleaner aggregation syntax
    """
    print("\n" + "=" * 80)
    print("Example 2: Stripe Customer Overview (from dbt_stripe)")
    print("=" * 80)
    
    print("\n--- Original SQL (simplified) ---")
    original_sql = """
WITH transactions_grouped AS (
    SELECT
        customer_id,
        SUM(CASE WHEN balance_transaction_type IN ('charge', 'payment') 
            THEN balance_transaction_amount ELSE 0 END) AS total_sales,
        SUM(CASE WHEN balance_transaction_type IN ('payment_refund', 'refund') 
            THEN balance_transaction_amount ELSE 0 END) AS total_refunds,
        SUM(balance_transaction_amount) AS total_gross_transaction_amount,
        SUM(balance_transaction_fee) AS total_fees,
        COUNT(CASE WHEN balance_transaction_type IN ('charge', 'payment') 
            THEN 1 END) AS total_sales_count,
        MIN(CASE WHEN balance_transaction_type IN ('charge', 'payment') 
            THEN balance_transaction_created_at END) AS first_sale_date,
        MAX(CASE WHEN balance_transaction_type IN ('charge', 'payment') 
            THEN balance_transaction_created_at END) AS most_recent_sale_date
    FROM stripe__balance_transactions
    WHERE balance_transaction_type IN ('payment', 'charge', 'payment_refund', 'refund')
    GROUP BY customer_id
)
SELECT 
    c.customer_id,
    c.description AS customer_description,
    c.created_at AS customer_created_at,
    COALESCE(tg.total_sales, 0) AS total_sales,
    COALESCE(tg.total_refunds, 0) AS total_refunds,
    COALESCE(tg.total_gross_transaction_amount, 0) AS total_gross_transaction_amount,
    COALESCE(tg.total_fees, 0) AS total_fees,
    tg.first_sale_date,
    tg.most_recent_sale_date
FROM stg_stripe__customer c
LEFT JOIN transactions_grouped tg ON c.customer_id = tg.customer_id
"""
    print(original_sql)
    
    print("\n--- ASQL Version ---")
    asql = """
from stripe__balance_transactions
where balance_transaction_type in ("payment", "charge", "payment_refund", "refund")
group by customer_id (
    sum(case balance_transaction_type == "charge" or balance_transaction_type == "payment" 
        then balance_transaction_amount else 0 end) as total_sales,
    sum(case balance_transaction_type == "payment_refund" or balance_transaction_type == "refund" 
        then balance_transaction_amount else 0 end) as total_refunds,
    sum(balance_transaction_amount) as total_gross_transaction_amount,
    sum(balance_transaction_fee) as total_fees,
    count(case balance_transaction_type == "charge" or balance_transaction_type == "payment" 
        then 1 end) as total_sales_count,
    min(case balance_transaction_type == "charge" or balance_transaction_type == "payment" 
        then balance_transaction_created_at end) as first_sale_date,
    max(case balance_transaction_type == "charge" or balance_transaction_type == "payment" 
        then balance_transaction_created_at end) as most_recent_sale_date
)
join stg_stripe__customer on transactions.customer_id == customer.customer_id
select 
    customer.customer_id,
    customer.description as customer_description,
    customer.created_at as customer_created_at,
    coalesce(total_sales, 0) as total_sales,
    coalesce(total_refunds, 0) as total_refunds,
    coalesce(total_gross_transaction_amount, 0) as total_gross_transaction_amount,
    coalesce(total_fees, 0) as total_fees,
    first_sale_date,
    most_recent_sale_date
"""
    print(asql.strip())
    print("\nNote: ASQL's pipeline makes the aggregation logic clearer!")


def example_3_zendesk_ticket_enriched() -> None:
    """Example 3: Zendesk Ticket Enrichment with Multiple User Joins
    
    Original: Complex joins to requester, submitter, assignee users
    ASQL: Clear pipeline showing each join step
    """
    print("\n" + "=" * 80)
    print("Example 3: Zendesk Ticket Enriched (from dbt_zendesk)")
    print("=" * 80)
    
    print("\n--- Original SQL (simplified) ---")
    original_sql = """
WITH ticket AS (
    SELECT * FROM int_zendesk__ticket_aggregates
),
users AS (
    SELECT * FROM int_zendesk__user_aggregates
),
requester_updates AS (
    SELECT * FROM int_zendesk__requester_updates
),
assignee_updates AS (
    SELECT * FROM int_zendesk__assignee_updates
)
SELECT 
    ticket.*,
    requester.email AS requester_email,
    requester.name AS requester_name,
    requester.is_active AS is_requester_active,
    COALESCE(requester_updates.total_updates, 0) AS requester_ticket_update_count,
    submitter.email AS submitter_email,
    submitter.name AS submitter_name,
    submitter.is_active AS is_submitter_active,
    assignee.email AS assignee_email,
    assignee.name AS assignee_name,
    assignee.is_active AS is_assignee_active,
    COALESCE(assignee_updates.total_updates, 0) AS assignee_ticket_update_count
FROM ticket
JOIN users AS requester ON requester.user_id = ticket.requester_id
JOIN users AS submitter ON submitter.user_id = ticket.submitter_id
LEFT JOIN users AS assignee ON assignee.user_id = ticket.assignee_id
LEFT JOIN requester_updates ON requester_updates.ticket_id = ticket.ticket_id 
    AND requester_updates.requester_id = ticket.requester_id
LEFT JOIN assignee_updates ON assignee_updates.ticket_id = ticket.ticket_id 
    AND assignee_updates.assignee_id = ticket.assignee_id
"""
    print(original_sql)
    
    print("\n--- ASQL Version ---")
    asql = """
from int_zendesk__ticket_aggregates
join int_zendesk__user_aggregates as requester 
    on ticket.requester_id == requester.user_id
join int_zendesk__user_aggregates as submitter 
    on ticket.submitter_id == submitter.user_id
left join int_zendesk__user_aggregates as assignee 
    on ticket.assignee_id == assignee.user_id
left join int_zendesk__requester_updates 
    on requester_updates.ticket_id == ticket.ticket_id 
    and requester_updates.requester_id == ticket.requester_id
left join int_zendesk__assignee_updates 
    on assignee_updates.ticket_id == ticket.ticket_id 
    and assignee_updates.assignee_id == ticket.assignee_id
select 
    ticket.*,
    requester.email as requester_email,
    requester.name as requester_name,
    requester.is_active as is_requester_active,
    coalesce(requester_updates.total_updates, 0) as requester_ticket_update_count,
    submitter.email as submitter_email,
    submitter.name as submitter_name,
    submitter.is_active as is_submitter_active,
    assignee.email as assignee_email,
    assignee.name as assignee_name,
    assignee.is_active as is_assignee_active,
    coalesce(assignee_updates.total_updates, 0) as assignee_ticket_update_count
"""
    print(asql.strip())
    print("\nNote: ASQL's sequential joins are easier to read and understand!")


def example_4_stripe_balance_transactions() -> None:
    """Example 4: Stripe Balance Transactions with Complex Dispute Logic
    
    Original: Multiple CTEs for disputes, charges, refunds
    ASQL: Clear step-by-step transformations
    """
    print("\n" + "=" * 80)
    print("Example 4: Stripe Balance Transactions (from dbt_stripe)")
    print("=" * 80)
    
    print("\n--- Original SQL (simplified) ---")
    original_sql = """
WITH dispute_summary AS (
    SELECT charge_id, 
           STRING_AGG(dispute_id, ',') AS dispute_ids,
           STRING_AGG(DISTINCT dispute_reason, ',') AS dispute_reasons,
           COUNT(dispute_id) AS dispute_count
    FROM stg_stripe__dispute
    GROUP BY charge_id
),
order_disputes AS (
    SELECT charge_id, dispute_id, dispute_status, dispute_amount,
           ROW_NUMBER() OVER (PARTITION BY charge_id, dispute_status 
                              ORDER BY dispute_created_at DESC) = 1 AS is_latest_status_dispute
    FROM stg_stripe__dispute
)
SELECT
    bt.balance_transaction_id,
    bt.created_at AS balance_transaction_created_at,
    bt.amount AS balance_transaction_amount,
    bt.fee AS balance_transaction_fee,
    bt.net AS balance_transaction_net,
    bt.type AS balance_transaction_type,
    COALESCE(charge.amount, refund.amount, latest_disputes.latest_dispute_amount) AS customer_facing_amount,
    charge.charge_id,
    dispute_summary.dispute_ids,
    dispute_summary.dispute_count
FROM stg_stripe__balance_transaction bt
LEFT JOIN stg_stripe__charge charge 
    ON charge.balance_transaction_id = bt.balance_transaction_id
LEFT JOIN stg_stripe__refund refund 
    ON refund.balance_transaction_id = bt.balance_transaction_id
LEFT JOIN dispute_summary 
    ON charge.charge_id = dispute_summary.charge_id
"""
    print(original_sql)
    
    print("\n--- ASQL Version ---")
    asql = """
from stg_stripe__balance_transaction
left join stg_stripe__charge 
    on charge.balance_transaction_id == balance_transaction.balance_transaction_id
left join stg_stripe__refund 
    on refund.balance_transaction_id == balance_transaction.balance_transaction_id
left join (
    from stg_stripe__dispute
    group by charge_id (
        string_agg(dispute_id) as dispute_ids,
        string_agg(distinct dispute_reason) as dispute_reasons,
        count(dispute_id) as dispute_count
    )
) as dispute_summary 
    on charge.charge_id == dispute_summary.charge_id
select
    balance_transaction.balance_transaction_id,
    balance_transaction.created_at as balance_transaction_created_at,
    balance_transaction.amount as balance_transaction_amount,
    balance_transaction.fee as balance_transaction_fee,
    balance_transaction.net as balance_transaction_net,
    balance_transaction.type as balance_transaction_type,
    coalesce(charge.amount, refund.amount) as customer_facing_amount,
    charge.charge_id,
    dispute_summary.dispute_ids,
    dispute_summary.dispute_count
"""
    print(asql.strip())
    print("\nNote: ASQL's pipeline shows each transformation clearly!")


def example_5_shopify_customer_cohorts() -> None:
    """Example 5: Shopify Customer Cohorts with Window Functions
    
    Original: Complex window functions for cohort analysis
    ASQL: Clearer aggregation and windowing syntax
    """
    print("\n" + "=" * 80)
    print("Example 5: Shopify Customer Cohorts (from dbt_shopify)")
    print("=" * 80)
    
    print("\n--- Original SQL (simplified) ---")
    original_sql = """
WITH customer_calendar AS (
    SELECT 
        calendar.date_day AS date_month,
        customers.customer_id,
        customers.first_order_timestamp,
        DATE_TRUNC('month', first_order_timestamp) AS cohort_month
    FROM calendar
    INNER JOIN customers 
        ON DATE_TRUNC('month', first_order_timestamp) <= calendar.date_day
),
orders_joined AS (
    SELECT 
        customer_calendar.date_month,
        customer_calendar.customer_id,
        customer_calendar.cohort_month,
        COALESCE(COUNT(DISTINCT orders.order_id), 0) AS order_count_in_month,
        COALESCE(SUM(orders.order_adjusted_total), 0) AS total_price_in_month
    FROM customer_calendar
    LEFT JOIN orders
        ON customer_calendar.customer_id = orders.customer_id
        AND customer_calendar.date_month = DATE_TRUNC('month', orders.created_timestamp)
    GROUP BY customer_calendar.date_month, customer_calendar.customer_id, customer_calendar.cohort_month
),
windows AS (
    SELECT *,
        SUM(total_price_in_month) OVER (
            PARTITION BY customer_id 
            ORDER BY date_month 
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS total_price_lifetime,
        SUM(order_count_in_month) OVER (
            PARTITION BY customer_id 
            ORDER BY date_month 
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS order_count_lifetime,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id 
            ORDER BY date_month ASC
        ) AS cohort_month_number
    FROM orders_joined
)
SELECT * FROM windows
"""
    print(original_sql)
    
    print("\n--- ASQL Version ---")
    asql = """
from calendar
join customers 
    on date_trunc("month", customers.first_order_timestamp) <= calendar.date_day
join (
    from orders
    group by customer_id, date_trunc("month", created_timestamp) (
        count(distinct order_id) as order_count_in_month,
        sum(order_adjusted_total) as total_price_in_month
    )
) as orders_joined 
    on customer_calendar.customer_id == orders_joined.customer_id
    and customer_calendar.date_month == orders_joined.date_month
select
    customer_calendar.date_month,
    customer_calendar.customer_id,
    customer_calendar.cohort_month,
    orders_joined.order_count_in_month,
    orders_joined.total_price_in_month,
    sum(total_price_in_month) over (
        partition by customer_id 
        order by date_month 
        rows between unbounded preceding and current row
    ) as total_price_lifetime,
    sum(order_count_in_month) over (
        partition by customer_id 
        order by date_month 
        rows between unbounded preceding and current row
    ) as order_count_lifetime,
    row_number() over (
        partition by customer_id 
        order by date_month asc
    ) as cohort_month_number
"""
    print(asql.strip())
    print("\nNote: ASQL's pipeline syntax makes cohort analysis more readable!")


if __name__ == "__main__":
    example_1_shopify_line_items()
    example_2_stripe_customer_overview()
    example_3_zendesk_ticket_enriched()
    example_4_stripe_balance_transactions()
    example_5_shopify_customer_cohorts()
    
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    print("""
These examples show how ASQL's pipeline-based syntax simplifies complex SQL queries
from real-world dbt models. Key benefits:

1. **Clearer Structure**: Each transformation step is explicit
2. **Better Readability**: Pipeline flows top-to-bottom like natural language
3. **Easier Debugging**: Each step becomes a descriptive CTE
4. **Less Verbose**: No need for nested CTEs and complex aliases

Original queries from Fivetran's production dbt packages:
- https://github.com/fivetran/dbt_shopify
- https://github.com/fivetran/dbt_stripe
- https://github.com/fivetran/dbt_zendesk
""")

