"""Tests for when conditional expressions in ASQL.

The when expression provides a more readable CASE syntax:
- when expr is value then result → CASE WHEN expr = value THEN result END
- when expr > value then result → CASE WHEN expr > value THEN result END
- otherwise result → ELSE result
"""

from tests.validator import ASQLValidator


class TestWhenBasic(ASQLValidator):
    """Test basic when expressions."""
    
    def test_simple_when_is(self) -> None:
        """when expr is value then result."""
        # Use validate_contains instead of validate_all due to quote style differences
        for dialect in ["duckdb", "postgres", "mysql"]:
            self.validate_contains(
                'from users select when status is "active" then 1 else 0 as is_active',
                "CASE", "WHEN", "status", "active", "THEN", "1", "ELSE", "0", "END",
                dialect=dialect
            )
    
    def test_when_otherwise(self) -> None:
        """Test 'otherwise' as alternative to 'else'."""
        self.validate_contains(
            'from users select when status is "active" then 1 otherwise 0 as is_active',
            "CASE", "WHEN", "ELSE", "END"
        )


class TestWhenComparison(ASQLValidator):
    """Test when with comparison operators."""
    
    def test_when_less_than(self) -> None:
        """when expr < value then result."""
        self.validate_contains(
            'from users select when age < 18 then "minor" else "adult" as category',
            "CASE", "WHEN", "age", "<", "18", "THEN", "ELSE", "END"
        )
    
    def test_when_greater_than(self) -> None:
        """when expr > value then result."""
        self.validate_contains(
            'from products select when price > 100 then "expensive" else "affordable" as tier',
            "CASE", "WHEN", "price", ">", "100"
        )
    
    def test_when_multiple_conditions(self) -> None:
        """Multiple when branches with comparisons (comma-separated per spec)."""
        self.validate_contains(
            'from users select when age < 4 then "infant", < 12 then "child", < 18 then "teen", otherwise "adult" as age_group',
            "CASE", "WHEN", "infant", "child", "teen", "adult"
        )


class TestWhenIn(ASQLValidator):
    """Test when with IN operator."""
    
    def test_when_in_list(self) -> None:
        """when expr in (values) then result (comma-separated per spec)."""
        self.validate_contains(
            'from users select when status in ("active", "pending") then "open", in ("completed", "shipped") then "done", otherwise "unknown" as status_category',
            "CASE", "WHEN", "IN", "open", "done"
        )


class TestWhenNested(ASQLValidator):
    """Test nested when expressions."""
    
    def test_when_in_aggregation(self) -> None:
        """when inside SUM for conditional counting."""
        self.validate_contains(
            '''from orders
                group by customer_id (
                    sum(when status is "completed" then 1 otherwise 0) as completed_count
                )''',
            "SUM", "CASE", "WHEN", "completed"
        )


class TestWhenCrossDialect(ASQLValidator):
    """Cross-dialect when expression tests."""
    
    def test_when_all_dialects(self) -> None:
        """Test simple when across all dialects."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite", "bigquery", "snowflake"]:
            self.validate_contains(
                'from users select when status is "active" then 1 else 0 as flag',
                "CASE", "WHEN", "THEN", "ELSE", "END",
                dialect=dialect
            )
