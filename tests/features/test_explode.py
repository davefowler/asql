"""Tests for explode clause in ASQL.

Explode expands arrays into rows:
- `explode array as item` → UNNEST/CROSS JOIN/FLATTEN depending on dialect
"""

from tests.validator import ASQLValidator


class TestExplode(ASQLValidator):
    """Test explode clause transformation."""
    
    def test_explode_basic(self) -> None:
        """explode compiles to UNNEST/CROSS JOIN."""
        result = self.validate_contains(
            "from posts explode tags as tag",
            "tag"
        )
        # Default dialect uses UNNEST
        assert "UNNEST" in result.upper() or "CROSS JOIN" in result.upper()
    
    def test_explode_with_select(self) -> None:
        """explode with explicit select."""
        result = self.validate_contains(
            "from posts explode tags as tag select id, tag",
            "id", "tag"
        )
        assert "UNNEST" in result.upper() or "CROSS JOIN" in result.upper()
    
    def test_explode_with_function(self) -> None:
        """explode with split function."""
        result = self.validate_contains(
            "from posts explode split(tags_csv, ',') as tag",
            "tag"
        )
        assert "UNNEST" in result.upper() or "CROSS JOIN" in result.upper()


class TestExplodeCrossDialect(ASQLValidator):
    """Cross-dialect explode tests."""
    
    def test_explode_postgres(self) -> None:
        """explode compiles to UNNEST for postgres."""
        result = self.validate_contains(
            "from posts explode tags as tag select id, tag",
            "UNNEST",
            dialect="postgres"
        )
        assert "UNNEST(tags)" in result
        assert "AS tag" in result
    
    def test_explode_bigquery(self) -> None:
        """explode compiles to UNNEST for bigquery."""
        result = self.validate_contains(
            "from posts explode tags as tag select id, tag",
            "UNNEST",
            dialect="bigquery"
        )
        assert "UNNEST(tags)" in result
    
    def test_explode_snowflake(self) -> None:
        """explode compiles to FLATTEN for snowflake."""
        result = self.validate_contains(
            "from posts explode tags as tag select id, tag",
            "FLATTEN",
            dialect="snowflake"
        )
        assert "FLATTEN" in result
        assert "tag" in result.lower()
