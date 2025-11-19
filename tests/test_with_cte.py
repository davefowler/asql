"""Tests for WITH/CTE functionality in ASQL."""

import pytest
from asql import compile


class TestWithCTE:
    """Test WITH statement for CTEs."""
    
    def test_simple_with_equals(self) -> None:
        """Test simple WITH statement using =."""
        asql = 'with active_users = from users where status == "active"'
        sql = compile(asql)
        assert "WITH" in sql.upper()
        assert "active_users" in sql.lower()
        assert "AS" in sql.upper()
        assert "SELECT" in sql.upper()
    
    def test_simple_with_as(self) -> None:
        """Test simple WITH statement using as."""
        asql = 'with active_users as from users where status == "active"'
        sql = compile(asql)
        assert "WITH" in sql.upper()
        assert "active_users" in sql.lower()
        assert "AS" in sql.upper()
        assert "SELECT" in sql.upper()
    
    def test_with_with_group_by(self) -> None:
        """Test WITH with GROUP BY."""
        asql = 'with by_country = from users group by country ( # as total_users )'
        sql = compile(asql)
        assert "WITH" in sql.upper()
        assert "by_country" in sql.lower()
        assert "GROUP BY" in sql.upper()
    
    def test_with_with_join(self) -> None:
        """Test WITH with JOIN."""
        asql = "with user_orders = from users join orders on users.id == orders.user_id"
        sql = compile(asql)
        assert "WITH" in sql.upper()
        assert "user_orders" in sql.lower()
        assert "JOIN" in sql.upper()


class TestWithCTEErrors:
    """Test WITH statement error handling."""
    
    def test_with_without_equals_or_as(self) -> None:
        """Test that WITH without = or as raises error."""
        from asql.errors import ASQLSyntaxError
        with pytest.raises(ASQLSyntaxError):
            compile("with active_users from users")
    
    def test_with_without_variable_name(self) -> None:
        """Test that WITH without variable name raises error."""
        from asql.errors import ASQLSyntaxError
        with pytest.raises(ASQLSyntaxError):
            compile("with = from users")
    
    def test_with_without_query(self) -> None:
        """Test that WITH without query raises error."""
        from asql.errors import ASQLSyntaxError
        with pytest.raises(ASQLSyntaxError):
            compile("with active_users =")
