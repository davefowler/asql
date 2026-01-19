"""
Tests for schema-aware column operators fallback.

Issue #80: Column operators (except, rename, replace) should work on dialects 
without EXCLUDE/EXCEPT support when schema is provided.

Run with: pytest tests/test_column_operators_fallback.py -v
"""

import pytest
from tests.fixtures import transpile
from asql.config import CompileSettings
from asql.schema import Schema
from asql.errors import ASQLDialectError


# Dialects without EXCLUDE support
NO_EXCLUDE_DIALECTS = ["postgres", "mysql", "sqlite", "redshift"]

# Dialects with EXCLUDE support
EXCLUDE_DIALECTS = ["bigquery", "snowflake", "duckdb"]


@pytest.fixture
def users_schema() -> Schema:
    """Schema with a users table."""
    return Schema.from_dict({
        'tables': {
            'users': {
                'columns': ['id', 'name', 'email', 'password_hash', 'created_at']
            }
        }
    })


@pytest.fixture
def products_schema() -> Schema:
    """Schema with a products table."""
    return Schema.from_dict({
        'tables': {
            'products': {
                'columns': ['id', 'name', 'price', 'description', 'created_at']
            }
        }
    })


class TestExceptOperatorWithSchema:
    """Test 'except' operator with schema for dialects without EXCLUDE support."""
    
    @pytest.mark.parametrize("dialect", NO_EXCLUDE_DIALECTS)
    def test_except_single_column(self, dialect: str, users_schema: Schema) -> None:
        """except single column expands to explicit column list."""
        settings = CompileSettings(schema=users_schema)
        result = transpile('from users except password_hash', dialect=dialect, settings=settings)
        
        # Should NOT contain EXCEPT syntax
        assert 'EXCEPT' not in result.upper()
        assert 'EXCLUDE' not in result.upper()
        
        # Should contain the non-excluded columns
        assert 'id' in result.lower()
        assert 'name' in result.lower()
        assert 'email' in result.lower()
        assert 'created_at' in result.lower()
        
        # Should NOT contain the excluded column
        assert 'password_hash' not in result.lower()
    
    @pytest.mark.parametrize("dialect", NO_EXCLUDE_DIALECTS)
    def test_except_multiple_columns(self, dialect: str, users_schema: Schema) -> None:
        """except multiple columns expands correctly."""
        settings = CompileSettings(schema=users_schema)
        result = transpile('from users except password_hash, email', dialect=dialect, settings=settings)
        
        assert 'EXCEPT' not in result.upper()
        
        # Should contain non-excluded columns
        assert 'id' in result.lower()
        assert 'name' in result.lower()
        assert 'created_at' in result.lower()
        
        # Should NOT contain excluded columns
        assert 'password_hash' not in result.lower()
        assert ', email' not in result.lower()  # email should be gone
    
    @pytest.mark.parametrize("dialect", EXCLUDE_DIALECTS)
    def test_except_uses_native_syntax_for_supported_dialects(
        self, dialect: str, users_schema: Schema
    ) -> None:
        """Dialects with EXCLUDE support should use native syntax."""
        settings = CompileSettings(schema=users_schema)
        result = transpile('from users except password_hash', dialect=dialect, settings=settings)
        
        # Should use native EXCEPT or EXCLUDE syntax
        assert 'EXCEPT' in result.upper() or 'EXCLUDE' in result.upper()


class TestExceptOperatorWithoutSchema:
    """Test 'except' operator without schema raises error for unsupported dialects."""
    
    @pytest.mark.parametrize("dialect", NO_EXCLUDE_DIALECTS)
    def test_except_without_schema_raises_error(self, dialect: str) -> None:
        """except without schema raises ASQLDialectError."""
        with pytest.raises(ASQLDialectError) as exc_info:
            transpile('from users except password_hash', dialect=dialect)
        
        # Error message should be helpful
        error_msg = str(exc_info.value)
        assert 'Column operators' in error_msg or 'except' in error_msg.lower()
        assert dialect.lower() in error_msg.lower() or 'PostgreSQL' in error_msg or 'MySQL' in error_msg
    
    @pytest.mark.parametrize("dialect", EXCLUDE_DIALECTS)
    def test_except_without_schema_works_for_supported_dialects(self, dialect: str) -> None:
        """Dialects with EXCLUDE support don't need schema."""
        # Should not raise
        result = transpile('from users except password_hash', dialect=dialect)
        assert result is not None
        assert 'EXCEPT' in result.upper() or 'EXCLUDE' in result.upper()


