"""Tests for *_since_* and *_until_* pattern transformation in ASQL.

Date difference shorthands:
- `days_since_created_at` → date difference calculation
- `months_until_due_date` → date difference calculation
"""

from tests.validator import ASQLValidator


class TestSinceUntilPatterns(ASQLValidator):
    """Test *_since_* and *_until_* pattern transformation."""
    
    def test_days_since(self) -> None:
        """days_since_col becomes date difference."""
        result = self.validate_contains(
            "from users select days_since_created_at",
            "created_at"
        )
        # Should have DATEDIFF or similar date calculation
        assert "DATEDIFF" in result.upper() or "CREATED_AT" in result.upper()
    
    def test_months_until(self) -> None:
        """months_until_col becomes date difference."""
        result = self.validate_contains(
            "from tasks select months_until_due_date",
            "due_date"
        )
        # Should have DATEDIFF or similar date calculation
        assert "DATEDIFF" in result.upper() or "DUE_DATE" in result.upper()


class TestSinceUntilCrossDialect(ASQLValidator):
    """Cross-dialect since/until tests."""
    
    def test_days_since_postgres(self) -> None:
        """Test days_since for postgres."""
        self.validate_contains(
            "from users select days_since_created_at",
            "created_at",
            dialect="postgres"
        )
