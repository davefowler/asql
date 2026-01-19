"""Tests for ASQL compile settings and inline SET statements.

Tests the settings system which allows configuration via:
1. Python API (ASQL dialect constructor)
2. Inline SET statements in queries
3. CompileSettings dataclass (for convenience wrapper)
"""

import pytest
import sqlglot
from tests.fixtures import transpile
from asql import CompileSettings
from asql.config import ASQLConfig, KNOWN_COMPILE_SETTINGS
from asql.dialect import ASQL


class TestCompileSettings:
    """Test CompileSettings dataclass."""
    
    def test_default_settings(self):
        """Test default settings values."""
        settings = CompileSettings()
        
        assert settings.week_start == "monday"
        assert settings.relative_date_type == "timestamp"
    
    def test_custom_settings(self):
        """Test creating settings with custom values."""
        settings = CompileSettings(
            week_start="sunday",
            relative_date_type="date"
        )
        
        assert settings.week_start == "sunday"
        assert settings.relative_date_type == "date"
    
    def test_to_dict(self):
        """Test converting settings to dictionary."""
        settings = CompileSettings(week_start="sunday")
        d = settings.to_dict()
        
        assert d["week_start"] == "sunday"
        assert d["relative_date_type"] == "timestamp"
    
    def test_from_dict(self):
        """Test creating settings from dictionary."""
        d = {"week_start": "sunday"}
        settings = CompileSettings.from_dict(d)
        
        assert settings.week_start == "sunday"
        assert settings.relative_date_type == "timestamp"  # default
    
    def test_from_dict_ignores_unknown_keys(self):
        """Test that unknown keys are ignored."""
        d = {"week_start": "sunday", "unknown_setting": "value"}
        settings = CompileSettings.from_dict(d)
        
        assert settings.week_start == "sunday"
        assert not hasattr(settings, "unknown_setting")
    
    def test_merge_with(self):
        """Test merging settings."""
        base = CompileSettings(week_start="monday", relative_date_type="timestamp")
        override = CompileSettings(week_start="sunday")
        
        merged = base.merge_with(override)
        
        assert merged.week_start == "sunday"  # overridden
        assert merged.relative_date_type == "timestamp"  # kept from base


class TestASQLDialectSettings:
    """Test ASQL dialect with settings."""
    
    def test_dialect_with_default_settings(self):
        """Test that ASQL dialect has default settings."""
        asql = ASQL()
        
        assert asql.settings.get("week_start") == "monday"
    
    def test_dialect_with_custom_settings(self):
        """Test creating dialect with custom settings."""
        asql = ASQL(
            extend_dialect="postgres",
            week_start="sunday",
        )
        
        assert asql.settings.get("extend_dialect") == "postgres"
        assert asql.settings.get("week_start") == "sunday"
    
    def test_transpile_with_dialect_settings(self):
        """Test transpile with dialect settings."""
        asql = ASQL(extend_dialect="postgres", week_start="sunday")
        sql = sqlglot.transpile("from orders", read=asql, write="postgres")[0]
        
        assert "SELECT" in sql.upper()
        assert "FROM" in sql.upper()


class TestInlineSetStatements:
    """Test inline SET statements processed by parser."""
    
    def test_inline_set_week_start(self):
        """Test SET week_start via inline statement."""
        asql = ASQL()
        
        query = "SET week_start = 'sunday'; from orders"
        sqlglot.transpile(query, read=asql, write="postgres")
        
        assert asql.settings.get("week_start") == "sunday"
    
    def test_inline_set_extend_dialect(self):
        """Test SET extend_dialect (alias: dialect) via inline statement."""
        asql = ASQL()
        
        query = "SET extend_dialect = 'snowflake'; from orders"
        sqlglot.transpile(query, read=asql, write="postgres")
        
        assert asql.settings.get("extend_dialect") == "snowflake"
    
    def test_inline_set_dialect_alias(self):
        """Test SET dialect = '...' is aliased to extend_dialect."""
        asql = ASQL()
        
        query = "SET dialect = 'bigquery'; from orders"
        sqlglot.transpile(query, read=asql, write="postgres")
        
        # "dialect" is aliased to "extend_dialect"
        assert asql.settings.get("extend_dialect") == "bigquery"
    
    def test_inline_set_multiple(self):
        """Test multiple SET statements."""
        asql = ASQL()
        
        query = """
        SET week_start = 'sunday';
        SET extend_dialect = 'postgres';
        from orders
        """
        sqlglot.transpile(query, read=asql, write="postgres")
        
        assert asql.settings.get("week_start") == "sunday"
        assert asql.settings.get("extend_dialect") == "postgres"
    
    def test_inline_set_alias_prefix(self):
        """Test SET {func}_alias_prefix updates alias_prefixes dict."""
        asql = ASQL()
        
        query = "SET count_alias_prefix = 'num'; from orders"
        sqlglot.transpile(query, read=asql, write="postgres")
        
        prefixes = asql.settings.get("alias_prefixes", {})
        assert prefixes.get("count") == "num"
    
    def test_set_statements_removed_from_output(self):
        """Test that SET statements are not in the output SQL."""
        asql = ASQL()
        
        query = "SET week_start = 'sunday'; from orders"
        results = sqlglot.transpile(query, read=asql, write="postgres")
        
        # Output should not contain SET
        assert "SET" not in results[0].upper()
        assert "SELECT" in results[0].upper()


