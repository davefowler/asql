"""Tests for implicit function alias expansion in ASQL.

Underscore shorthands automatically expand:
- `sum_amount` → SUM(amount) AS sum_amount
- `year_created_at` → YEAR(created_at) AS year_created_at
- `total_amount` → SUM(amount) AS total_amount
"""

from tests.validator import ASQLValidator


class TestImplicitFunctionAlias(ASQLValidator):
    """Test implicit function alias expansion."""
    
    def test_select_sum_amount(self) -> None:
        """sum_amount becomes SUM(amount) AS sum_amount."""
        result = self.validate_contains(
            "from sales select sum_amount",
            "SUM", "amount", "sum_amount"
        )
        assert "SUM(amount) AS sum_amount".upper() in result.upper()
    
    def test_select_year_created_at(self) -> None:
        """year_created_at becomes YEAR(created_at) AS year_created_at."""
        result = self.validate_contains(
            "from users select year_created_at",
            "YEAR", "created_at", "year_created_at"
        )
        assert "YEAR(created_at) AS year_created_at".upper() in result.upper()
    
    def test_select_total_amount_alias_maps_to_sum(self) -> None:
        """total_amount becomes SUM(amount) AS total_amount."""
        result = self.validate_contains(
            "from sales select total_amount",
            "SUM", "amount", "total_amount"
        )
        assert "SUM(amount) AS total_amount".upper() in result.upper()


class TestImplicitAliasCrossDialect(ASQLValidator):
    """Cross-dialect implicit alias tests."""
    
    def test_sum_amount_all_dialects(self) -> None:
        """Test sum_amount across all dialects."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite"]:
            self.validate_contains(
                "from sales select sum_amount",
                "SUM", "amount",
                dialect=dialect
            )
