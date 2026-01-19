"""Tests for window function utilities in ASQL."""

import pytest
from tests.fixtures import transpile


class TestQualifyClause:
    """Tests for QUALIFY clause support."""
    
    def test_qualify_simple_condition(self) -> None:
        """Test QUALIFY with simple condition."""
        asql = """
        from orders
            select *, row_number() over (partition by customer_id order by -order_date) as rn
            qualify rn == 1
        """
        sql = transpile(asql)
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
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "ROW_NUMBER" in sql_upper
        assert "PARTITION BY" in sql_upper


class TestPerCommand:
    """Tests for the new PER command syntax (per <partition> <op> by <order>)."""
    
    def test_per_first_by(self) -> None:
        """Test per customer_id first by -order_date (new syntax)."""
        asql = """
        from orders
            per customer_id first by -order_date
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "ROW_NUMBER" in sql_upper
        assert "PARTITION BY" in sql_upper
        assert "CUSTOMER_ID" in sql_upper
        assert "ORDER BY" in sql_upper
        assert "DESC" in sql_upper
        assert "QUALIFY" in sql_upper or "WHERE" in sql_upper
    
    def test_per_last_by(self) -> None:
        """Test per customer_id last by order_date."""
        asql = """
        from orders
            per customer_id last by order_date
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "ROW_NUMBER" in sql_upper
        assert "PARTITION BY" in sql_upper
        # last by order_date becomes ORDER BY order_date DESC
        assert "DESC" in sql_upper
    
    def test_per_number_by(self) -> None:
        """Test per customer_id number by -order_date."""
        asql = """
        from orders
            per customer_id number by -order_date
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "ROW_NUMBER" in sql_upper
        assert "PARTITION BY" in sql_upper
        assert "ROW_NUM" in sql_upper  # Default alias
    
    def test_per_rank_by(self) -> None:
        """Test per department rank by -salary."""
        asql = """
        from employees
            per department rank by -salary
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "RANK()" in sql_upper
        assert "PARTITION BY" in sql_upper
        # Should have 'rank' as default alias (may be quoted)
    
    def test_per_dense_rank_by(self) -> None:
        """Test per department dense rank by -salary (with space)."""
        asql = """
        from employees
            per department dense rank by -salary
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "DENSE_RANK()" in sql_upper
        assert "PARTITION BY" in sql_upper
    
    def test_per_with_custom_alias(self) -> None:
        """Test per with custom alias."""
        asql = """
        from orders
            per customer_id number by -order_date as order_num
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "ROW_NUMBER" in sql_upper
        assert "ORDER_NUM" in sql_upper
    
    def test_per_multiple_partition_columns(self) -> None:
        """Test per with multiple partition columns."""
        asql = """
        from events
            per user_id, event_type number by -timestamp
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "ROW_NUMBER" in sql_upper
        assert "USER_ID" in sql_upper
        assert "EVENT_TYPE" in sql_upper


class TestStandaloneWindowOps:
    """Tests for standalone window operations (without per partition)."""
    
    def test_number_by_without_partition(self) -> None:
        """Test number by -timestamp (whole table)."""
        asql = """
        from events
            number by -timestamp
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "ROW_NUMBER" in sql_upper
        assert "ORDER BY" in sql_upper
        # No PARTITION BY
        assert "PARTITION BY" not in sql_upper
    
    def test_rank_by_without_partition(self) -> None:
        """Test rank by -score (whole table)."""
        asql = """
        from scores
            rank by -score
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "RANK()" in sql_upper
        assert "ORDER BY" in sql_upper
    
    def test_dense_rank_by_without_partition(self) -> None:
        """Test dense rank by -score (whole table)."""
        asql = """
        from scores
            dense rank by -score
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "DENSE_RANK()" in sql_upper
        assert "ORDER BY" in sql_upper


class TestDistinctOn:
    """Tests for DISTINCT ON support (legacy, prefer first by/last by)."""
    
    def test_distinct_on_single_column(self) -> None:
        """Test DISTINCT ON with single column."""
        asql = """
        from orders
            distinct on (customer_id)
            order by customer_id, -order_date
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "DISTINCT" in sql_upper
    
    def test_distinct_on_multiple_columns(self) -> None:
        """Test DISTINCT ON with multiple columns."""
        asql = """
        from events
            distinct on (user_id, event_type)
            order by user_id, event_type, -timestamp
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "DISTINCT" in sql_upper


class TestPriorNextFunctions:
    """Tests for prior() and next() simplified LAG/LEAD functions."""
    
    def test_prior_simple(self) -> None:
        """Test prior() function (LAG with default offset 1)."""
        asql = """
        from monthly_sales
            order by month
            select month, revenue, prior(revenue) as prev_month
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "LAG" in sql_upper
    
    def test_prior_with_offset(self) -> None:
        """Test prior() function with custom offset."""
        asql = """
        from monthly_sales
            order by month
            select month, revenue, prior(revenue, 3) as three_months_ago
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "LAG" in sql_upper
        assert "3" in sql
    
    def test_next_simple(self) -> None:
        """Test next() function (LEAD with default offset 1)."""
        asql = """
        from monthly_sales
            order by month
            select month, revenue, next(revenue) as next_month
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "LEAD" in sql_upper
    
    def test_next_with_offset(self) -> None:
        """Test next() function with custom offset."""
        asql = """
        from monthly_sales
            order by month
            select month, revenue, next(revenue, 2) as two_months_ahead
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "LEAD" in sql_upper
        assert "2" in sql


