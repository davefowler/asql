"""Tests for || COALESCE operator in ASQL."""

import pytest
from asql import compile
from asql.reverse_compiler import reverse_compile


class TestCoalesceOperator:
    """Test || operator as COALESCE."""
    
    def test_simple_coalesce(self) -> None:
        """Test simple || COALESCE."""
        asql = "from users where not is_deleted || FALSE"
        sql = compile(asql)
        assert "COALESCE" in sql.upper()
        assert "is_deleted" in sql.lower()
        assert "FALSE" in sql.upper() or "false" in sql.lower()
    
    def test_coalesce_with_not(self) -> None:
        """Test NOT COALESCE pattern."""
        asql = "from users where not is_deleted || FALSE"
        sql = compile(asql)
        assert "NOT" in sql.upper()
        assert "COALESCE" in sql.upper()
    
    def test_coalesce_chain(self) -> None:
        """Test chained || operators."""
        asql = "from users select name || email || 'unknown' as display_name"
        sql = compile(asql)
        assert "COALESCE" in sql.upper()
        assert "name" in sql.lower()
        assert "email" in sql.lower()
    
    def test_coalesce_in_select(self) -> None:
        """Test || in SELECT clause."""
        asql = "from users select is_deleted || FALSE as is_deleted_value"
        sql = compile(asql)
        assert "COALESCE" in sql.upper()
        assert "is_deleted" in sql.lower()


class TestCoalesceReverse:
    """Test reverse compilation of COALESCE to ||."""
    
    def test_coalesce_to_pipe(self) -> None:
        """Test COALESCE converts to ||."""
        sql = "SELECT COALESCE(is_deleted, FALSE) FROM users"
        asql = reverse_compile(sql)
        assert "||" in asql
        assert "is_deleted" in asql.lower()
        assert "FALSE" in asql.upper() or "false" in asql.lower()
    
    def test_coalesce_chain_to_pipe(self) -> None:
        """Test COALESCE with multiple args converts to || chain."""
        sql = "SELECT COALESCE(name, email, 'unknown') FROM users"
        asql = reverse_compile(sql)
        assert "||" in asql
        assert asql.count("||") >= 2  # Should have at least 2 || operators

