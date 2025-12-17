"""Tests for ?? COALESCE operator in ASQL."""

import pytest
import sqlglot
from sqlglot import exp
from asql import compile
from asql.reverse_compiler import reverse_compile
from tests.fixtures import assert_valid_sql, assert_sql_contains


class TestCoalesceOperator:
    """Test ?? operator as COALESCE."""
    
    def test_simple_coalesce(self) -> None:
        """Test simple ?? COALESCE."""
        asql = "from users where not (is_deleted ?? FALSE)"
        sql = compile(asql)
        
        assert_sql_contains(sql, "COALESCE", "is_deleted", "FALSE")
        assert_valid_sql(sql)
        
        # Verify COALESCE structure
        parsed = sqlglot.parse_one(sql)
        where_clause = parsed.find(exp.Where)
        assert where_clause is not None
        coalesce = where_clause.find(exp.Coalesce)
        assert coalesce is not None, "COALESCE function not found in WHERE clause"
    
    def test_coalesce_with_not(self) -> None:
        """Test NOT COALESCE pattern."""
        asql = "from users where not (is_deleted ?? FALSE)"
        sql = compile(asql)
        assert "NOT" in sql.upper()
        assert "COALESCE" in sql.upper()
    
    def test_coalesce_chain(self) -> None:
        """Test chained ?? operators."""
        asql = "from users select name ?? email ?? 'unknown' as display_name"
        sql = compile(asql)
        
        assert_sql_contains(sql, "COALESCE", "name", "email", "unknown", "display_name")
        assert_valid_sql(sql)
        
        # Verify COALESCE with multiple arguments
        parsed = sqlglot.parse_one(sql)
        select = parsed.find(exp.Select)
        assert select is not None
        coalesce = select.find(exp.Coalesce)
        assert coalesce is not None, "COALESCE function not found in SELECT"
        # Verify all arguments are present
        coalesce_sql = coalesce.sql().lower()
        assert "name" in coalesce_sql and "email" in coalesce_sql
    
    def test_coalesce_in_select(self) -> None:
        """Test ?? in SELECT clause."""
        asql = "from users select is_deleted ?? FALSE as is_deleted_value"
        sql = compile(asql)
        assert "COALESCE" in sql.upper()
        assert "is_deleted" in sql.lower()


class TestCoalesceReverse:
    """Test reverse compilation of COALESCE to ??."""
    
    def test_coalesce_to_double_question(self) -> None:
        """Test COALESCE converts to ??."""
        sql = "SELECT COALESCE(is_deleted, FALSE) FROM users"
        asql = reverse_compile(sql)
        
        assert "??" in asql, f"Expected ?? operator in reverse-compiled ASQL: {asql}"
        assert "is_deleted" in asql.lower()
        assert "FALSE" in asql.upper() or "false" in asql.lower()
        
        # Round-trip test: compile back to SQL
        round_trip_sql = compile(asql)
        assert_valid_sql(round_trip_sql)
        assert_sql_contains(round_trip_sql, "COALESCE", "is_deleted")
    
    def test_coalesce_chain_to_double_question(self) -> None:
        """Test COALESCE with multiple args converts to ?? chain."""
        sql = "SELECT COALESCE(name, email, 'unknown') FROM users"
        asql = reverse_compile(sql)
        
        assert "??" in asql, f"Expected ?? operator in reverse-compiled ASQL: {asql}"
        assert asql.count("??") >= 2, f"Expected at least 2 ?? operators, got {asql.count('??')}"
        assert "name" in asql.lower() and "email" in asql.lower()
        
        # Round-trip test: compile back to SQL
        round_trip_sql = compile(asql)
        assert_valid_sql(round_trip_sql)
        assert_sql_contains(round_trip_sql, "COALESCE", "name", "email")


