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
    
    def test_except_works_on_postgres_with_schema(self) -> None:
        """Except should work on PostgreSQL with schema (Issue #80 fallback).
        
        When schema is provided, ASQL expands to explicit column list instead
        of using EXCEPT syntax. No warning is needed since the fallback works.
        """
        schema = Schema()
        schema.add_table(Table.from_column_list('users', ['id', 'name', 'password']))
        settings = CompileSettings(schema=schema)
        
        # Should compile without error or warning
        sql = compile('from users except password', dialect='postgres', settings=settings)
        
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


class TestDialectSchemaSync:
    """Test that dialect_schema.py stays in sync with parser definitions."""

    def test_all_transforms_have_schema_definitions(self) -> None:
        """All transforms in TRANSFORM_PARSERS should have corresponding schema definitions."""
        from asql.dialect import ASQLParser
        from asql.dialect_schema import TRANSFORMS, get_transform_by_keyword

        # Get all transform keywords from parser
        parser_keywords = set(ASQLParser.TRANSFORM_PARSERS.keys())

        # Filter out internal/alias transforms
        # These are implementation details or aliases that don't need UI schemas
        internal_keywords = {
            'ASQL_INNER_JOIN',  # Internal representation of & symbol
            'ASQL_QMARK_JOIN',  # Internal representation of &? and ?& symbols
            'ASQL_FULL_JOIN',   # Internal representation of ?&? symbol
            'ASQL_CROSS_JOIN',  # Internal representation of * symbol
        }

        # Alias keywords that map to primary transforms
        alias_keywords = {
            'FILTER',  # Alias for WHERE
            'IF',      # Alias for WHERE
            'PROJECT', # Alias for SELECT
        }

        # Keywords that are handled by JOIN with join_type parameter
        join_variants = {
            'LEFT',    # Handled by JOIN with join_type="LEFT"
            'RIGHT',   # Handled by JOIN with join_type="RIGHT"
            'FULL',    # Handled by JOIN with join_type="FULL"
            'CROSS',   # Handled by JOIN with join_type="CROSS"
        }

        # Exclude internal/alias/join-variant keywords
        required_keywords = parser_keywords - internal_keywords - alias_keywords - join_variants

        # Check each required keyword has a schema
        missing_schemas = []
        for keyword in required_keywords:
            transform = get_transform_by_keyword(keyword)
            if transform is None:
                missing_schemas.append(keyword)

        if missing_schemas:
            pytest.fail(
                f"Missing schema definitions for transforms: {', '.join(sorted(missing_schemas))}\n"
                f"Add these to dialect_schema.py TRANSFORMS class."
            )

    def test_transform_schemas_have_valid_parameters(self) -> None:
        """All transform schemas should have valid parameter definitions."""
        from asql.dialect_schema import get_all_transforms

        transforms = get_all_transforms()
        invalid_transforms = []

        for transform in transforms:
            # Check that parameters dict exists
            if not hasattr(transform, 'parameters'):
                invalid_transforms.append(f"{transform.label}: missing parameters dict")
                continue

            # Check each parameter has required fields
            for param_name, param in transform.parameters.items():
                if not hasattr(param, 'name'):
                    invalid_transforms.append(f"{transform.label}.{param_name}: missing 'name'")
                if not hasattr(param, 'widget'):
                    invalid_transforms.append(f"{transform.label}.{param_name}: missing 'widget'")
                if not hasattr(param, 'label'):
                    invalid_transforms.append(f"{transform.label}.{param_name}: missing 'label'")

        if invalid_transforms:
            pytest.fail(
                f"Invalid transform schemas:\n" +
                "\n".join(f"  - {err}" for err in invalid_transforms)
            )

    def test_operator_schemas_complete(self) -> None:
        """All operators in Parser.COMPARISON and Parser.EQUALITY should have schemas."""
        from sqlglot import Parser
        from asql.dialect_schema import OPERATORS

        # Get all comparison/equality tokens from SQLGlot Parser
        parser_tokens = set()
        for token in Parser.COMPARISON.keys():
            parser_tokens.add(token)
        for token in Parser.EQUALITY.keys():
            parser_tokens.add(token)

        # Get all tokens from dialect schema
        schema_tokens = set()
        for attr_name in dir(OPERATORS.COMPARISON):
            if not attr_name.startswith('_'):
                op = getattr(OPERATORS.COMPARISON, attr_name)
                if hasattr(op, 'token'):
                    schema_tokens.add(op.token)
        for attr_name in dir(OPERATORS.EQUALITY):
            if not attr_name.startswith('_'):
                op = getattr(OPERATORS.EQUALITY, attr_name)
                if hasattr(op, 'token'):
                    schema_tokens.add(op.token)

        # Check for missing operators
        missing = parser_tokens - schema_tokens
        if missing:
            pytest.fail(
                f"Missing operator schemas for tokens: {missing}\n"
                f"Add these to dialect_schema.py OPERATORS class."
            )
