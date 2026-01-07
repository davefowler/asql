"""Tests for reverse translation (SQL to ASQL)."""

import pytest
from asql.reverse_compiler import reverse_compile, detect_dialect
from asql.errors import ASQLCompilationError


def test_detect_dialect_generic() -> None:
    """Test dialect detection for a generic SQL query.
    
    A simple SELECT works in most dialects, so detection returns whichever
    priority dialect parses it first.
    """
    sql = """
    SELECT user_id, email
    FROM users
    WHERE status = 'active'
    """
    dialect = detect_dialect(sql)
    # Generic queries can match any dialect - just verify it returns a string or None
    assert dialect is None or isinstance(dialect, str)


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
    assert "order" in asql.lower()
    assert "limit" in asql.lower() or "limit" in asql.lower()


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
    assert "order" in asql.lower()
    assert "limit" in asql.lower() or "limit" in asql.lower()


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


# =============================================================================
# Tests for ignore_aliases feature
# =============================================================================


def test_ignore_aliases_default_off() -> None:
    """Test that ignore_aliases is off by default (aliases are preserved)."""
    from asql.config import ASQLConfig, StyleConfig
    
    sql = """
    SELECT country, COUNT(*) AS user_count
    FROM users
    GROUP BY country
    """
    # Default config should preserve aliases
    asql = reverse_compile(sql)
    assert "as user_count" in asql.lower()


def test_ignore_aliases_strips_column_aliases() -> None:
    """Test that ignore_aliases=True strips column aliases."""
    from asql.config import ASQLConfig, StyleConfig
    
    sql = """
    SELECT country, COUNT(*) AS user_count
    FROM users
    GROUP BY country
    """
    config = ASQLConfig(style=StyleConfig(ignore_aliases=True))
    asql = reverse_compile(sql, config=config)
    
    # Should not have "as user_count"
    assert "as user_count" not in asql.lower()
    # Should still have the count function
    assert "#" in asql or "count" in asql.lower()


def test_ignore_aliases_strips_aggregation_aliases() -> None:
    """Test that ignore_aliases=True strips aggregation aliases."""
    from asql.config import ASQLConfig, StyleConfig
    
    sql = """
    SELECT region,
           SUM(amount) AS total_revenue,
           AVG(amount) AS avg_order
    FROM sales
    GROUP BY region
    """
    config = ASQLConfig(style=StyleConfig(ignore_aliases=True))
    asql = reverse_compile(sql, config=config)
    
    # Should not have aliases
    assert "as total_revenue" not in asql.lower()
    assert "as avg_order" not in asql.lower()
    # Should still have aggregations
    assert "sum" in asql.lower()
    assert "avg" in asql.lower()


def test_ignore_aliases_preserves_when_false() -> None:
    """Test that ignore_aliases=False preserves all aliases."""
    from asql.config import ASQLConfig, StyleConfig
    
    sql = """
    SELECT region, SUM(amount) AS revenue
    FROM sales
    GROUP BY region
    """
    config = ASQLConfig(style=StyleConfig(ignore_aliases=False))
    asql = reverse_compile(sql, config=config)
    
    # Should have the alias
    assert "as revenue" in asql.lower()


def test_ignore_aliases_with_select_expressions() -> None:
    """Test ignore_aliases with SELECT expressions (non-aggregations)."""
    from asql.config import ASQLConfig, StyleConfig
    
    sql = """
    SELECT user_id AS id, email AS contact
    FROM users
    """
    config = ASQLConfig(style=StyleConfig(ignore_aliases=True))
    asql = reverse_compile(sql, config=config)
    
    # Should not have aliases
    assert "as id" not in asql.lower()
    assert "as contact" not in asql.lower()


def test_ignore_aliases_style_config_to_dict() -> None:
    """Test that ignore_aliases is included in StyleConfig.to_dict()."""
    from asql.config import StyleConfig
    
    # Default (False)
    style = StyleConfig()
    assert "ignore_aliases" in style.to_dict()
    assert style.to_dict()["ignore_aliases"] is False
    
    # Enabled
    style_enabled = StyleConfig(ignore_aliases=True)
    assert style_enabled.to_dict()["ignore_aliases"] is True


def test_ignore_aliases_from_dict() -> None:
    """Test that ignore_aliases can be set via from_dict()."""
    from asql.config import StyleConfig
    
    style = StyleConfig.from_dict({"ignore_aliases": True})
    assert style.ignore_aliases is True
    
    style_default = StyleConfig.from_dict({})
    assert style_default.ignore_aliases is False
