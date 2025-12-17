"""Tests for auto-qualification of conflicting column names in joins."""

import pytest
from asql import compile


class TestAutoQualifyColumns:
    """Test automatic qualification of columns in joins."""
    
    def test_select_star_with_join_expands_to_table_star(self) -> None:
        """Test that SELECT * with joins expands to table.* for each table."""
        asql = "from users & orders on users.id = orders.user_id"
        sql = compile(asql)
        
        # Should expand SELECT * to users.*, orders.*
        sql_upper = sql.upper()
        assert "SELECT" in sql_upper
        assert "USERS.*" in sql_upper or "users.*" in sql
        assert "ORDERS.*" in sql_upper or "orders.*" in sql
        assert "JOIN" in sql_upper
    
    def test_select_star_with_left_join(self) -> None:
        """Test SELECT * with LEFT JOIN."""
        asql = "from users &? orders on users.id = orders.user_id"
        sql = compile(asql)
        
        sql_upper = sql.upper()
        assert "LEFT JOIN" in sql_upper
        assert "USERS.*" in sql_upper or "users.*" in sql
        assert "ORDERS.*" in sql_upper or "orders.*" in sql
    
    def test_select_star_with_multiple_joins(self) -> None:
        """Test SELECT * with multiple joins."""
        asql = """from orders 
            & customers on orders.customer_id = customers.id 
            & order_items on orders.id = order_items.order_id"""
        sql = compile(asql)
        
        sql_upper = sql.upper()
        assert "ORDERS.*" in sql_upper or "orders.*" in sql
        assert "CUSTOMERS.*" in sql_upper or "customers.*" in sql
        assert "ORDER_ITEMS.*" in sql_upper or "order_items.*" in sql
    
    def test_select_star_with_aliases(self) -> None:
        """Test SELECT * with table aliases."""
        asql = "from users &? orders as o on users.id = o.user_id"
        sql = compile(asql)
        
        sql_upper = sql.upper()
        assert "LEFT JOIN" in sql_upper
        # Should use alias 'o' for orders table
        assert "O.*" in sql_upper or "o.*" in sql
        assert "USERS.*" in sql_upper or "users.*" in sql
    
    def test_no_expansion_without_joins(self) -> None:
        """Test that SELECT * without joins is not expanded."""
        asql = "from users"
        sql = compile(asql)
        
        sql_upper = sql.upper()
        assert "SELECT *" in sql_upper or "SELECT  *" in sql_upper
        # Should not have table-qualified stars
        assert "USERS.*" not in sql_upper
    
    def test_explicit_select_not_affected(self) -> None:
        """Test that explicit SELECT columns are not affected."""
        asql = "from users & orders on users.id = orders.user_id select users.name, orders.amount"
        sql = compile(asql)
        
        sql_upper = sql.upper()
        assert "SELECT" in sql_upper
        assert "NAME" in sql_upper or "name" in sql
        assert "AMOUNT" in sql_upper or "amount" in sql
        # Should not have table.* expansion since we have explicit columns
        assert "USERS.*" not in sql_upper
        assert "ORDERS.*" not in sql_upper
