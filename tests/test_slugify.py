"""Tests for slugify() URL-friendly slug function in ASQL."""

import pytest
import sqlglot
from sqlglot import exp
from asql import compile
from tests.fixtures import assert_valid_sql, assert_sql_contains


class TestSlugifyFunction:
    """Test slugify() function for URL-friendly slug generation."""
    
    def test_simple_slugify(self) -> None:
        """Test slugify() with a single column."""
        asql = "from products select slugify(name) as slug"
        sql = compile(asql)
        
        assert_sql_contains(sql, "LOWER", "REGEXP_REPLACE", "TRIM", "name")
        assert_valid_sql(sql)
        
        # Verify structure
        parsed = sqlglot.parse_one(sql)
        select = parsed.find(exp.Select)
        assert select is not None
    
    def test_slugify_lowercase(self) -> None:
        """Test that slugify() converts to lowercase."""
        asql = "from products select slugify(title) as slug"
        sql = compile(asql)
        
        # Should use LOWER function
        assert_sql_contains(sql, "LOWER")
        assert_valid_sql(sql)
    
    def test_slugify_regex_replace(self) -> None:
        """Test that slugify() uses regex to replace non-alphanumeric chars."""
        asql = "from products select slugify(name) as slug"
        sql = compile(asql)
        
        # Should use REGEXP_REPLACE
        assert_sql_contains(sql, "REGEXP_REPLACE")
        # Should have the pattern for non-alphanumeric characters
        assert "[^a-z0-9]+" in sql
        assert_valid_sql(sql)
    
    def test_slugify_trim(self) -> None:
        """Test that slugify() trims leading/trailing hyphens."""
        asql = "from products select slugify(name) as slug"
        sql = compile(asql)
        
        # Should use TRIM to remove leading/trailing hyphens
        assert_sql_contains(sql, "TRIM")
        assert "'-'" in sql or '"-"' in sql
        assert_valid_sql(sql)
    
    def test_slugify_with_alias(self) -> None:
        """Test slugify() with explicit alias."""
        asql = "from products select slugify(title) as url_slug"
        sql = compile(asql)
        
        assert_sql_contains(sql, "url_slug")
        assert_valid_sql(sql)
    
    def test_slugify_in_select_list(self) -> None:
        """Test slugify() alongside other columns."""
        asql = """
        from products
        select
            id,
            name,
            slugify(name) as slug,
            price
        """
        sql = compile(asql)
        
        assert_sql_contains(sql, "id", "name", "slug", "price")
        assert_sql_contains(sql, "REGEXP_REPLACE", "LOWER", "TRIM")
        assert_valid_sql(sql)
    
    def test_slugify_in_where(self) -> None:
        """Test slugify() in WHERE clause."""
        asql = """
        from products
        where slugify(name) = 'hello-world'
        """
        sql = compile(asql)
        
        assert_sql_contains(sql, "WHERE", "REGEXP_REPLACE", "LOWER", "TRIM")
        assert_valid_sql(sql)
    
    def test_slugify_with_concat(self) -> None:
        """Test slugify() with concatenated expressions."""
        asql = "from products select slugify(concat(category, '-', name)) as slug"
        sql = compile(asql)
        
        assert_sql_contains(sql, "CONCAT", "REGEXP_REPLACE", "LOWER")
        assert_valid_sql(sql)
    
    def test_slugify_with_table_qualification(self) -> None:
        """Test slugify() with table-qualified column."""
        asql = "from products select slugify(products.name) as slug"
        sql = compile(asql)
        
        assert_sql_contains(sql, "products.name")
        assert_valid_sql(sql)
    
    def test_multiple_slugify_calls(self) -> None:
        """Test multiple slugify() calls in same query."""
        asql = """
        from products
        select
            slugify(name) as name_slug,
            slugify(category) as category_slug
        """
        sql = compile(asql)
        
        # Should have two REGEXP_REPLACE patterns
        sql_lower = sql.lower()
        count = sql_lower.count("regexp_replace")
        assert count == 2, f"Expected 2 REGEXP_REPLACE calls, found {count}"
        assert_valid_sql(sql)
    
    def test_slugify_nested_function(self) -> None:
        """Test slugify() with nested function calls."""
        asql = "from products select slugify(upper(name)) as slug"
        sql = compile(asql)
        
        # Should have both UPPER and LOWER
        assert_sql_contains(sql, "UPPER", "LOWER")
        assert_valid_sql(sql)


