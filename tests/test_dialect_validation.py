"""Tests for ASQL dialect feature validation.

These tests verify that compile-time validation catches unsupported
feature + dialect combinations before generating invalid SQL.
"""

import pytest
import warnings
from tests.fixtures import transpile
from asql.errors import ASQLDialectError, ASQLDialectWarning
from asql.schema import Schema, Table
from asql.config import CompileSettings


class TestColumnOperatorsValidation:
    """Test validation for column operators (except, rename, replace)."""
    
    def test_except_errors_on_postgres_without_schema(self) -> None:
        """Except should error on PostgreSQL without schema."""
        with pytest.raises(ASQLDialectError, match="(?i)column operators.*require.*schema"):
            transpile('from users except password', dialect='postgres')
    
    def test_except_errors_on_mysql_without_schema(self) -> None:
        """Except should error on MySQL without schema."""
        with pytest.raises(ASQLDialectError, match="(?i)column operators.*require.*schema"):
            transpile('from users except password', dialect='mysql')
    
    def test_except_errors_on_sqlite_without_schema(self) -> None:
        """Except should error on SQLite without schema."""
        with pytest.raises(ASQLDialectError, match="(?i)column operators.*require.*schema"):
            transpile('from users except password', dialect='sqlite')
    
    def test_except_errors_on_redshift_without_schema(self) -> None:
        """Except should error on Redshift without schema."""
        with pytest.raises(ASQLDialectError, match="(?i)column operators.*require.*schema"):
            transpile('from users except password', dialect='redshift')
    
    def test_except_works_on_postgres_with_schema(self) -> None:
        """Except should work on PostgreSQL with schema (Issue #80 fallback).
        
        When schema is provided, ASQL expands to explicit column list instead
        of using EXCEPT syntax. No warning is needed since the fallback works.
        """
        schema = Schema()
        schema.add_table(Table.from_column_list('users', ['id', 'name', 'password']))
        settings = CompileSettings(schema=schema)
        
        # Should compile without error or warning
        sql = transpile('from users except password', dialect='postgres', settings=settings)
        
        # Should NOT contain EXCEPT syntax (PostgreSQL doesn't support it)
        assert 'EXCEPT' not in sql.upper()
        assert 'EXCLUDE' not in sql.upper()
        
        # Should contain the non-excluded columns
        assert 'id' in sql.lower()
        assert 'name' in sql.lower()
        
        # Should NOT contain the excluded column
        assert 'password' not in sql.lower()
    
    def test_except_works_on_bigquery(self) -> None:
        """Except should work on BigQuery (supported dialect)."""
        sql = transpile('from users except password', dialect='bigquery')
        assert 'EXCEPT' in sql.upper() or 'EXCLUDE' in sql.upper()
    
    def test_except_works_on_snowflake(self) -> None:
        """Except should work on Snowflake (supported dialect)."""
        sql = transpile('from users except password', dialect='snowflake')
        assert 'EXCEPT' in sql.upper() or 'EXCLUDE' in sql.upper()
    
    def test_except_works_on_duckdb(self) -> None:
        """Except should work on DuckDB (supported dialect)."""
        sql = transpile('from users except password', dialect='duckdb')
        assert 'EXCEPT' in sql.upper() or 'EXCLUDE' in sql.upper()
    
    def test_rename_errors_on_postgres_without_schema(self) -> None:
        """Rename should error on PostgreSQL without schema."""
        with pytest.raises(ASQLDialectError, match="(?i)column operators.*require.*schema"):
            transpile('from users rename id as user_id', dialect='postgres')
    
    def test_replace_errors_on_postgres_without_schema(self) -> None:
        """Replace should error on PostgreSQL without schema."""
        with pytest.raises(ASQLDialectError, match="(?i)column operators.*require.*schema"):
            transpile('from users replace name with upper(name)', dialect='postgres')
    
    def test_combined_operators_error_on_postgres(self) -> None:
        """Combined operators should error on PostgreSQL."""
        with pytest.raises(ASQLDialectError):
            transpile(
                'from users except password rename id as user_id replace name with upper(name)',
                dialect='postgres'
            )
    
    @pytest.mark.parametrize('dialect', ['bigquery', 'snowflake', 'duckdb'])
    def test_column_operators_work_on_supported_dialects(self, dialect: str) -> None:
        """Column operators should work on supported dialects."""
        sql = transpile('from users except password rename id as user_id', dialect=dialect)
        assert 'EXCEPT' in sql.upper() or 'EXCLUDE' in sql.upper()
        assert 'USER_ID' in sql.upper()
    
    def test_error_message_includes_workarounds(self) -> None:
        """Error message should mention schema as workaround."""
        with pytest.raises(ASQLDialectError) as exc_info:
            transpile('from users except password', dialect='postgres')
        
        error_msg = str(exc_info.value)
        # Message should mention schema as the solution
        assert 'schema' in error_msg.lower()
    
    @pytest.mark.xfail(reason="Docs link not yet added to error message")
    def test_error_message_includes_docs_link(self) -> None:
        """Error message should include link to documentation."""
        with pytest.raises(ASQLDialectError) as exc_info:
            transpile('from users except password', dialect='postgres')
        
        error_msg = str(exc_info.value)
        assert 'dialect-limitations' in error_msg.lower() or 'asql.dev' in error_msg.lower()


