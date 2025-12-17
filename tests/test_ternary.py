"""Tests for ternary conditional expressions in ASQL."""

import pytest
import sqlglot
from sqlglot import exp
from asql import compile
from tests.fixtures import assert_valid_sql, assert_sql_contains


class TestTernaryExpressions:
    """Test ternary conditional expressions."""
    
    def test_simple_ternary(self) -> None:
        """Test simple ternary: condition ? true_value : false_value."""
        asql = 'from orders select amount > 1000 ? "high" : "low" as tier'
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "amount", ">", "1000", "THEN", "high", "ELSE", "low")
        assert_valid_sql(sql)
        
        # Verify CASE structure
        parsed = sqlglot.parse_one(sql)
        case_expr = parsed.find(exp.Case)
        assert case_expr is not None, "CASE expression not found"
    
    def test_ternary_with_equality(self) -> None:
        """Test ternary with equality condition."""
        asql = 'from users select status == "active" ? 1 : 0 as is_active'
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "status", "active", "THEN", "1", "ELSE", "0")
        assert_valid_sql(sql)
    
    def test_ternary_with_parentheses(self) -> None:
        """Test ternary with parenthesized condition."""
        asql = 'from users select (age >= 18) ? "adult" : "minor" as age_group'
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "age", ">=", "18", "THEN", "adult", "ELSE", "minor")
        assert_valid_sql(sql)
    
    def test_ternary_with_coalesce(self) -> None:
        """Test ternary with coalesce operator."""
        asql = 'from users select (score ?? 0) > 80 ? "pass" : "fail" as result'
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "COALESCE", "score", "0", ">", "80", "THEN", "pass", "ELSE", "fail")
        assert_valid_sql(sql)
    
    def test_multiple_ternaries(self) -> None:
        """Test multiple ternary expressions in select."""
        asql = '''from orders
  select 
    amount > 1000 ? "high" : "low" as tier,
    status == "active" ? 1 : 0 as is_active'''
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "amount", ">", "1000", "THEN", "high")
        assert_sql_contains(sql, "CASE", "WHEN", "status", "active", "THEN", "1")
        assert_valid_sql(sql)
    
    def test_ternary_in_aggregation(self) -> None:
        """Test ternary expressions in aggregations."""
        asql = '''from orders
  group by customer_id
  select
    customer_id,
    sum(status == "completed" ? amount : 0) as completed_amount'''
        sql = compile(asql)
        
        assert_sql_contains(sql, "SUM", "CASE", "WHEN", "status", "completed", "THEN", "amount", "ELSE", "0")
        assert_valid_sql(sql)
    
    def test_ternary_with_function_calls(self) -> None:
        """Test ternary with function calls."""
        asql = 'from users select sum(revenue) > 1000 ? "high" : "low" as category'
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "SUM", "revenue", ">", "1000", "THEN", "high", "ELSE", "low")
        assert_valid_sql(sql)
    
    def test_nested_ternary(self) -> None:
        """Test nested ternary expressions."""
        asql = 'from users select age >= 18 ? (age >= 65 ? "senior" : "adult") : "minor" as category'
        sql = compile(asql)
        
        # Should have nested CASE expressions
        assert_sql_contains(sql, "CASE", "WHEN", "age", ">=", "18")
        assert_valid_sql(sql)
    
    def test_ternary_with_string_literals(self) -> None:
        """Test ternary with string literals."""
        asql = 'from products select price > 50 ? "expensive" : "affordable" as price_category'
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "price", ">", "50", "THEN", "expensive", "ELSE", "affordable")
        assert_valid_sql(sql)
    
    def test_ternary_with_numbers(self) -> None:
        """Test ternary with numeric values."""
        asql = 'from orders select amount > 100 ? 1 : 0 as is_large'
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "amount", ">", "100", "THEN", "1", "ELSE", "0")
        assert_valid_sql(sql)
    
    def test_ternary_with_cast_operator(self) -> None:
        """Test ternary doesn't interfere with cast operator ::."""
        asql = 'from users select created_at::DATE as date_day, status == "active" ? 1 : 0 as is_active'
        sql = compile(asql)
        
        assert_sql_contains(sql, "CAST", "created_at", "AS", "DATE")
        assert_sql_contains(sql, "CASE", "WHEN", "status", "active", "THEN", "1", "ELSE", "0")
        assert_valid_sql(sql)
    
    def test_ternary_in_where_clause(self) -> None:
        """Test ternary expressions can be used in WHERE clauses."""
        asql = 'from users where (status == "active" ? 1 : 0) = 1'
        sql = compile(asql)
        
        assert_sql_contains(sql, "WHERE", "CASE", "WHEN", "status", "active", "THEN", "1", "ELSE", "0")
        assert_valid_sql(sql)


class TestTernaryDialects:
    """Test ternary expressions across different SQL dialects."""
    
    def test_postgresql_dialect(self) -> None:
        """Test ternary expressions compile to PostgreSQL."""
        asql = 'from orders select amount > 1000 ? "high" : "low" as tier'
        sql = compile(asql, dialect="postgres")
        
        assert_sql_contains(sql, "CASE", "WHEN", "THEN", "ELSE", "END")
        assert_valid_sql(sql)
    
    def test_mysql_dialect(self) -> None:
        """Test ternary expressions compile to MySQL."""
        asql = 'from orders select amount > 1000 ? "high" : "low" as tier'
        sql = compile(asql, dialect="mysql")
        
        assert_sql_contains(sql, "CASE", "WHEN", "THEN", "ELSE", "END")
        assert_valid_sql(sql)
    
    def test_snowflake_dialect(self) -> None:
        """Test ternary expressions compile to Snowflake."""
        asql = 'from orders select amount > 1000 ? "high" : "low" as tier'
        sql = compile(asql, dialect="snowflake")
        
        assert_sql_contains(sql, "CASE", "WHEN", "THEN", "ELSE", "END")
        assert_valid_sql(sql)
