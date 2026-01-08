"""Tests for date literal and relative date syntax in ASQL.

Date handling features:
- @2024-01-15 → DATE '2024-01-15' (date literal)
- @2024-01-15T10:30:00 → TIMESTAMP (timestamp literal)
- 7 days ago → CURRENT_DATE - INTERVAL '7' DAY
- 3 days from now → CURRENT_DATE + INTERVAL '3' DAY
- col + 7 days → col + INTERVAL '7' DAY (date arithmetic)
"""

from tests.validator import ASQLValidator


class TestDateLiterals(ASQLValidator):
    """Test @date literal syntax."""
    
    def test_date_literal(self) -> None:
        """@2024-01-15 becomes DATE literal."""
        self.validate_contains(
            "from users where created_at >= @2024-01-15",
            "2024-01-15"
        )
    
    def test_timestamp_literal(self) -> None:
        """@2024-01-15T10:30:00 becomes TIMESTAMP."""
        self.validate_contains(
            "from users where created_at >= @2024-01-15T10:30:00",
            "2024-01-15"
        )


class TestRelativeDates(ASQLValidator):
    """Test relative date syntax."""
    
    def test_days_ago(self) -> None:
        """7 days ago becomes CURRENT_DATE - INTERVAL."""
        self.validate_contains(
            "from users where created_at >= 7 days ago",
            "INTERVAL", "7"
        )
    
    def test_month_ago(self) -> None:
        """1 month ago becomes CURRENT_DATE - INTERVAL."""
        self.validate_contains(
            "from users where created_at >= 1 month ago",
            "INTERVAL"
        )
    
    def test_days_from_now(self) -> None:
        """3 days from now becomes CURRENT_DATE + INTERVAL."""
        self.validate_contains(
            "from tasks where due_date <= 3 days from now",
            "INTERVAL", "+", "3"
        )


class TestDateArithmetic(ASQLValidator):
    """Test date arithmetic syntax."""
    
    def test_add_days(self) -> None:
        """col + 7 days becomes col + INTERVAL."""
        self.validate_contains(
            "from orders select order_date + 7 days as delivery_date",
            "INTERVAL", "7"
        )
    
    def test_subtract_month(self) -> None:
        """col - 1 month becomes col - INTERVAL."""
        self.validate_contains(
            "from events select event_date - 1 month as last_month",
            "INTERVAL"
        )


class TestDateFunctionsCrossDialect(ASQLValidator):
    """Cross-dialect date function tests."""
    
    def test_relative_date_cross_dialect(self) -> None:
        """Test relative date across dialects."""
        # Just verify it compiles - exact syntax varies by dialect
        for dialect in ["duckdb", "postgres", "mysql", "sqlite"]:
            self.validate_contains(
                "from users where created_at >= 7 days ago",
                "INTERVAL",
                dialect=dialect
            )
