"""Tests for window function utilities in ASQL."""

import pytest
from asql import compile


class TestQualifyClause:
    """Tests for QUALIFY clause support."""
    
    def test_qualify_simple_condition(self) -> None:
        """Test QUALIFY with simple condition."""
        asql = """
        from orders
            select *, row_number() over (partition by customer_id order by -order_date) as rn
            qualify rn == 1
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        # QUALIFY should be in the output for dialects that support it
        # For others, it will be a subquery
        assert "ROW_NUMBER" in sql_upper
        assert "PARTITION BY" in sql_upper
        assert "ORDER BY" in sql_upper
    
    def test_qualify_with_row_number(self) -> None:
        """Test QUALIFY with ROW_NUMBER for deduplication."""
        asql = """
        from customers
            select *, row_number() over (partition by email order by -created_at) as rn
            qualify rn == 1
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "ROW_NUMBER" in sql_upper
        assert "PARTITION BY" in sql_upper


class TestDistinctOn:
    """Tests for DISTINCT ON support."""
    
    def test_distinct_on_single_column(self) -> None:
        """Test DISTINCT ON with single column."""
        asql = """
        from orders
            distinct on (customer_id)
            sort customer_id, -order_date
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "DISTINCT" in sql_upper
    
    def test_distinct_on_multiple_columns(self) -> None:
        """Test DISTINCT ON with multiple columns."""
        asql = """
        from events
            distinct on (user_id, event_type)
            sort user_id, event_type, -timestamp
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "DISTINCT" in sql_upper


class TestPriorNextFunctions:
    """Tests for prior() and next() simplified LAG/LEAD functions."""
    
    def test_prior_simple(self) -> None:
        """Test prior() function (LAG with default offset 1)."""
        asql = """
        from monthly_sales
            sort month
            select month, revenue, prior(revenue) as prev_month
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "LAG" in sql_upper
    
    def test_prior_with_offset(self) -> None:
        """Test prior() function with custom offset."""
        asql = """
        from monthly_sales
            sort month
            select month, revenue, prior(revenue, 3) as three_months_ago
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "LAG" in sql_upper
        assert "3" in sql
    
    def test_next_simple(self) -> None:
        """Test next() function (LEAD with default offset 1)."""
        asql = """
        from monthly_sales
            sort month
            select month, revenue, next(revenue) as next_month
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "LEAD" in sql_upper
    
    def test_next_with_offset(self) -> None:
        """Test next() function with custom offset."""
        asql = """
        from monthly_sales
            sort month
            select month, revenue, next(revenue, 2) as two_months_ahead
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "LEAD" in sql_upper
        assert "2" in sql


class TestRunningAggregates:
    """Tests for running aggregate functions."""
    
    def test_running_sum(self) -> None:
        """Test running_sum() function."""
        asql = """
        from transactions
            sort date
            select date, amount, running_sum(amount) as cumulative_total
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "SUM" in sql_upper
        # Should have OVER clause with ROWS UNBOUNDED PRECEDING
        assert "OVER" in sql_upper
    
    def test_running_avg(self) -> None:
        """Test running_avg() function."""
        asql = """
        from transactions
            sort date
            select date, amount, running_avg(amount) as avg_to_date
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "AVG" in sql_upper
        assert "OVER" in sql_upper
    
    def test_running_count(self) -> None:
        """Test running_count() function."""
        asql = """
        from transactions
            sort date
            select date, running_count(*) as transaction_number
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "COUNT" in sql_upper
        assert "OVER" in sql_upper


class TestRollingAggregates:
    """Tests for rolling aggregate functions with window size."""
    
    def test_rolling_avg(self) -> None:
        """Test rolling_avg() function with window size."""
        asql = """
        from daily_sales
            sort date
            select date, revenue, rolling_avg(revenue, 7) as seven_day_avg
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "AVG" in sql_upper
        assert "OVER" in sql_upper
    
    def test_rolling_sum(self) -> None:
        """Test rolling_sum() function with window size."""
        asql = """
        from daily_sales
            sort date
            select date, revenue, rolling_sum(revenue, 30) as thirty_day_total
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "SUM" in sql_upper
        assert "OVER" in sql_upper


class TestWindowFunctionsWithOver:
    """Tests for window functions with OVER clause."""
    
    def test_row_number_over(self) -> None:
        """Test row_number() over (partition by ... order by ...)."""
        asql = """
        from orders
            select *, row_number() over (partition by customer_id order by -order_date) as rn
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "ROW_NUMBER" in sql_upper
        assert "OVER" in sql_upper
        assert "PARTITION BY" in sql_upper
        assert "ORDER BY" in sql_upper
    
    def test_rank_over(self) -> None:
        """Test rank() over (partition by ... order by ...)."""
        asql = """
        from employees
            select *, rank() over (partition by department order by -salary) as salary_rank
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "RANK" in sql_upper
        assert "OVER" in sql_upper
    
    def test_sum_over_partition(self) -> None:
        """Test SUM() over partition."""
        asql = """
        from sales
            select *, sum(amount) over (partition by region) as region_total
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "SUM" in sql_upper
        assert "OVER" in sql_upper
        assert "PARTITION BY" in sql_upper


