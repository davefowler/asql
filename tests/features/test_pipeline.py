"""Tests for pipeline operator (|) in ASQL.

The pipeline operator allows chaining query operations:
- `from table | where ... | limit N`
"""

from tests.validator import ASQLValidator


class TestPipelineOperators(ASQLValidator):
    """Test pipeline operator syntax."""
    
    def test_simple_pipeline(self) -> None:
        """Pipeline operators chain query operations."""
        self.validate_contains(
            "from users | where active | limit 10",
            "FROM", "users", "WHERE", "active", "LIMIT", "10"
        )
    
    def test_pipeline_with_strings(self) -> None:
        """Pipeline operators in strings are preserved."""
        # The | inside the string should be preserved
        result = self.validate_contains(
            "from users | where name = 'test|value'",
            "FROM", "users", "WHERE", "name"
        )
        assert "test|value" in result.lower() or "'test|value'" in result


class TestPipelineCrossDialect(ASQLValidator):
    """Cross-dialect pipeline tests."""
    
    def test_pipeline_all_dialects(self) -> None:
        """Test pipeline across all dialects."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite"]:
            self.validate_contains(
                "from users | where active | limit 5",
                "FROM", "WHERE", "LIMIT",
                dialect=dialect
            )
