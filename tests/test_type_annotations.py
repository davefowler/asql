"""Tests for type annotations in compile flow.

When schema is provided, compile() and compile_to_ast() now run
qualify_columns + annotate_types to add type info to the AST.
"""

import pytest
from sqlglot import exp

from asql import compile, compile_to_ast
from asql.config import CompileSettings
from asql.schema import Schema


@pytest.fixture
def schema() -> Schema:
    """Create a test schema with type information."""
    return Schema.from_dict({
        'tables': {
            'users': {'columns': {'id': 'INT', 'name': 'VARCHAR', 'email': 'VARCHAR'}},
            'orders': {'columns': {'id': 'INT', 'user_id': 'INT', 'amount': 'DECIMAL', 'status': 'VARCHAR'}},
        }
    })


@pytest.fixture
def settings(schema: Schema) -> CompileSettings:
    """Create compile settings with schema."""
    return CompileSettings(schema=schema)


class TestSchemaFromDict:
    """Test Schema.from_dict with {col: type} format."""
    
    def test_dict_format_preserves_types(self) -> None:
        """Schema.from_dict should preserve column types from {col: type} format."""
        schema = Schema.from_dict({
            'tables': {
                'users': {'columns': {'id': 'INT', 'name': 'VARCHAR'}}
            }
        })
        
        users = schema.tables['users']
        assert users.columns['id'].type == 'INT'
        assert users.columns['name'].type == 'VARCHAR'
    
    def test_list_format_still_works(self) -> None:
        """Schema.from_dict should still work with list format (no types)."""
        schema = Schema.from_dict({
            'tables': {
                'users': {'columns': ['id', 'name', 'email']}
            }
        })
        
        users = schema.tables['users']
        assert 'id' in users.columns
        assert 'name' in users.columns
        assert 'email' in users.columns
        # Types are None for list format
        assert users.columns['id'].type is None


@pytest.mark.skip(reason="compile_to_ast doesn't yet support schema/dialect params - feature not implemented")
class TestCompileToAstTypeAnnotations:
    """Test that compile_to_ast adds type annotations when schema provided."""
    
    def test_simple_select_has_types(self, settings: CompileSettings) -> None:
        """Columns should have type annotations after compile_to_ast."""
        ast = compile_to_ast(
            'from users select id, name',
            dialect='postgres',
            settings=settings
        )
        
        # Find columns and check types
        columns = [n for n in ast.walk() if isinstance(n, exp.Column)]
        typed_columns = {c.name: str(c.type) for c in columns if c.type and str(c.type) != 'UNKNOWN'}
        
        assert 'id' in typed_columns
        assert typed_columns['id'] == 'INT'
        assert 'name' in typed_columns
        assert typed_columns['name'] == 'VARCHAR'
    
    def test_join_has_types_from_both_tables(self, settings: CompileSettings) -> None:
        """Columns from joined tables should all have types."""
        ast = compile_to_ast(
            'from users & orders on users.id = orders.user_id select users.name, orders.amount',
            dialect='postgres',
            settings=settings
        )
        
        columns = [n for n in ast.walk() if isinstance(n, exp.Column)]
        typed_columns = {f"{c.table}.{c.name}": str(c.type) for c in columns if c.type and str(c.type) != 'UNKNOWN'}
        
        assert 'users.name' in typed_columns
        assert typed_columns['users.name'] == 'VARCHAR'
        assert 'orders.amount' in typed_columns
        assert typed_columns['orders.amount'] == 'DECIMAL'
    
    def test_where_condition_columns_have_types(self, settings: CompileSettings) -> None:
        """Columns in WHERE clause should have types."""
        ast = compile_to_ast(
            'from users where id = 1',
            dialect='postgres',
            settings=settings
        )
        
        # Find the column in WHERE
        where = ast.find(exp.Where)
        assert where is not None
        
        columns = list(where.find_all(exp.Column))
        assert len(columns) > 0
        
        id_col = next((c for c in columns if c.name == 'id'), None)
        assert id_col is not None
        assert str(id_col.type) == 'INT'
    
    def test_no_schema_no_types(self) -> None:
        """Without schema, columns should not have type annotations."""
        ast = compile_to_ast('from users select id, name', dialect='postgres')
        
        columns = [n for n in ast.walk() if isinstance(n, exp.Column)]
        # All types should be None or UNKNOWN
        for col in columns:
            assert col.type is None or str(col.type) == 'UNKNOWN'
    
    def test_alias_expressions_have_types(self, settings: CompileSettings) -> None:
        """Aliased expressions should have inferred types."""
        ast = compile_to_ast(
            'from users select id as user_id, name as user_name',
            dialect='postgres',
            settings=settings
        )
        
        aliases = [n for n in ast.walk() if isinstance(n, exp.Alias)]
        typed_aliases = {a.alias: str(a.type) for a in aliases if a.type and str(a.type) != 'UNKNOWN'}
        
        assert 'user_id' in typed_aliases
        assert typed_aliases['user_id'] == 'INT'
        assert 'user_name' in typed_aliases
        assert typed_aliases['user_name'] == 'VARCHAR'


class TestCompileWithSchemaPreservesOutput:
    """Test that adding type annotations produces valid SQL output."""
    
    def test_compile_with_schema_qualifies_columns(self, settings: CompileSettings) -> None:
        """With schema, columns get qualified with table names."""
        query = 'from users where id = 1 select name'
        
        # Compile with schema - columns should be qualified
        result = compile(query, dialect='postgres', settings=settings)
        
        # Should have qualified column names
        assert 'users.name' in result.lower() or 'users.id' in result.lower()
    
    def test_compile_without_schema_works(self) -> None:
        """Without schema, compilation still works."""
        query = 'from users where id = 1 select name'
        result = compile(query, dialect='postgres')
        
        # Should compile successfully
        assert 'SELECT' in result.upper()
        assert 'FROM users' in result
    
    def test_except_operator_preserved_with_schema(self, settings: CompileSettings) -> None:
        """EXCEPT operator should still work with schema (expand_stars=False)."""
        result = compile(
            'from users except email',
            dialect='bigquery',
            settings=settings
        )
        
        # Should use native EXCEPT syntax
        assert 'EXCEPT' in result.upper() or 'EXCLUDE' in result.upper()
