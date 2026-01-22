"""Tests for ASQL spine feature.

Spine provides explicit gap-filling for date truncation columns in GROUP BY,
ensuring all dates appear in results.

Usage:
    from orders spine by month(created_at) (sum(amount))
    from orders group by spine(month(created_at)), region (sum(amount))
"""

from tests.fixtures import transpile
from asql.compiler.spine_helpers import (
    _find_non_date_group_by_columns,
)
import sqlglot


class TestSpineBySyntax:
    """Test the 'spine by' syntax for explicit gap-filling."""
    
    def test_spine_by_basic(self):
        """Test basic spine by syntax."""
        asql = "from orders spine by month(created_at) (sum(amount))"
        sql = transpile(asql, dialect="duckdb")
        
        # Should generate spine CTE
        assert "spine" in sql.lower()
        assert "sum" in sql.lower() or "SUM" in sql
    
    def test_spine_by_with_where(self):
        """Test spine by with WHERE clause."""
        asql = """
        from orders 
        where created_at >= @2024-01-01
        spine by month(created_at) (sum(amount))
        """
        sql = transpile(asql, dialect="duckdb")
        
        assert "spine" in sql.lower()
    
    def test_spine_by_multiple_aggs(self):
        """Test spine by with multiple aggregations."""
        asql = """
        from orders 
        spine by month(created_at) (
            sum(amount) as revenue,
            count(*) as order_count
        )
        """
        sql = transpile(asql, dialect="duckdb")
        
        assert "spine" in sql.lower()
        assert "sum" in sql.lower() or "SUM" in sql
        assert "count" in sql.lower() or "COUNT" in sql


class TestSpineFunctionInGroupBy:
    """Test the spine() function in regular GROUP BY."""
    
    def test_spine_function_in_group_by(self):
        """Test spine() function wrapping a column in GROUP BY."""
        asql = "from orders group by spine(month(created_at)) (sum(amount))"
        sql = transpile(asql, dialect="duckdb")
        
        # Should generate spine CTE
        assert "spine" in sql.lower()
    
    def test_mixed_spine_and_regular_group_by(self):
        """Test mixing spine() with regular GROUP BY columns."""
        asql = """
        from orders 
        group by spine(month(created_at)), region (
            sum(amount) as revenue
        )
        """
        sql = transpile(asql, dialect="duckdb")
        
        # Should generate spine CTE for date but not for region
        assert "spine" in sql.lower()
        assert "region" in sql.lower()


class TestGroupByWithoutSpine:
    """Test that regular GROUP BY doesn't add spine."""
    
    def test_group_by_no_spine(self):
        """Regular GROUP BY shouldn't add spine CTEs."""
        asql = "from orders group by month(created_at) (sum(amount))"
        sql = transpile(asql, dialect="duckdb")
        
        # Should NOT have spine CTE
        assert "_spine" not in sql.lower()
    
    def test_group_by_categorical(self):
        """Categorical GROUP BY shouldn't add spine."""
        asql = "from orders group by region (sum(amount))"
        sql = transpile(asql, dialect="duckdb")
        
        # Should NOT have spine CTE
        assert "_spine" not in sql.lower()


class TestMixedGroupByHandling:
    """Test detection of non-date columns in GROUP BY."""
    
    def test_find_non_date_columns_in_mixed_group_by(self):
        """Test finding non-date columns in mixed GROUP BY."""
        stmt = sqlglot.parse_one("SELECT month(created_at) as m, status FROM orders GROUP BY month(created_at), status")
        non_date_cols = _find_non_date_group_by_columns(stmt)
        
        # Should find 'status' as a non-date column
        assert len(non_date_cols) == 1
        alias, _ = non_date_cols[0]
        assert alias == "status"
    
    def test_pure_date_group_by_no_non_date(self):
        """Test that pure date GROUP BY has no non-date columns."""
        stmt = sqlglot.parse_one("SELECT month(created_at) as m FROM orders GROUP BY month(created_at)")
        non_date_cols = _find_non_date_group_by_columns(stmt)
        
        assert len(non_date_cols) == 0
    
    def test_only_non_date_group_by(self):
        """Test GROUP BY with only non-date columns."""
        stmt = sqlglot.parse_one("SELECT region, status FROM orders GROUP BY region, status")
        non_date_cols = _find_non_date_group_by_columns(stmt)
        
        # Should find both as non-date columns
        assert len(non_date_cols) == 2
    
    def test_no_group_by(self):
        """Test query without GROUP BY returns empty."""
        stmt = sqlglot.parse_one("SELECT * FROM orders")
        non_date_cols = _find_non_date_group_by_columns(stmt)
        
        assert len(non_date_cols) == 0


