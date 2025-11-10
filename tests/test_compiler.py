"""Tests for ASQL compiler."""

import pytest
from asql import compile
from asql.errors import ASQLSyntaxError, ASQLCompilationError


def test_compile_simple_from() -> None:
    """Test compiling a simple FROM clause."""
    asql = "from users"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "FROM" in sql_upper
    assert "USERS" in sql_upper
    assert "SELECT" in sql_upper
    assert "*" in sql


def test_compile_from_where() -> None:
    """Test compiling FROM with WHERE clause."""
    asql = 'from users where status == "active"'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "FROM" in sql_upper
    assert "USERS" in sql_upper
    assert "WHERE" in sql_upper
    assert "STATUS" in sql_upper
    assert "active" in sql.lower() or "'active'" in sql.lower() or '"active"' in sql.lower()


def test_compile_from_select() -> None:
    """Test compiling FROM with SELECT."""
    asql = "from users select name, email"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "FROM" in sql_upper
    assert "USERS" in sql_upper
    assert "SELECT" in sql_upper
    assert "name" in sql.lower()
    assert "email" in sql.lower()


def test_compile_from_where_select() -> None:
    """Test compiling FROM, WHERE, and SELECT."""
    asql = 'from users where status == "active" select name'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "FROM" in sql_upper
    assert "USERS" in sql_upper
    assert "WHERE" in sql_upper
    assert "SELECT" in sql_upper
    assert "name" in sql.lower()


def test_compile_empty_query() -> None:
    """Test that empty query raises error."""
    with pytest.raises(ASQLSyntaxError):
        compile("")


def test_compile_must_start_with_from() -> None:
    """Test that query must start with FROM."""
    with pytest.raises(ASQLSyntaxError):
        compile("select * from users")


def test_compile_dialect_postgres() -> None:
    """Test compiling with PostgreSQL dialect."""
    asql = 'from users where status == "active"'
    sql = compile(asql, dialect="postgres")
    sql_upper = sql.upper()
    assert "FROM" in sql_upper
    assert "USERS" in sql_upper
    assert "WHERE" in sql_upper

