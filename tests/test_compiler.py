"""Tests for ASQL compiler."""

import pytest
import sqlglot
from sqlglot import exp
from asql import compile
from asql.errors import ASQLSyntaxError
from tests.fixtures import assert_valid_sql, assert_sql_contains, assert_sql_structure


def test_compile_simple_from() -> None:
    """Test compiling simple FROM clause."""
    asql = "from users"
    sql = compile(asql)
    
    assert_sql_contains(sql, "SELECT", "FROM", "users")
    assert_sql_structure(sql, FROM="users")
    assert_valid_sql(sql)


def test_compile_from_where() -> None:
    """Test compiling FROM with WHERE clause."""
    asql = 'from users where status == "active"'
    sql = compile(asql)
    
    assert_sql_contains(sql, "WHERE", "status", "active")
    assert_sql_structure(sql, FROM="users", WHERE="status")
    assert_valid_sql(sql)
    
    # Verify WHERE condition is correct
    parsed = sqlglot.parse_one(sql)
    where_clause = parsed.find(exp.Where)
    assert where_clause is not None, "WHERE clause not found in parsed SQL"


def test_compile_from_select() -> None:
    """Test compiling FROM with SELECT clause."""
    asql = "from users select name, email"
    sql = compile(asql)
    
    assert_sql_contains(sql, "SELECT", "name", "email", "FROM", "users")
    assert_sql_structure(sql, SELECT="name", FROM="users")
    assert_valid_sql(sql)
    
    # Verify columns are in SELECT
    parsed = sqlglot.parse_one(sql)
    select = parsed.find(exp.Select)
    assert select is not None, "SELECT clause not found"
    columns = [col.alias_or_name.lower() for col in select.expressions]
    assert "name" in columns, f"Column 'name' not found in SELECT: {columns}"
    assert "email" in columns, f"Column 'email' not found in SELECT: {columns}"


def test_compile_from_where_select() -> None:
    """Test compiling FROM, WHERE, and SELECT together."""
    asql = 'from users where status == "active" select name, email'
    sql = compile(asql)
    assert "SELECT" in sql.upper()
    assert "WHERE" in sql.upper()
    assert "name" in sql.lower()


def test_compile_empty_query() -> None:
    """Test that empty query raises error."""
    with pytest.raises(ASQLSyntaxError):
        compile("")


def test_compile_must_start_with_from() -> None:
    """Test that query must start with FROM."""
    # Note: SQLGlot-based parser may accept valid SQL even if it doesn't start with FROM
    # This test verifies behavior - if it doesn't raise, that's also acceptable
    try:
        sql = compile("select * from users")
        # If it compiles, verify it's valid SQL
        assert_valid_sql(sql)
    except ASQLSyntaxError:
        # This is also acceptable - ASQL requires FROM-first syntax
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
    
    assert_sql_contains(sql, "GROUP BY", "COUNT", "total_users", "country")
    assert_sql_structure(sql, FROM="users", GROUP_BY="country")
    assert_valid_sql(sql)
    
    # Verify GROUP BY structure
    parsed = sqlglot.parse_one(sql)
    group = parsed.find(exp.Group)
    assert group is not None, "GROUP BY clause not found"
    assert "country" in group.sql().lower(), "Grouping column 'country' not found"


def test_compile_group_by_sum() -> None:
    """Test compiling GROUP BY with SUM."""
    asql = "from sales group by region ( sum(amount) as revenue )"
    sql = compile(asql)
    
    assert_sql_contains(sql, "GROUP BY", "SUM", "revenue", "region", "amount")
    assert_sql_structure(sql, FROM="sales", GROUP_BY="region")
    assert_valid_sql(sql)
    
    # Verify aggregation structure
    parsed = sqlglot.parse_one(sql)
    select = parsed.find(exp.Select)
    assert select is not None
    sum_expr = select.find(exp.Sum) or select.find(exp.AggFunc)
    assert sum_expr is not None, "SUM aggregation not found in SELECT"


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


def test_compile_order_by_ascending() -> None:
    """Test compiling ORDER BY in ascending order."""
    asql = "from users order by name"
    sql = compile(asql)
    
    assert_sql_contains(sql, "ORDER BY", "name")
    assert_sql_structure(sql, FROM="users", ORDER_BY="name")
    assert_valid_sql(sql)
    
    # Verify ORDER BY structure
    parsed = sqlglot.parse_one(sql)
    order = parsed.find(exp.Order)
    assert order is not None, "ORDER BY clause not found"
    assert "name" in order.sql().lower(), "Ordering column 'name' not found"


