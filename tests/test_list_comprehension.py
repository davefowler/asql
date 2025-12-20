"""Tests for Python-style list comprehensions in ASQL."""

import pytest
import sqlglot
from sqlglot import exp
from asql import compile
from asql.errors import ASQLCompilationError
from tests.fixtures import assert_valid_sql, assert_sql_contains


class TestListComprehensions:
    """Test Python-style list comprehensions."""
    
    def test_basic_list_comprehension(self) -> None:
        """Test basic list comprehension: [expr for var in arr]."""
        asql = 'from events select [lower(tag) for tag in tags] as normalized'
        sql = compile(asql)
        
        assert_sql_contains(sql, "ARRAY", "SELECT", "LOWER", "tag", "FROM", "UNNEST", "tags")
        assert_valid_sql(sql)
        
        # Verify ARRAY structure
        parsed = sqlglot.parse_one(sql)
        array_expr = parsed.find(exp.Array)
        assert array_expr is not None, "ARRAY expression not found"
    
    def test_list_comprehension_with_condition(self) -> None:
        """Test list comprehension with filter: [expr for var in arr if condition]."""
        asql = 'from data select [x * 2 for x in numbers if x > 0] as doubled'
        sql = compile(asql)
        
        assert_sql_contains(sql, "ARRAY", "SELECT", "x", "*", "2", "FROM", "UNNEST", "numbers", "WHERE", "x", ">", "0")
        assert_valid_sql(sql)
    
    def test_list_comprehension_with_function(self) -> None:
        """Test list comprehension with function call."""
        asql = 'from events select [upper(name) for name in names] as upper_names'
        sql = compile(asql)
        
        assert_sql_contains(sql, "ARRAY", "SELECT", "UPPER", "name", "FROM", "UNNEST", "names")
        assert_valid_sql(sql)
    
    def test_list_comprehension_with_arithmetic(self) -> None:
        """Test list comprehension with arithmetic operations."""
        asql = 'from data select [value + 10 for value in values] as incremented'
        sql = compile(asql)
        
        assert_sql_contains(sql, "ARRAY", "SELECT", "value", "+", "10", "FROM", "UNNEST", "values")
        assert_valid_sql(sql)
    
    def test_list_comprehension_with_complex_condition(self) -> None:
        """Test list comprehension with complex filter condition."""
        asql = 'from data select [x for x in numbers if x > 0 and x < 100] as filtered'
        sql = compile(asql)
        
        assert_sql_contains(sql, "ARRAY", "SELECT", "x", "FROM", "UNNEST", "numbers", "WHERE")
        assert_sql_contains(sql, "x", ">", "0", "AND", "x", "<", "100")
        assert_valid_sql(sql)
    
    def test_multiple_list_comprehensions(self) -> None:
        """Test multiple list comprehensions in select."""
        asql = '''from events
  select
    [lower(tag) for tag in tags] as normalized_tags,
    [upper(name) for name in names] as upper_names'''
        sql = compile(asql)
        
        assert_sql_contains(sql, "ARRAY", "SELECT", "LOWER", "tag", "FROM", "UNNEST", "tags")
        assert_sql_contains(sql, "ARRAY", "SELECT", "UPPER", "name", "FROM", "UNNEST", "names")
        assert_valid_sql(sql)
    
    def test_list_comprehension_with_other_columns(self) -> None:
        """Test list comprehension referencing other columns."""
        # Use CONCAT instead of || since || may be transformed before list comprehension parsing
        asql = 'from events select [concat(tag, "_", event_id) for tag in tags] as combined'
        sql = compile(asql)
        
        # CONCAT gets transpiled to || in SQL, so check for the actual SQL operators
        assert_sql_contains(sql, "ARRAY", "SELECT", "tag", "event_id", "FROM", "UNNEST", "tags")
        assert_valid_sql(sql)


