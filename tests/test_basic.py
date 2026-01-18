"""Basic tests to verify setup."""

from asql import compile
from tests.fixtures import assert_valid_sql, assert_sql_contains


def test_import() -> None:
    """Test that we can import the asql module."""
    import asql
    assert asql is not None
    # Verify version is accessible and follows semver pattern (e.g., "0.1.0")
    assert hasattr(asql, "__version__")
    assert isinstance(asql.__version__, str)
    # Check it looks like a semver version
    version_parts = asql.__version__.split(".")
    assert len(version_parts) >= 2, f"Version should be semver format: {asql.__version__}"


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

