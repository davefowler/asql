"""Tests for -column DESC syntax in ORDER BY.

The - prefix before a column name in ORDER BY makes it descending:
- order by -col → ORDER BY col DESC
- order by col → ORDER BY col (ASC by default)
- order by -col1, col2 → ORDER BY col1 DESC, col2
"""

from tests.validator import ASQLValidator


class TestOrderDescBasic(ASQLValidator):
    """Test basic -column DESC syntax."""
    
    def test_simple_desc(self) -> None:
        """-col becomes col DESC (with NULLS LAST on supported dialects)."""
        self.validate_all(
            "from users order by -created_at",
            write={
                "duckdb": "SELECT * FROM users ORDER BY created_at DESC",
                "postgres": "SELECT * FROM users ORDER BY created_at DESC NULLS LAST",
                "mysql": "SELECT * FROM users ORDER BY created_at DESC",
                "sqlite": "SELECT * FROM users ORDER BY created_at DESC",
                "bigquery": "SELECT * FROM users ORDER BY created_at DESC",
                "snowflake": "SELECT * FROM users ORDER BY created_at DESC NULLS LAST",
            }
        )
    
    def test_simple_asc(self) -> None:
        """col without prefix is ASC (with NULLS FIRST on supported dialects)."""
        self.validate_all(
            "from users order by name",
            write={
                "duckdb": "SELECT * FROM users ORDER BY name NULLS FIRST",
                "postgres": "SELECT * FROM users ORDER BY name NULLS FIRST",
                "mysql": "SELECT * FROM users ORDER BY name",
                "sqlite": "SELECT * FROM users ORDER BY name",
            }
        )


class TestOrderDescMultiple(ASQLValidator):
    """Test multiple columns in ORDER BY."""
    
    def test_mixed_order(self) -> None:
        """Mixed ascending and descending."""
        self.validate_contains(
            "from users order by -created_at, name",
            "ORDER BY", "created_at", "DESC", "name"
        )
    
    def test_multiple_desc(self) -> None:
        """Multiple descending columns."""
        self.validate_contains(
            "from users order by -created_at, -updated_at",
            "ORDER BY", "created_at", "DESC", "updated_at", "DESC"
        )
    
    def test_three_columns(self) -> None:
        """Three columns with mixed order."""
        self.validate_contains(
            "from users order by -score, name, -age",
            "ORDER BY", "score", "DESC", "name", "age", "DESC"
        )


class TestOrderDescWithFunctions(ASQLValidator):
    """Test -prefix with function calls in ORDER BY."""
    
    def test_desc_with_function(self) -> None:
        """Test -function(col) for DESC."""
        self.validate_contains(
            "from users order by -month(created_at)",
            "ORDER BY", "DESC"
        )


class TestOrderDescCrossDialect(ASQLValidator):
    """Cross-dialect ORDER BY DESC tests."""
    
    def test_desc_with_limit(self) -> None:
        """Test ORDER BY DESC with LIMIT (NULLS LAST on supported dialects)."""
        self.validate_all(
            "from users order by -created_at limit 10",
            write={
                "duckdb": "SELECT * FROM users ORDER BY created_at DESC LIMIT 10",
                "postgres": "SELECT * FROM users ORDER BY created_at DESC NULLS LAST LIMIT 10",
                "mysql": "SELECT * FROM users ORDER BY created_at DESC LIMIT 10",
                "sqlite": "SELECT * FROM users ORDER BY created_at DESC LIMIT 10",
            }
        )
    
    def test_desc_with_group_by(self) -> None:
        """Test ORDER BY DESC after GROUP BY."""
        self.validate_contains(
            "from users group by country ( # as total ) order by -total",
            "GROUP BY", "ORDER BY", "total", "DESC"
        )