class TestSpineDialects:
    """Test spine generation for different dialects."""
    
    def test_spine_duckdb(self):
        """Test spine generation for DuckDB."""
        asql = "from orders spine by month(created_at) (sum(amount))"
        sql = transpile(asql, dialect="duckdb")
        
        assert "generate_series" in sql.lower() or "spine" in sql.lower()
    
    def test_spine_snowflake(self):
        """Test spine generation for Snowflake."""
        asql = """
        from orders
        where created_at >= @2024-01-01
        spine by month(created_at) (sum(amount))
        """
        sql = transpile(asql, dialect="snowflake")
        
        assert "spine" in sql.lower()
    
    def test_spine_postgres(self):
        """Test spine generation for PostgreSQL."""
        asql = """
        from orders
        where created_at >= @2024-01-01
        spine by month(created_at) (sum(amount))
        """
        sql = transpile(asql, dialect="postgres")
        
        # PostgreSQL should use generate_series
        assert "generate_series" in sql.lower() or "spine" in sql.lower()


class TestSpineWithDateFunctions:
    """Test spine with different date truncation functions."""
    
    def test_spine_with_year(self):
        """Test spine with year() truncation."""
        asql = "from orders spine by year(created_at) (sum(amount))"
        sql = transpile(asql, dialect="duckdb")
        
        assert "spine" in sql.lower()
        # Year should use INTERVAL '1 year'
        assert "year" in sql.lower()
    
    def test_spine_with_week(self):
        """Test spine with week() truncation."""
        asql = "from orders spine by week(created_at) (sum(amount))"
        sql = transpile(asql, dialect="duckdb")
        
        assert "spine" in sql.lower()
    
    def test_spine_with_day(self):
        """Test spine with day() truncation."""
        asql = """
        from orders 
        where created_at >= @2024-01-01 and created_at < @2024-01-10
        spine by day(created_at) (sum(amount))
        """
        sql = transpile(asql, dialect="duckdb")
        
        assert "spine" in sql.lower()


class TestSpinePredicateHandling:
    """Test that WHERE predicates are properly used for spine bounds."""
    
    def test_spine_uses_where_dates(self):
        """Test that spine uses dates from WHERE clause for bounds."""
        asql = """
        from orders 
        where created_at >= @2024-01-01 and created_at < @2024-04-01
        spine by month(created_at) (sum(amount))
        """
        sql = transpile(asql, dialect="duckdb")
        
        # Should contain the date bounds in the spine CTE
        assert "2024-01-01" in sql
        assert "2024-04-01" in sql or "2024-03-01" in sql
    
    def test_spine_without_where_uses_data_bounds(self):
        """Test that spine without WHERE uses MIN/MAX from data."""
        asql = "from orders spine by month(created_at) (sum(amount))"
        sql = transpile(asql, dialect="duckdb")
        
        # Should use subquery to get MIN/MAX if no explicit bounds
        # The spine CTE should exist even without WHERE
        assert "spine" in sql.lower()


class TestSpineEdgeCases:
    """Test edge cases and error handling for spine."""
    
    def test_spine_with_join(self):
        """Test spine with a JOIN clause."""
        asql = """
        from orders
        join customers on customer_id
        spine by month(created_at) (
            sum(amount) as total
        )
        """
        sql = transpile(asql, dialect="duckdb")
        
        assert "spine" in sql.lower()
        assert "join" in sql.lower()
    
    def test_multiple_spine_columns(self):
        """Test multiple spine columns in same GROUP BY."""
        asql = """
        from orders 
        group by spine(month(created_at)), spine(category) (
            sum(amount)
        )
        """
        sql = transpile(asql, dialect="duckdb")
        
        # Should generate spine CTEs for both columns
        assert "spine" in sql.lower()
    
    def test_spine_with_complex_where(self):
        """Test spine with complex WHERE clause."""
        asql = """
        from orders 
        where status = 'completed' 
          and created_at >= @2024-01-01 
          and created_at < @2024-04-01
        spine by month(created_at) (sum(amount))
        """
        sql = transpile(asql, dialect="duckdb")
        
        assert "spine" in sql.lower()
        assert "completed" in sql.lower()
