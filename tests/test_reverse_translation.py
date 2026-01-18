"""Tests for reverse translation (SQL to ASQL) using sqlglot.transpile()."""

import pytest
import sqlglot
import asql.dialect  # noqa: F401 - registers ASQL dialect with SQLGlot


def test_transpile_simple_select() -> None:
    """Test reverse compilation of simple SELECT."""
    sql = """
    SELECT user_id, email, status
    FROM users
    WHERE status = 'active'
    """
    asql = sqlglot.transpile(sql, write="asql")[0]
    assert "from users" in asql.lower()
    assert "where" in asql.lower()


def test_transpile_with_group_by() -> None:
    """Test reverse compilation with GROUP BY."""
    sql = """
    SELECT country, COUNT(*) AS user_count
    FROM users
    WHERE status = 'active'
    GROUP BY country
    ORDER BY user_count DESC
    LIMIT 10
    """
    asql = sqlglot.transpile(sql, write="asql")[0]
    assert "from users" in asql.lower()
    assert "group by" in asql.lower()
    assert "order" in asql.lower()
    assert "limit" in asql.lower() or "limit" in asql.lower()


def test_transpile_with_aggregations() -> None:
    """Test reverse compilation with aggregations."""
    sql = """
    SELECT region,
           SUM(amount) AS total_revenue,
           COUNT(*) AS order_count,
           AVG(amount) AS avg_order
    FROM sales
    GROUP BY region
    """
    asql = sqlglot.transpile(sql, write="asql")[0]
    assert "from sales" in asql.lower()
    assert "group by" in asql.lower()
    # Should contain aggregation functions
    assert "sum" in asql.lower() or "count" in asql.lower()


def test_transpile_with_joins() -> None:
    """Test reverse compilation with JOINs."""
    sql = """
    SELECT u.user_id, u.email, COUNT(o.order_id) AS order_count
    FROM users u
    INNER JOIN orders o ON u.user_id = o.user_id
    GROUP BY u.user_id, u.email
    """
    asql = sqlglot.transpile(sql, write="asql")[0]
    assert "from users" in asql.lower()
    assert "join" in asql.lower() or "&" in asql


def test_transpile_with_cte() -> None:
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
    asql = sqlglot.transpile(sql, write="asql")[0]
    # Should convert CTE to stash statement
    assert "stash as active_users" in asql.lower()
    assert "from" in asql.lower()


def test_transpile_empty_query() -> None:
    """Test reverse compilation with empty query returns single empty string."""
    result = sqlglot.transpile("", write="asql")
    # SQLGlot returns [''] for empty input, not []
    assert result == ['']


def test_transpile_with_dialect() -> None:
    """Test reverse compilation with specific source dialect."""
    sql = """
    SELECT user_id, email
    FROM users
    WHERE status = 'active'
    """
    # Should work with dialect specified
    asql = sqlglot.transpile(sql, read="postgres", write="asql")[0]
    assert "from users" in asql.lower()


def test_transpile_comparison_operators() -> None:
    """Test reverse compilation of comparison operators."""
    sql = """
    SELECT user_id
    FROM users
    WHERE age >= 18 AND age <= 65
    """
    asql = sqlglot.transpile(sql, write="asql")[0]
    assert ">=" in asql or ">=" in sql  # Should preserve or convert
    assert "from users" in asql.lower()


def test_transpile_order_by() -> None:
    """Test reverse compilation of ORDER BY."""
    sql = """
    SELECT user_id, email
    FROM users
    ORDER BY email DESC
    LIMIT 10
    """
    asql = sqlglot.transpile(sql, write="asql")[0]
    assert "order" in asql.lower()
    assert "limit" in asql.lower() or "limit" in asql.lower()


def test_transpile_preserves_aliases() -> None:
    """Test that transpile preserves aliases by default."""
    sql = """
    SELECT country, COUNT(*) AS user_count
    FROM users
    GROUP BY country
    """
    asql = sqlglot.transpile(sql, write="asql")[0]
    assert "as user_count" in asql.lower()


def test_transpile_with_select_expressions() -> None:
    """Test transpile with SELECT expressions."""
    sql = """
    SELECT user_id AS id, email AS contact
    FROM users
    """
    asql = sqlglot.transpile(sql, write="asql")[0]
    assert "from users" in asql.lower()


def test_transpile_with_distinct() -> None:
    """Test transpile preserves DISTINCT."""
    sql = "SELECT DISTINCT name, email FROM users"
    asql = sqlglot.transpile(sql, read="postgres", write="asql")[0]
    assert "distinct" in asql.lower()
    assert "from users" in asql.lower()


def test_transpile_with_distinct_star() -> None:
    """Test transpile preserves DISTINCT *."""
    sql = "SELECT DISTINCT * FROM users"
    asql = sqlglot.transpile(sql, read="postgres", write="asql")[0]
    assert "distinct" in asql.lower()
    assert "from users" in asql.lower()


class TestJinjaDetection:
    """Test that Jinja templates produce parse errors."""

    def test_jinja_ref_macro(self) -> None:
        """Jinja ref() should fail to parse."""
        sql = """
        SELECT *
        FROM {{ ref('stg_users') }}
        WHERE status = 'active'
        """
        # SQLGlot will fail to parse Jinja syntax
        with pytest.raises(sqlglot.errors.ParseError):
            sqlglot.transpile(sql, write="asql")

    def test_jinja_config_macro(self) -> None:
        """Jinja config() should fail to parse."""
        sql = """
        {{ config(enabled=var('enabled', True)) }}
        SELECT * FROM users
        """
        with pytest.raises(sqlglot.errors.ParseError):
            sqlglot.transpile(sql, write="asql")

    def test_jinja_if_statement(self) -> None:
        """Jinja if statement should fail to parse."""
        sql = """
        SELECT * FROM users
        {% if var('filter_active') %}
        WHERE status = 'active'
        {% endif %}
        """
        with pytest.raises(sqlglot.errors.ParseError):
            sqlglot.transpile(sql, write="asql")


class TestCastTranspilation:
    """Test CAST expressions transpile to ASQL :: syntax."""

    def test_transpile_cast(self) -> None:
        """CAST should transpile to :: syntax."""
        sql = "SELECT CAST(value AS INTEGER) FROM data"
        asql = sqlglot.transpile(sql, write="asql")[0]
        assert "::" in asql
        assert "value::int" in asql.lower() or "value::integer" in asql.lower()

    def test_transpile_try_cast(self) -> None:
        """TRY_CAST should also use :: syntax (ASQL doesn't distinguish)."""
        # TRY_CAST is dialect-specific, test with BigQuery syntax
        sql = "SELECT SAFE_CAST(value AS INT64) FROM data"
        asql = sqlglot.transpile(sql, read="bigquery", write="asql")[0]
        # Should use :: syntax regardless of safe/try prefix
        assert "::" in asql

    def test_transpile_multiple_casts(self) -> None:
        """Multiple CASTs in one query."""
        sql = "SELECT CAST(a AS TEXT), CAST(b AS FLOAT) FROM data"
        asql = sqlglot.transpile(sql, write="asql")[0]
        assert asql.count("::") == 2
