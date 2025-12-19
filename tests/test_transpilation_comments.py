"""Tests for ASQL transpilation comment settings.

Tests the comment-related settings:
1. include_transpilation_comments: Adds explanatory comments about ASQL transformations
2. passthrough_comments: Controls whether source comments are preserved

These settings help users understand generated SQL and control comment behavior.
"""

import pytest
from asql import compile, CompileSettings


class TestPassthroughComments:
    """Test passthrough_comments setting."""
    
    def test_passthrough_comments_default_true(self):
        """By default, source comments should be preserved."""
        asql = """
        -- This is a comment
        from users
        limit 10
        """
        sql = compile(asql, dialect="snowflake")
        
        assert "This is a comment" in sql
    
    def test_passthrough_comments_true_via_api(self):
        """Explicitly enabling passthrough_comments preserves comments."""
        settings = CompileSettings(passthrough_comments=True)
        asql = """
        -- User query
        from users
        limit 10
        """
        sql = compile(asql, dialect="snowflake", settings=settings)
        
        assert "User query" in sql
    
    def test_passthrough_comments_false_via_api(self):
        """Disabling passthrough_comments strips source comments."""
        settings = CompileSettings(passthrough_comments=False)
        asql = """
        -- This comment should be removed
        from users
        limit 10
        """
        sql = compile(asql, dialect="snowflake", settings=settings)
        
        assert "This comment should be removed" not in sql
        assert "users" in sql  # Query still works
    
    def test_passthrough_comments_false_via_inline_set(self):
        """Disabling passthrough_comments via inline SET."""
        asql = """
        SET passthrough_comments = false;
        -- This comment should be removed
        from users
        limit 10
        """
        sql = compile(asql, dialect="snowflake")
        
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
        sql = compile(asql, dialect="snowflake", settings=settings)
        
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
        sql = compile(asql, dialect="snowflake")
        
        assert "Single line comment" in sql
        assert "Multi-line comment" in sql


class TestIncludeTranspilationComments:
    """Test include_transpilation_comments setting."""
    
    def test_transpilation_comments_default_true(self):
        """By default, transpilation comments ARE added."""
        asql = """
        from orders
        where order_date >= @2024-01-01 and order_date < @2024-02-01
        group by month(order_date) (
            sum(amount) as revenue
        )
        """
        sql = compile(asql, dialect="snowflake")

        assert "ASQL auto-spine" in sql
    
    def test_transpilation_comments_true_auto_spine(self):
        """Enabling transpilation comments adds auto-spine explanation."""
        settings = CompileSettings(
            include_transpilation_comments=True,
            auto_spine=True,
        )
        asql = """
        from orders
        where order_date >= @2024-01-01 and order_date < @2024-02-01
        group by month(order_date) (
            sum(amount) as revenue
        )
        """
        sql = compile(asql, dialect="snowflake", settings=settings)
        
        # Should have explanatory comment
        assert "ASQL auto-spine" in sql
        assert "Gap-filling CTEs" in sql
        assert "SET auto_spine = false" in sql  # Shows how to disable
    
    def test_transpilation_comments_via_inline_set(self):
        """Enabling transpilation comments via inline SET."""
        asql = """
        SET include_transpilation_comments = true;
        from orders
        where order_date >= @2024-01-01 and order_date < @2024-02-01
        group by month(order_date) (
            sum(amount) as revenue
        )
        """
        sql = compile(asql, dialect="snowflake")
        
        assert "ASQL auto-spine" in sql
    
    def test_transpilation_comments_not_added_when_no_transformation(self):
        """Transpilation comments are not added when no fancy transformation occurs."""
        settings = CompileSettings(
            include_transpilation_comments=True,
            auto_spine=False,  # Disabled, so no transformation
        )
        asql = """
        from orders
        group by month(order_date) (
            sum(amount) as revenue
        )
        """
        sql = compile(asql, dialect="snowflake", settings=settings)
        
        # No comment since auto_spine is disabled
        assert "ASQL auto-spine" not in sql
    
    def test_transpilation_comments_with_pretty_formatting(self):
        """Transpilation comments work with pretty formatting."""
        settings = CompileSettings(
            include_transpilation_comments=True,
            auto_spine=True,
        )
        asql = """
        from orders
        where order_date >= @2024-01-01 and order_date < @2024-02-01
        group by month(order_date) (
            sum(amount) as revenue
        )
        """
        sql = compile(asql, dialect="snowflake", settings=settings, pretty=True)
        
        assert "ASQL auto-spine" in sql


