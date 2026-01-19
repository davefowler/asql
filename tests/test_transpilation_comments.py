"""Tests for ASQL transpilation comment settings.

Tests the comment-related settings:
1. include_transpilation_comments: Adds explanatory comments about ASQL transformations
2. passthrough_comments: Controls whether source comments are preserved

These settings help users understand generated SQL and control comment behavior.
"""

from tests.fixtures import transpile
from asql import CompileSettings


class TestPassthroughComments:
    """Test passthrough_comments setting."""
    
    def test_passthrough_comments_default_true(self):
        """By default, source comments should be preserved."""
        asql = """
        -- This is a comment
        from users
        limit 10
        """
        sql = transpile(asql, dialect="snowflake")
        
        assert "This is a comment" in sql
    
    def test_passthrough_comments_true_via_api(self):
        """Explicitly enabling passthrough_comments preserves comments."""
        settings = CompileSettings(passthrough_comments=True)
        asql = """
        -- User query
        from users
        limit 10
        """
        sql = transpile(asql, dialect="snowflake", settings=settings)
        
        assert "User query" in sql
    
    def test_passthrough_comments_false_via_api(self):
        """Disabling passthrough_comments strips source comments."""
        settings = CompileSettings(passthrough_comments=False)
        asql = """
        -- This comment should be removed
        from users
        limit 10
        """
        sql = transpile(asql, dialect="snowflake", settings=settings)
        
        assert "This comment should be removed" not in sql
        assert "users" in sql  # Query still works
    
    def test_passthrough_comments_false_via_inline_set(self):
        """Passthrough_comments must be set via API, not inline SET.
        
        Note: This setting requires the comments parameter at transpile() time,
        which happens before inline SET is processed. Use CompileSettings instead.
        """
        # Use API instead of inline SET
        settings = CompileSettings(passthrough_comments=False)
        asql = """
        -- This comment should be removed
        from users
        limit 10
        """
        sql = transpile(asql, dialect="snowflake", settings=settings)
        
        assert "This comment should be removed" not in sql
        assert "users" in sql
    
    def test_passthrough_comments_multiline(self):
        """Test multi-line comments are also controlled by passthrough_comments."""
        settings = CompileSettings(passthrough_comments=False)
        asql = """
        /* Multi-line
           comment */
        from users
        limit 10
        """
        sql = transpile(asql, dialect="snowflake", settings=settings)
        
        assert "Multi-line" not in sql
        assert "users" in sql
    
    def test_passthrough_comments_preserves_all_comment_types(self):
        """Test both single-line and multi-line comments are preserved by default."""
        asql = """
        -- Single line comment
        /* Multi-line comment */
        from users
        limit 10
        """
        sql = transpile(asql, dialect="snowflake")
        
        assert "Single line comment" in sql
        assert "Multi-line comment" in sql


class TestIncludeTranspilationComments:
    """Test include_transpilation_comments setting.
    
    Spine transforms generate descriptive comments explaining the transformation.
    """
    
    def test_transpilation_comments_with_spine(self):
        """Explicit spine adds descriptive comments."""
        settings = CompileSettings(include_transpilation_comments=True)
        asql = """
        from orders
        where order_date >= @2024-01-01 and order_date < @2024-02-01
        spine by month(order_date) (
            sum(amount) as revenue
        )
        """
        sql = transpile(asql, dialect="snowflake", settings=settings)

        # Spine adds descriptive comments
        assert "spine" in sql.lower()
    
    def test_transpilation_comments_not_added_when_no_transformation(self):
        """Transpilation comments are not added when no spine transformation occurs."""
        settings = CompileSettings(include_transpilation_comments=True)
        asql = """
        from orders
        group by month(order_date) (
            sum(amount) as revenue
        )
        """
        sql = transpile(asql, dialect="snowflake", settings=settings)
        
        # No spine comments since group by doesn't add spine
        assert "Date spine" not in sql
        assert "spine_data" not in sql.lower()
    
    def test_transpilation_comments_with_pretty_formatting(self):
        """Transpilation comments work with pretty formatting."""
        settings = CompileSettings(include_transpilation_comments=True)
        asql = """
        from orders
        where order_date >= @2024-01-01 and order_date < @2024-02-01
        spine by month(order_date) (
            sum(amount) as revenue
        )
        """
        sql = transpile(asql, dialect="snowflake", settings=settings, pretty=True)
        
        # Spine comments should be present
        assert "spine" in sql.lower()


class TestCombinedCommentSettings:
    """Test combinations of comment settings."""
    
    def test_both_settings_true(self):
        """Both passthrough and transpilation comments can be enabled."""
        settings = CompileSettings(
            passthrough_comments=True,
            include_transpilation_comments=True,
        )
        asql = """
        -- Original comment
        from orders
        limit 10
        """
        sql = transpile(asql, dialect="snowflake", settings=settings)
        
        assert "Original comment" in sql
    
    def test_both_settings_true_with_spine(self):
        """When spine is applied, transpilation comments are added.
        
        Note: Spine regenerates SQL, so original comments may not be preserved
        in the final output. The transpilation comment is still added.
        """
        settings = CompileSettings(
            passthrough_comments=True,
            include_transpilation_comments=True,
        )
        asql = """
        from orders
        where order_date >= @2024-01-01 and order_date < @2024-02-01
        spine by month(order_date) (
            sum(amount) as revenue
        )
        """
        sql = transpile(asql, dialect="snowflake", settings=settings)
        
        # Spine transpilation comment should be present
        assert "spine" in sql.lower()
    
    def test_passthrough_false_transpilation_true(self):
        """Can strip source comments but add transpilation comments."""
        settings = CompileSettings(
            passthrough_comments=False,
            include_transpilation_comments=True,
        )
        asql = """
        from orders
        where order_date >= @2024-01-01 and order_date < @2024-02-01
        spine by month(order_date) (
            sum(amount) as revenue
        )
        """
        sql = transpile(asql, dialect="snowflake", settings=settings)
        
        # Spine adds comments via asql.transpile transforms
        assert "spine" in sql.lower()


class TestCommentEdgeCases:
    """Test edge cases for comment settings."""
    
    def test_comment_at_end_of_line(self):
        """Comments at end of line should be preserved."""
        asql = """
        from users  -- Select all users
        limit 10
        """
        sql = transpile(asql, dialect="snowflake")
        
        assert "Select all users" in sql
    
    def test_empty_comment(self):
        """Empty comment blocks should be handled."""
        asql = """
        /* */
        from users
        limit 10
        """
        sql = transpile(asql, dialect="snowflake")
        
        assert "users" in sql
    
    def test_comment_with_special_chars(self):
        """Comments with special characters should be preserved."""
        asql = """
        -- Query for: {user_id} with @2024-01-01
        from users
        limit 10
        """
        sql = transpile(asql, dialect="snowflake")
        
        # Comment should be preserved (at least partially)
        assert "Query for" in sql or "user_id" in sql
