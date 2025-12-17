"""Basic tests to verify setup."""

import pytest
from asql import compile
from tests.fixtures import assert_valid_sql, assert_sql_contains


def test_import() -> None:
    """Test that we can import the asql module."""
    import asql
    assert asql is not None
    assert asql.__version__ == "0.1.0"


def test_basic_compilation() -> None:
    """Test that basic compilation works and produces valid SQL."""
    asql_query = "from users"
    sql = compile(asql_query)
    
    # Verify SQL is generated
    assert sql is not None
    assert len(sql) > 0
    
    # Verify SQL structure
    assert_sql_contains(sql, "SELECT", "FROM", "users")
    
    # Verify SQL is valid (can be parsed)
    assert_valid_sql(sql)

