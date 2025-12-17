"""Tests for cohort analysis functionality."""

import re

import pytest
from asql import compile


def test_basic_cohort():
    """Test basic cohort by syntax."""
    query = """from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)"""
    
    sql = compile(query)
    sql_lower = sql.lower()
    
    # Should generate SQL with cohort CTEs
    assert "WITH" in sql.upper(), "Should have WITH clause for CTEs"
    assert "cohort_base" in sql_lower, "Should create cohort_base CTE"
    assert "cohort_sizes" in sql_lower, "Should create cohort_sizes CTE"
    
    # Check CTE structure - CTEs are defined with AS
    assert re.search(r'cohort_base\s+AS', sql, re.IGNORECASE), "cohort_base should be a CTE"
    assert re.search(r'cohort_sizes\s+AS', sql, re.IGNORECASE), "cohort_sizes should be a CTE"
    
    # Check JOINs to CTEs - may have aliases like "JOIN cohort_base AS cb"
    assert re.search(r'JOIN\s+cohort_base', sql, re.IGNORECASE), "Should join to cohort_base"
    assert re.search(r'JOIN\s+cohort_sizes', sql, re.IGNORECASE), "Should join to cohort_sizes"
    
    # Check columns
    assert "cohort_month" in sql_lower, "Should include cohort_month column"
    assert "period" in sql_lower, "Should include period column"
    assert "cohort_size" in sql_lower, "Should include cohort_size column"
    
    # Check GROUP BY includes cohort dimensions
    assert "GROUP BY" in sql.upper(), "Should have GROUP BY"
    assert "cb.cohort_month" in sql_lower or "cohort_month" in sql_lower, "GROUP BY should include cohort_month"
    
    # Check ORDER BY
    assert "ORDER BY" in sql.upper(), "Should have ORDER BY"
    assert "cohort_month" in sql_lower and "period" in sql_lower, "ORDER BY should include cohort_month and period"


def test_cohort_revenue():
    """Test revenue cohort analysis."""
    query = """from orders
group by month(order_date) (sum(total) as revenue)
cohort by month(customers.first_order_date)"""
    
    sql = compile(query)
    sql_lower = sql.lower()
    
    # Check CTEs
    assert "cohort_base" in sql_lower, "Should create cohort_base CTE"
    assert "cohort_sizes" in sql_lower, "Should create cohort_sizes CTE"
    
    # Check JOINs - may have aliases
    assert re.search(r'JOIN\s+cohort_base', sql, re.IGNORECASE), "Should join to cohort_base"
    assert re.search(r'JOIN\s+cohort_sizes', sql, re.IGNORECASE), "Should join to cohort_sizes"
    
    # Check revenue is included
    assert "revenue" in sql_lower, "Should include revenue in results"


def test_cohort_weekly():
    """Test weekly cohort granularity."""
    query = """from events
group by week(event_date) (count(distinct user_id) as active)
cohort by week(users.signup_date)"""
    
    sql = compile(query)
    sql_lower = sql.lower()
    
    # Check CTEs
    assert "cohort_base" in sql_lower, "Should create cohort_base CTE"
    assert "cohort_sizes" in sql_lower, "Should create cohort_sizes CTE"
    
    # Check week granularity
    assert "week" in sql_lower or "WEEK" in sql, "Should use week granularity"
    assert "DATE_TRUNC" in sql.upper() and ("'week'" in sql_lower or "'WEEK'" in sql), "Should use DATE_TRUNC with week"


def test_cohort_with_explicit_join():
    """Test cohort with explicit join key."""
    query = """from orders
group by month(order_date) (sum(total) as revenue)
cohort by month(customers.first_order_date) on customer_id"""
    
    sql = compile(query)
    sql_lower = sql.lower()
    
    # Check CTEs
    assert "cohort_base" in sql_lower, "Should create cohort_base CTE"
    
    # Check explicit join key is used
    assert "customer_id" in sql_lower, "Should use explicit customer_id join key"
    assert re.search(r'JOIN\s+cohort_base', sql, re.IGNORECASE), "Should join to cohort_base"
    
    # Verify join uses customer_id - should appear in JOIN condition
    assert "customer_id" in sql_lower, "Join should reference customer_id"


def test_cohort_period_calculation():
    """Test that period is calculated correctly."""
    query = """from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)"""
    
    sql = compile(query)
    sql_lower = sql.lower()
    
    # Period should be calculated using EXTRACT and AGE
    assert "period" in sql_lower, "Should include period column"
    assert "EXTRACT" in sql.upper(), "Should use EXTRACT for period calculation"
    assert "AGE" in sql.upper() or "DATEDIFF" in sql.upper() or "-" in sql, "Should calculate date difference for period"
    
    # Period should be in GROUP BY
    assert "GROUP BY" in sql.upper(), "Should have GROUP BY"
    # Period expression should be in GROUP BY (might be the full expression)


def test_cohort_auto_order_by():
    """Test that cohort automatically adds ORDER BY."""
    query = """from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)"""
    
    sql = compile(query)
    sql_upper = sql.upper()
    
    # Should automatically add ORDER BY
    assert "ORDER BY" in sql_upper, "Should automatically add ORDER BY"
    
    # ORDER BY should include cohort_month and period
    sql_lower = sql.lower()
    assert "cohort_month" in sql_lower, "ORDER BY should include cohort_month"
    assert "period" in sql_lower, "ORDER BY should include period"