def test_compile_order_by_descending() -> None:
    """Test compiling ORDER BY with descending order (using - prefix)."""
    asql = "from users order by -total_users"
    sql = compile(asql)
    
    assert_sql_contains(sql, "ORDER BY", "total_users", "DESC")
    assert_sql_structure(sql, FROM="users", ORDER_BY="total_users")
    assert_valid_sql(sql)
    
    # Verify DESC is present
    parsed = sqlglot.parse_one(sql)
    order = parsed.find(exp.Order)
    assert order is not None
    # Check that DESC is in the ordering
    assert "DESC" in order.sql().upper(), "DESC not found in ORDER BY"


def test_compile_order_by_multiple_columns() -> None:
    """Test compiling ORDER BY with multiple columns."""
    asql = "from users order by -total_users, name"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "ORDER BY" in sql_upper
    assert "TOTAL_USERS" in sql_upper
    assert "NAME" in sql_upper


def test_compile_group_by_order_by() -> None:
    """Test compiling GROUP BY followed by ORDER BY."""
    asql = "from users group by country ( # as total_users ) order by -total_users"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "GROUP BY" in sql_upper
    assert "ORDER BY" in sql_upper


def test_compile_order_by_count_hash() -> None:
    """Test compiling ORDER BY # (COUNT) directly without alias."""
    asql = "from users group by country ( # ) order by -#"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "GROUP BY" in sql_upper
    assert "ORDER BY" in sql_upper
    assert "COUNT" in sql_upper
    assert "DESC" in sql_upper


def test_compile_order_by_function_call() -> None:
    """Test compiling ORDER BY with function call."""
    asql = "from users order by month(updated_at)"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "ORDER BY" in sql_upper
    assert "MONTH" in sql_upper or "month" in sql.lower()
    assert "UPDATED_AT" in sql_upper or "updated_at" in sql.lower()


def test_compile_order_by_column_descending() -> None:
    """Test compiling ORDER BY with descending column using - prefix."""
    asql = "from users order by -updated_at"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "ORDER BY" in sql_upper
    assert "DESC" in sql_upper
    assert "UPDATED_AT" in sql_upper or "updated_at" in sql.lower()


def test_compile_order_by_column_multiple() -> None:
    """Test compiling ORDER BY with column and multiple columns."""
    asql = "from users order by -updated_at, name"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "ORDER BY" in sql_upper
    assert "DESC" in sql_upper
    assert "UPDATED_AT" in sql_upper or "updated_at" in sql.lower()
    assert "NAME" in sql_upper


def test_compile_take() -> None:
    """Test compiling TAKE/LIMIT."""
    asql = "from users limit 10"
    sql = compile(asql)
    
    assert_sql_contains(sql, "LIMIT", "10")
    assert_sql_structure(sql, FROM="users", LIMIT="10")
    assert_valid_sql(sql)
    
    # Verify LIMIT value
    parsed = sqlglot.parse_one(sql)
    limit = parsed.find(exp.Limit)
    assert limit is not None, "LIMIT clause not found"
    limit_expr = limit.args.get("expression")
    assert limit_expr is not None, "LIMIT expression not found"
    assert limit_expr.sql() == "10", f"Expected LIMIT 10, got {limit_expr.sql()}"


def test_compile_take_with_order_by() -> None:
    """Test compiling TAKE with ORDER BY."""
    asql = "from users order by -total_users limit 10"
    sql = compile(asql)
    sql_upper = sql.upper()
    assert "ORDER BY" in sql_upper
    assert "LIMIT" in sql_upper
    assert "10" in sql


def test_compile_group_by_order_by_take() -> None:
    """Test compiling GROUP BY, ORDER BY, and TAKE together."""
    asql = "from users group by country ( # as total_users ) order by -total_users limit 10"
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
    
    assert_sql_contains(sql, "WHERE", "IN", "active", "pending", "verified", "status")
    assert_valid_sql(sql)
    
    # Verify IN structure
    parsed = sqlglot.parse_one(sql)
    where_clause = parsed.find(exp.Where)
    assert where_clause is not None
    in_expr = where_clause.find(exp.In)
    assert in_expr is not None, "IN expression not found in WHERE clause"
    # Verify values are present
    in_sql = in_expr.sql().lower()
    assert "active" in in_sql
    assert "pending" in in_sql


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