class TestSlugifyCrossDialect:
    """Test slugify() function across different SQL dialects."""
    
    def test_slugify_postgresql(self) -> None:
        """Test slugify() compiles to PostgreSQL."""
        asql = "from products select slugify(name) as slug"
        sql = compile(asql, dialect="postgres")
        
        assert_sql_contains(sql, "REGEXP_REPLACE", "LOWER", "TRIM")
        assert_valid_sql(sql)
    
    def test_slugify_duckdb(self) -> None:
        """Test slugify() compiles to DuckDB."""
        asql = "from products select slugify(name) as slug"
        sql = compile(asql, dialect="duckdb")
        
        # DuckDB supports REGEXP_REPLACE
        assert_sql_contains(sql, "REGEXP_REPLACE", "LOWER")
        assert_valid_sql(sql)
    
    def test_slugify_bigquery(self) -> None:
        """Test slugify() compiles to BigQuery."""
        asql = "from products select slugify(name) as slug"
        sql = compile(asql, dialect="bigquery")
        
        # BigQuery supports REGEXP_REPLACE
        assert_sql_contains(sql, "REGEXP_REPLACE", "LOWER")
        assert_valid_sql(sql)
    
    def test_slugify_snowflake(self) -> None:
        """Test slugify() compiles to Snowflake."""
        asql = "from products select slugify(name) as slug"
        sql = compile(asql, dialect="snowflake")
        
        # Snowflake supports REGEXP_REPLACE
        assert_sql_contains(sql, "REGEXP_REPLACE", "LOWER")
        assert_valid_sql(sql)


class TestSlugifyEdgeCases:
    """Test edge cases for slugify() function."""
    
    def test_slugify_empty_arg(self) -> None:
        """Test that slugify() handles empty strings."""
        asql = "from products select slugify('') as slug"
        sql = compile(asql)
        
        assert_valid_sql(sql)
    
    def test_slugify_case_insensitive(self) -> None:
        """Test that SLUGIFY (uppercase) works too."""
        asql = "from products select SLUGIFY(name) as slug"
        sql = compile(asql)
        
        assert_sql_contains(sql, "REGEXP_REPLACE", "LOWER", "TRIM")
        assert_valid_sql(sql)
    
    def test_slugify_preserves_other_content(self) -> None:
        """Test that slugify transformation preserves other query parts."""
        asql = """
        from products
        where category = 'electronics'
        select id, slugify(name) as slug
        order by id
        limit 10
        """
        sql = compile(asql)
        
        assert_sql_contains(sql, "WHERE", "ORDER BY", "LIMIT")
        assert_valid_sql(sql)
    
    def test_slugify_with_string_literal(self) -> None:
        """Test slugify() with string literal argument."""
        asql = "from products select slugify('Hello World!') as slug"
        sql = compile(asql)
        
        assert_sql_contains(sql, "Hello World!")
        assert_valid_sql(sql)
    
    def test_slugify_in_group_by(self) -> None:
        """Test slugify() in GROUP BY context."""
        asql = """
        from products
        group by slugify(category) (
            count(*) as product_count
        )
        """
        sql = compile(asql)
        
        assert_sql_contains(sql, "GROUP BY", "REGEXP_REPLACE")
        assert_valid_sql(sql)
    
    def test_slugify_in_order_by(self) -> None:
        """Test slugify() in ORDER BY context."""
        asql = """
        from products
        order by slugify(name)
        """
        sql = compile(asql)
        
        assert_sql_contains(sql, "ORDER BY", "REGEXP_REPLACE")
        assert_valid_sql(sql)
    
    def test_slugify_with_coalesce(self) -> None:
        """Test slugify() with coalesce for NULL handling."""
        asql = "from products select slugify(coalesce(name, 'unknown')) as slug"
        sql = compile(asql)
        
        assert_sql_contains(sql, "COALESCE", "REGEXP_REPLACE", "LOWER")
        assert_valid_sql(sql)