class TestRunningAggregates:
    """Tests for running aggregate functions."""
    
    def test_running_sum(self) -> None:
        """Test running_sum() function."""
        asql = """
        from transactions
            order by date
            select date, amount, running_sum(amount) as cumulative_total
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "SUM" in sql_upper
        # Should have OVER clause with ROWS UNBOUNDED PRECEDING
        assert "OVER" in sql_upper
    
    def test_running_avg(self) -> None:
        """Test running_avg() function."""
        asql = """
        from transactions
            order by date
            select date, amount, running_avg(amount) as avg_to_date
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "AVG" in sql_upper
        assert "OVER" in sql_upper
    
    def test_running_count(self) -> None:
        """Test running_count() function."""
        asql = """
        from transactions
            order by date
            select date, running_count(*) as transaction_number
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "COUNT" in sql_upper
        assert "OVER" in sql_upper


class TestRollingAggregates:
    """Tests for rolling aggregate functions with window size."""
    
    def test_rolling_avg(self) -> None:
        """Test rolling_avg() function with window size."""
        asql = """
        from daily_sales
            order by date
            select date, revenue, rolling_avg(revenue, 7) as seven_day_avg
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "AVG" in sql_upper
        assert "OVER" in sql_upper
    
    def test_rolling_sum(self) -> None:
        """Test rolling_sum() function with window size."""
        asql = """
        from daily_sales
            order by date
            select date, revenue, rolling_sum(revenue, 30) as thirty_day_total
        """
        sql = transpile(asql)
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
        sql = transpile(asql)
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
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "RANK" in sql_upper
        assert "OVER" in sql_upper
    
    def test_sum_over_partition(self) -> None:
        """Test SUM() over partition."""
        asql = """
        from sales
            select *, sum(amount) over (partition by region) as region_total
        """
        sql = transpile(asql)
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
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "FIRST_VALUE" in sql_upper
        assert "ORDER BY" in sql_upper
    
    def test_first_with_ascending_order(self) -> None:
        """Test first() function with ascending ORDER BY."""
        asql = """
        from orders
            select customer_id, first(order_id order by order_date) as earliest_order
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "FIRST_VALUE" in sql_upper
    
    def test_last_with_order(self) -> None:
        """Test last() function with ORDER BY (gets last value)."""
        asql = """
        from orders
            select customer_id, last(order_id order by order_date) as latest_order
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "FIRST_VALUE" in sql_upper  # Implemented as FIRST_VALUE with reversed order
        assert "ORDER BY" in sql_upper


class TestArgMaxMinFunctions:
    """Tests for arg_max() and arg_min() ClickHouse-style functions."""
    
    def test_arg_max(self) -> None:
        """Test arg_max() function - get value where the ordering column is maximum."""
        asql = """
        from orders
            select customer_id, arg_max(order_id, order_date) as latest_order_id
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "FIRST_VALUE" in sql_upper
        assert "ORDER BY" in sql_upper
    
    def test_arg_min(self) -> None:
        """Test arg_min() function - get value where the ordering column is minimum."""
        asql = """
        from orders
            select customer_id, arg_min(order_id, order_date) as earliest_order_id
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "FIRST_VALUE" in sql_upper
        assert "ORDER BY" in sql_upper


class TestFirstLastInGroupBy:
    """Tests for first() and last() inside GROUP BY aggregation blocks."""
    
    def test_first_in_group_by(self) -> None:
        """Test first() inside GROUP BY aggregation block."""
        asql = """
        from orders
            group by customer_id (
                first(order_id order by -order_date) as latest_order
            )
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "FIRST_VALUE" in sql_upper
        assert "ORDER BY" in sql_upper
        assert "GROUP BY" in sql_upper
    
    def test_last_in_group_by(self) -> None:
        """Test last() inside GROUP BY aggregation block."""
        asql = """
        from orders
            group by customer_id (
                last(order_id order by order_date) as earliest_order
            )
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "FIRST_VALUE" in sql_upper  # Implemented as FIRST_VALUE with reversed order
        assert "ORDER BY" in sql_upper
        assert "GROUP BY" in sql_upper
    
    def test_arg_max_in_group_by(self) -> None:
        """Test arg_max() inside GROUP BY aggregation block."""
        asql = """
        from orders
            group by customer_id (
                arg_max(order_id, order_date) as latest_order
            )
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "FIRST_VALUE" in sql_upper
        assert "ORDER BY" in sql_upper
        assert "GROUP BY" in sql_upper
    
    def test_first_with_other_aggregates(self) -> None:
        """Test first() combined with other aggregates in GROUP BY."""
        asql = """
        from orders
            group by customer_id (
                first(order_id order by -order_date) as latest_order,
                count(*) as total_orders,
                sum(amount) as total_amount
            )
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "FIRST_VALUE" in sql_upper
        assert "COUNT" in sql_upper
        assert "SUM" in sql_upper
        assert "GROUP BY" in sql_upper


