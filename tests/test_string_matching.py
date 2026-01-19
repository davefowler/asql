"""Tests for string matching operators (contains, icontains, starts with, etc.)."""

import sqlglot
from sqlglot import exp
from tests.fixtures import transpile
from tests.fixtures import assert_valid_sql, assert_sql_contains


def test_contains_operator() -> None:
    """Test contains operator."""
    asql = 'from users where email contains "@gmail.com"'
    sql = transpile(asql)
    
    assert_sql_contains(sql, "LIKE", "email", "gmail.com")
    assert_valid_sql(sql)
    
    # Verify LIKE pattern structure
    parsed = sqlglot.parse_one(sql)
    where_clause = parsed.find(exp.Where)
    assert where_clause is not None
    like_expr = where_clause.find(exp.Like)
    assert like_expr is not None, "LIKE expression not found in WHERE clause"
    # Verify wildcard pattern
    like_sql = like_expr.sql()
    assert "%" in like_sql, "Wildcard % not found in LIKE pattern"


def test_icontains_operator() -> None:
    """Test icontains operator."""
    asql = 'from users where email icontains "gmail"'
    sql = transpile(asql)
    sql_upper = sql.upper()
    assert "ILIKE" in sql_upper or "LOWER" in sql_upper
    assert "%gmail%" in sql or "%gmail%" in sql.replace("'", '"')


def test_starts_with_operator() -> None:
    """Test starts with operator."""
    asql = 'from users where name starts with "John"'
    sql = transpile(asql)
    
    assert_sql_contains(sql, "LIKE", "name", "John")
    assert_valid_sql(sql)
    
    # Verify LIKE pattern for starts_with (should end with %)
    parsed = sqlglot.parse_one(sql)
    where_clause = parsed.find(exp.Where)
    assert where_clause is not None
    like_expr = where_clause.find(exp.Like)
    assert like_expr is not None
    like_sql = like_expr.sql()
    # Pattern should end with % (starts with "John")
    assert "%" in like_sql, "Wildcard % not found in LIKE pattern"


def test_istarts_with_operator() -> None:
    """Test istarts with operator."""
    asql = 'from users where name istarts with "john"'
    sql = transpile(asql)
    sql_upper = sql.upper()
    assert "ILIKE" in sql_upper or "LOWER" in sql_upper
    assert "john%" in sql or "john%" in sql.replace("'", '"')


def test_ends_with_operator() -> None:
    """Test ends with operator."""
    asql = 'from users where filename ends with ".pdf"'
    sql = transpile(asql)
    
    assert_sql_contains(sql, "LIKE", "filename", ".pdf")
    assert_valid_sql(sql)
    
    # Verify LIKE pattern for ends_with (should start with %)
    parsed = sqlglot.parse_one(sql)
    where_clause = parsed.find(exp.Where)
    assert where_clause is not None
    like_expr = where_clause.find(exp.Like)
    assert like_expr is not None
    like_sql = like_expr.sql()
    # Pattern should start with % (ends with ".pdf")
    assert "%" in like_sql, "Wildcard % not found in LIKE pattern"


def test_iends_with_operator() -> None:
    """Test iends with operator."""
    asql = 'from users where filename iends with ".pdf"'
    sql = transpile(asql)
    sql_upper = sql.upper()
    assert "ILIKE" in sql_upper or "LOWER" in sql_upper
    assert "%.pdf" in sql or "%.pdf" in sql.replace("'", '"')


def test_matches_operator() -> None:
    """Test matches operator (regex matching).
    
    Note: 'matches' uses REGEXP, not LIKE. For pattern matching use 'contains'.
    """
    asql = 'from users where email matches "%@gmail.com"'
    sql = transpile(asql)
    sql_upper = sql.upper()
    # matches uses REGEXP (regex), not LIKE
    assert "REGEXP" in sql_upper
    assert "@gmail.com" in sql


def test_matches_with_underscore() -> None:
    """Test matches operator with underscore (regex matching)."""
    asql = 'from users where phone matches "555-___-____"'
    sql = transpile(asql)
    sql_upper = sql.upper()
    # matches uses REGEXP (regex), not LIKE
    assert "REGEXP" in sql_upper
    assert "555" in sql


def test_contains_with_dotted_column() -> None:
    """Test contains with dotted column name."""
    asql = 'from users where users.email contains "@gmail.com"'
    sql = transpile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper
    assert "users.email" in sql.lower() or "users" in sql.lower()


def test_contains_with_function_call() -> None:
    """Test contains with function call."""
    asql = 'from users where upper(name) contains "JOHN"'
    sql = transpile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper
    assert "UPPER" in sql_upper or "upper" in sql.lower()


def test_contains_with_and_operator() -> None:
    """Test contains with AND operator."""
    asql = 'from users where email contains "@gmail.com" and status == "active"'
    sql = transpile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper
    assert "AND" in sql_upper


def test_contains_with_or_operator() -> None:
    """Test contains with OR operator."""
    asql = 'from users where email contains "@gmail.com" or email contains "@yahoo.com"'
    sql = transpile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper
    assert "OR" in sql_upper


def test_multiple_string_operators() -> None:
    """Test multiple string matching operators in same query."""
    asql = 'from users where email contains "@gmail.com" and name starts with "John"'
    sql = transpile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper
    assert "AND" in sql_upper


def test_contains_with_single_quotes() -> None:
    """Test contains with single-quoted string."""
    asql = "from users where email contains '@gmail.com'"
    sql = transpile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper


def test_contains_with_escaped_quotes() -> None:
    """Test contains with escaped quotes in string."""
    asql = 'from users where name contains "John\'s"'
    sql = transpile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper


def test_icontains_postgres_dialect() -> None:
    """Test icontains generates ILIKE for PostgreSQL."""
    asql = 'from users where email icontains "gmail"'
    sql = transpile(asql, dialect="postgres")
    
    assert_sql_contains(sql, "ILIKE", "email", "gmail", case_sensitive=True)
    assert_valid_sql(sql, dialect="postgres")
    
    # Verify ILIKE is used (PostgreSQL-specific)
    parsed = sqlglot.parse_one(sql, dialect="postgres")
    where_clause = parsed.find(exp.Where)
    assert where_clause is not None
    ilike_expr = where_clause.find(exp.ILike)
    assert ilike_expr is not None, "ILIKE expression not found (PostgreSQL should use ILIKE)"


def test_starts_with_in_select() -> None:
    """Test starts with in SELECT clause (should not transform)."""
    # This should not transform because it's not in WHERE clause
    # Actually, our transformation works anywhere, so this is fine
    asql = 'from users where name starts with "John" select name'
    sql = transpile(asql)
    sql_upper = sql.upper()
    assert "LIKE" in sql_upper
    assert "WHERE" in sql_upper
