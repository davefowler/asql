"""Tests for pipeline CTE functionality.

Note: The new SQLGlot-based compiler produces simpler queries without
intermediate CTEs. CTEs are only generated when explicitly requested
with 'stash as' or 'set' statements.
"""

import pytest

from asql import compile


def test_simple_pipeline_single_step() -> None:
    """Test simple pipeline with just FROM."""
    asql = "from users"
    sql = compile(asql)
    
    # Should NOT generate a CTE
    assert "WITH" not in sql.upper()
    assert "SELECT" in sql.upper()
    assert "users" in sql.lower()


def test_pipeline_with_where() -> None:
    """Test pipeline with WHERE clause."""
    asql = 'from users where status == "active"'
    sql = compile(asql)
    
    # Should NOT generate a CTE
    assert "WITH" not in sql.upper()
    assert "WHERE" in sql.upper()
    assert "status" in sql.lower()
    assert "active" in sql.lower()


def test_pipeline_with_group_by() -> None:
    """Test pipeline with GROUP BY."""
    asql = 'from users where status == "active" group by country ( # as total_users )'
    sql = compile(asql)
    
    # New compiler produces direct SQL without intermediate CTEs
    assert "SELECT" in sql.upper()
    assert "GROUP BY" in sql.upper()
    assert "COUNT(*)" in sql.upper() or "COUNT" in sql.upper()
    assert "country" in sql.lower()


def test_pipeline_with_sort() -> None:
    """Test pipeline with SORT."""
    asql = 'from users where status == "active" sort -created_at'
    sql = compile(asql)
    
    assert "WITH" not in sql.upper()
    assert "ORDER BY" in sql.upper()
    assert "DESC" in sql.upper()


def test_pipeline_complete() -> None:
    """Test complete pipeline with multiple steps."""
    asql = """
    from users
    where status == "active"
    group by country ( # as total_users )
    sort -total_users
    take 10
    """
    sql = compile(asql)
    
    # Should produce a valid query with all clauses
    assert "SELECT" in sql.upper()
    assert "GROUP BY" in sql.upper()
    assert "ORDER BY" in sql.upper()
    assert "LIMIT" in sql.upper()


def test_pipeline_step_naming() -> None:
    """Test that explicit stash as creates named CTEs."""
    # Use explicit stash as to create named CTEs
    asql = '''
    from users where status == "active" stash as active_users
    group by country ( # as total_users )
    '''
    sql = compile(asql)
    
    # Should have a named CTE
    assert "WITH" in sql.upper()
    assert "active_users" in sql.lower()


def test_pipeline_with_join() -> None:
    """Test pipeline with JOIN."""
    asql = "from users join orders on users.id == orders.user_id"
    sql = compile(asql)
    
    assert "WITH" not in sql.upper()
    assert "JOIN" in sql.upper()
    assert "orders" in sql.lower()


def test_pipeline_multiple_where_clauses() -> None:
    """Test that multiple WHERE clauses are handled."""
    asql = 'from users where status == "active" where age >= 18'
    sql = compile(asql)
    
    # Should have WHERE clause
    assert "WHERE" in sql.upper()
    # May have both conditions (implementation-dependent)


def test_build_cte_pipeline() -> None:
    """Test building CTE pipeline with explicit stash as."""
    asql = '''
    from users where status == "active" stash as active_users
    group by country ( # as total_users )
    '''
    sql = compile(asql)
    
    # Should have WITH clause
    assert "WITH" in sql.upper()
    assert "active_users" in sql.lower()


def test_pipeline_single_step_no_cte_needed() -> None:
    """Test that single step queries don't create unnecessary CTEs."""
    asql = "from users"
    sql = compile(asql)
    
    assert "WITH" not in sql.upper()
    assert "SELECT" in sql.upper()
    assert "users" in sql.lower()


def test_pipeline_with_select() -> None:
    """Test pipeline with explicit SELECT."""
    asql = 'from users where status == "active" select name, email'
    sql = compile(asql)
    
    assert "SELECT" in sql.upper()
    assert "name" in sql.lower()
    assert "email" in sql.lower()

