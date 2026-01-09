"""Tests for multi-word function normalization in ASQL.

Multi-word functions are normalized:
- `day of week col` → DAYOFWEEK(col)
- `row number()` → ROW_NUMBER()
"""

from tests.validator import ASQLValidator


class TestFunctionSpaceNormalization(ASQLValidator):
    """Test multi-word function normalization."""
    
    def test_day_of_week_spaces(self) -> None:
        """day of week col becomes DAYOFWEEK(col)."""
        result = self.validate_contains(
            "from events select day of week created_at",
            "created_at"
        )
        assert "DAYOFWEEK" in result.upper() or "DAY_OF_WEEK" in result.upper()
    
    def test_row_number_spaces(self) -> None:
        """row number() becomes ROW_NUMBER()."""
        result = self.validate_contains(
            "from events select row number() over (order by id)",
            "ROW_NUMBER"
        )
        assert "ROW_NUMBER" in result.upper()


class TestFunctionNormalizationCrossDialect(ASQLValidator):
    """Cross-dialect function normalization tests."""
    
    def test_row_number_all_dialects(self) -> None:
        """Test row number across all dialects."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite"]:
            self.validate_contains(
                "from events select row number() over (order by id)",
                "ROW_NUMBER",
                dialect=dialect
            )
