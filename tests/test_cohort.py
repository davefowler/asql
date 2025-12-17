"""Tests for cohort analysis functionality."""

import pytest
from asql import compile


def test_basic_cohort():
    """Test basic cohort by syntax."""
    query = """from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)"""
    
    sql = compile(query)
    
    # Should generate SQL with cohort CTEs
    assert "cohort_base" in sql.lower()
    assert "cohort_sizes" in sql.lower()
    assert "cohort_month" in sql.lower()
    assert "period" in sql.lower()


def test_cohort_revenue():
    """Test revenue cohort analysis."""
    query = """from orders
group by month(order_date) (sum(total) as revenue)
cohort by month(customers.first_order_date)"""
    
    sql = compile(query)
    
    assert "cohort_base" in sql.lower()
    assert "revenue" in sql.lower()


def test_cohort_weekly():
    """Test weekly cohort granularity."""
    query = """from events
group by week(event_date) (count(distinct user_id) as active)
cohort by week(users.signup_date)"""
    
    sql = compile(query)
    
    assert "cohort_base" in sql.lower()
    assert "week" in sql.lower() or "WEEK" in sql


def test_cohort_with_explicit_join():
    """Test cohort with explicit join key."""
    query = """from orders
group by month(order_date) (sum(total) as revenue)
cohort by month(customers.first_order_date) on customer_id"""
    
    sql = compile(query)
    
    assert "cohort_base" in sql.lower()
    assert "customer_id" in sql.lower()
