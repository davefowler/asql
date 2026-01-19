"""Tests for PostgreSQL-style casting (::) in ASQL."""

import sqlglot
from sqlglot import exp
from tests.fixtures import transpile
from tests.fixtures import assert_valid_sql, assert_sql_contains


class TestCastOperator:
    """Test :: operator for type casting."""
    
    def test_simple_cast_timestamp(self) -> None:
        """Test simple cast to TIMESTAMP."""
        asql = "from fields select _fivetran_synced::TIMESTAMP as _fivetran_synced"
        sql = transpile(asql)
        
        assert_sql_contains(sql, "_fivetran_synced", "TIMESTAMP")
        assert_valid_sql(sql)
        
        # Verify CAST structure
        parsed = sqlglot.parse_one(sql)
        select = parsed.find(exp.Select)
        assert select is not None
        cast_expr = select.find(exp.Cast)
        assert cast_expr is not None, "CAST expression not found in SELECT"
        assert "TIMESTAMP" in cast_expr.sql().upper()
    
    def test_cast_to_date(self) -> None:
        """Test cast to DATE."""
        asql = "from events select created_at::DATE as date_day"
        sql = transpile(asql)
        assert "CAST" in sql.upper() or "DATE" in sql.upper()
        assert "created_at" in sql.lower()
    
    def test_cast_to_int(self) -> None:
        """Test cast to INT."""
        asql = "from products select price::INT as price_int"
        sql = transpile(asql)
        assert "CAST" in sql.upper() or "INT" in sql.upper()
        assert "price" in sql.lower()
    
    def test_cast_to_varchar(self) -> None:
        """Test cast to VARCHAR."""
        asql = "from users select id::VARCHAR as user_id_str"
        sql = transpile(asql)
        assert "CAST" in sql.upper() or "VARCHAR" in sql.upper()
        assert "id" in sql.lower()
    
    def test_cast_in_where_clause(self) -> None:
        """Test cast in WHERE clause."""
        asql = 'from orders where created_at::DATE == "2024-01-01"'
        sql = transpile(asql)
        assert "CAST" in sql.upper() or "DATE" in sql.upper()
        assert "created_at" in sql.lower()
        assert "WHERE" in sql.upper()
    
    def test_cast_with_arithmetic(self) -> None:
        """Test cast with arithmetic operations."""
        asql = "from products select price::INT * 2 as double_price"
        sql = transpile(asql)
        assert "CAST" in sql.upper() or "INT" in sql.upper()
        assert "*" in sql or "MUL" in sql.upper()
    
    def test_cast_chained(self) -> None:
        """Test chained casts (right-associative)."""
        asql = "from fields select value::FLOAT::INT as int_value"
        sql = transpile(asql)
        
        assert_sql_contains(sql, "value", "INT", "int_value")
        assert_valid_sql(sql)
        
        # Verify nested CAST structure
        parsed = sqlglot.parse_one(sql)
        select = parsed.find(exp.Select)
        assert select is not None
        cast_expr = select.find(exp.Cast)
        assert cast_expr is not None, "CAST expression not found"
        # Should have INT in the outer cast
        assert "INT" in cast_expr.sql().upper()
    
    def test_cast_in_select_list(self) -> None:
        """Test cast in SELECT list with multiple columns."""
        asql = "from users select name, age::VARCHAR as age_str, email"
        sql = transpile(asql)
        assert "CAST" in sql.upper() or "VARCHAR" in sql.upper()
        assert "age" in sql.lower()
        assert "name" in sql.lower()
        assert "email" in sql.lower()


class TestCastReverse:
    """Test reverse compilation of CAST(... AS ...) to :: using sqlglot.transpile()."""
    
    def test_cast_to_double_colon_timestamp(self) -> None:
        """Test CAST(... AS TIMESTAMP) converts to ::TIMESTAMP."""
        sql = "SELECT CAST(_fivetran_synced AS TIMESTAMP) AS _fivetran_synced FROM fields"
        asql = sqlglot.transpile(sql, write="asql")[0]
        
        assert "::" in asql, f"Expected :: operator in reverse-compiled ASQL: {asql}"
        assert "_fivetran_synced" in asql.lower()
        assert "TIMESTAMP" in asql.upper()
        
        # Round-trip test: compile back to SQL
        round_trip_sql = transpile(asql)
        assert_valid_sql(round_trip_sql)
        assert_sql_contains(round_trip_sql, "_fivetran_synced", "TIMESTAMP")
    
    def test_cast_to_double_colon_date(self) -> None:
        """Test CAST(... AS DATE) converts to ::DATE."""
        sql = "SELECT CAST(created_at AS DATE) AS date_day FROM events"
        asql = sqlglot.transpile(sql, write="asql")[0]
        assert "::" in asql
        assert "created_at" in asql.lower()
        assert "DATE" in asql.upper()
    
    def test_cast_to_double_colon_int(self) -> None:
        """Test CAST(... AS INT) converts to ::INT."""
        sql = "SELECT CAST(price AS INT) AS price_int FROM products"
        asql = sqlglot.transpile(sql, write="asql")[0]
        assert "::" in asql
        assert "price" in asql.lower()
        assert "INT" in asql.upper()
    
    def test_cast_to_double_colon_varchar(self) -> None:
        """Test CAST(... AS VARCHAR) converts to ::VARCHAR."""
        sql = "SELECT CAST(id AS VARCHAR) AS user_id_str FROM users"
        asql = sqlglot.transpile(sql, write="asql")[0]
        assert "::" in asql
        assert "id" in asql.lower()
        assert "VARCHAR" in asql.upper()
    
    def test_cast_in_where_clause_reverse(self) -> None:
        """Test CAST in WHERE clause converts correctly."""
        sql = "SELECT * FROM orders WHERE CAST(created_at AS DATE) = '2024-01-01'"
        asql = sqlglot.transpile(sql, write="asql")[0]
        
        assert "::" in asql, f"Expected :: operator in reverse-compiled ASQL: {asql}"
        assert "created_at" in asql.lower()
        assert "DATE" in asql.upper()
        assert "where" in asql.lower()
        
        # Round-trip test: compile back to SQL
        round_trip_sql = transpile(asql)
        assert_valid_sql(round_trip_sql)
        assert_sql_contains(round_trip_sql, "created_at", "DATE", "WHERE")
    
    def test_cast_with_alias_reverse(self) -> None:
        """Test CAST with alias converts correctly."""
        sql = "SELECT CAST(amount AS FLOAT) AS amount_float FROM transactions"
        asql = sqlglot.transpile(sql, write="asql")[0]
        assert "::" in asql
        assert "amount" in asql.lower()
        assert "FLOAT" in asql.upper()
        assert "as" in asql.lower()


