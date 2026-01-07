"""Tests for when conditional expressions in ASQL."""

import pytest
import sqlglot
from sqlglot import exp
from asql import compile
from tests.fixtures import assert_valid_sql, assert_sql_contains


class TestWhenExpressions:
    """Test when conditional expressions."""
    
    def test_simple_case_with_is(self) -> None:
        """Test simple case: when expr is value then result."""
        asql = 'from users select when status is "active" then 1 as is_active'
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "status", "active", "THEN", "1")
        assert_valid_sql(sql)
        
        # Verify CASE structure
        parsed = sqlglot.parse_one(sql)
        case_expr = parsed.find(exp.Case)
        assert case_expr is not None, "CASE expression not found"
    
    def test_simple_case_multiple_branches(self) -> None:
        """Test simple case with multiple branches."""
        asql = '''from users select
  when status
    is "active" then "Active User"
    is "pending" then "Pending"
    otherwise "Unknown"
  as status_label'''
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "status", "active", "THEN", "Active User")
        assert_sql_contains(sql, "WHEN", "pending", "THEN", "Pending")
        assert_sql_contains(sql, "ELSE", "Unknown")
        assert_valid_sql(sql)
    
    def test_implied_equality(self) -> None:
        """Test implied equality: when expr value then result."""
        asql = 'from users select when status "active" then 1 as is_active'
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "status", "active", "THEN", "1")
        assert_valid_sql(sql)
    
    def test_comparison_operators(self) -> None:
        """Test comparison operators in when expressions."""
        asql = '''from users select
  when age
    < 4 then "infant"
    < 12 then "child"
    < 18 then "teen"
    otherwise "adult"
  as age_group'''
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "age", "<", "4", "THEN", "infant")
        assert_sql_contains(sql, "WHEN", "age", "<", "12", "THEN", "child")
        assert_valid_sql(sql)
    
    def test_is_not_operator(self) -> None:
        """Test is not operator."""
        asql = '''from users select
  when status
    is not "deleted" then 1
    otherwise 0
  as is_not_deleted'''
        sql = compile(asql)
        
        # sqlglot may render != as <> depending on dialect/normalization
        assert_sql_contains(sql, "CASE", "WHEN", "status", "deleted", "THEN", "1")
        assert ("!=" in sql) or ("<>" in sql), f"Expected != or <>, got: {sql}"
        assert_sql_contains(sql, "ELSE", "0")
        assert_valid_sql(sql)
    
    def test_in_operator(self) -> None:
        """Test in operator."""
        asql = '''from users select
  when status
    in ("active", "pending") then "open"
    in ("completed", "shipped") then "done"
    otherwise "unknown"
  as status_category'''
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "status", "IN", "active", "pending", "THEN", "open")
        assert_valid_sql(sql)
    
    def test_searched_case(self) -> None:
        """Test searched case: when condition then result."""
        asql = '''from users select
  when
    age < 18 and country = "US" then "US Minor"
    age < 18 then "Minor"
    otherwise "Adult"
  as category'''
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "age", "<", "18", "THEN", "US Minor")
        assert_valid_sql(sql)
    
    def test_searched_case_simple(self) -> None:
        """Test simple searched case."""
        asql = 'from users select when age < 18 then "Minor" otherwise "Adult" as category'
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "age", "<", "18", "THEN", "Minor")
        assert_sql_contains(sql, "ELSE", "Adult")
        assert_valid_sql(sql)
    
    def test_else_vs_otherwise(self) -> None:
        """Test that both else and otherwise work."""
        asql1 = 'from users select when status is "active" then 1 else 0 as is_active'
        asql2 = 'from users select when status is "active" then 1 otherwise 0 as is_active'
        
        sql1 = compile(asql1)
        sql2 = compile(asql2)
        
        assert_sql_contains(sql1, "ELSE", "0")
        assert_sql_contains(sql2, "ELSE", "0")
        assert_valid_sql(sql1)
        assert_valid_sql(sql2)
    
    def test_when_in_aggregation(self) -> None:
        """Test when expressions in aggregations."""
        asql = '''from orders
  group by customer_id
  select
    customer_id,
    sum(when status is "completed" then 1 otherwise 0) as completed_count'''
        sql = compile(asql)
        
        assert_sql_contains(sql, "SUM", "CASE", "WHEN", "status", "completed", "THEN", "1", "ELSE", "0")
        assert_valid_sql(sql)
    
    def test_complex_business_logic(self) -> None:
        """Test complex business logic with when."""
        asql = '''from opportunity
  select
    when
      is_won then "Won"
      not is_won and is_closed then "Lost"
      otherwise "Other"
    as status'''
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "is_won", "THEN", "Won")
        assert_valid_sql(sql)
    
    def test_multiple_comparison_operators(self) -> None:
        """Test multiple comparison operators."""
        asql = '''from products select
  when price
    < 10 then "cheap"
    <= 50 then "moderate"
    > 50 then "expensive"
    otherwise "unknown"
  as price_category'''
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "price", "<", "10", "THEN", "cheap")
        assert_sql_contains(sql, "WHEN", "price", "<=", "50", "THEN", "moderate")
        assert_sql_contains(sql, "WHEN", "price", ">", "50", "THEN", "expensive")
        assert_valid_sql(sql)
    
    def test_when_with_function_calls(self) -> None:
        """Test when expressions with function calls."""
        asql = '''from users select
  when lower(status)
    is "active" then 1
    otherwise 0
  as is_active_lower'''
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "LOWER", "status", "active", "THEN", "1")
        assert_valid_sql(sql)
    
    def test_when_in_where_clause(self) -> None:
        """Test when expressions can be used in WHERE clauses."""
        asql = '''from users
  where when status is "active" then 1 else 0 = 1'''
        sql = compile(asql)
        
        assert_sql_contains(sql, "WHERE", "CASE", "WHEN", "status", "active")
        assert_valid_sql(sql)


class TestWhenDialects:
    """Test when expressions across different SQL dialects."""
    
    def test_postgresql_dialect(self) -> None:
        """Test when expressions compile to PostgreSQL."""
        asql = 'from users select when status is "active" then 1 else 0 as is_active'
        sql = compile(asql, dialect="postgres")
        
        assert_sql_contains(sql, "CASE", "WHEN", "THEN", "ELSE", "END")
        assert_valid_sql(sql)
    
    def test_mysql_dialect(self) -> None:
        """Test when expressions compile to MySQL."""
        asql = 'from users select when status is "active" then 1 else 0 as is_active'
        sql = compile(asql, dialect="mysql")
        
        assert_sql_contains(sql, "CASE", "WHEN", "THEN", "ELSE", "END")
        assert_valid_sql(sql)
    
    def test_snowflake_dialect(self) -> None:
        """Test when expressions compile to Snowflake."""
        asql = 'from users select when status is "active" then 1 else 0 as is_active'
        sql = compile(asql, dialect="snowflake")
        
        assert_sql_contains(sql, "CASE", "WHEN", "THEN", "ELSE", "END")
        assert_valid_sql(sql)
