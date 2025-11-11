"""Tests for ASQL compiler."""

from asql import compile


def test_compile_simple_from() -> None:
    """Test compiling simple FROM clause."""
    asql = "from users"
    sql = compile(asql)
    assert "SELECT" in sql.upper()
    assert "FROM" in sql.upper()
    assert "users" in sql.lower()


def test_compile_from_where() -> None:
    """Test compiling FROM with WHERE clause."""
    asql = 'from users where status == "active"'
    sql = compile(asql)
    assert "WHERE" in sql.upper()
    assert "status" in sql.lower()


def test_compile_from_select() -> None:
    """Test compiling FROM with SELECT clause."""
    asql = "from users select name, email"
    sql = compile(asql)
    assert "SELECT" in sql.upper()
    assert "name" in sql.lower()
    assert "email" in sql.lower()


def test_compile_from_where_select() -> None:
    """Test compiling FROM, WHERE, and SELECT together."""
    asql = 'from users where status == "active" select name, email'
    sql = compile(asql)
    assert "SELECT" in sql.upper()
    assert "WHERE" in sql.upper()
    assert "name" in sql.lower()


def test_compile_empty_query() -> None:
    """Test that empty query raises error."""
    try:
        compile("")
        assert False, "Should have raised error"
    except Exception:
        pass


def test_compile_must_start_with_from() -> None:
    """Test that query must start with FROM."""
    try:
        compile("select * from users")
        assert False, "Should have raised error"
    except Exception:
        pass


def test_compile_dialect_postgres() -> None:
    """Test compiling with PostgreSQL dialect."""
    asql = "from users"
    sql = compile(asql, dialect="postgres")
    assert "SELECT" in sql.upper()
    assert "FROM" in sql.upper()


def test_compile_group_by_count() -> None:
    """Test compiling GROUP BY with COUNT (#)."""
    asql = "from users group by country ( # as total_users )"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "GROUP BY" in sql_upper
    assert "COUNT" in sql_upper
    assert "total_users" in sql.lower()


def test_compile_group_by_sum() -> None:
    """Test compiling GROUP BY with SUM."""
    asql = "from sales group by region ( sum(amount) as revenue )"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "GROUP BY" in sql_upper
    assert "SUM" in sql_upper
    assert "revenue" in sql.lower()


def test_compile_group_by_multiple_aggregations() -> None:
    """Test compiling GROUP BY with multiple aggregations."""
    asql = "from sales group by region ( sum(amount) as revenue, # as orders )"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "GROUP BY" in sql_upper
    assert "SUM" in sql_upper
    assert "COUNT" in sql_upper


def test_compile_group_by_multiple_columns() -> None:
    """Test compiling GROUP BY with multiple columns."""
    asql = "from sales group by region, month ( sum(amount) as revenue )"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "GROUP BY" in sql_upper
    assert "region" in sql.lower()
    assert "month" in sql.lower()


def test_compile_group_by_avg() -> None:
    """Test compiling GROUP BY with AVG."""
    asql = "from users group by country ( avg(age) as avg_age )"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "GROUP BY" in sql_upper
    assert "AVG" in sql_upper


def test_compile_sort_ascending() -> None:
    """Test compiling SORT in ascending order."""
    asql = "from users sort name"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "ORDER BY" in sql_upper
    assert "NAME" in sql_upper


def test_compile_sort_descending() -> None:
    """Test compiling SORT with descending order (using - prefix)."""
    asql = "from users sort -total_users"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "ORDER BY" in sql_upper
    assert "TOTAL_USERS" in sql_upper
    assert "DESC" in sql_upper


def test_compile_sort_multiple_columns() -> None:
    """Test compiling SORT with multiple columns."""
    asql = "from users sort -total_users, name"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "ORDER BY" in sql_upper
    assert "TOTAL_USERS" in sql_upper
    assert "NAME" in sql_upper


def test_compile_group_by_sort() -> None:
    """Test compiling GROUP BY followed by SORT."""
    asql = "from users group by country ( # as total_users ) sort -total_users"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "GROUP BY" in sql_upper
    assert "ORDER BY" in sql_upper


def test_compile_sort_by_count_hash() -> None:
    """Test compiling SORT by # (COUNT) directly without alias."""
    asql = "from users group by country ( # ) sort -#"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "GROUP BY" in sql_upper
    assert "ORDER BY" in sql_upper
    assert "COUNT" in sql_upper
    assert "DESC" in sql_upper


def test_compile_sort_function_call() -> None:
    """Test compiling SORT with function call."""
    asql = "from users sort month(updated_at)"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "ORDER BY" in sql_upper
    assert "MONTH" in sql_upper or "month" in sql.lower()
    assert "UPDATED_AT" in sql_upper or "updated_at" in sql.lower()