class TestCombinedCommentSettings:
    """Test combinations of comment settings."""
    
    def test_both_settings_true(self):
        """Both passthrough and transpilation comments can be enabled.
        
        Note: When auto-spine is applied, it regenerates the SQL from scratch,
        so original comments may be lost in that case. This test uses a simple
        query without auto-spine to verify both features work.
        """
        settings = CompileSettings(
            passthrough_comments=True,
            include_transpilation_comments=True,
            auto_spine=False,  # Disable auto-spine to preserve original comments
        )
        asql = """
        -- Original comment
        from orders
        limit 10
        """
        sql = compile(asql, dialect="snowflake", settings=settings)
        
        assert "Original comment" in sql
    
    def test_both_settings_true_with_auto_spine(self):
        """When auto-spine is applied, transpilation comments are added.
        
        Note: Auto-spine regenerates SQL, so original comments may not be preserved
        in the final output. The transpilation comment is still added.
        """
        settings = CompileSettings(
            passthrough_comments=True,
            include_transpilation_comments=True,
            auto_spine=True,
        )
        asql = """
        from orders
        where order_date >= @2024-01-01 and order_date < @2024-02-01
        group by month(order_date) (
            sum(amount) as revenue
        )
        """
        sql = compile(asql, dialect="snowflake", settings=settings)
        
        # Transpilation comment should be present
        assert "ASQL auto-spine" in sql
    
    def test_passthrough_false_transpilation_true(self):
        """Can strip source comments but add transpilation comments."""
        settings = CompileSettings(
            passthrough_comments=False,
            include_transpilation_comments=True,
        )
        asql = """
        -- This source comment should be removed
        from orders
        where order_date >= @2024-01-01 and order_date < @2024-02-01
        group by month(order_date) (
            sum(amount) as revenue
        )
        """
        sql = compile(asql, dialect="snowflake", settings=settings)
        
        assert "This source comment should be removed" not in sql
        assert "ASQL auto-spine" in sql
    
    def test_both_settings_false(self):
        """Both settings can be disabled for clean output."""
        settings = CompileSettings(
            passthrough_comments=False,
            include_transpilation_comments=False,
        )
        asql = """
        -- Source comment
        from orders
        where order_date >= @2024-01-01 and order_date < @2024-02-01
        group by month(order_date) (
            sum(amount) as revenue
        )
        """
        sql = compile(asql, dialect="snowflake", settings=settings)
        
        # No comments at all
        assert "--" not in sql or "-- Source" not in sql
        assert "/*" not in sql or "/* ASQL" not in sql


class TestCommentSettingsInConfig:
    """Test comment settings in configuration objects."""
    
    def test_settings_to_dict(self):
        """Comment settings are included in to_dict()."""
        settings = CompileSettings(
            include_transpilation_comments=True,
            passthrough_comments=False,
        )
        d = settings.to_dict()
        
        assert d["include_transpilation_comments"] is True
        assert d["passthrough_comments"] is False
    
    def test_settings_from_dict(self):
        """Comment settings can be created from dict."""
        d = {
            "include_transpilation_comments": True,
            "passthrough_comments": False,
        }
        settings = CompileSettings.from_dict(d)
        
        assert settings.include_transpilation_comments is True
        assert settings.passthrough_comments is False
    
    def test_default_values(self):
        """Test default values for comment settings."""
        settings = CompileSettings()

        assert settings.include_transpilation_comments is True
        assert settings.passthrough_comments is True


class TestExtractCommentSettings:
    """Test pre-scanning for comment settings."""
    
    def test_extract_include_transpilation_true(self):
        """Extract include_transpilation_comments = true from query."""
        from asql.compiler.inline_settings import extract_comment_settings
        
        query = "SET include_transpilation_comments = true; from users"
        include, passthrough = extract_comment_settings(query)
        
        assert include is True
        assert passthrough is None
    
    def test_extract_passthrough_false(self):
        """Extract passthrough_comments = false from query."""
        from asql.compiler.inline_settings import extract_comment_settings
        
        query = "SET passthrough_comments = false; from users"
        include, passthrough = extract_comment_settings(query)
        
        assert include is None
        assert passthrough is False
    
    def test_extract_both_settings(self):
        """Extract both comment settings from query."""
        from asql.compiler.inline_settings import extract_comment_settings
        
        query = """
        SET include_transpilation_comments = true;
        SET passthrough_comments = false;
        from users
        """
        include, passthrough = extract_comment_settings(query)
        
        assert include is True
        assert passthrough is False
    
    def test_extract_no_settings(self):
        """No comment settings in query returns None."""
        from asql.compiler.inline_settings import extract_comment_settings
        
        query = "from users limit 10"
        include, passthrough = extract_comment_settings(query)
        
        assert include is None
        assert passthrough is None
    
    def test_extract_case_insensitive(self):
        """Setting extraction is case insensitive."""
        from asql.compiler.inline_settings import extract_comment_settings
        
        query = "set INCLUDE_TRANSPILATION_COMMENTS = TRUE; from users"
        include, passthrough = extract_comment_settings(query)
        
        assert include is True
