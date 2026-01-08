"""Tests for sample clause in ASQL.

Sample syntax:
- sample N → ORDER BY RANDOM() LIMIT N (fixed sample)
- sample N% → TABLESAMPLE BERNOULLI(N) (percentage sample)
- sample N per col → stratified sampling with ROW_NUMBER() PARTITION BY
"""

from tests.validator import ASQLValidator


class TestSampleFixed(ASQLValidator):
    """Test fixed sample size (sample N)."""
    
    def test_sample_fixed_n(self) -> None:
        """sample N becomes ORDER BY RANDOM() LIMIT N."""
        # Different dialects may use RANDOM() or RAND()
        self.validate_contains(
            "from orders sample 100",
            "ORDER BY", "LIMIT", "100"
        )
    
    def test_sample_fixed_with_where(self) -> None:
        """sample N with WHERE clause."""
        self.validate_contains(
            "from orders where status = 'active' sample 50",
            "WHERE", "ORDER BY", "LIMIT", "50"
        )
    
    def test_sample_with_select(self) -> None:
        """sample with explicit SELECT - sample should come before select."""
        # Note: sample should be placed after FROM, not after SELECT
        self.validate_contains(
            "from orders sample 25 select id, amount",
            "ORDER BY", "LIMIT", "25", "id", "amount"
        )


class TestSamplePercentage(ASQLValidator):
    """Test percentage sampling (sample N%)."""
    
    def test_sample_percentage(self) -> None:
        """sample N% becomes TABLESAMPLE BERNOULLI(N)."""
        self.validate_contains(
            "from orders sample 10%",
            "TABLESAMPLE", "BERNOULLI"
        )
    
    def test_sample_percentage_decimal(self) -> None:
        """sample with decimal percentage."""
        self.validate_contains(
            "from orders sample 0.5%",
            "TABLESAMPLE", "0.5"
        )


class TestSampleStratified(ASQLValidator):
    """Test stratified sampling (sample N per col)."""
    
    def test_sample_stratified(self) -> None:
        """sample N per col becomes window function with QUALIFY."""
        self.validate_contains(
            "from orders sample 100 per category",
            "QUALIFY", "ROW_NUMBER()", "PARTITION BY", "CATEGORY"
        )
    
    def test_sample_stratified_with_underscore_column(self) -> None:
        """Stratified sample with underscore column name."""
        self.validate_contains(
            "from orders sample 50 per product_category",
            "PARTITION BY", "PRODUCT_CATEGORY"
        )


class TestSampleCrossDialect(ASQLValidator):
    """Cross-dialect sample tests."""
    
    def test_sample_fixed_all_dialects(self) -> None:
        """Fixed sample across dialects - RANDOM() or RAND() depending on dialect."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite"]:
            self.validate_contains(
                "from orders sample 100",
                "ORDER BY", "LIMIT",
                dialect=dialect
            )
