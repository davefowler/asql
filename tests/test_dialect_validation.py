"""Tests for ASQL dialect feature validation.

These tests verify that compile-time validation catches unsupported
feature + dialect combinations before generating invalid SQL.
"""

import pytest
import warnings
from asql import compile
from asql.errors import ASQLDialectError, ASQLDialectWarning
from asql.schema import Schema, Table
from asql.config import CompileSettings


class TestColumnOperatorsValidation:
    """Test validation for column operators (except, rename, replace)."""
    
    def test_except_errors_on_postgres_without_schema(self) -> None:
        """Except should error on PostgreSQL without schema."""
        with pytest.raises(ASQLDialectError, match="except.*not supported.*PostgreSQL"):
            compile('from users except password', dialect='postgres')
    
    def test_except_errors_on_mysql_without_schema(self) -> None:
        """Except should error on MySQL without schema."""
        with pytest.raises(ASQLDialectError, match="except.*not supported.*MySQL"):
            compile('from users except password', dialect='mysql')
    
    def test_except_errors_on_sqlite_without_schema(self) -> None:
        """Except should error on SQLite without schema."""
        with pytest.raises(ASQLDialectError, match="except.*not supported.*SQLite"):
            compile('from users except password', dialect='sqlite')
    
    def test_except_errors_on_redshift_without_schema(self) -> None:
        """Except should error on Redshift without schema."""
        with pytest.raises(ASQLDialectError, match="except.*not supported.*Redshift"):
            compile('from users except password', dialect='redshift')
    
    def test_except_warns_on_postgres_with_schema(self) -> None:
        """Except should warn (not error) on PostgreSQL with schema."""
        schema = Schema()
        schema.add_table(Table.from_column_list('users', ['id', 'name', 'password']))
        settings = CompileSettings(schema=schema)
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            sql = compile('from users except password', dialect='postgres', settings=settings)
            
            assert len(w) == 1
            assert issubclass(w[0].category, ASQLDialectWarning)
            assert "not natively supported" in str(w[0].message).lower()
    
    def test_except_works_on_bigquery(self) -> None:
        """Except should work on BigQuery (supported dialect)."""
        sql = compile('from users except password', dialect='bigquery')
        assert 'EXCEPT' in sql.upper() or 'EXCLUDE' in sql.upper()
    
    def test_except_works_on_snowflake(self) -> None:
        """Except should work on Snowflake (supported dialect)."""
        sql = compile('from users except password', dialect='snowflake')
        assert 'EXCEPT' in sql.upper() or 'EXCLUDE' in sql.upper()
    
    def test_except_works_on_duckdb(self) -> None:
        """Except should work on DuckDB (supported dialect)."""
        sql = compile('from users except password', dialect='duckdb')
        assert 'EXCEPT' in sql.upper() or 'EXCLUDE' in sql.upper()
    
    def test_rename_errors_on_postgres_without_schema(self) -> None:
        """Rename should error on PostgreSQL without schema."""
        with pytest.raises(ASQLDialectError, match="rename.*not supported"):
            compile('from users rename id as user_id', dialect='postgres')
    
    def test_replace_errors_on_postgres_without_schema(self) -> None:
        """Replace should error on PostgreSQL without schema."""
        with pytest.raises(ASQLDialectError, match="replace.*not supported"):
            compile('from users replace name with upper(name)', dialect='postgres')
    
    def test_combined_operators_error_on_postgres(self) -> None:
        """Combined operators should error on PostgreSQL."""
        with pytest.raises(ASQLDialectError):
            compile(
                'from users except password rename id as user_id replace name with upper(name)',
                dialect='postgres'
            )
    
    @pytest.mark.parametrize('dialect', ['bigquery', 'snowflake', 'duckdb'])
    def test_column_operators_work_on_supported_dialects(self, dialect: str) -> None:
        """Column operators should work on supported dialects."""
        sql = compile('from users except password rename id as user_id', dialect=dialect)
        assert 'EXCEPT' in sql.upper() or 'EXCLUDE' in sql.upper()
        assert 'USER_ID' in sql.upper()
    
    def test_error_message_includes_workarounds(self) -> None:
        """Error message should include helpful workaround options."""
        with pytest.raises(ASQLDialectError) as exc_info:
            compile('from users except password', dialect='postgres')
        
        error_msg = str(exc_info.value)
        assert 'schema' in error_msg.lower() or 'select' in error_msg.lower()
        assert 'bigquery' in error_msg.lower() or 'snowflake' in error_msg.lower() or 'duckdb' in error_msg.lower()
    
    def test_error_message_includes_docs_link(self) -> None:
        """Error message should include link to documentation."""
        with pytest.raises(ASQLDialectError) as exc_info:
            compile('from users except password', dialect='postgres')
        
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
            sql = compile('from users select name[1:5] as prefix', dialect=dialect)
            
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
            sql = compile('from users select name[1:5] as prefix', dialect='duckdb')
            
            # Should convert to SUBSTRING 
            assert 'SUBSTRING' in sql.upper()
            
            # Should not have dialect warnings for DuckDB
            dialect_warnings = [warning for warning in w if issubclass(warning.category, ASQLDialectWarning)]
            assert len(dialect_warnings) == 0
    
    def test_slice_generates_correct_sql_for_postgres(self) -> None:
        """Slice syntax should generate correct PostgreSQL SUBSTRING syntax."""
        sql = compile('from users select name[1:5] as prefix', dialect='postgres')
        # PostgreSQL uses FROM ... FOR syntax
        assert 'SUBSTRING(name FROM 1 FOR 5)' in sql
    
    def test_slice_edge_cases(self) -> None:
        """Test various slice syntax patterns."""
        # Slice from start (email[:5] → LEFT)
        sql = compile('from users select email[:5] as prefix', dialect='postgres')
        assert 'LEFT(email, 5)' in sql
        
        # Slice to end (email[1:] → SUBSTRING without length)
        sql = compile('from users select email[1:] as suffix', dialect='postgres')
        assert 'SUBSTRING(email FROM 1)' in sql
        
        # Negative slice (email[-5:] → RIGHT)
        sql = compile('from users select email[-5:] as last_five', dialect='postgres')
        assert 'RIGHT(email, 5)' in sql


