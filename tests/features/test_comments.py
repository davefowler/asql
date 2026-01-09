"""Tests for comment preservation in ASQL.

Comments should be preserved during compilation:
- `-- comment` → preserved (may be converted to /* */)
- `/* comment */` → preserved
"""

from tests.validator import ASQLValidator


class TestCommentPreservation(ASQLValidator):
    """Test that comments are preserved during transformation."""
    
    def test_single_line_comment(self) -> None:
        """Single-line comments are preserved (may be converted to /* */ style)."""
        result = self.validate_contains(
            "-- This is a comment\nfrom users",
            "SELECT", "FROM", "users"
        )
        # SQLGlot may convert -- to /* */
        assert "This is a comment" in result
    
    def test_multi_line_comment(self) -> None:
        """Multi-line comments are preserved."""
        result = self.validate_contains(
            "/* Comment */\nfrom users",
            "SELECT", "FROM", "users"
        )
        assert "Comment" in result


class TestCommentsCrossDialect(ASQLValidator):
    """Cross-dialect comment tests."""
    
    def test_comments_all_dialects(self) -> None:
        """Test comment preservation across all dialects."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite"]:
            result = self.validate_contains(
                "/* Test comment */\nfrom users",
                "SELECT", "FROM",
                dialect=dialect
            )
            assert "Test comment" in result
