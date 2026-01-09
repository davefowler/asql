"""Tests for natural language aggregate syntax in ASQL.

Natural aggregates allow more readable syntax:
- `sum of amount` → SUM(amount)
- `avg price` → AVG(price)
- `total amount` → SUM(amount)
"""

from tests.validator import ASQLValidator


class TestNaturalAggregates(ASQLValidator):
    """Test natural language aggregate syntax."""
    
    def test_sum_of(self) -> None:
        """sum of amount becomes SUM(amount)."""
        self.validate_contains(
            "from sales select sum of amount",
            "SUM", "amount"
        )
    
    def test_avg_column(self) -> None:
        """avg price becomes AVG(price)."""
        self.validate_contains(
            "from products select avg price",
            "AVG", "price"
        )
    
    def test_total_column(self) -> None:
        """total amount becomes SUM(amount)."""
        self.validate_contains(
            "from sales select total amount",
            "SUM", "amount"
        )


class TestNaturalAggregatesCrossDialect(ASQLValidator):
    """Cross-dialect natural aggregate tests."""
    
    def test_sum_of_all_dialects(self) -> None:
        """Test sum of across all dialects."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite"]:
            self.validate_contains(
                "from sales select sum of amount",
                "SUM", "amount",
                dialect=dialect
            )
