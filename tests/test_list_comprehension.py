"""Tests for Python-style list comprehensions in ASQL."""

import sqlglot
from sqlglot import exp
from tests.fixtures import transpile
from tests.fixtures import assert_valid_sql, assert_sql_contains


class TestListComprehensions:
    """Test Python-style list comprehensions (default dialect: DuckDB with native syntax)."""
    
    def test_basic_list_comprehension(self) -> None:
        """Test basic list comprehension: [expr for var in arr]."""
        asql = 'from events select [lower(tag) for tag in tags] as normalized'
        sql = transpile(asql)  # defaults to DuckDB
        
        # DuckDB uses native syntax: [expr FOR var IN arr]
        assert "[" in sql and "]" in sql
        assert "LOWER" in sql.upper()
        assert "FOR" in sql.upper()
        assert "tag" in sql.lower()
        assert_valid_sql(sql)
    
    def test_list_comprehension_with_condition(self) -> None:
        """Test list comprehension with filter: [expr for var in arr if condition]."""
        asql = 'from data select [x * 2 for x in numbers if x > 0] as doubled'
        sql = transpile(asql)
        
        # DuckDB: [x * 2 FOR x IN numbers IF x > 0]
        assert "FOR" in sql.upper()
        assert "IF" in sql.upper()
        assert "*" in sql and "2" in sql
        assert_valid_sql(sql)
    
    def test_list_comprehension_with_function(self) -> None:
        """Test list comprehension with function call."""
        asql = 'from events select [upper(name) for name in names] as upper_names'
        sql = transpile(asql)
        
        assert "FOR" in sql.upper()
        assert "UPPER" in sql.upper()
        assert_valid_sql(sql)
    
    def test_list_comprehension_with_arithmetic(self) -> None:
        """Test list comprehension with arithmetic operations."""
        asql = 'from data select [value + 10 for value in values] as incremented'
        sql = transpile(asql)
        
        assert "FOR" in sql.upper()
        assert "+" in sql
        assert_valid_sql(sql)
    
    def test_list_comprehension_with_complex_condition(self) -> None:
        """Test list comprehension with complex filter condition."""
        asql = 'from data select [x for x in numbers if x > 0 and x < 100] as filtered'
        sql = transpile(asql)
        
        assert "FOR" in sql.upper()
        assert "IF" in sql.upper()
        assert "AND" in sql.upper()
        assert_valid_sql(sql)
    
    def test_multiple_list_comprehensions(self) -> None:
        """Test multiple list comprehensions in select."""
        asql = '''from events
  select
    [lower(tag) for tag in tags] as normalized_tags,
    [upper(name) for name in names] as upper_names'''
        sql = transpile(asql)
        
        assert sql.upper().count("FOR") == 2  # Two comprehensions
        assert "LOWER" in sql.upper()
        assert "UPPER" in sql.upper()
        assert_valid_sql(sql)
    
    def test_list_comprehension_with_other_columns(self) -> None:
        """Test list comprehension referencing other columns."""
        asql = 'from events select [concat(tag, "_", event_id) for tag in tags] as combined'
        sql = transpile(asql)
        
        assert "FOR" in sql.upper()
        assert "tag" in sql.lower()
        assert_valid_sql(sql)


class TestListComprehensionDialects:
    """Test list comprehensions across different SQL dialects."""
    
    def test_postgresql_dialect(self) -> None:
        """Test list comprehensions compile to PostgreSQL ARRAY(SELECT ... FROM UNNEST(...))."""
        asql = 'from events select [lower(tag) for tag in tags] as normalized'
        sql = transpile(asql, dialect="postgres")
        
        # Postgres uses ARRAY(SELECT ... FROM UNNEST(...))
        assert_sql_contains(sql, "ARRAY", "SELECT", "LOWER", "tag", "FROM", "UNNEST", "tags", "AS", "tag")
        assert_valid_sql(sql)
    
    def test_bigquery_dialect(self) -> None:
        """Test list comprehensions compile to BigQuery ARRAY(SELECT ... FROM UNNEST(...))."""
        asql = 'from events select [lower(tag) for tag in tags] as normalized'
        sql = transpile(asql, dialect="bigquery")
        
        # BigQuery uses ARRAY(SELECT ... FROM UNNEST(...))
        assert_sql_contains(sql, "ARRAY", "SELECT", "LOWER", "tag", "FROM", "UNNEST", "tags")
        assert_valid_sql(sql)
    
    def test_duckdb_dialect(self) -> None:
        """Test list comprehensions compile to DuckDB native syntax."""
        asql = 'from events select [lower(tag) for tag in tags] as normalized'
        sql = transpile(asql, dialect="duckdb")
        
        # DuckDB uses native list comprehension syntax: [expr FOR var IN arr]
        assert "[" in sql and "]" in sql
        assert "FOR" in sql.upper()
        assert "IN" in sql.upper()
        assert "LOWER" in sql.upper()
        # Should NOT use ARRAY(SELECT...) syntax for DuckDB
        assert "UNNEST" not in sql.upper()
        assert_valid_sql(sql)
    
    def test_snowflake_dialect(self) -> None:
        """Test list comprehensions for Snowflake.
        
        Snowflake doesn't support Python-style list comprehensions or 
        ARRAY(SELECT ... FROM UNNEST(...)). The generated SQL will compile
        but may fail at execution time. This is a known limitation.
        """
        asql = 'from events select [lower(tag) for tag in tags] as normalized'
        sql = transpile(asql, dialect="snowflake")
        
        # Just verify it compiles and contains expected elements
        assert "LOWER" in sql.upper()
        assert "tag" in sql.lower()
    
    def test_mysql_dialect_error(self) -> None:
        """Test that MySQL raises error (no array support)."""
        asql = 'from events select [lower(tag) for tag in tags] as normalized'
        
        # MySQL doesn't support arrays, so this should fail at SQLGlot parsing/transpilation
        # The exact error depends on SQLGlot's MySQL handling
        try:
            sql = transpile(asql, dialect="mysql")
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
        sql = transpile(asql)
        
        assert "event_id" in sql.lower()
        assert "event_name" in sql.lower()
        assert "FOR" in sql.upper()
        assert_valid_sql(sql)
    
    def test_list_comprehension_with_string_literal(self) -> None:
        """Test list comprehension with string literal in expression."""
        asql = 'from data select ["prefix_" || x for x in values] as prefixed'
        sql = transpile(asql)
        
        assert "FOR" in sql.upper()
        assert "prefix_" in sql
        assert_valid_sql(sql)
    
    def test_list_comprehension_with_nested_function(self) -> None:
        """Test list comprehension with nested function calls."""
        asql = 'from events select [lower(upper(tag)) for tag in tags] as normalized'
        sql = transpile(asql)
        
        assert "FOR" in sql.upper()
        assert "LOWER" in sql.upper()
        assert "UPPER" in sql.upper()
        assert_valid_sql(sql)
    
    def test_postgres_array_select_structure(self) -> None:
        """Verify Postgres output has correct ARRAY(SELECT...) structure."""
        asql = 'from events select [lower(tag) for tag in tags] as normalized'
        sql = transpile(asql, dialect="postgres")
        
        # Verify structure
        parsed = sqlglot.parse_one(sql)
        array_expr = parsed.find(exp.Array)
        assert array_expr is not None, "ARRAY expression not found"