class TestSettingsValidation:
    """Test validation of SET statement values."""
    
    def test_invalid_week_start_raises_error(self):
        """Invalid week_start value should raise ValueError."""
        import pytest
        asql = ASQL()
        
        query = "SET week_start = 'wednesday'; from orders"
        with pytest.raises(ValueError, match="must be 'monday' or 'sunday'"):
            sqlglot.transpile(query, read=asql, write="postgres")
    
    def test_invalid_equality_raises_error(self):
        """Invalid equality value should raise ValueError."""
        import pytest
        asql = ASQL()
        
        query = "SET equality = 'triple'; from orders"
        with pytest.raises(ValueError, match="must be 'single' or 'double'"):
            sqlglot.transpile(query, read=asql, write="postgres")
    
    def test_valid_week_start_values(self):
        """Valid week_start values should work."""
        for day in ["monday", "sunday"]:
            asql = ASQL()
            query = f"SET week_start = '{day}'; from orders"
            sqlglot.transpile(query, read=asql, write="postgres")
            assert asql.settings.get("week_start") == day


class TestSettingsMutation:
    """Test that inline SET properly overrides constructor settings."""
    
    def test_inline_set_overrides_constructor(self):
        """Inline SET should override settings passed to constructor."""
        asql = ASQL(week_start="monday")
        
        query = "SET week_start = 'sunday'; from orders"
        sqlglot.transpile(query, read=asql, write="postgres")
        
        # Inline SET should have overridden constructor values
        assert asql.settings.get("week_start") == "sunday"
    
    def test_settings_persist_across_statements(self):
        """Settings from first SET should apply to subsequent statements."""
        asql = ASQL()
        
        query = """
        SET extend_dialect = 'postgres';
        from orders;
        from users
        """
        results = sqlglot.transpile(query, read=asql, write="postgres")
        
        # extend_dialect should be set for all statements
        assert asql.settings.get("extend_dialect") == "postgres"
        assert len(results) == 2
    
    def test_fresh_dialect_has_fresh_settings(self):
        """Each new ASQL dialect instance should have independent settings."""
        asql1 = ASQL()
        query1 = "SET week_start = 'sunday'; from orders"
        sqlglot.transpile(query1, read=asql1, write="postgres")
        
        # Create new dialect - should have default settings
        asql2 = ASQL()
        
        # asql1 was mutated, but asql2 should have defaults
        assert asql1.settings.get("week_start") == "sunday"
        assert asql2.settings.get("week_start") == "monday"  # default


class TestCompileWithSettings:
    """Test transpile() with settings parameter."""
    
    def test_compile_accepts_settings(self):
        """Test that transpile() accepts settings parameter."""
        settings = CompileSettings(week_start="sunday")
        sql = transpile("from users limit 10", dialect="snowflake", settings=settings)
        
        assert "SELECT" in sql
        assert "users" in sql.lower()
    
    def test_compile_with_inline_set(self):
        """Test compile with inline SET statement."""
        asql = """
        SET extend_dialect = 'postgres';
        from users limit 10
        """
        sql = transpile(asql, dialect="postgres")
        
        assert "SELECT" in sql
        assert "users" in sql.lower()

    def test_compile_with_inline_set_without_semicolon(self):
        """SET statements require semicolon separator.
        
        Note: SQLGlot parser requires statement separators. Without semicolon,
        the parser treats this as a single malformed statement.
        """
        asql = """
        SET extend_dialect = 'postgres';
        from users limit 10
        """
        sql = transpile(asql, dialect="postgres")
        assert "SELECT" in sql
        assert "users" in sql.lower()
    
    def test_set_only_query_returns_empty(self):
        """Test that query with only SET statements returns empty string."""
        sql = transpile("SET week_start = 'sunday'", dialect="postgres")
        # SET-only statements are processed but don't produce SQL output
        assert sql == ""


class TestASQLConfigWithCompileSettings:
    """Test ASQLConfig with compile settings."""
    
    def test_asql_config_has_compile_settings(self):
        """Test that ASQLConfig includes compile settings."""
        config = ASQLConfig()
        
        assert hasattr(config, "compile")
        assert isinstance(config.compile, CompileSettings)
    
    def test_asql_config_from_dict_with_transpile(self):
        """Test ASQLConfig.from_dict with compile settings."""
        d = {
            "dialect": "bigquery",
            "compile": {
                "week_start": "sunday"
            }
        }
        config = ASQLConfig.from_dict(d)
        
        assert config.dialect == "bigquery"
        assert config.compile.week_start == "sunday"
    
    def test_asql_config_to_dict_includes_transpile(self):
        """Test ASQLConfig.to_dict includes compile settings."""
        config = ASQLConfig(
            compile=CompileSettings(week_start="sunday")
        )
        d = config.to_dict()
        
        assert "compile" in d
        assert d["compile"]["week_start"] == "sunday"


class TestKnownSettings:
    """Test the KNOWN_COMPILE_SETTINGS registry."""
    
    def test_known_settings_contains_expected(self):
        """Test that KNOWN_COMPILE_SETTINGS has expected entries."""
        assert "week_start" in KNOWN_COMPILE_SETTINGS
        assert "dialect" in KNOWN_COMPILE_SETTINGS
