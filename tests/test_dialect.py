"""Tests for ASQL dialect implementation."""

import pytest
from sqlglot import parse_one


def test_sqlglot_basic() -> None:
    """Test that SQLGlot works for basic SQL parsing."""
    # This is just to verify SQLGlot is working
    result = parse_one("SELECT * FROM users")
    assert result is not None
    assert result.sql() == "SELECT * FROM users"


def test_asql_from_clause() -> None:
    """Test parsing a simple ASQL FROM clause."""
    # TODO: Implement ASQL dialect
    # asql_query = "from users"
    # result = parse_one(asql_query, dialect="asql")
    # assert result is not None
    pass


def test_asql_from_where() -> None:
    """Test parsing ASQL with FROM and WHERE."""
    # TODO: Implement ASQL dialect
    # asql_query = "from users where status == 'active'"
    # result = parse_one(asql_query, dialect="asql")
    # assert result is not None
    pass