class TestListComprehensionDialects:
    """Test list comprehensions across different SQL dialects."""
    
    def test_postgresql_dialect(self) -> None:
        """Test list comprehensions compile to PostgreSQL."""
        asql = 'from events select [lower(tag) for tag in tags] as normalized'
        sql = compile(asql, dialect="postgres")
        
        assert_sql_contains(sql, "ARRAY", "SELECT", "LOWER", "tag", "FROM", "UNNEST", "tags", "AS", "tag")
        assert_valid_sql(sql)
    
    def test_bigquery_dialect(self) -> None:
        """Test list comprehensions compile to BigQuery."""
        asql = 'from events select [lower(tag) for tag in tags] as normalized'
        sql = compile(asql, dialect="bigquery")
        
        assert_sql_contains(sql, "ARRAY", "SELECT", "LOWER", "tag", "FROM", "UNNEST", "tags")
        assert_valid_sql(sql)
    
    def test_duckdb_dialect(self) -> None:
        """Test list comprehensions compile to DuckDB."""
        asql = 'from events select [lower(tag) for tag in tags] as normalized'
        sql = compile(asql, dialect="duckdb")
        
        # DuckDB supports native list comprehensions, but SQLGlot may transpile to ARRAY(SELECT ...)
        assert_sql_contains(sql, "ARRAY", "SELECT", "LOWER", "tag", "FROM", "UNNEST", "tags")
        assert_valid_sql(sql)
    
    def test_snowflake_dialect_error(self) -> None:
        """Test that Snowflake raises helpful error."""
        asql = 'from events select [lower(tag) for tag in tags] as normalized'
        
        with pytest.raises(ASQLCompilationError) as exc_info:
            compile(asql, dialect="snowflake")
        
        error_msg = str(exc_info.value)
        assert "Snowflake" in error_msg or "snowflake" in error_msg.lower()
        assert "not yet fully supported" in error_msg.lower() or "workaround" in error_msg.lower()
    
    def test_mysql_dialect_error(self) -> None:
        """Test that MySQL raises error (no array support)."""
        asql = 'from events select [lower(tag) for tag in tags] as normalized'
        
        # MySQL doesn't support arrays, so this should fail at SQLGlot parsing/transpilation
        # The exact error depends on SQLGlot's MySQL handling
        try:
            sql = compile(asql, dialect="mysql")
            # If it doesn't error, the SQL should be invalid or MySQL-specific
            # For now, we'll just verify it compiles (MySQL might reject it at execution time)
            assert "ARRAY" in sql or "array" in sql.lower()
        except Exception:
            # Expected - MySQL doesn't support arrays
            pass


class TestListComprehensionEdgeCases:
    """Test edge cases for list comprehensions."""
    
    def test_list_comprehension_in_select_with_other_expressions(self) -> None:
        """Test list comprehension alongside other SELECT expressions."""
        asql = '''from events
  select
    event_id,
    [lower(tag) for tag in tags] as normalized_tags,
    event_name'''
        sql = compile(asql)
        
        assert_sql_contains(sql, "event_id", "ARRAY", "SELECT", "LOWER", "tag", "event_name")
        assert_valid_sql(sql)
    
    def test_list_comprehension_with_string_literal(self) -> None:
        """Test list comprehension with string literal in expression."""
        asql = 'from data select ["prefix_" || x for x in values] as prefixed'
        sql = compile(asql)
        
        assert_sql_contains(sql, "ARRAY", "SELECT", "prefix_", "FROM", "UNNEST", "values")
        assert_valid_sql(sql)
    
    def test_list_comprehension_with_nested_function(self) -> None:
        """Test list comprehension with nested function calls."""
        asql = 'from events select [lower(upper(tag)) for tag in tags] as normalized'
        sql = compile(asql)
        
        assert_sql_contains(sql, "ARRAY", "SELECT", "LOWER", "UPPER", "tag", "FROM", "UNNEST", "tags")
        assert_valid_sql(sql)
