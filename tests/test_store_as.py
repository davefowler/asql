"""Tests for store as CTE functionality in ASQL."""

import pytest
from asql import compile
from asql.errors import ASQLSyntaxError


class TestStoreAs:
    """Test store as functionality for CTEs."""
    
    def test_simple_store_as(self) -> None:
        """Test simple store as in pipeline."""
        asql = """
        from users
          where status == "active"
          store as active_users
        """
        sql = compile(asql)
        assert "WITH" in sql.upper()
        assert "active_users" in sql.lower()
        assert "AS" in sql.upper()
        assert "SELECT" in sql.upper()
        assert "status" in sql.lower()
    
    def test_store_as_with_group_by(self) -> None:
        """Test store as with GROUP BY."""
        asql = """
        from users
          where status == "active"
          group by country ( # as total_users )
          store as by_country
        """
        sql = compile(asql)
        assert "WITH" in sql.upper()
        assert "by_country" in sql.lower()
        assert "GROUP BY" in sql.upper()
        assert "country" in sql.lower()
    
    def test_store_as_with_select(self) -> None:
        """Test store as with SELECT."""
        asql = """
        from users
          where status == "active"
          select name, email
          store as active_users
        """
        sql = compile(asql)
        assert "WITH" in sql.upper()
        assert "active_users" in sql.lower()
        assert "name" in sql.lower()
        assert "email" in sql.lower()
    
    def test_store_as_continues_pipeline(self) -> None:
        """Test that pipeline can continue after store as."""
        asql = """
        from users
          where status == "active"
          store as active_users
          group by country ( # as total_users )
        """
        sql = compile(asql)
        assert "WITH" in sql.upper()
        assert "active_users" in sql.lower()
        assert "GROUP BY" in sql.upper()
        # Should have multiple CTEs
        assert sql.upper().count("WITH") >= 1
    
    def test_store_as_with_multiple_operations(self) -> None:
        """Test store as with multiple operations before it."""
        asql = """
        from sales
          where amount > 100
          group by region ( sum(amount) as revenue )
          select region, revenue
          store as revenue_by_region
        """
        sql = compile(asql)
        assert "WITH" in sql.upper()
        assert "revenue_by_region" in sql.lower()
        assert "revenue" in sql.lower()
        assert "region" in sql.lower()


class TestStoreAsErrors:
    """Test store as error handling."""
    
    def test_store_as_without_name(self) -> None:
        """Test that store as without name raises error."""
        with pytest.raises(ASQLSyntaxError):
            compile("from users store as")
    
    def test_store_without_as(self) -> None:
        """Test that store without as raises error."""
        with pytest.raises(ASQLSyntaxError):
            compile("from users store revenue")
    
    def test_store_as_at_start(self) -> None:
        """Test that store as cannot be at the start."""
        with pytest.raises(ASQLSyntaxError):
            compile("store as revenue")

