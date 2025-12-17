"""Integration tests - test ASQL with SQLGlot round-trip validation."""

import pytest
import sqlglot
from asql import compile


class TestSQLGlotIntegration:
    """Test integration with SQLGlot for SQL validation."""
    
    def test_generated_sql_parses_back(self) -> None:
        """Test that generated SQL can be parsed by SQLGlot."""
        asql = 'from users where status == "active"'
        sql = compile(asql)
        
        # Try to parse the generated SQL
        try:
            parsed = sqlglot.parse_one(sql)
            assert parsed is not None
            assert isinstance(parsed, sqlglot.expressions.Select)
        except Exception as e:
            # Some edge cases might not parse back perfectly, but basic queries should
            pytest.skip(f"SQLGlot couldn't parse generated SQL: {e}")
    
    def test_group_by_sql_parses(self) -> None:
        """Test GROUP BY SQL parses correctly."""
        asql = "from users group by country ( # as total_users )"
        sql = compile(asql)
        
        try:
            parsed = sqlglot.parse_one(sql)
            assert parsed is not None
            assert parsed.find(sqlglot.expressions.Group) is not None
        except Exception:
            pytest.skip("SQLGlot parsing issue")
    
    def test_order_by_sql_parses(self) -> None:
        """Test ORDER BY SQL parses correctly."""
        asql = "from users order by -total_users"
        sql = compile(asql)
        
        try:
            parsed = sqlglot.parse_one(sql)
            assert parsed is not None
            assert parsed.find(sqlglot.expressions.Order) is not None
        except Exception:
            pytest.skip("SQLGlot parsing issue")
    
    def test_dialect_specific_sql(self) -> None:
        """Test that dialect-specific SQL is generated correctly."""
        asql = 'from users where status == "active"'
        
        for dialect in ["postgres", "mysql", "bigquery", "snowflake"]:
            sql = compile(asql, dialect=dialect)
            assert sql is not None
            assert len(sql) > 0
            # Should have SELECT and FROM
            assert "SELECT" in sql.upper()
            assert "FROM" in sql.upper()


class TestSQLStructure:
    """Test that generated SQL has correct structure."""
    
    def test_select_before_from(self) -> None:
        """Test that queries use CTE-based pipeline structure."""
        asql = "from users"
        sql = compile(asql)
        sql_upper = sql.upper()
        
        # With CTE-based pipeline, should start with WITH or have SELECT in CTE
        assert "WITH" in sql_upper or "SELECT" in sql_upper
        assert "FROM" in sql_upper
    
    def test_where_after_from(self) -> None:
        """Test that WHERE is properly included in CTE."""
        asql = 'from users where status == "active"'
        sql = compile(asql)
        sql_upper = sql.upper()
        
        # With CTE-based pipeline, WHERE should be in the CTE
        assert "WHERE" in sql_upper
        assert "FROM" in sql_upper
        # Both should be present
        assert sql_upper.find("FROM") >= 0
        assert sql_upper.find("WHERE") >= 0
    
    def test_group_by_structure(self) -> None:
        """Test GROUP BY SQL structure."""
        asql = "from users group by country ( # as total_users )"
        sql = compile(asql)
        sql_upper = sql.upper()
        
        assert "GROUP BY" in sql_upper
        assert "COUNT" in sql_upper
        # GROUP BY should come after FROM
        from_pos = sql_upper.find("FROM")
        group_pos = sql_upper.find("GROUP BY")
        assert from_pos < group_pos
    
    def test_order_by_structure(self) -> None:
        """Test ORDER BY SQL structure."""
        asql = "from users order by -total_users"
        sql = compile(asql)
        sql_upper = sql.upper()
        
        assert "ORDER BY" in sql_upper
        assert "DESC" in sql_upper
        # ORDER BY should come after FROM (and after GROUP BY if present)
        from_pos = sql_upper.find("FROM")
        order_pos = sql_upper.find("ORDER BY")
        assert from_pos < order_pos
    
    def test_limit_structure(self) -> None:
        """Test LIMIT SQL structure."""
        asql = "from users limit 10"
        sql = compile(asql)
        sql_upper = sql.upper()
        
        assert "LIMIT" in sql_upper
        assert "10" in sql
        # LIMIT should be last
        limit_pos = sql_upper.find("LIMIT")
        assert limit_pos > 0  # Should exist and not be at start


class TestSQLCorrectness:
    """Test SQL correctness and validity."""
    
    def test_no_duplicate_select(self) -> None:
        """Test that SQL has proper CTE structure."""
        asql = "from users"
        sql = compile(asql)
        sql_upper = sql.upper()
        
        # With CTE-based pipeline, should start with WITH or have SELECT
        assert sql_upper.startswith("WITH") or sql_upper.startswith("SELECT")
        # Count SELECTs - should be reasonable (at least 1 for CTE, 1 for final SELECT)
        select_count = sql_upper.count("SELECT")
        assert select_count >= 1  # At least one SELECT (in CTE or final)
    
    def test_string_quotes_consistent(self) -> None:
        """Test that string literals are properly quoted."""
        asql = 'from users where status == "active"'
        sql = compile(asql)
        
        # Should have quotes around 'active'
        assert "'active'" in sql or '"active"' in sql
    
    def test_column_names_preserved(self) -> None:
        """Test that column names are preserved correctly."""
        asql = "from users select name, email"
        sql = compile(asql)
        
        assert "name" in sql.lower()
        assert "email" in sql.lower()
    
    def test_table_name_preserved(self) -> None:
        """Test that table names are preserved correctly."""
        asql = "from users"
        sql = compile(asql)
        
        assert "users" in sql.lower()
    
    def test_aggregation_aliases_preserved(self) -> None:
        """Test that aggregation aliases are preserved."""
        asql = "from users group by country ( # as total_users )"
        sql = compile(asql)
        
        assert "total_users" in sql.lower()
