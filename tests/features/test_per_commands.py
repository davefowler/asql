"""Tests for PER command in ASQL.

PER provides window function shortcuts:
- `per col first by -order` → ROW_NUMBER with QUALIFY
- `per col number by order` → ROW_NUMBER column
"""

from tests.validator import ASQLValidator


class TestPerCommands(ASQLValidator):
    """Test PER command syntax."""
    
    def test_per_first_by(self) -> None:
        """per col first by -order becomes window function with QUALIFY."""
        result = self.validate_contains(
            "from orders per customer_id first by -order_date",
            "customer_id"
        )
        assert "ROW_NUMBER" in result.upper() or "QUALIFY" in result.upper()
        assert "PARTITION BY" in result.upper() or "CUSTOMER_ID" in result.upper()
    
    def test_per_number_by(self) -> None:
        """per col number by order adds ROW_NUMBER column."""
        result = self.validate_contains(
            "from orders per customer_id number by -order_date",
            "customer_id"
        )
        assert "ROW_NUMBER" in result.upper()


class TestPerCommandsCrossDialect(ASQLValidator):
    """Cross-dialect PER command tests."""
    
    def test_per_first_by_duckdb(self) -> None:
        """Test per first by for duckdb."""
        result = self.validate_contains(
            "from orders per customer_id first by -order_date",
            "customer_id",
            dialect="duckdb"
        )
        assert "ROW_NUMBER" in result.upper() or "QUALIFY" in result.upper()
