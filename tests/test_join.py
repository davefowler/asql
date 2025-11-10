"""Tests for JOIN functionality in ASQL."""

import pytest
from asql import compile


class TestJoin:
    """Test JOIN clause parsing and SQL generation."""
    
    def test_simple_join(self) -> None:
        """Test simple JOIN."""
        asql = "from users join orders on users.id == orders.user_id"
        sql = compile(asql)
        assert "JOIN" in sql.upper()
        assert "users" in sql.lower()
        assert "orders" in sql.lower()
        assert "ON" in sql.upper()
    
    def test_join_with_where(self) -> None:
        """Test JOIN with WHERE clause."""
        asql = 'from users join orders on users.id == orders.user_id where orders.status == "active"'
        sql = compile(asql)
        assert "JOIN" in sql.upper()
        assert "WHERE" in sql.upper()
        assert "status" in sql.lower()
    
    def test_join_with_select(self) -> None:
        """Test JOIN with SELECT clause."""
        asql = "from users join orders on users.id == orders.user_id select users.name, orders.amount"
        sql = compile(asql)
        assert "JOIN" in sql.upper()
        assert "SELECT" in sql.upper()
        assert "name" in sql.lower()
        assert "amount" in sql.lower()
    
    def test_join_with_group_by(self) -> None:
        """Test JOIN with GROUP BY."""
        asql = "from users join orders on users.id == orders.user_id group by users.country ( sum(orders.amount) as total )"
        sql = compile(asql)
        assert "JOIN" in sql.upper()
        assert "GROUP BY" in sql.upper()
        assert "SUM" in sql.upper() or "sum" in sql.lower()
    
    def test_join_multiple_conditions(self) -> None:
        """Test JOIN with multiple conditions using AND."""
        asql = "from users join orders on users.id == orders.user_id and orders.status == \"active\""
        sql = compile(asql)
        assert "JOIN" in sql.upper()
        assert "AND" in sql.upper()
    
    def test_join_with_arithmetic(self) -> None:
        """Test JOIN condition with arithmetic."""
        asql = "from users join orders on users.id == orders.user_id + 0"
        sql = compile(asql)
        assert "JOIN" in sql.upper()
        assert "+" in sql
    
    def test_join_table_alias(self) -> None:
        """Test JOIN with table names (no aliases yet, but should work)."""
        asql = "from users join orders on users.id == orders.user_id"
        sql = compile(asql)
        assert "JOIN" in sql.upper()
        # Should have both table names
        assert "users" in sql.lower()
        assert "orders" in sql.lower()


class TestJoinErrors:
    """Test JOIN error handling."""
    
    def test_join_without_on(self) -> None:
        """Test that JOIN without ON raises error."""
        from asql.errors import ASQLSyntaxError
        with pytest.raises(ASQLSyntaxError):
            compile("from users join orders")
    
    def test_join_without_table(self) -> None:
        """Test that JOIN without table name raises error."""
        from asql.errors import ASQLSyntaxError
        with pytest.raises(ASQLSyntaxError):
            compile("from users join on users.id == orders.user_id")
    
    def test_join_without_condition(self) -> None:
        """Test that JOIN without condition raises error."""
        from asql.errors import ASQLSyntaxError
        with pytest.raises(ASQLSyntaxError):
            compile("from users join orders on")