class TestFirstLastFunctions:
    """Tests for first() and last() aggregate functions with ordering."""
    
    def test_first_with_order(self) -> None:
        """Test first() function with ORDER BY."""
        asql = """
        from orders
            select customer_id, first(order_id order by -order_date) as latest_order
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "FIRST_VALUE" in sql_upper
        assert "ORDER BY" in sql_upper
    
    def test_first_with_ascending_order(self) -> None:
        """Test first() function with ascending ORDER BY."""
        asql = """
        from orders
            select customer_id, first(order_id order by order_date) as earliest_order
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "FIRST_VALUE" in sql_upper
    
    def test_last_with_order(self) -> None:
        """Test last() function with ORDER BY (gets last value)."""
        asql = """
        from orders
            select customer_id, last(order_id order by order_date) as latest_order
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "FIRST_VALUE" in sql_upper  # Implemented as FIRST_VALUE with reversed order
        assert "ORDER BY" in sql_upper


class TestArgMaxMinFunctions:
    """Tests for arg_max() and arg_min() ClickHouse-style functions."""
    
    def test_arg_max(self) -> None:
        """Test arg_max() function - get value where sort column is maximum."""
        asql = """
        from orders
            select customer_id, arg_max(order_id, order_date) as latest_order_id
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "FIRST_VALUE" in sql_upper
        assert "ORDER BY" in sql_upper
    
    def test_arg_min(self) -> None:
        """Test arg_min() function - get value where sort column is minimum."""
        asql = """
        from orders
            select customer_id, arg_min(order_id, order_date) as earliest_order_id
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "FIRST_VALUE" in sql_upper
        assert "ORDER BY" in sql_upper


class TestIntegrationScenarios:
    """Integration tests for common window function patterns."""
    
    def test_dedup_most_recent_order_per_customer(self) -> None:
        """Test deduplication pattern: get most recent order per customer."""
        asql = """
        from orders
            select *, row_number() over (partition by customer_id order by -order_date) as rn
            qualify rn == 1
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "ROW_NUMBER" in sql_upper
        assert "PARTITION BY" in sql_upper
    
    def test_running_total_with_order(self) -> None:
        """Test running total with explicit ordering."""
        asql = """
        from daily_revenue
            sort date
            select date, revenue, running_sum(revenue) as cumulative
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "SUM" in sql_upper
        assert "OVER" in sql_upper
    
    def test_prior_next_for_comparison(self) -> None:
        """Test using prior and next for comparison calculations."""
        asql = """
        from monthly_metrics
            sort month
            select 
                month,
                revenue,
                prior(revenue) as prev_month,
                next(revenue) as next_month
        """
        sql = compile(asql)
        sql_upper = sql.upper()
        assert "LAG" in sql_upper
        assert "LEAD" in sql_upper
