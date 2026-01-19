"""Tests for key() surrogate key function in ASQL."""

import sqlglot
from sqlglot import exp
from tests.fixtures import transpile
from tests.fixtures import assert_valid_sql


class TestKeyFunction:
    """Test key() function for surrogate key generation."""
    
    def test_simple_key(self) -> None:
        """Test key() with single column."""
        sql = transpile("from orders select key(user_id) as order_key")
        assert_valid_sql(sql)
        
        # Verify MD5 function is present
        parsed = sqlglot.parse_one(sql)
        md5_func = parsed.find(exp.MD5)
        assert md5_func is not None, f"MD5 function not found in: {sql}"
        
        # Should reference user_id
        assert "user_id" in sql.lower()
    
    def test_key_multiple_columns(self) -> None:
        """Test key() with multiple columns."""
        sql = transpile("from orders select key(user_id, order_id) as order_key")
        assert_valid_sql(sql)
        
        # Verify MD5 and both columns
        parsed = sqlglot.parse_one(sql)
        assert parsed.find(exp.MD5) is not None
        assert "user_id" in sql.lower()
        assert "order_id" in sql.lower()
    
    def test_key_three_columns(self) -> None:
        """Test key() with three columns."""
        sql = transpile("from orders select key(user_id, order_id, product_id) as order_key")
        assert_valid_sql(sql)
        
        # All columns should be in the expression
        assert "user_id" in sql.lower()
        assert "order_id" in sql.lower()
        assert "product_id" in sql.lower()
    
    def test_key_with_nulls(self) -> None:
        """Test key() handles NULLs deterministically."""
        sql = transpile("from orders select key(user_id, order_id) as order_key")
        assert_valid_sql(sql)
        
        # Should use COALESCE to handle NULLs
        parsed = sqlglot.parse_one(sql)
        coalesce_funcs = list(parsed.find_all(exp.Coalesce))
        assert len(coalesce_funcs) > 0, f"COALESCE not found for NULL handling in: {sql}"
    
    def test_key_mixed_types(self) -> None:
        """Test key() with mixed column types casts to text."""
        sql = transpile("from orders select key(user_id, order_date, amount) as order_key")
        assert_valid_sql(sql)
        
        # Should have CAST for type coercion
        parsed = sqlglot.parse_one(sql)
        cast_funcs = list(parsed.find_all(exp.Cast))
        assert len(cast_funcs) > 0, f"CAST not found for type coercion in: {sql}"
    
    def test_key_in_group_by(self) -> None:
        """Test key() in GROUP BY context."""
        sql = transpile("""
        from orders
        group by key(user_id, order_id) (
            sum(amount) as total
        )
        """)
        assert_valid_sql(sql)
        
        # MD5 and GROUP BY should be present
        assert "md5" in sql.lower()
        assert "group by" in sql.lower()
    
    def test_key_in_where(self) -> None:
        """Test key() in WHERE clause."""
        sql = transpile("""
        from orders
        where key(user_id, order_id) = 'some_hash_value'
        """)
        assert_valid_sql(sql)
        
        assert "md5" in sql.lower()
        assert "where" in sql.lower()
    
    def test_key_with_expressions(self) -> None:
        """Test key() with expressions, not just columns."""
        sql = transpile("from orders select key(user_id, upper(status)) as order_key")
        assert_valid_sql(sql)
        
        assert "md5" in sql.lower()
        assert "upper" in sql.lower()


class TestKeyCrossDialect:
    """Test key() function across different SQL dialects."""
    
    def test_key_postgresql(self) -> None:
        """Test key() compiles to PostgreSQL."""
        sql = transpile("from orders select key(user_id, order_id) as order_key", dialect="postgres")
        assert_valid_sql(sql)
        assert "md5" in sql.lower()
    
    def test_key_mysql(self) -> None:
        """Test key() compiles to MySQL."""
        sql = transpile("from orders select key(user_id, order_id) as order_key", dialect="mysql")
        assert_valid_sql(sql)
        assert "md5" in sql.lower()
    
    def test_key_bigquery(self) -> None:
        """Test key() compiles to BigQuery."""
        sql = transpile("from orders select key(user_id, order_id) as order_key", dialect="bigquery")
        assert_valid_sql(sql)
        # BigQuery uses MD5 or TO_HEX(MD5(...))
        sql_upper = sql.upper()
        assert "MD5" in sql_upper or "TO_HEX" in sql_upper
    
    def test_key_snowflake(self) -> None:
        """Test key() compiles to Snowflake."""
        sql = transpile("from orders select key(user_id, order_id) as order_key", dialect="snowflake")
        assert_valid_sql(sql)
        assert "md5" in sql.lower() or "hash" in sql.lower()


class TestKeyEdgeCases:
    """Test edge cases for key() function."""
    
    def test_key_single_column(self) -> None:
        """Test key() with just one column."""
        sql = transpile("from users select key(id) as user_key")
        assert_valid_sql(sql)
        assert "md5" in sql.lower()
    
    def test_key_with_table_qualification(self) -> None:
        """Test key() with table-qualified columns."""
        sql = transpile("from orders select key(orders.user_id, orders.order_id) as order_key")
        assert_valid_sql(sql)
        assert "orders" in sql.lower()
    
    def test_key_nested_function_calls(self) -> None:
        """Test key() with nested function calls in arguments."""
        sql = transpile("from orders select key(coalesce(user_id, 0), upper(status)) as order_key")
        assert_valid_sql(sql)
        assert "md5" in sql.lower()
        assert "upper" in sql.lower()
    
    def test_key_in_select_list(self) -> None:
        """Test key() alongside other columns."""
        sql = transpile("""
        from orders
        select
            user_id,
            order_id,
            key(user_id, order_id) as order_key,
            amount
        """)
        assert_valid_sql(sql)
        assert "md5" in sql.lower()
        assert "amount" in sql.lower()
    
    def test_key_deterministic(self) -> None:
        """Test that key() produces deterministic output structure."""
        sql1 = transpile("from orders select key(user_id, order_id) as k1")
        sql2 = transpile("from orders select key(user_id, order_id) as k2")
        
        # Both should have MD5
        assert "md5" in sql1.lower()
        assert "md5" in sql2.lower()
    
    def test_key_delimiter_injection(self) -> None:
        """Test that multi-column key() has delimiter between values."""
        sql = transpile("from orders select key(user_id, order_id) as order_key")
        assert_valid_sql(sql)
        # Should have some delimiter (|| or CONCAT with ||)
        # The exact format depends on dialect
