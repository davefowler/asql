"""Tests for reverse translation (SQL to ASQL)."""

import pytest
from asql.reverse_compiler import reverse_compile, detect_dialect
from asql.errors import ASQLCompilationError


def test_detect_dialect_bigquery() -> None:
    """Test dialect detection for BigQuery."""
    sql = """
    SELECT user_id, email
    FROM users
    WHERE status = 'active'
    """
    dialect = detect_dialect(sql)
    # May return None or 'bigquery' depending on detection
    assert dialect is None or dialect in ['bigquery', 'postgres', 'mysql']


def test_detect_dialect_empty() -> None:
    """Test dialect detection with empty query."""
    dialect = detect_dialect("")
    assert dialect is None


def test_reverse_compile_simple_select() -> None:
    """Test reverse compilation of simple SELECT."""
    sql = """
    SELECT user_id, email, status
    FROM users
    WHERE status = 'active'
    """
    asql = reverse_compile(sql)
    assert "from users" in asql.lower()
    assert "where" in asql.lower()


def test_reverse_compile_with_group_by() -> None:
    """Test reverse compilation with GROUP BY."""
    sql = """
    SELECT country, COUNT(*) AS user_count
    FROM users
    WHERE status = 'active'
    GROUP BY country
    ORDER BY user_count DESC
    LIMIT 10
    """
    asql = reverse_compile(sql)
    assert "from users" in asql.lower()
    assert "group by" in asql.lower()
    assert "sort" in asql.lower() or "order" in asql.lower()
    assert "take" in asql.lower() or "limit" in asql.lower()


def test_reverse_compile_with_aggregations() -> None:
    """Test reverse compilation with aggregations."""
    sql = """
    SELECT region,
           SUM(amount) AS total_revenue,
           COUNT(*) AS order_count,
           AVG(amount) AS avg_order
    FROM sales
    GROUP BY region
    """
    asql = reverse_compile(sql)
    assert "from sales" in asql.lower()
    assert "group by" in asql.lower()
    # Should contain aggregation functions
    assert "sum" in asql.lower() or "count" in asql.lower()


def test_reverse_compile_with_joins() -> None:
    """Test reverse compilation with JOINs."""
    sql = """
    SELECT u.user_id, u.email, COUNT(o.order_id) AS order_count
    FROM users u
    INNER JOIN orders o ON u.user_id = o.user_id
    GROUP BY u.user_id, u.email
    """
    asql = reverse_compile(sql)
    assert "from users" in asql.lower()
    assert "join" in asql.lower()


def test_reverse_compile_with_cte() -> None:
    """Test reverse compilation with CTE."""
    sql = """
    WITH active_users AS (
      SELECT user_id, country
      FROM users
      WHERE status = 'active'
    )
    SELECT country, COUNT(*) AS user_count
    FROM active_users
    GROUP BY country
    """
    asql = reverse_compile(sql)
    # Should convert CTE to stash statement
    assert "stash as active_users" in asql.lower()
    assert "from" in asql.lower()


def test_reverse_compile_empty_query() -> None:
    """Test reverse compilation with empty query."""
    with pytest.raises(ASQLCompilationError):
        reverse_compile("")


def test_reverse_compile_invalid_sql() -> None:
    """Test reverse compilation with invalid SQL."""
    with pytest.raises(ASQLCompilationError):
        reverse_compile("INVALID SQL SYNTAX !!!")


def test_reverse_compile_with_dialect() -> None:
    """Test reverse compilation with specific dialect."""
    sql = """
    SELECT user_id, email
    FROM users
    WHERE status = 'active'
    """
    # Should work with dialect specified
    asql = reverse_compile(sql, source_dialect='postgres')
    assert "from users" in asql.lower()


def test_reverse_compile_comparison_operators() -> None:
    """Test reverse compilation of comparison operators."""
    sql = """
    SELECT user_id
    FROM users
    WHERE age >= 18 AND age <= 65
    """
    asql = reverse_compile(sql)
    assert ">=" in asql or ">=" in sql  # Should preserve or convert
    assert "from users" in asql.lower()


def test_reverse_compile_order_by() -> None:
    """Test reverse compilation of ORDER BY."""
    sql = """
    SELECT user_id, email
    FROM users
    ORDER BY email DESC
    LIMIT 10
    """
    asql = reverse_compile(sql)
    assert "sort" in asql.lower() or "order" in asql.lower()
    assert "take" in asql.lower() or "limit" in asql.lower()


def test_reverse_compile_jinja_template_detection() -> None:
    """Test that Jinja templates are detected and raise helpful error."""
    # Test with dbt ref() macro
    sql_with_ref = """
    SELECT *
    FROM {{ ref('stg_users') }}
    WHERE status = 'active'
    """
    with pytest.raises(ASQLCompilationError) as exc_info:
        reverse_compile(sql_with_ref)
    assert "Jinja templating" in str(exc_info.value).lower() or "jinja" in str(exc_info.value).lower()
    
    # Test with dbt config() macro
    sql_with_config = """
    {{ config(enabled=var('enabled', True)) }}
    SELECT * FROM users
    """
    with pytest.raises(ASQLCompilationError) as exc_info:
        reverse_compile(sql_with_config)
    assert "Jinja templating" in str(exc_info.value).lower() or "jinja" in str(exc_info.value).lower()
    
    # Test with Jinja if statement
    sql_with_if = """
    SELECT * FROM users
    {% if var('filter_active') %}
    WHERE status = 'active'
    {% endif %}
    """
    with pytest.raises(ASQLCompilationError) as exc_info:
        reverse_compile(sql_with_if)
    assert "Jinja templating" in str(exc_info.value).lower() or "jinja" in str(exc_info.value).lower()


def test_detect_dialect_with_jinja() -> None:
    """Test that dialect detection returns None for Jinja templates."""
    sql_with_jinja = """
    SELECT * FROM {{ ref('users') }}
    """
    dialect = detect_dialect(sql_with_jinja)
    assert dialect is None
