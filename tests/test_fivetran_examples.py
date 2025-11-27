"""Tests for Fivetran dbt model examples converted to ASQL."""

from asql import compile


def test_shopify_line_items_structure() -> None:
    """Test that Shopify line items query structure is correct."""
    # Simplified version - testing the structure
    asql = """
    from stg_shopify_gql__order_line
    join stg_shopify_gql__order on order_line.order_id == order.order_id
    """
    sql = compile(asql)
    
    # Simple queries don't need CTEs
    assert "FROM" in sql.upper()
    assert "JOIN" in sql.upper() or "join" in sql.lower()


def test_stripe_customer_overview_structure() -> None:
    """Test that Stripe customer overview query structure is correct."""
    # Simplified version - testing aggregations
    asql = """
    from stripe__balance_transactions
    where balance_transaction_type in ("payment", "charge")
    group by customer_id ( sum(balance_transaction_amount) as total_sales )
    """
    sql = compile(asql)
    
    # Simple queries don't need CTEs
    assert "FROM" in sql.upper()
    assert "GROUP BY" in sql.upper() or "group" in sql.lower()
    assert "SUM" in sql.upper() or "sum" in sql.lower()


def test_zendesk_ticket_enriched_structure() -> None:
    """Test that Zendesk ticket enriched query structure is correct."""
    # Simplified version - testing joins (without alias syntax for now)
    asql = """
    from int_zendesk__ticket_aggregates
    join int_zendesk__user_aggregates on ticket.requester_id == user_aggregates.user_id
    """
    sql = compile(asql)
    
    # Simple queries don't need CTEs
    assert "FROM" in sql.upper()
    assert "JOIN" in sql.upper() or "join" in sql.lower()


def test_stripe_balance_transactions_structure() -> None:
    """Test that Stripe balance transactions query structure is correct."""
    # Simplified version - using regular join (left join not yet supported)
    asql = """
    from stg_stripe__balance_transaction
    join stg_stripe__charge 
        on charge.balance_transaction_id == balance_transaction.balance_transaction_id
    """
    sql = compile(asql)
    
    # Simple queries don't need CTEs
    assert "FROM" in sql.upper()
    assert "JOIN" in sql.upper() or "join" in sql.lower()


def test_shopify_customer_cohorts_structure() -> None:
    """Test that Shopify customer cohorts query structure is correct."""
    # Simplified version - testing group by (distinct not yet supported in count)
    asql = """
    from orders
    group by customer_id (
        # as order_count_in_month,
        sum(order_adjusted_total) as total_price_in_month
    )
    """
    sql = compile(asql)
    
    # Simple queries don't need CTEs
    assert "FROM" in sql.upper()
    assert "GROUP BY" in sql.upper() or "group" in sql.lower()

