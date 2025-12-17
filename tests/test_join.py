"""Tests for JOIN functionality in ASQL."""

import pytest
from asql import compile


class TestJoinOperators:
    """Test new ASQL join operator syntax."""
    
    def test_inner_join_operator(self) -> None:
        """Test & operator for INNER JOIN."""
        asql = "from users & orders on users.id = orders.user_id"
        sql = compile(asql)
        assert "JOIN" in sql.upper()
        assert "users" in sql.lower()
        assert "orders" in sql.lower()
        assert "ON" in sql.upper()
    
    def test_left_join_operator(self) -> None:
        """Test &? operator for LEFT JOIN."""
        asql = "from users &? orders on users.id = orders.user_id"
        sql = compile(asql)
        assert "LEFT JOIN" in sql.upper()
        assert "users" in sql.lower()
        assert "orders" in sql.lower()
    
    def test_right_join_operator(self) -> None:
        """Test ?& operator for RIGHT JOIN."""
        asql = "from users ?& orders on users.id = orders.user_id"
        sql = compile(asql)
        assert "RIGHT JOIN" in sql.upper()
        assert "users" in sql.lower()
        assert "orders" in sql.lower()
    
    def test_full_outer_join_operator(self) -> None:
        """Test ?&? operator for FULL OUTER JOIN."""
        asql = "from users ?&? orders on users.id = orders.user_id"
        sql = compile(asql)
        assert "FULL" in sql.upper()
        assert "OUTER" in sql.upper() or "JOIN" in sql.upper()
        assert "users" in sql.lower()
        assert "orders" in sql.lower()
    
    def test_cross_join_operator(self) -> None:
        """Test * operator for CROSS JOIN."""
        asql = "from users * roles"
        sql = compile(asql)
        assert "CROSS JOIN" in sql.upper()
        assert "users" in sql.lower()
        assert "roles" in sql.lower()


class TestJoinWithAlias:
    """Test join operators with table aliases."""
    
    def test_left_join_with_alias(self) -> None:
        """Test LEFT JOIN with AS alias."""
        asql = "from opportunities &? users as owner on opportunities.owner_id = owner.id"
        sql = compile(asql)
        assert "LEFT JOIN" in sql.upper()
        assert "users AS owner" in sql or "users as owner" in sql.lower()
        assert "owner.id" in sql.lower()
    
    def test_inner_join_with_alias(self) -> None:
        """Test INNER JOIN with AS alias."""
        asql = "from orders & customers as c on orders.customer_id = c.id"
        sql = compile(asql)
        assert "JOIN" in sql.upper()
        assert "customers AS c" in sql or "customers as c" in sql.lower()
    
    def test_multiple_aliases_same_table(self) -> None:
        """Test multiple joins to same table with different aliases."""
        asql = """from accounts 
            &? users as owner on accounts.owner_id = owner.id 
            &? users as manager on accounts.manager_id = manager.id"""
        sql = compile(asql)
        assert "LEFT JOIN" in sql.upper()
        assert "owner" in sql.lower()
        assert "manager" in sql.lower()


class TestChainedJoins:
    """Test multiple joins in a single query."""
    
    def test_chained_inner_joins(self) -> None:
        """Test chaining multiple INNER JOINs."""
        asql = """from orders 
            & customers on orders.customer_id = customers.id 
            & order_items on orders.id = order_items.order_id"""
        sql = compile(asql)
        assert sql.upper().count("JOIN") >= 2
        assert "customers" in sql.lower()
        assert "order_items" in sql.lower()
    
    def test_mixed_join_types(self) -> None:
        """Test mixing INNER and LEFT joins."""
        asql = """from orders 
            & customers on orders.customer_id = customers.id 
            &? shipping on orders.id = shipping.order_id"""
        sql = compile(asql)
        assert "JOIN" in sql.upper()
        assert "LEFT JOIN" in sql.upper()


