"""Tests for JOIN functionality in ASQL."""

import pytest
import sqlglot
from sqlglot import exp
from asql import compile
from asql.errors import ASQLSyntaxError
from tests.fixtures import assert_valid_sql, assert_sql_contains


class TestJoinOperators:
    """Test new ASQL join operator syntax."""
    
    def test_inner_join_operator(self) -> None:
        """Test & operator for INNER JOIN."""
        asql = "from users & orders on users.id = orders.user_id"
        sql = compile(asql)
        
        assert_sql_contains(sql, "JOIN", "users", "orders", "ON")
        assert_valid_sql(sql)
        
        # Verify JOIN structure
        parsed = sqlglot.parse_one(sql)
        join = parsed.find(exp.Join)
        assert join is not None, "JOIN expression not found"
        # sqlglot represents INNER joins with empty kind/side (LEFT joins set join.side="LEFT")
        assert join.side in (None, ""), f"Expected INNER JOIN, got side={join.side!r}"
        # Verify ON condition
        assert join.args.get("on") is not None, "ON condition not found in JOIN"
    
    def test_left_join_operator(self) -> None:
        """Test &? operator for LEFT JOIN."""
        asql = "from users &? orders on users.id = orders.user_id"
        sql = compile(asql)
        
        assert_sql_contains(sql, "LEFT JOIN", "users", "orders")
        assert_valid_sql(sql)
        
        # Verify LEFT JOIN structure
        parsed = sqlglot.parse_one(sql)
        join = parsed.find(exp.Join)
        assert join is not None, "JOIN expression not found"
        assert (join.side or "").upper() == "LEFT", f"Expected LEFT JOIN, got side={join.side!r}"
    
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
        
        join_count = sql.upper().count("JOIN")
        assert join_count >= 2, f"Expected at least 2 JOINs, got {join_count}"
        assert_sql_contains(sql, "customers", "order_items", "orders")
        assert_valid_sql(sql)
        
        # Verify multiple JOINs in structure
        parsed = sqlglot.parse_one(sql)
        joins = list(parsed.find_all(exp.Join))
        assert len(joins) >= 2, f"Expected at least 2 JOIN expressions, got {len(joins)}"
    
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