class TestRenameOperatorWithSchema:
    """Test 'rename' operator with schema for dialects without EXCLUDE support."""
    
    @pytest.mark.parametrize("dialect", NO_EXCLUDE_DIALECTS)
    def test_rename_column(self, dialect: str, users_schema: Schema) -> None:
        """rename column expands to explicit column list with alias."""
        settings = CompileSettings(schema=users_schema)
        result = transpile('from users rename id as user_id', dialect=dialect, settings=settings)
        
        # Should NOT contain EXCEPT syntax
        assert 'EXCEPT' not in result.upper()
        assert 'EXCLUDE' not in result.upper()
        
        # Should contain the renamed column
        assert 'user_id' in result.lower()
        
        # Original 'id' should appear as "id AS user_id", not standalone
        # The exact pattern depends on SQLGlot formatting


class TestReplaceOperatorWithSchema:
    """Test 'replace' operator with schema for dialects without EXCLUDE support."""
    
    @pytest.mark.parametrize("dialect", NO_EXCLUDE_DIALECTS)
    def test_replace_column(self, dialect: str, users_schema: Schema) -> None:
        """replace column expands with expression."""
        settings = CompileSettings(schema=users_schema)
        result = transpile('from users replace name with upper(name)', dialect=dialect, settings=settings)
        
        # Should NOT contain EXCEPT syntax
        assert 'EXCEPT' not in result.upper()
        assert 'EXCLUDE' not in result.upper()
        
        # Should contain the replacement expression
        assert 'upper' in result.lower()


class TestCombinedOperatorsWithSchema:
    """Test combined column operators with schema."""
    
    @pytest.mark.parametrize("dialect", NO_EXCLUDE_DIALECTS)
    def test_except_and_rename(self, dialect: str, users_schema: Schema) -> None:
        """except + rename combined works correctly."""
        settings = CompileSettings(schema=users_schema)
        result = transpile(
            'from users except password_hash rename id as user_id', 
            dialect=dialect, 
            settings=settings
        )
        
        assert 'EXCEPT' not in result.upper()
        assert 'password_hash' not in result.lower()
        assert 'user_id' in result.lower()
    
    @pytest.mark.parametrize("dialect", NO_EXCLUDE_DIALECTS)
    def test_except_and_replace(self, dialect: str, users_schema: Schema) -> None:
        """except + replace combined works correctly."""
        settings = CompileSettings(schema=users_schema)
        result = transpile(
            'from users except password_hash replace name with upper(name)', 
            dialect=dialect, 
            settings=settings
        )
        
        assert 'EXCEPT' not in result.upper()
        assert 'password_hash' not in result.lower()
        assert 'upper' in result.lower()


class TestSchemaFromDict:
    """Test Schema.from_dict for column operators."""
    
    def test_from_dict_with_columns_list(self) -> None:
        """Schema can be created with columns as list."""
        schema = Schema.from_dict({
            'tables': {
                'users': {
                    'columns': ['id', 'name', 'email']
                }
            }
        })
        
        assert schema.has_table('users')
        table = schema.get_table('users')
        assert table is not None
        assert table.has_column('id')
        assert table.has_column('name')
        assert table.has_column('email')
    
    def test_column_lookup_case_insensitive(self) -> None:
        """Column lookup should be case-insensitive."""
        schema = Schema.from_dict({
            'tables': {
                'users': {
                    'columns': ['ID', 'Name', 'EMAIL']
                }
            }
        })
        
        table = schema.get_table('users')
        assert table is not None
        assert table.has_column('id')
        assert table.has_column('ID')
        assert table.has_column('Id')


class TestEdgeCases:
    """Test edge cases for column operators fallback."""
    
    def test_table_not_in_schema_falls_back_to_except(self, users_schema: Schema) -> None:
        """If table not in schema, use EXCEPT syntax (will fail at runtime)."""
        settings = CompileSettings(schema=users_schema)
        # orders table not in schema
        # For supported dialects, this should work with EXCEPT
        result = transpile('from orders except secret_col', dialect='duckdb', settings=settings)
        # DuckDB supports EXCLUDE, so this should use native syntax
        assert 'EXCLUDE' in result.upper() or 'EXCEPT' in result.upper()
    
    def test_empty_schema(self) -> None:
        """Empty schema falls back to EXCEPT syntax."""
        schema = Schema.from_dict({'tables': {}})
        settings = CompileSettings(schema=schema)
        
        # For supported dialects, this should still work
        result = transpile('from users except password', dialect='snowflake', settings=settings)
        assert 'EXCLUDE' in result.upper() or 'EXCEPT' in result.upper()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