class TestJoinWithClauses:
    """Test joins combined with other clauses."""
    
    def test_join_with_where(self) -> None:
        """Test JOIN with WHERE clause."""
        asql = 'from users &? orders on users.id = orders.user_id where orders.status = "active"'
        sql = compile(asql)
        assert "LEFT JOIN" in sql.upper()
        assert "WHERE" in sql.upper()
        assert "status" in sql.lower()
    
    def test_join_with_select(self) -> None:
        """Test JOIN with SELECT clause."""
        asql = "from users & orders on users.id = orders.user_id select users.name, orders.amount"
        sql = compile(asql)
        assert "JOIN" in sql.upper()
        assert "SELECT" in sql.upper()
        assert "name" in sql.lower()
        assert "amount" in sql.lower()
    
    def test_join_with_group_by(self) -> None:
        """Test JOIN with GROUP BY."""
        asql = "from users &? orders on users.id = orders.user_id group by users.country (sum(orders.amount) as total)"
        sql = compile(asql)
        assert "LEFT JOIN" in sql.upper()
        assert "GROUP BY" in sql.upper()
        assert "SUM" in sql.upper() or "sum" in sql.lower()
    
    def test_join_with_order_by(self) -> None:
        """Test JOIN with ORDER BY."""
        asql = "from users &? orders on users.id = orders.user_id order by -orders.created_at"
        sql = compile(asql)
        assert "LEFT JOIN" in sql.upper()
        assert "ORDER BY" in sql.upper()
        assert "DESC" in sql.upper()


class TestJoinConditions:
    """Test various join condition patterns."""
    
    def test_join_multiple_conditions(self) -> None:
        """Test JOIN with multiple conditions using AND."""
        asql = 'from users &? orders on users.id = orders.user_id and orders.status = "active"'
        sql = compile(asql)
        assert "LEFT JOIN" in sql.upper()
        assert "AND" in sql.upper()
    
    def test_join_with_arithmetic(self) -> None:
        """Test JOIN condition with arithmetic."""
        asql = "from users & orders on users.id = orders.user_id + 0"
        sql = compile(asql)
        assert "JOIN" in sql.upper()
        assert "+" in sql


class TestSelfJoin:
    """Test self-join patterns."""
    
    def test_self_join_with_alias(self) -> None:
        """Test self-join for hierarchies."""
        asql = "from employees &? employees as manager on employees.manager_id = manager.id"
        sql = compile(asql)
        assert "LEFT JOIN" in sql.upper()
        assert "employees" in sql.lower()
        assert "manager" in sql.lower()
    
    def test_self_join_explicit_aliases(self) -> None:
        """Test self-join with both tables aliased."""
        asql = "from employees as e1 &? employees as e2 on e1.manager_id = e2.id"
        sql = compile(asql)
        assert "LEFT JOIN" in sql.upper()
        assert "e1" in sql.lower() or "e1" in sql
        assert "e2" in sql.lower() or "e2" in sql


class TestBackwardCompatibility:
    """Test backward compatibility with traditional JOIN syntax."""
    
    def test_traditional_join(self) -> None:
        """Test traditional JOIN keyword still works."""
        asql = "from users join orders on users.id = orders.user_id"
        sql = compile(asql)
        assert "JOIN" in sql.upper()
        assert "users" in sql.lower()
        assert "orders" in sql.lower()
    
    def test_traditional_left_join(self) -> None:
        """Test traditional LEFT JOIN still works."""
        asql = "from users left join orders on users.id = orders.user_id"
        sql = compile(asql)
        assert "LEFT JOIN" in sql.upper()
    
    def test_traditional_with_alias(self) -> None:
        """Test traditional JOIN with alias."""
        asql = "from employees as e1 left join employees as e2 on e1.manager_id = e2.id"
        sql = compile(asql)
        assert "LEFT JOIN" in sql.upper()
        assert "e1" in sql
        assert "e2" in sql


class TestJoinEdgeCases:
    """Test edge cases in join handling."""
    
    def test_join_without_on(self) -> None:
        """Test that JOIN without ON is treated as cross/comma join."""
        sql = compile("from users & orders")
        # SQLGlot converts this to a cross/comma join
        assert "FROM" in sql.upper()
    
    def test_join_without_table(self) -> None:
        """Test that JOIN without table name raises error."""
        from asql.errors import ASQLSyntaxError
        with pytest.raises(ASQLSyntaxError):
            compile("from users &? on users.id = orders.user_id")
    
    def test_cross_join_with_alias(self) -> None:
        """Test CROSS JOIN with alias."""
        asql = "from users * roles as r"
        sql = compile(asql)
        assert "CROSS JOIN" in sql.upper()
        assert "roles" in sql.lower()
