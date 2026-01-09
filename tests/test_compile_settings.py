"""Tests for ASQL compile settings and inline SET statements.

Tests the CompileSettings system which allows configuration via:
1. Python API (CompileSettings dataclass)
2. Config file (asql.config.yaml)
3. Inline SET statements in queries
"""

import pytest
from asql import compile, CompileSettings, get_settings_from_query
from asql.config import ASQLConfig, KNOWN_COMPILE_SETTINGS
from asql.compiler import extract_inline_settings
import sqlglot


class TestCompileSettings:
    """Test CompileSettings dataclass."""
    
    def test_default_settings(self):
        """Test default settings values."""
        settings = CompileSettings()
        
        assert settings.auto_spine is True  # Default on - filter out zeros if you don't want them
        assert settings.week_start == "monday"
        assert settings.relative_date_type == "timestamp"
    
    def test_custom_settings(self):
        """Test creating settings with custom values."""
        settings = CompileSettings(
            auto_spine=True,
            week_start="sunday",
            relative_date_type="date"
        )
        
        assert settings.auto_spine is True
        assert settings.week_start == "sunday"
        assert settings.relative_date_type == "date"
    
    def test_to_dict(self):
        """Test converting settings to dictionary."""
        settings = CompileSettings(auto_spine=True)
        d = settings.to_dict()
        
        assert d["auto_spine"] is True
        assert d["week_start"] == "monday"
        assert d["relative_date_type"] == "timestamp"
    
    def test_from_dict(self):
        """Test creating settings from dictionary."""
        d = {"auto_spine": True, "week_start": "sunday"}
        settings = CompileSettings.from_dict(d)
        
        assert settings.auto_spine is True
        assert settings.week_start == "sunday"
        assert settings.relative_date_type == "timestamp"  # default
    
    def test_from_dict_ignores_unknown_keys(self):
        """Test that unknown keys are ignored."""
        d = {"auto_spine": True, "unknown_setting": "value"}
        settings = CompileSettings.from_dict(d)
        
        assert settings.auto_spine is True
        assert not hasattr(settings, "unknown_setting")
    
    def test_merge_with(self):
        """Test merging settings."""
        # With auto_spine=True as default, test that False overrides True
        base = CompileSettings(auto_spine=True, week_start="monday")
        override = CompileSettings(auto_spine=False)  # week_start stays default
        
        merged = base.merge_with(override)
        
        assert merged.auto_spine is False  # overridden (differs from default True)
        assert merged.week_start == "monday"  # kept from base


class TestInlineSetStatements:
    """Test parsing inline SET statements."""
    
    def test_extract_auto_spine_true(self):
        """Test extracting SET auto_spine = true."""
        statements = sqlglot.parse("SET auto_spine = true; SELECT * FROM t")
        settings, dialect, queries = extract_inline_settings(statements)
        
        assert settings.auto_spine is True
        assert len(queries) == 1
    
    def test_extract_auto_spine_false(self):
        """Test extracting SET auto_spine = false."""
        statements = sqlglot.parse("SET auto_spine = false; SELECT * FROM t")
        settings, dialect, queries = extract_inline_settings(statements)
        
        assert settings.auto_spine is False
        assert len(queries) == 1
    
    def test_extract_dialect(self):
        """Test extracting SET dialect = 'postgres'."""
        statements = sqlglot.parse("SET dialect = 'postgres'; SELECT * FROM t")
        settings, dialect, queries = extract_inline_settings(statements)
        
        assert dialect == "postgres"
        assert len(queries) == 1
    
    def test_extract_week_start(self):
        """Test extracting SET week_start = 'sunday'."""
        statements = sqlglot.parse("SET week_start = 'sunday'; SELECT * FROM t")
        settings, dialect, queries = extract_inline_settings(statements)
        
        assert settings.week_start == "sunday"
    
    def test_extract_multiple_settings(self):
        """Test extracting multiple SET statements."""
        sql = """
        SET auto_spine = true;
        SET week_start = 'sunday';
        SET dialect = 'bigquery';
        SELECT * FROM orders
        """
        statements = sqlglot.parse(sql)
        settings, dialect, queries = extract_inline_settings(statements)
        
        assert settings.auto_spine is True
        assert settings.week_start == "sunday"
        assert dialect == "bigquery"
        assert len(queries) == 1
    
    def test_no_set_statements(self):
        """Test query without SET statements."""
        statements = sqlglot.parse("SELECT * FROM orders WHERE status = 'active'")
        settings, dialect, queries = extract_inline_settings(statements)
        
        # Should get defaults from CompileSettings() which starts fresh
        # (extract_inline_settings creates a new CompileSettings, not the global default)
        assert settings.week_start == "monday"
        assert dialect is None
        assert len(queries) == 1
    
    def test_unknown_setting_ignored(self):
        """Test that unknown settings are silently ignored."""
        statements = sqlglot.parse("SET unknown_setting = 'value'; SELECT * FROM t")
        settings, dialect, queries = extract_inline_settings(statements)
        
        # Should not raise, and query should work
        assert len(queries) == 1


