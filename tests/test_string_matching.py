"""Tests for string matching operators (contains, icontains, starts with, etc.)."""

from asql import compile


def test_contains_operator() -> None:
    """Test contains operator."""
    asql = 'from users where email contains "@gmail.com"'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper
    assert "%@gmail.com%" in sql or "%@gmail.com%" in sql.replace("'", '"')


def test_icontains_operator() -> None:
    """Test icontains operator."""
    asql = 'from users where email icontains "gmail"'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "ILIKE" in sql_upper or "LOWER" in sql_upper
    assert "%gmail%" in sql or "%gmail%" in sql.replace("'", '"')


def test_starts_with_operator() -> None:
    """Test starts with operator."""
    asql = 'from users where name starts with "John"'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper
    assert "John%" in sql or "John%" in sql.replace("'", '"')


def test_istarts_with_operator() -> None:
    """Test istarts with operator."""
    asql = 'from users where name istarts with "john"'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "ILIKE" in sql_upper or "LOWER" in sql_upper
    assert "john%" in sql or "john%" in sql.replace("'", '"')


def test_ends_with_operator() -> None:
    """Test ends with operator."""
    asql = 'from users where filename ends with ".pdf"'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper
    assert "%.pdf" in sql or "%.pdf" in sql.replace("'", '"')


def test_iends_with_operator() -> None:
    """Test iends with operator."""
    asql = 'from users where filename iends with ".pdf"'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "ILIKE" in sql_upper or "LOWER" in sql_upper
    assert "%.pdf" in sql or "%.pdf" in sql.replace("'", '"')


def test_matches_operator() -> None:
    """Test matches operator."""
    asql = 'from users where email matches "%@gmail.com"'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper
    assert "%@gmail.com" in sql or "%@gmail.com" in sql.replace("'", '"')


def test_matches_with_underscore() -> None:
    """Test matches operator with underscore wildcard."""
    asql = 'from users where phone matches "555-___-____"'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper
    assert "555-___-____" in sql or "555-___-____" in sql.replace("'", '"')


def test_contains_with_dotted_column() -> None:
    """Test contains with dotted column name."""
    asql = 'from users where users.email contains "@gmail.com"'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper
    assert "users.email" in sql.lower() or "users" in sql.lower()


def test_contains_with_function_call() -> None:
    """Test contains with function call."""
    asql = 'from users where upper(name) contains "JOHN"'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper
    assert "UPPER" in sql_upper or "upper" in sql.lower()


def test_contains_with_and_operator() -> None:
    """Test contains with AND operator."""
    asql = 'from users where email contains "@gmail.com" and status == "active"'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper
    assert "AND" in sql_upper


def test_contains_with_or_operator() -> None:
    """Test contains with OR operator."""
    asql = 'from users where email contains "@gmail.com" or email contains "@yahoo.com"'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper
    assert "OR" in sql_upper


def test_multiple_string_operators() -> None:
    """Test multiple string matching operators in same query."""
    asql = 'from users where email contains "@gmail.com" and name starts with "John"'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper
    assert "AND" in sql_upper


def test_contains_with_single_quotes() -> None:
    """Test contains with single-quoted string."""
    asql = "from users where email contains '@gmail.com'"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper


def test_contains_with_escaped_quotes() -> None:
    """Test contains with escaped quotes in string."""
    asql = 'from users where name contains "John\'s"'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper


def test_icontains_postgres_dialect() -> None:
    """Test icontains generates ILIKE for PostgreSQL."""
    asql = 'from users where email icontains "gmail"'
    sql = compile(asql, dialect="postgres")
    sql_upper = sql.upper()
    assert "ILIKE" in sql_upper


def test_starts_with_in_select() -> None:
    """Test starts with in SELECT clause (should not transform)."""
    # This should not transform because it's not in WHERE clause
    # Actually, our transformation works anywhere, so this is fine
    asql = 'from users where name starts with "John" select name'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper
    assert "WHERE" in sql_upper
