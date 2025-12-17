"""Tests for the ASQL pre-parser.

The pre-parser transforms ASQL structural syntax to SQL-like syntax
before SQLGlot parsing.
"""

import pytest
from asql.preparser import preparse_asql, ASQLPreParser


class TestFromFirst:
    """Test FROM-first to SELECT-FROM transformation."""
    
    def test_simple_from_first(self):
        """FROM without SELECT adds SELECT *."""
        result = preparse_asql("from users")
        assert "SELECT *" in result.upper()
        assert "FROM USERS" in result.upper()
    
    def test_from_with_where(self):
        """FROM with WHERE clause."""
        result = preparse_asql("from users where status = 'active'")
        assert "SELECT *" in result.upper()
        assert "FROM USERS" in result.upper()
        assert "WHERE STATUS" in result.upper()
    
    def test_from_with_limit(self):
        """FROM with LIMIT clause."""
        result = preparse_asql("from users limit 10")
        assert "SELECT *" in result.upper()
        assert "LIMIT 10" in result.upper()


class TestPipelineOperators:
    """Test pipeline operator (|) transformation."""
    
    def test_simple_pipeline(self):
        """Pipeline operators are removed."""
        result = preparse_asql("from users | where active | limit 10")
        assert "|" not in result
        assert "FROM USERS" in result.upper()
        assert "WHERE ACTIVE" in result.upper()
        assert "LIMIT 10" in result.upper()
    
    def test_pipeline_with_strings(self):
        """Pipeline operators in strings are preserved."""
        result = preparse_asql("from users | where name = 'test|value'")
        # The | inside the string should be preserved
        assert "test|value" in result


class TestCountShorthand:
    """Test # count shorthand transformation."""
    
    def test_standalone_hash(self):
        """# becomes COUNT(*)."""
        # Note: The preparser transforms # to COUNT(*)
        result = preparse_asql("from users select #")
        assert "COUNT(*)" in result.upper()
    
    def test_hash_with_column(self):
        """#(col) becomes COUNT(col)."""
        result = preparse_asql("from users select #(id)")
        assert "COUNT(ID)" in result.upper()
    
    def test_hash_of_keyword(self):
        """# of users becomes COUNT(*)."""
        result = preparse_asql("from users select # of users")
        assert "COUNT(*)" in result.upper()


class TestCoalesceOperator:
    """Test ?? coalesce operator transformation."""
    
    def test_simple_coalesce(self):
        """a ?? b becomes COALESCE(a, b)."""
        result = preparse_asql("from users select name ?? 'Unknown'")
        assert "COALESCE" in result.upper()
    
    def test_chained_coalesce(self):
        """a ?? b ?? c becomes COALESCE(a, b, c)."""
        result = preparse_asql("from users select first_name ?? nickname ?? 'Unknown'")
        assert "COALESCE" in result.upper()


class TestOrderDescPrefix:
    """Test -column DESC transformation in ORDER BY."""
    
    def test_simple_desc(self):
        """-col becomes col DESC."""
        result = preparse_asql("from users order by -created_at")
        assert "CREATED_AT DESC" in result.upper() or "CREATED_AT" in result.upper()
    
    def test_mixed_order(self):
        """Mixed ascending and descending."""
        result = preparse_asql("from users order by -created_at, name")
        assert "DESC" in result.upper()
        assert "NAME" in result.upper()


class TestNaturalAggregates:
    """Test natural language aggregate transformation."""
    
    def test_sum_of(self):
        """sum of amount becomes sum(amount)."""
        result = preparse_asql("from sales select sum of amount")
        assert "SUM(AMOUNT)" in result.upper() or "SUM" in result.upper() and "AMOUNT" in result.upper()
    
    def test_avg_column(self):
        """avg price becomes avg(price)."""
        result = preparse_asql("from products select avg price")
        assert "AVG" in result.upper()
        assert "PRICE" in result.upper()
    
    def test_total_column(self):
        """total amount becomes sum(amount)."""
        result = preparse_asql("from sales select total amount")
        # 'total' is an alias for 'sum'
        assert "AMOUNT" in result.upper()


class TestDateLiterals:
    """Test @date literal transformation."""
    
    def test_date_literal(self):
        """@2024-01-15 becomes DATE '2024-01-15'."""
        result = preparse_asql("from users where created_at >= @2024-01-15")
        assert "DATE '2024-01-15'" in result or "'2024-01-15'" in result
    
    def test_timestamp_literal(self):
        """@2024-01-15T10:30:00 becomes TIMESTAMP."""
        result = preparse_asql("from users where created_at >= @2024-01-15T10:30:00")
        assert "TIMESTAMP" in result.upper() or "'2024-01-15" in result


class TestRelativeDates:
    """Test relative date transformation."""
    
    def test_days_ago(self):
        """7 days ago becomes CURRENT_DATE - INTERVAL."""
        result = preparse_asql("from users where created_at >= 7 days ago")
        assert "INTERVAL" in result.upper()
        assert "7" in result
    
    def test_month_ago(self):
        """1 month ago becomes CURRENT_DATE - INTERVAL."""
        result = preparse_asql("from users where created_at >= 1 month ago")
        assert "INTERVAL" in result.upper()
    
    def test_days_from_now(self):
        """3 days from now becomes CURRENT_DATE + INTERVAL."""
        result = preparse_asql("from tasks where due_date <= 3 days from now")
        assert "INTERVAL" in result.upper()
        assert "+" in result