class TestCompileWithSettings:
    """Test compile() with settings parameter."""
    
    def test_compile_accepts_settings(self):
        """Test that compile() accepts settings parameter."""
        settings = CompileSettings(auto_spine=True)
        sql = compile("from users limit 10", dialect="snowflake", settings=settings)
        
        assert "SELECT" in sql
        assert "users" in sql
    
    def test_compile_with_inline_set(self):
        """Test compile with inline SET statement."""
        asql = """
        SET dialect = 'postgres';
        from users limit 10
        """
        sql = compile(asql)
        
        assert "SELECT" in sql
        assert "users" in sql

    def test_compile_with_inline_set_without_semicolon(self):
        """SET statements should work even without a trailing semicolon."""
        asql = """
        SET dialect = 'postgres'
        from users limit 10
        """
        sql = compile(asql)
        assert "SELECT" in sql
        assert "users" in sql
    
    def test_inline_set_overrides_passed_settings(self):
        """Test that inline SET overrides passed settings."""
        # Test that setting auto_spine=false overrides the default of True
        base_settings = CompileSettings(auto_spine=True)
        
        asql = """
        SET auto_spine = false;
        from orders limit 10
        """
        
        # The inline SET should override base_settings
        # Currently we can't directly verify auto_spine effect,
        # but we verify the parsing works
        settings, _ = get_settings_from_query(asql, base_settings)
        assert settings.auto_spine is False
    
    def test_set_only_query_raises(self):
        """Test that query with only SET statements raises error."""
        with pytest.raises(Exception):  # ASQLSyntaxError
            compile("SET auto_spine = true")


class TestGetSettingsFromQuery:
    """Test get_settings_from_query helper."""
    
    def test_get_settings_basic(self):
        """Test extracting settings from query."""
        asql = """
        SET auto_spine = true;
        SET dialect = 'postgres';
        from orders limit 10
        """
        settings, dialect = get_settings_from_query(asql)
        
        assert settings.auto_spine is True
        assert dialect == "postgres"

    def test_get_settings_without_semicolons(self):
        """SET statements without semicolons should still be parsed."""
        asql = """
        SET auto_spine = false
        SET week_start = 'sunday'
        from orders limit 10
        """
        settings, dialect = get_settings_from_query(asql)
        assert settings.auto_spine is False
        assert settings.week_start == "sunday"
        assert dialect is None
    
    def test_get_settings_with_base(self):
        """Test extracting settings with base settings."""
        base = CompileSettings(week_start="sunday")
        
        asql = """
        SET auto_spine = true;
        from orders limit 10
        """
        settings, dialect = get_settings_from_query(asql, base)
        
        assert settings.auto_spine is True
        assert settings.week_start == "sunday"  # kept from base
    
    def test_get_settings_no_set(self):
        """Test query without SET returns defaults."""
        settings, dialect = get_settings_from_query("from users limit 10")
        
        assert settings.auto_spine is True  # Default is now True
        assert settings.week_start == "monday"
        assert dialect is None
    
    def test_get_settings_invalid_query_returns_defaults(self):
        """Test that invalid query returns base settings."""
        settings, dialect = get_settings_from_query("invalid asql ;;;")
        
        # Should not raise, returns defaults
        assert settings.auto_spine is True  # Default is now True


class TestASQLConfigWithCompileSettings:
    """Test ASQLConfig with compile settings."""
    
    def test_asql_config_has_compile_settings(self):
        """Test that ASQLConfig includes compile settings."""
        config = ASQLConfig()
        
        assert hasattr(config, "compile")
        assert isinstance(config.compile, CompileSettings)
    
    def test_asql_config_from_dict_with_compile(self):
        """Test ASQLConfig.from_dict with compile settings."""
        d = {
            "dialect": "bigquery",
            "compile": {
                "auto_spine": True,
                "week_start": "sunday"
            }
        }
        config = ASQLConfig.from_dict(d)
        
        assert config.dialect == "bigquery"
        assert config.compile.auto_spine is True
        assert config.compile.week_start == "sunday"
    
    def test_asql_config_to_dict_includes_compile(self):
        """Test ASQLConfig.to_dict includes compile settings."""
        config = ASQLConfig(
            compile=CompileSettings(auto_spine=True)
        )
        d = config.to_dict()
        
        assert "compile" in d
        assert d["compile"]["auto_spine"] is True


class TestKnownSettings:
    """Test the KNOWN_COMPILE_SETTINGS registry."""
    
    def test_known_settings_contains_expected(self):
        """Test that KNOWN_COMPILE_SETTINGS has expected entries."""
        assert "auto_spine" in KNOWN_COMPILE_SETTINGS
        assert "week_start" in KNOWN_COMPILE_SETTINGS
        assert "dialect" in KNOWN_COMPILE_SETTINGS
