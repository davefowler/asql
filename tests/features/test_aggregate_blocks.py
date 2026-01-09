"""Tests for aggregate block syntax in ASQL.

Aggregate blocks provide a cleaner GROUP BY syntax:
- `group by col (agg1, agg2)` → SELECT col, agg1, agg2 GROUP BY col
"""

from tests.validator import ASQLValidator


class TestAggregateBlocks(ASQLValidator):
    """Test aggregate block syntax."""
    
    def test_simple_aggregate_block(self) -> None:
        """group by col (agg) becomes SELECT col, agg GROUP BY col."""
        self.validate_contains(
            "from sales group by region (sum(amount) as revenue)",
            "SELECT", "GROUP BY", "region", "SUM"
        )
    
    def test_multiple_aggregates(self) -> None:
        """Multiple aggregates in block."""
        self.validate_contains(
            "from sales group by region (sum(amount) as revenue, count(*) as cnt)",
            "SUM", "COUNT", "GROUP BY"
        )


class TestAggregateBlocksCrossDialect(ASQLValidator):
    """Cross-dialect aggregate block tests."""
    
    def test_aggregate_block_all_dialects(self) -> None:
        """Test aggregate blocks across all dialects."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite"]:
            self.validate_contains(
                "from sales group by region (sum(amount) as revenue)",
                "SUM", "GROUP BY",
                dialect=dialect
            )