class TestSliceSyntaxValidation:
    """Test validation for slice syntax [start:end].
    
    NOTE: Issue #77 fixed - slice syntax now works for all dialects.
    The preparser converts slice syntax to SUBSTRING/LEFT/RIGHT, which
    SQLGlot correctly transpiles to all dialects.
    """
    
    @pytest.mark.parametrize('dialect', ['postgres', 'bigquery', 'snowflake', 'mysql'])
    def test_slice_works_on_all_dialects(self, dialect: str) -> None:
        """Slice syntax should work on all dialects (Issue #77 fixed)."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            sql = transpile('from users select name[1:5] as prefix', dialect=dialect)
            
            # Should convert to SUBSTRING (or dialect equivalent)
            assert 'SUBSTRING' in sql.upper(), f"Expected SUBSTRING in SQL for {dialect}: {sql}"
            
            # Should not have dialect warnings for slice syntax
            dialect_warnings = [warning for warning in w if issubclass(warning.category, ASQLDialectWarning)]
            slice_warnings = [warning for warning in dialect_warnings 
                              if 'slice' in str(warning.message).lower() or '#77' in str(warning.message)]
            assert len(slice_warnings) == 0, f"Unexpected slice warning for {dialect}"
    
    def test_slice_works_on_duckdb(self) -> None:
        """Slice syntax should work on DuckDB (natively supported + SUBSTRING)."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            sql = transpile('from users select name[1:5] as prefix', dialect='duckdb')
            
            # Should convert to SUBSTRING 
            assert 'SUBSTRING' in sql.upper()
            
            # Should not have dialect warnings for DuckDB
            dialect_warnings = [warning for warning in w if issubclass(warning.category, ASQLDialectWarning)]
            assert len(dialect_warnings) == 0
    
    def test_slice_generates_correct_sql_for_postgres(self) -> None:
        """Slice syntax should generate correct PostgreSQL SUBSTRING syntax."""
        sql = transpile('from users select name[1:5] as prefix', dialect='postgres')
        # PostgreSQL uses FROM ... FOR syntax
        assert 'SUBSTRING(name FROM 1 FOR 5)' in sql
    
    def test_slice_edge_cases(self) -> None:
        """Test various slice syntax patterns."""
        # Slice from start (email[:5] → LEFT)
        sql = transpile('from users select email[:5] as prefix', dialect='postgres')
        assert 'LEFT(email, 5)' in sql
        
        # Slice to end (email[1:] → SUBSTRING without length)
        sql = transpile('from users select email[1:] as suffix', dialect='postgres')
        assert 'SUBSTRING(email FROM 1)' in sql
        
        # Negative slice (email[-5:] → RIGHT)
        sql = transpile('from users select email[-5:] as last_five', dialect='postgres')
        assert 'RIGHT(email, 5)' in sql


class TestDialectAliases:
    """Test that dialect aliases work correctly."""
    
    def test_postgresql_alias_works(self) -> None:
        """'postgresql' should be treated same as 'postgres'."""
        with pytest.raises(ASQLDialectError):
            transpile('from users except password', dialect='postgresql')


class TestNoDialectSpecified:
    """Test behavior when no dialect is specified."""
    
    def test_no_validation_without_dialect(self) -> None:
        """Validation should be skipped when no dialect is specified."""
        # Should compile without error (validation is skipped)
        sql = transpile('from users except password')
        # May or may not have EXCEPT depending on default dialect
        assert 'SELECT' in sql.upper() and 'FROM' in sql.upper()


class TestErrorMessages:
    """Test that error messages are helpful and informative."""
    
    def test_error_includes_dialect_name(self) -> None:
        """Error should include the dialect name."""
        with pytest.raises(ASQLDialectError) as exc_info:
            transpile('from users except password', dialect='postgres')
        
        error_msg = str(exc_info.value)
        assert 'postgres' in error_msg.lower() or 'postgresql' in error_msg.lower()
    
    def test_error_includes_feature_name(self) -> None:
        """Error should mention which feature is unsupported."""
        with pytest.raises(ASQLDialectError) as exc_info:
            transpile('from users except password', dialect='postgres')
        
        error_msg = str(exc_info.value)
        assert 'except' in error_msg.lower() or 'column' in error_msg.lower()
    
    def test_no_slice_warnings_after_fix(self) -> None:
        """Slice syntax should no longer generate warnings (Issue #77 fixed)."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            transpile('from users select name[1:5] as prefix', dialect='postgres')
            
            dialect_warnings = [warning for warning in w if issubclass(warning.category, ASQLDialectWarning)]
            # No slice-related warnings should be generated
            slice_warnings = [warning for warning in dialect_warnings
                              if 'slice' in str(warning.message).lower() or '#77' in str(warning.message)]
            assert len(slice_warnings) == 0, "Slice syntax should not generate warnings after fix"


class TestDialectSchemaSync:
    """Test that ui-metadata.json stays in sync with parser definitions.
    
    NOTE: Main sync tests are in tests/test_schema_sync.py.
    This is a simple check that the schema file exists and is valid.
    """

    def test_ui_metadata_exists_and_valid(self) -> None:
        """ui-metadata.json should exist and be valid JSON."""
        import json
        from pathlib import Path
        
        schema_path = Path(__file__).parent.parent / "asql" / "ui-metadata.json"
        assert schema_path.exists(), "asql/ui-metadata.json should exist"
        
        with open(schema_path) as f:
            schema = json.load(f)
        
        assert "transforms" in schema
        assert "operators" in schema
        assert "joins" in schema