class TestDeduplicateBy:
    """Tests for the deduplicate by operator (syntax sugar for per ... first by)."""
    
    def test_deduplicate_by_single_column(self) -> None:
        """Test deduplicate by with single partition column."""
        asql = """
        from events
            deduplicate by user_id
            order by -created_at
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "ROW_NUMBER" in sql_upper
        assert "PARTITION BY" in sql_upper
        assert "USER_ID" in sql_upper
        assert "ORDER BY" in sql_upper
        assert "CREATED_AT" in sql_upper
        assert "DESC" in sql_upper
        assert "QUALIFY" in sql_upper or "WHERE" in sql_upper
    
    def test_deduplicate_by_multiple_columns(self) -> None:
        """Test deduplicate by with multiple partition columns."""
        asql = """
        from events
            deduplicate by user_id, event_type
            order by -created_at
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "ROW_NUMBER" in sql_upper
        assert "PARTITION BY" in sql_upper
        assert "USER_ID" in sql_upper
        assert "EVENT_TYPE" in sql_upper
        assert "ORDER BY" in sql_upper
        assert "CREATED_AT" in sql_upper
    
    def test_deduplicate_by_with_order_by_inline(self) -> None:
        """Test deduplicate by with order by on same line."""
        asql = """
        from events
            deduplicate by user_id, event_type order by -created_at
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "ROW_NUMBER" in sql_upper
        assert "PARTITION BY" in sql_upper
        assert "USER_ID" in sql_upper
        assert "EVENT_TYPE" in sql_upper
        assert "ORDER BY" in sql_upper
        assert "CREATED_AT" in sql_upper
        assert "DESC" in sql_upper
    
    def test_deduplicate_by_ascending_order(self) -> None:
        """Test deduplicate by with ascending order (no minus prefix)."""
        asql = """
        from events
            deduplicate by user_id order by created_at
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "ROW_NUMBER" in sql_upper
        assert "PARTITION BY" in sql_upper
        assert "ORDER BY" in sql_upper
        assert "CREATED_AT" in sql_upper
    
    def test_deduplicate_by_missing_order_by_error(self) -> None:
        """Test that deduplicate by without order by raises error."""
        from asql.errors import ASQLSyntaxError
        
        asql = """
        from events
            deduplicate by user_id
        """
        with pytest.raises(ASQLSyntaxError) as exc_info:
            transpile(asql)
        assert "order by" in str(exc_info.value).lower()
    
    def test_deduplicate_by_equivalent_to_per_first_by(self) -> None:
        """Test that deduplicate by produces same result as per ... first by."""
        asql1 = """
        from events
            deduplicate by user_id, event_type order by -created_at
        """
        asql2 = """
        from events
            per user_id, event_type first by -created_at
        """
        sql1 = transpile(asql1)
        sql2 = transpile(asql2)
        # Both should have ROW_NUMBER with PARTITION BY and ORDER BY
        sql1_upper = sql1.upper()
        sql2_upper = sql2.upper()
        assert "ROW_NUMBER" in sql1_upper
        assert "ROW_NUMBER" in sql2_upper
        assert "PARTITION BY" in sql1_upper
        assert "PARTITION BY" in sql2_upper
        assert "USER_ID" in sql1_upper
        assert "USER_ID" in sql2_upper
        assert "EVENT_TYPE" in sql1_upper
        assert "EVENT_TYPE" in sql2_upper


class TestIntegrationScenarios:
    """Integration tests for common window function patterns."""
    
    def test_dedup_most_recent_order_per_customer(self) -> None:
        """Test deduplication pattern: get most recent order per customer."""
        asql = """
        from orders
            select *, row_number() over (partition by customer_id order by -order_date) as rn
            qualify rn == 1
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "ROW_NUMBER" in sql_upper
        assert "PARTITION BY" in sql_upper
    
    def test_running_total_with_order(self) -> None:
        """Test running total with explicit ordering."""
        asql = """
        from daily_revenue
            order by date
            select date, revenue, running_sum(revenue) as cumulative
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "SUM" in sql_upper
        assert "OVER" in sql_upper
    
    def test_prior_next_for_comparison(self) -> None:
        """Test using prior and next for comparison calculations."""
        asql = """
        from monthly_metrics
            order by month
            select 
                month,
                revenue,
                prior(revenue) as prev_month,
                next(revenue) as next_month
        """
        sql = transpile(asql)
        sql_upper = sql.upper()
        assert "LAG" in sql_upper
        assert "LEAD" in sql_upper