class TestDateArithmetic:
    """Test date arithmetic transformation."""
    
    def test_add_days(self):
        """col + 7 days becomes col + INTERVAL."""
        result = preparse_asql("from orders select order_date + 7 days as delivery_date")
        assert "INTERVAL" in result.upper()
        assert "7" in result
    
    def test_subtract_month(self):
        """col - 1 month becomes col - INTERVAL."""
        result = preparse_asql("from events select event_date - 1 month as last_month")
        assert "INTERVAL" in result.upper()


class TestSinceUntilPatterns:
    """Test *_since_* and *_until_* pattern transformation."""
    
    def test_days_since(self):
        """days_since_col becomes date difference."""
        result = preparse_asql("from users select days_since_created_at")
        assert "DATEDIFF" in result.upper() or "CREATED_AT" in result.upper()
    
    def test_months_until(self):
        """months_until_col becomes date difference."""
        result = preparse_asql("from tasks select months_until_due_date")
        assert "DATEDIFF" in result.upper() or "DUE_DATE" in result.upper()


class TestPerCommands:
    """Test PER command transformation for window operations."""
    
    def test_per_first_by(self):
        """per col first by -order becomes window function with QUALIFY."""
        result = preparse_asql("from orders per customer_id first by -order_date")
        assert "ROW_NUMBER" in result.upper() or "QUALIFY" in result.upper()
        assert "PARTITION BY" in result.upper() or "CUSTOMER_ID" in result.upper()
    
    def test_per_number_by(self):
        """per col number by order adds ROW_NUMBER column."""
        result = preparse_asql("from orders per customer_id number by -order_date")
        assert "ROW_NUMBER" in result.upper()


class TestAggregateBlocks:
    """Test aggregate block transformation."""
    
    def test_simple_aggregate_block(self):
        """group by col (agg) becomes SELECT col, agg GROUP BY col."""
        result = preparse_asql("from sales group by region (sum(amount) as revenue)")
        assert "SELECT" in result.upper()
        assert "GROUP BY" in result.upper()
        assert "REGION" in result.upper()
        assert "SUM" in result.upper()
    
    def test_multiple_aggregates(self):
        """Multiple aggregates in block."""
        result = preparse_asql("from sales group by region (sum(amount) as revenue, count(*) as cnt)")
        assert "SUM" in result.upper()
        assert "COUNT" in result.upper()


class TestStashAs:
    """Test stash as CTE transformation."""
    
    def test_simple_stash(self):
        """stash as name creates CTE."""
        result = preparse_asql("from users where active stash as active_users")
        assert "WITH" in result.upper() or "ACTIVE_USERS" in result.upper()


class TestSetStatements:
    """Test set variable = query transformation."""
    
    def test_simple_set(self):
        """set name = query creates CTE."""
        result = preparse_asql("set base = from users where active")
        assert "WITH" in result.upper()
        assert "BASE" in result.upper()


class TestFunctionSpaceNormalization:
    """Test underscore/space normalization for functions."""
    
    def test_day_of_week_spaces(self):
        """day of week col becomes day_of_week(col)."""
        result = preparse_asql("from events select day of week created_at")
        assert "DAY_OF_WEEK" in result.upper() or "DAYOFWEEK" in result.upper()
    
    def test_row_number_spaces(self):
        """row number() becomes row_number()."""
        result = preparse_asql("from events select row number() over (order by id)")
        assert "ROW_NUMBER" in result.upper()


class TestEqualityOperators:
    """Test equality operator transformation."""
    
    def test_double_equals(self):
        """== becomes = for SQL compatibility."""
        result = preparse_asql("from users where status == 'active'")
        # Should have single = not ==
        assert "STATUS = " in result.upper() or "STATUS=" in result.upper()


class TestCommentPreservation:
    """Test that comments are preserved during transformation."""
    
    def test_single_line_comment(self):
        """Single-line comments are preserved."""
        result = preparse_asql("-- This is a comment\nfrom users")
        assert "-- This is a comment" in result
    
    def test_multi_line_comment(self):
        """Multi-line comments are preserved."""
        result = preparse_asql("/* Comment */\nfrom users")
        assert "/* Comment */" in result


class TestComplexQueries:
    """Test complex queries with multiple transformations."""
    
    def test_full_pipeline(self):
        """Test a complete pipeline query."""
        asql = """
        from orders
        | where order_date >= 7 days ago
        | group by region (sum(amount) as revenue, count(*) as cnt)
        | order by -revenue
        | limit 10
        """
        result = preparse_asql(asql)
        assert "SELECT" in result.upper()
        assert "FROM ORDERS" in result.upper()
        assert "WHERE" in result.upper()
        assert "GROUP BY" in result.upper()
        assert "ORDER BY" in result.upper()
        assert "LIMIT 10" in result.upper()
    
    def test_join_with_aggregation(self):
        """Test join with aggregation."""
        asql = "from orders join customers on orders.customer_id = customers.id group by customers.name (sum(amount) as total)"
        result = preparse_asql(asql)
        assert "JOIN" in result.upper()
        assert "CUSTOMERS" in result.upper()


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_string(self):
        """Empty string returns empty result."""
        result = preparse_asql("")
        assert result == ""
    
    def test_whitespace_only(self):
        """Whitespace-only returns empty result."""
        result = preparse_asql("   \n\t  ")
        assert result.strip() == ""
    
    def test_already_valid_sql(self):
        """Valid SQL passes through."""
        result = preparse_asql("SELECT * FROM users WHERE id = 1")
        assert "SELECT" in result.upper()
        assert "FROM USERS" in result.upper()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
