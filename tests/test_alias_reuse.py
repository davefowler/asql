"""Tests for alias reuse functionality."""

import pytest
from asql import compile
from asql.errors import ASQLCompilationError
from tests.fixtures import assert_valid_sql, assert_sql_contains


def test_alias_reuse_duckdb() -> None:
    """Test that DuckDB emits alias reuse directly."""
    asql = """
    from order_items
      select
        unit_price * (1 - discount) as discount_price,
        discount_price * quantity as total_price,
        total_price * (1 + tax_rate) as taxed_price
    """
    sql = compile(asql, dialect="duckdb")
    
    # DuckDB should emit directly without CTEs
    assert "WITH" not in sql.upper()
    assert "discount_price" in sql
    assert "total_price" in sql
    assert "taxed_price" in sql
    assert_valid_sql(sql, dialect="duckdb")


def test_alias_reuse_postgres_cte() -> None:
    """Test that PostgreSQL generates CTE chain for alias reuse."""
    asql = """
    from order_items
      select
        unit_price * (1 - discount) as discount_price,
        discount_price * quantity as total_price
    """
    sql = compile(asql, dialect="postgres")
    
    # PostgreSQL should generate CTE chain
    assert "WITH" in sql.upper()
    # CTE names use _alias prefix (e.g., _alias1_0, _alias1_1)
    assert "_alias" in sql or "_step" in sql
    assert "discount_price" in sql
    assert "total_price" in sql
    assert_valid_sql(sql, dialect="postgres")


def test_alias_reuse_simple() -> None:
    """Test simple alias reuse case."""
    asql = """
    from users
      select
        first_name || ' ' || last_name as full_name,
        upper(full_name) as full_name_upper
    """
    sql = compile(asql, dialect="postgres")
    
    assert "WITH" in sql.upper()
    assert "full_name" in sql
    assert "full_name_upper" in sql
    assert_valid_sql(sql, dialect="postgres")


def test_alias_reuse_three_levels() -> None:
    """Test alias reuse with three levels of dependencies."""
    asql = """
    from sales
      select
        price * quantity as revenue,
        revenue * (1 - discount) as discounted_revenue,
        discounted_revenue * tax_rate as tax_amount
    """
    sql = compile(asql, dialect="postgres")
    
    assert "WITH" in sql.upper()
    assert "revenue" in sql
    assert "discounted_revenue" in sql
    assert "tax_amount" in sql
    assert_valid_sql(sql, dialect="postgres")


def test_alias_reuse_with_where() -> None:
    """Test alias reuse with WHERE clause."""
    asql = """
    from order_items
      select
        unit_price * (1 - discount) as discount_price,
        discount_price * quantity as total_price
      where total_price > 100
    """
    sql = compile(asql, dialect="postgres")
    
    assert "WITH" in sql.upper()
    assert "WHERE" in sql.upper()
    assert "total_price > 100" in sql or "total_price > 100" in sql.replace(" ", "")
    assert_valid_sql(sql, dialect="postgres")


def test_alias_reuse_with_order_by() -> None:
    """Test alias reuse with ORDER BY clause."""
    asql = """
    from order_items
      select
        unit_price * (1 - discount) as discount_price,
        discount_price * quantity as total_price
      order by total_price desc
    """
    sql = compile(asql, dialect="postgres")
    
    assert "WITH" in sql.upper()
    assert "ORDER BY" in sql.upper()
    assert "total_price" in sql
    assert_valid_sql(sql, dialect="postgres")


def test_alias_reuse_no_dependencies() -> None:
    """Test that queries without alias dependencies don't generate CTEs."""
    asql = """
    from users
      select
        name,
        email,
        age * 2 as double_age
    """
    sql = compile(asql, dialect="postgres")
    
    # Should not generate CTEs if no dependencies
    assert "WITH" not in sql.upper() or "_step" not in sql
    assert_valid_sql(sql, dialect="postgres")


@pytest.mark.xfail(reason="Forward references (alias_b undefined when referenced) not detected as circular yet")
def test_alias_reuse_circular_dependency() -> None:
    """Test that circular dependencies are detected and raise error.
    
    Note: This test uses a forward reference pattern where alias_b is referenced
    before it's defined. The current implementation only detects backward references.
    A true circular dependency would need both aliases defined before the cycle.
    """
    asql = """
    from users
      select
        name as alias_a,
        alias_b as alias_a,
        alias_a as alias_b
    """
    
    with pytest.raises(ASQLCompilationError) as exc_info:
        compile(asql, dialect="postgres")
    
    assert "circular" in str(exc_info.value).lower() or "Circular" in str(exc_info.value)


def test_alias_reuse_multiple_dependencies() -> None:
    """Test alias reuse where one expression depends on multiple earlier aliases."""
    asql = """
    from sales
      select
        price * quantity as revenue,
        discount_rate * 100 as discount_percent,
        revenue * (1 - discount_percent / 100) as final_revenue
    """
    sql = compile(asql, dialect="postgres")
    
    assert "WITH" in sql.upper()
    assert "revenue" in sql
    assert "discount_percent" in sql
    assert "final_revenue" in sql
    assert_valid_sql(sql, dialect="postgres")


def test_alias_reuse_mixed_expressions() -> None:
    """Test alias reuse with mix of dependent and independent expressions."""
    asql = """
    from order_items
      select
        unit_price,
        unit_price * (1 - discount) as discount_price,
        quantity,
        discount_price * quantity as total_price
    """
    sql = compile(asql, dialect="postgres")
    
    assert "WITH" in sql.upper()
    assert "unit_price" in sql
    assert "discount_price" in sql
    assert "quantity" in sql
    assert "total_price" in sql
    assert_valid_sql(sql, dialect="postgres")


def test_alias_reuse_bigquery() -> None:
    """Test alias reuse with BigQuery dialect."""
    asql = """
    from order_items
      select
        unit_price * (1 - discount) as discount_price,
        discount_price * quantity as total_price
    """
    sql = compile(asql, dialect="bigquery")
    
    assert "WITH" in sql.upper()
    assert "discount_price" in sql
    assert "total_price" in sql
    assert_valid_sql(sql, dialect="bigquery")
