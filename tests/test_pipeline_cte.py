"""Tests for pipeline CTE functionality."""

import pytest

from asql import compile
from asql.parser import ASQLParser
from asql.pipeline import PipelineStep


def test_simple_pipeline_single_step() -> None:
    """Test simple pipeline with just FROM."""
    asql = "from users"
    sql = compile(asql)
    
    # Should NOT generate a CTE (optimization: single simple step)
    assert "WITH" not in sql.upper()
    assert "SELECT" in sql.upper()
    assert "users" in sql.lower()  # Table name should appear


def test_pipeline_with_where() -> None:
    """Test pipeline with WHERE clause."""
    asql = 'from users where status == "active"'
    sql = compile(asql)
    
    # Should NOT generate a CTE (optimization: single merged step)
    assert "WITH" not in sql.upper()
    assert "WHERE" in sql.upper()
    assert "status" in sql.lower()
    assert "active" in sql.lower()


def test_pipeline_with_group_by() -> None:
    """Test pipeline with GROUP BY creates multiple CTEs."""
    asql = 'from users where status == "active" group by country ( # as total_users )'
    sql = compile(asql)
    
    # Should generate multiple CTEs
    assert sql.upper().count("WITH") >= 1
    # First CTE should be WHERE step
    assert "1_where" in sql.lower() or "1_where_status" in sql.lower()
    # Second CTE should be GROUP BY step
    assert "2_group_by" in sql.lower() or "2_group_by_country" in sql.lower()
    # Second CTE should reference first CTE (may be quoted)
    sql_no_spaces = sql.replace(" ", "").replace('"', "").lower()
    assert "from1_where" in sql_no_spaces or "from1_where_status" in sql_no_spaces


def test_pipeline_with_sort() -> None:
    """Test pipeline with SORT."""
    asql = 'from users where status == "active" sort -created_at'
    sql = compile(asql)
    
    # Should NOT generate a CTE (optimization: single merged step)
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
    
    # Should have multiple CTEs
    assert sql.upper().count("WITH") >= 1
    # Should have ORDER BY
    assert "ORDER BY" in sql.upper()
    # Should have LIMIT
    assert "LIMIT" in sql.upper() or "LIMIT 10" in sql


def test_pipeline_step_naming() -> None:
    """Test that step names are descriptive."""
    # Test through actual compilation
    asql = 'from users where status == "active" group by country ( # as total_users )'
    sql = compile(asql)
    
    # Should have descriptive CTE names
    assert "1_where" in sql.lower() or "1_where_status" in sql.lower()
    assert "2_group_by" in sql.lower() or "2_group_by_country" in sql.lower()


def test_pipeline_with_join() -> None:
    """Test pipeline with JOIN creates new step."""
    asql = "from users join orders on users.id == orders.user_id"
    sql = compile(asql)
    
    # Should NOT generate a CTE (optimization: FROM and JOIN merged into single step)
    assert "WITH" not in sql.upper()
    assert "JOIN" in sql.upper()
    assert "orders" in sql.lower()


def test_pipeline_multiple_where_clauses() -> None:
    """Test that multiple WHERE clauses are combined."""
    asql = 'from users where status == "active" where age >= 18'
    sql = compile(asql)
    
    # Should combine WHEREs with AND
    assert "WHERE" in sql.upper()
    assert "AND" in sql.upper()


def test_pipeline_step_identification() -> None:
    """Test that parser correctly identifies pipeline steps."""
    asql = 'from users where status == "active" group by country ( # as total_users )'
    parser = ASQLParser(asql)
    steps = parser.parse_pipeline()
    
    assert len(steps) == 2
    assert steps[0].where_clauses
    assert steps[1].group_by is not None


def test_build_cte_pipeline() -> None:
    """Test building CTE pipeline from steps."""
    # Test through actual compilation
    asql = 'from users where status == "active" group by country ( # as total_users )'
    sql = compile(asql)
    
    # Should have WITH clause with multiple CTEs
    assert "WITH" in sql.upper()
    # Should reference previous CTE (may be quoted)
    sql_no_spaces = sql.replace(" ", "").replace('"', "").lower()
    assert "from1_where" in sql_no_spaces or "from1_where_status" in sql_no_spaces


def test_pipeline_single_step_no_cte_needed() -> None:
    """Test that single step queries don't create unnecessary CTEs."""
    asql = "from users"
    sql = compile(asql)
    
    # Should NOT create CTE (optimization: single simple step)
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

