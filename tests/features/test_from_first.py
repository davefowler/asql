"""Tests for FROM-first syntax in ASQL.

FROM-first is the core ASQL syntax:
- `from table` becomes `SELECT * FROM table`
- `from table where ...` becomes `SELECT * FROM table WHERE ...`
- `from table limit N` becomes `SELECT * FROM table LIMIT N`
"""

from tests.validator import ASQLValidator


class TestFromFirst(ASQLValidator):
    """Test FROM-first syntax."""
    
    def test_simple_from_first(self) -> None:
        """from table becomes SELECT * FROM table."""
        self.validate_contains(
            "from users",
            "SELECT", "FROM", "users"
        )
    
    def test_from_with_where(self) -> None:
        """from table where ... becomes SELECT * FROM table WHERE ..."""
        self.validate_contains(
            "from users where status = 'active'",
            "FROM", "users", "WHERE", "status"
        )
    
    def test_from_with_limit(self) -> None:
        """from table limit N becomes SELECT * FROM table LIMIT N."""
        self.validate_contains(
            "from users limit 10",
            "FROM", "users", "LIMIT", "10"
        )


class TestFromFirstCrossDialect(ASQLValidator):
    """Cross-dialect FROM-first tests."""
    
    def test_from_first_all_dialects(self) -> None:
        """Test simple from across all dialects."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite", "bigquery", "snowflake"]:
            self.validate_contains(
                "from users",
                "SELECT", "FROM", "users",
                dialect=dialect
            )
