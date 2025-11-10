"""Tests for SET/CTE functionality in ASQL."""

import pytest
from asql import compile


class TestSetCTE:
    """Test SET statement for CTEs."""
    
    def test_simple_set(self) -> None:
        """Test simple SET statement."""
        asql = 'set active_users = from users where status == "active"'
        sql = compile(asql)
        assert "WITH" in sql.upper()
        assert "active_users" in sql.lower()
        assert "AS" in sql.upper()
        assert "SELECT" in sql.upper()
    
    def test_set_with_group_by(self) -> None:
        """Test SET with GROUP BY."""
        asql = 'set by_country = from users group by country ( # as total_users )'
        sql = compile(asql)
        assert "WITH" in sql.upper()
        assert "by_country" in sql.lower()
        assert "GROUP BY" in sql.upper()
    
    def test_set_with_join(self) -> None:
        """Test SET with JOIN."""
        asql = "set user_orders = from users join orders on users.id == orders.user_id"
        sql = compile(asql)
        assert "WITH" in sql.upper()
        assert "user_orders" in sql.lower()
        assert "JOIN" in sql.upper()


class TestSetCTEErrors:
    """Test SET statement error handling."""
    
    def test_set_without_equals(self) -> None:
        """Test that SET without = raises error."""
        from asql.errors import ASQLSyntaxError
        with pytest.raises(ASQLSyntaxError):
            compile("set active_users from users")
    
    def test_set_without_variable_name(self) -> None:
        """Test that SET without variable name raises error."""
        from asql.errors import ASQLSyntaxError
        with pytest.raises(ASQLSyntaxError):
            compile("set = from users")
    
    def test_set_without_query(self) -> None:
        """Test that SET without query raises error."""
        from asql.errors import ASQLSyntaxError
        with pytest.raises(ASQLSyntaxError):
            compile("set active_users =")
