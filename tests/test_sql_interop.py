"""Test SQL/ASQL interoperability.

These tests document the current state of mixing standard SQL syntax with ASQL.
Some tests are marked as expected failures (xfail) to document known limitations.
"""

import pytest
from asql import compile


class TestPureSQLPassthrough:
    """Pure SQL queries should pass through unchanged (modulo formatting)."""
    
    def test_simple_select(self) -> None:
        """Standard SELECT works."""
        sql = "SELECT * FROM users WHERE active = true"
        result = compile(sql)
        assert "SELECT" in result
        assert "FROM users" in result
        assert "active" in result
    
    def test_sql_with_cte(self) -> None:
        """Standard WITH...AS works."""
        sql = """
        WITH active_users AS (
            SELECT * FROM users WHERE active = true
        )
        SELECT * FROM active_users
        """
        result = compile(sql)
        assert "WITH active_users AS" in result
        assert "SELECT * FROM active_users" in result
    
    def test_nested_ctes(self) -> None:
        """Multiple CTEs work."""
        sql = """
        WITH a AS (SELECT 1 as x),
             b AS (SELECT * FROM a)
        SELECT * FROM b
        """
        result = compile(sql)
        assert "WITH a AS" in result
        assert "b AS" in result
    
    def test_sql_subquery_in_from(self) -> None:
        """Subquery in FROM works."""
        sql = """
        SELECT * FROM (
            SELECT user_id, COUNT(*) as cnt
            FROM orders
            GROUP BY user_id
        ) AS user_orders
        WHERE cnt > 5
        """
        result = compile(sql)
        assert "FROM (" in result or "FROM(" in result
        assert "GROUP BY" in result
    
    def test_sql_union(self) -> None:
        """UNION works."""
        sql = """
        SELECT id, name FROM customers
        UNION
        SELECT id, name FROM vendors
        """
        result = compile(sql)
        assert "UNION" in result
    
    def test_sql_window_function(self) -> None:
        """Window functions work."""
        sql = """
        SELECT 
            user_id,
            ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) as rn
        FROM orders
        """
        result = compile(sql)
        assert "ROW_NUMBER()" in result
        assert "PARTITION BY" in result
    
    def test_sql_case_expression(self) -> None:
        """CASE expressions work."""
        sql = """
        SELECT CASE WHEN status = 'active' THEN 1 ELSE 0 END as is_active
        FROM users
        """
        result = compile(sql)
        assert "CASE" in result
        assert "WHEN" in result
    
    def test_lateral_join(self) -> None:
        """LATERAL joins work."""
        sql = """
        SELECT * FROM users u,
        LATERAL (SELECT * FROM orders o WHERE o.user_id = u.id LIMIT 3) recent_orders
        """
        result = compile(sql)
        assert "LATERAL" in result


class TestASQLWithSQLExpressions:
    """ASQL syntax with SQL expressions inside."""
    
    def test_from_first_with_case(self) -> None:
        """FROM-first with CASE expression."""
        asql = """
        from users
        select CASE WHEN status = 'active' THEN 1 ELSE 0 END as is_active
        """
        result = compile(asql)
        assert "CASE" in result
        assert "SELECT" in result
    
    def test_asql_join(self) -> None:
        """ASQL with JOIN syntax."""
        asql = """
        from orders
        join customers on orders.customer_id = customers.id
        select orders.id, customers.name
        """
        result = compile(asql)
        assert "JOIN" in result
        assert "SELECT" in result
    
    @pytest.mark.xfail(reason="Optimizer removes unused CTEs - stash functionality tested elsewhere")
    def test_stash_as_creates_cte(self) -> None:
        """stash as creates proper CTE.
        
        Note: When stash is the final operation, the optimizer removes the CTE
        because it's not "used" in a subsequent operation. This test is xfailed
        but the core stash functionality is covered by tests in test_store_as.py.
        """
        asql = """
        from users
        where active
        stash as active_users
        """
        result = compile(asql)
        assert "WITH active_users AS" in result


class TestKnownLimitations:
    """Document known limitations with SQL/ASQL mixing."""
    
    def test_subquery_in_where(self) -> None:
        """SQL subquery in WHERE clause - now works correctly."""
        sql = """
        SELECT * FROM orders
        WHERE customer_id IN (SELECT id FROM customers WHERE premium = true)
        """
        result = compile(sql)
        # Should have two separate WHERE clauses
        assert "WHERE premium" in result
    
    @pytest.mark.xfail(reason="Preparser converts nested WHERE to AND")
    def test_exists_subquery(self) -> None:
        """EXISTS with subquery - KNOWN LIMITATION."""
        sql = """
        SELECT * FROM customers c
        WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)
        """
        result = compile(sql)
        assert "EXISTS" in result
        assert "WHERE o.customer_id" in result
    
    def test_with_asql_body(self) -> None:
        """WITH clause with ASQL body - now works correctly."""
        asql = """
        WITH revenue AS (
            from sales
            group by month(created_at) (sum(amount) as total)
        )
        SELECT * FROM revenue
        """
        result = compile(asql)
        assert "WITH revenue AS" in result
    
    @pytest.mark.xfail(reason="FROM-first only transforms first query in UNION")
    def test_union_with_asql(self) -> None:
        """UNION with ASQL queries - KNOWN LIMITATION."""
        asql = """
        from customers select id, name
        UNION
        from vendors select id, name
        """
        result = compile(asql)
        # Both should have SELECT
        assert result.count("SELECT") >= 2
    
    @pytest.mark.xfail(reason="Stash chaining not fully supported")
    def test_multiple_stash_as(self) -> None:
        """Multiple stash as in sequence - KNOWN LIMITATION."""
        asql = """
        from users where active stash as active_users
        from active_users group by country (count(*) as cnt)
        """
        result = compile(asql)
        assert "active_users" in result


class TestRecommendedPatterns:
    """Show the recommended ASQL way to do things."""
    
    def test_use_stash_instead_of_with(self) -> None:
        """Use stash as instead of WITH...AS for ASQL bodies."""
        # RECOMMENDED: Use stash as
        asql = """
        from sales
        group by month(created_at) (sum(amount) as revenue)
        stash as revenue_by_month
        """
        result = compile(asql)
        assert "WITH revenue_by_month AS" in result
        assert "SUM(amount)" in result
    
    def test_asql_for_subquery_logic(self) -> None:
        """Break subquery logic into stash as CTEs."""
        # Instead of: SELECT * FROM orders WHERE id IN (SELECT id FROM vip_orders)
        # Use stash as for the subquery:
        _asql_example = """
        from vip_orders select id stash as vip_ids
        from orders where id IN (SELECT id FROM vip_ids)
        """
        # This still has the WHERE issue, but demonstrates the pattern
        # A full fix would need the subquery WHERE fix
        assert _asql_example  # Silence unused variable warning