class TestDialectAliases:
    """Test that dialect aliases work correctly."""
    
    def test_postgresql_alias_works(self) -> None:
        """'postgresql' should be treated same as 'postgres'."""
        with pytest.raises(ASQLDialectError):
            compile('from users except password', dialect='postgresql')


class TestNoDialectSpecified:
    """Test behavior when no dialect is specified."""
    
    def test_no_validation_without_dialect(self) -> None:
        """Validation should be skipped when no dialect is specified."""
        # Should compile without error (validation is skipped)
        sql = compile('from users except password')
        # May or may not have EXCEPT depending on default dialect
        assert 'SELECT' in sql.upper() and 'FROM' in sql.upper()


class TestErrorMessages:
    """Test that error messages are helpful and informative."""
    
    def test_error_includes_dialect_name(self) -> None:
        """Error should include the dialect name."""
        with pytest.raises(ASQLDialectError) as exc_info:
            compile('from users except password', dialect='postgres')
        
        error_msg = str(exc_info.value)
        assert 'postgres' in error_msg.lower() or 'postgresql' in error_msg.lower()
    
    def test_error_includes_feature_name(self) -> None:
        """Error should mention which feature is unsupported."""
        with pytest.raises(ASQLDialectError) as exc_info:
            compile('from users except password', dialect='postgres')
        
        error_msg = str(exc_info.value)
        assert 'except' in error_msg.lower() or 'column' in error_msg.lower()
    
    def test_no_slice_warnings_after_fix(self) -> None:
        """Slice syntax should no longer generate warnings (Issue #77 fixed)."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            compile('from users select name[1:5] as prefix', dialect='postgres')
            
            dialect_warnings = [warning for warning in w if issubclass(warning.category, ASQLDialectWarning)]
            # No slice-related warnings should be generated
            slice_warnings = [warning for warning in dialect_warnings
                              if 'slice' in str(warning.message).lower() or '#77' in str(warning.message)]
            assert len(slice_warnings) == 0, "Slice syntax should not generate warnings after fix"