def test_compile_sort_column_descending() -> None:
    """Test compiling SORT with descending column using - prefix."""
    asql = "from users sort -updated_at"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "ORDER BY" in sql_upper
    assert "DESC" in sql_upper
    assert "UPDATED_AT" in sql_upper or "updated_at" in sql.lower()


def test_compile_sort_column_multiple() -> None:
    """Test compiling SORT with column and multiple columns."""
    asql = "from users sort -updated_at, name"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "ORDER BY" in sql_upper
    assert "DESC" in sql_upper
    assert "UPDATED_AT" in sql_upper or "updated_at" in sql.lower()
    assert "NAME" in sql_upper


def test_compile_take() -> None:
    """Test compiling TAKE/LIMIT."""
    asql = "from users take 10"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "LIMIT" in sql_upper
    assert "10" in sql


def test_compile_take_with_sort() -> None:
    """Test compiling TAKE with SORT."""
    asql = "from users sort -total_users take 10"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "ORDER BY" in sql_upper
    assert "LIMIT" in sql_upper
    assert "10" in sql


def test_compile_group_by_sort_take() -> None:
    """Test compiling GROUP BY, SORT, and TAKE together."""
    asql = "from users group by country ( # as total_users ) sort -total_users take 10"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "GROUP BY" in sql_upper
    assert "ORDER BY" in sql_upper
    assert "LIMIT" in sql_upper
    assert "10" in sql


def test_compile_where_not_equal() -> None:
    """Test compiling WHERE with != operator."""
    asql = 'from users where status != "inactive"'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "WHERE" in sql_upper
    assert "STATUS" in sql_upper
    assert "!=" in sql or "<>" in sql or "NOT" in sql_upper


def test_compile_where_less_than() -> None:
    """Test compiling WHERE with < operator."""
    asql = "from users where age < 18"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "WHERE" in sql_upper
    assert "AGE" in sql_upper
    assert "<" in sql


def test_compile_where_greater_than() -> None:
    """Test compiling WHERE with > operator."""
    asql = "from users where age > 65"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "WHERE" in sql_upper
    assert "AGE" in sql_upper
    assert ">" in sql


def test_compile_where_less_equal() -> None:
    """Test compiling WHERE with <= operator."""
    asql = "from users where age <= 18"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "WHERE" in sql_upper
    assert "AGE" in sql_upper
    assert "<=" in sql


def test_compile_where_greater_equal() -> None:
    """Test compiling WHERE with >= operator."""
    asql = "from users where age >= 18"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "WHERE" in sql_upper
    assert "AGE" in sql_upper
    assert ">=" in sql


def test_compile_where_is_null() -> None:
    """Test compiling WHERE with IS NULL."""
    asql = "from users where email is null"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "WHERE" in sql_upper
    assert "IS NULL" in sql_upper


def test_compile_where_is_not_null() -> None:
    """Test compiling WHERE with IS NOT NULL."""
    asql = "from users where email is not null"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "WHERE" in sql_upper
    assert "IS" in sql_upper
    assert "NULL" in sql_upper


def test_compile_where_and() -> None:
    """Test compiling WHERE with AND operator."""
    asql = 'from users where status == "active" and age >= 18'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "WHERE" in sql_upper
    assert "AND" in sql_upper


def test_compile_where_or() -> None:
    """Test compiling WHERE with OR operator."""
    asql = 'from users where status == "active" or status == "pending"'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "WHERE" in sql_upper
    assert "OR" in sql_upper


def test_compile_where_not() -> None:
    """Test compiling WHERE with NOT operator."""
    asql = 'from users where not status == "inactive"'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "WHERE" in sql_upper
    assert "NOT" in sql_upper


def test_compile_where_multiple_conditions() -> None:
    """Test compiling WHERE with multiple conditions."""
    asql = 'from users where status == "active" and age >= 18 and email is not null'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "WHERE" in sql_upper
    assert "AND" in sql_upper


def test_compile_where_in() -> None:
    """Test compiling WHERE with IN operator."""
    asql = 'from users where status in ("active", "pending", "verified")'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "WHERE" in sql_upper
    assert "IN" in sql_upper
    assert "active" in sql.lower()
    assert "pending" in sql.lower()


def test_compile_where_not_in() -> None:
    """Test compiling WHERE with NOT IN operator."""
    asql = 'from users where status not in ("inactive", "deleted", "banned")'
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "WHERE" in sql_upper
    assert "NOT" in sql_upper
    assert "IN" in sql_upper
    assert "inactive" in sql.lower()


def test_compile_where_in_numbers() -> None:
    """Test compiling WHERE with IN operator using numbers."""
    asql = "from users where age in (18, 19, 20, 21)"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "WHERE" in sql_upper
    assert "IN" in sql_upper
    assert "18" in sql
    assert "19" in sql
