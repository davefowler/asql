"""Tests for equality operator (==) in ASQL.

ASQL uses == for equality which compiles to SQL =:
- `where status == 'active'` → WHERE status = 'active'
"""

from tests.validator import ASQLValidator


class TestEqualityOperators(ASQLValidator):
    """Test equality operator transformation."""
    
    def test_double_equals(self) -> None:
        """== is tokenized as equality; compiled SQL uses =."""
        result = self.validate_contains(
            "from users where status == 'active'",
            "WHERE", "status"
        )
        assert "STATUS = " in result.upper() or "STATUS=" in result.upper()


class TestEqualityCrossDialect(ASQLValidator):
    """Cross-dialect equality tests."""
    
    def test_double_equals_all_dialects(self) -> None:
        """Test == across all dialects."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite"]:
            result = self.validate_contains(
                "from users where status == 'active'",
                "WHERE", "status",
                dialect=dialect
            )
            assert "STATUS = " in result.upper() or "STATUS=" in result.upper()