class TestExplicitFKColumnShorthand:
    """Test explicit FK column shorthand syntax for joins."""
    
    def test_explicit_fk_column_inner_join(self) -> None:
        """Test FK column shorthand with INNER JOIN."""
        asql = "from accounts & users on owner_id"
        sql = compile(asql)
        
        assert_sql_contains(sql, "JOIN", "accounts", "users", "ON")
        assert "accounts.owner_id" in sql.lower()
        assert "users.id" in sql.lower()
        assert_valid_sql(sql)
    
    def test_explicit_fk_column_left_join(self) -> None:
        """Test FK column shorthand with LEFT JOIN."""
        asql = "from accounts &? users on owner_id"
        sql = compile(asql)
        
        assert "LEFT JOIN" in sql.upper()
        assert "accounts.owner_id" in sql.lower()
        assert "users.id" in sql.lower()
        assert_valid_sql(sql)
    
    def test_explicit_fk_column_right_join(self) -> None:
        """Test FK column shorthand with RIGHT JOIN."""
        asql = "from accounts ?& users on owner_id"
        sql = compile(asql)
        
        assert "RIGHT JOIN" in sql.upper()
        assert "accounts.owner_id" in sql.lower()
        assert "users.id" in sql.lower()
    
    def test_explicit_fk_column_with_alias(self) -> None:
        """Test FK column shorthand with table alias."""
        asql = "from accounts &? users as u on owner_id"
        sql = compile(asql)
        
        assert "LEFT JOIN" in sql.upper()
        assert "accounts.owner_id" in sql.lower()
        # Should use alias in the condition
        assert "u.id" in sql.lower()
        assert_valid_sql(sql)
    
    def test_explicit_fk_column_chained_joins(self) -> None:
        """Test FK column shorthand with multiple chained joins."""
        asql = """from orders 
            & customers on customer_id 
            &? shipping on shipping_id"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "orders", "customers", "shipping")
        assert "orders.customer_id" in sql.lower()
        assert "customers.id" in sql.lower()
        # Note: the second FK is relative to the first table in FROM
        assert "orders.shipping_id" in sql.lower()
        assert_valid_sql(sql)
    
    def test_explicit_fk_fallback_to_full_condition(self) -> None:
        """Test that full explicit conditions still work (passthrough)."""
        asql = "from accounts & users on accounts.owner_id = users.id"
        sql = compile(asql)
        
        assert_sql_contains(sql, "JOIN", "accounts", "users", "ON")
        assert "accounts.owner_id" in sql.lower()
        assert "users.id" in sql.lower()
        assert_valid_sql(sql)
    
    def test_explicit_fk_fallback_with_equality(self) -> None:
        """Test that conditions with = operator fall back to passthrough."""
        asql = "from accounts & users on accounts.owner_id = users.user_id"
        sql = compile(asql)
        
        # Should pass through unchanged - not expand as FK shorthand
        assert "accounts.owner_id" in sql.lower()
        assert "users.user_id" in sql.lower()
        assert_valid_sql(sql)
    
    def test_explicit_fk_fallback_complex_condition(self) -> None:
        """Test that complex conditions with AND fall back to passthrough."""
        asql = 'from accounts & users on accounts.owner_id = users.id and users.active = true'
        sql = compile(asql)
        
        assert "AND" in sql.upper()
        assert "accounts.owner_id" in sql.lower()
        assert_valid_sql(sql)
    
    def test_explicit_fk_with_underscore_column(self) -> None:
        """Test FK shorthand with underscore in column name."""
        asql = "from orders & users on created_by_id"
        sql = compile(asql)
        
        assert "orders.created_by_id" in sql.lower()
        assert "users.id" in sql.lower()
        assert_valid_sql(sql)
    
    def test_traditional_join_fk_shorthand(self) -> None:
        """Test FK shorthand with traditional JOIN keyword."""
        asql = "from accounts join users on owner_id"
        sql = compile(asql)
        
        assert "accounts.owner_id" in sql.lower()
        assert "users.id" in sql.lower()
        assert_valid_sql(sql)
    
    def test_traditional_left_join_fk_shorthand(self) -> None:
        """Test FK shorthand with traditional LEFT JOIN."""
        asql = "from accounts left join users on owner_id"
        sql = compile(asql)
        
        assert "LEFT JOIN" in sql.upper()
        assert "accounts.owner_id" in sql.lower()
        assert "users.id" in sql.lower()
        assert_valid_sql(sql)
    
    def test_traditional_join_fk_shorthand_with_alias(self) -> None:
        """Test FK shorthand with traditional JOIN and alias."""
        asql = "from accounts left join users as u on owner_id"
        sql = compile(asql)
        
        assert "LEFT JOIN" in sql.upper()
        assert "accounts.owner_id" in sql.lower()
        assert "u.id" in sql.lower()
        assert_valid_sql(sql)


class TestJoinEdgeCases:
    """Test edge cases in join handling."""
    
    def test_join_without_on(self) -> None:
        """Test that JOIN without ON is treated as cross/comma join."""
        sql = compile("from users & orders")
        
        assert_sql_contains(sql, "FROM", "users", "orders")
        assert_valid_sql(sql)
        
        # SQLGlot converts this to a cross/comma join
        parsed = sqlglot.parse_one(sql)
        # Should have both tables in FROM
        from_clause = parsed.find(exp.From)
        assert from_clause is not None, "FROM clause not found"
    
    def test_join_without_table(self) -> None:
        """Test that JOIN without table name raises error."""
        with pytest.raises(ASQLSyntaxError):
            compile("from users &? on users.id = orders.user_id")
    
    def test_cross_join_with_alias(self) -> None:
        """Test CROSS JOIN with alias."""
        asql = "from users * roles as r"
        sql = compile(asql)
        assert "CROSS JOIN" in sql.upper()
        assert "roles" in sql.lower()
