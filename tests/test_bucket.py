"""Tests for bucket() function for binning/discretization in ASQL."""

import pytest
import sqlglot
from sqlglot import exp
from asql import compile
from tests.fixtures import assert_valid_sql, assert_sql_contains


class TestBucketExplicitBoundaries:
    """Test bucket() with explicit boundaries."""
    
    def test_boundaries_with_labels(self) -> None:
        """Test bucket with explicit boundaries and labels."""
        asql = """from students
select *,
  bucket(score, [0, 60, 70, 80, 90, 100], ['F', 'D', 'C', 'B', 'A']) as grade"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "score", "THEN")
        assert_sql_contains(sql, "F", "D", "C", "B", "A")
        assert_valid_sql(sql)
        
        # Verify CASE structure
        parsed = sqlglot.parse_one(sql)
        case_expr = parsed.find(exp.Case)
        assert case_expr is not None, "CASE expression not found"
    
    def test_boundaries_without_labels(self) -> None:
        """Test bucket with explicit boundaries but no labels (auto-labeled)."""
        asql = """from sales
select *,
  bucket(amount, [0, 100, 500, 1000]) as amount_tier"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "amount", "THEN")
        # Should have auto-generated labels like '0-100', '100-500', etc.
        assert_sql_contains(sql, "0-100")
        assert_sql_contains(sql, "100-500")
        assert_sql_contains(sql, "500-1000")
        assert_valid_sql(sql)
    
    def test_boundaries_numeric_values(self) -> None:
        """Test bucket with numeric boundaries."""
        asql = """from products
select *,
  bucket(price, [0, 10, 50, 100, 500]) as price_tier"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "price")
        assert_valid_sql(sql)
    
    def test_boundaries_with_negative_values(self) -> None:
        """Test bucket with negative boundaries."""
        asql = """from temperature_readings
select *,
  bucket(temp_celsius, [-40, -20, 0, 20, 40]) as temp_category"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "temp_celsius")
        assert_valid_sql(sql)
    
    def test_boundaries_with_decimal_values(self) -> None:
        """Test bucket with decimal boundaries."""
        asql = """from measurements
select *,
  bucket(value, [0.0, 0.5, 1.0, 1.5, 2.0]) as value_range"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "value")
        assert_valid_sql(sql)


class TestBucketWidthBased:
    """Test bucket() with width-based parameters."""
    
    def test_start_end_width(self) -> None:
        """Test bucket with start, end, and width parameters."""
        asql = """from data
select *,
  bucket(value, start=0, end=100, width=10) as value_bucket"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "value")
        # Should generate buckets 0-10, 10-20, ..., 90-100
        assert_sql_contains(sql, "0-10")
        assert_sql_contains(sql, "90-100")
        assert_valid_sql(sql)
    
    def test_start_end_width_uneven(self) -> None:
        """Test bucket with width that doesn't divide range evenly."""
        asql = """from data
select *,
  bucket(value, start=0, end=25, width=10) as value_bucket"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "value")
        # Should include 0-10, 10-20, 20-25
        assert_valid_sql(sql)


class TestBucketInContext:
    """Test bucket() in various query contexts."""
    
    def test_bucket_in_select(self) -> None:
        """Test bucket in a simple SELECT."""
        asql = """from users
select name, bucket(age, [0, 18, 30, 50, 100], ['minor', 'young', 'adult', 'senior']) as age_group"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "age")
        assert_sql_contains(sql, "minor", "young", "adult", "senior")
        assert_valid_sql(sql)
    
    def test_bucket_with_where(self) -> None:
        """Test bucket in query with WHERE clause."""
        asql = """from sales
where status = 'completed'
select *,
  bucket(amount, [0, 100, 500, 1000, 10000]) as amount_tier"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "WHERE", "status")
        assert_sql_contains(sql, "CASE", "WHEN", "amount")
        assert_valid_sql(sql)
    
    def test_bucket_in_group_by(self) -> None:
        """Test grouping by bucket result."""
        asql = """from orders
select bucket(total, [0, 50, 100, 500]) as order_tier, count(*) as order_count
group by bucket(total, [0, 50, 100, 500])"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "total")
        assert_sql_contains(sql, "GROUP BY")
        assert_valid_sql(sql)
    
    def test_bucket_with_alias(self) -> None:
        """Test bucket with explicit alias."""
        asql = """from customers
select
  name,
  bucket(lifetime_value, [0, 100, 1000, 10000, 100000], ['bronze', 'silver', 'gold', 'platinum']) as customer_tier"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "customer_tier")
        assert_sql_contains(sql, "bronze", "silver", "gold", "platinum")
        assert_valid_sql(sql)
    
    def test_multiple_buckets(self) -> None:
        """Test multiple bucket functions in same query."""
        asql = """from customers
select
  name,
  bucket(age, [0, 18, 30, 50, 65, 100]) as age_group,
  bucket(income, [0, 30000, 60000, 100000, 200000]) as income_bracket"""
        sql = compile(asql)
        
        # Should have two CASE expressions
        assert sql.upper().count("CASE") == 2
        assert_sql_contains(sql, "age_group", "income_bracket")
        assert_valid_sql(sql)


class TestBucketBoundaryBehavior:
    """Test bucket boundary inclusivity behavior."""
    
    def test_left_inclusive(self) -> None:
        """Test that buckets are left-inclusive by default."""
        asql = """from data
select bucket(value, [0, 10, 20, 30]) as bucket_val"""
        sql = compile(asql)
        
        # Should use >= for lower bound
        assert_sql_contains(sql, ">=")
        assert_valid_sql(sql)
    
    def test_last_bucket_includes_upper(self) -> None:
        """Test that the last bucket includes the upper boundary."""
        asql = """from data
select bucket(value, [0, 10, 20]) as bucket_val"""
        sql = compile(asql)
        
        # Last bucket should use <= for upper bound
        assert_sql_contains(sql, "<=")
        assert_valid_sql(sql)
    
    def test_out_of_range_returns_null(self) -> None:
        """Test that values outside boundaries return NULL."""
        asql = """from data
select bucket(value, [0, 10, 20]) as bucket_val"""
        sql = compile(asql)
        
        # Should have ELSE NULL
        assert_sql_contains(sql, "ELSE", "NULL")
        assert_valid_sql(sql)


class TestBucketDialects:
    """Test bucket function across different SQL dialects."""
    
    def test_postgresql_dialect(self) -> None:
        """Test bucket compiles to PostgreSQL."""
        asql = """from users
select bucket(age, [0, 18, 65, 100], ['minor', 'adult', 'senior']) as age_group"""
        sql = compile(asql, dialect="postgres")
        
        assert_sql_contains(sql, "CASE", "WHEN", "THEN", "ELSE", "END")
        assert_valid_sql(sql)
    
    def test_mysql_dialect(self) -> None:
        """Test bucket compiles to MySQL."""
        asql = """from users
select bucket(age, [0, 18, 65, 100], ['minor', 'adult', 'senior']) as age_group"""
        sql = compile(asql, dialect="mysql")
        
        assert_sql_contains(sql, "CASE", "WHEN", "THEN", "ELSE", "END")
        assert_valid_sql(sql)
    
    def test_snowflake_dialect(self) -> None:
        """Test bucket compiles to Snowflake."""
        asql = """from users
select bucket(age, [0, 18, 65, 100], ['minor', 'adult', 'senior']) as age_group"""
        sql = compile(asql, dialect="snowflake")
        
        assert_sql_contains(sql, "CASE", "WHEN", "THEN", "ELSE", "END")
        assert_valid_sql(sql)
    
    def test_duckdb_dialect(self) -> None:
        """Test bucket compiles to DuckDB."""
        asql = """from users
select bucket(age, [0, 18, 65, 100], ['minor', 'adult', 'senior']) as age_group"""
        sql = compile(asql, dialect="duckdb")
        
        assert_sql_contains(sql, "CASE", "WHEN", "THEN", "ELSE", "END")
        assert_valid_sql(sql)


class TestBucketEdgeCases:
    """Test bucket function edge cases."""
    
    def test_expression_as_input(self) -> None:
        """Test bucket with expression as input instead of column."""
        asql = """from orders
select bucket(total * 1.1, [0, 100, 500, 1000]) as adjusted_tier"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "total", "1.1")
        assert_valid_sql(sql)
    
    def test_function_as_input(self) -> None:
        """Test bucket with function call as input."""
        asql = """from orders
select bucket(abs(total), [0, 100, 500, 1000]) as abs_tier"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "ABS")
        assert_valid_sql(sql)
    
    def test_bucket_preserves_surrounding_query(self) -> None:
        """Test that bucket doesn't break surrounding query structure."""
        asql = """from orders
where status = 'completed'
select id, bucket(total, [0, 100, 500]) as tier
order by id
limit 10"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "WHERE", "status")
        assert_sql_contains(sql, "ORDER BY")
        assert_sql_contains(sql, "LIMIT")
        assert_sql_contains(sql, "CASE", "WHEN")
        assert_valid_sql(sql)
    
    def test_two_boundaries(self) -> None:
        """Test bucket with minimum two boundaries (one bin)."""
        asql = """from data
select bucket(value, [0, 100]) as single_bucket"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "value")
        assert_sql_contains(sql, "0-100")
        assert_valid_sql(sql)
    
    def test_quoted_identifiers(self) -> None:
        """Test bucket with quoted column names."""
        asql = '''from data
select bucket("Value Column", [0, 50, 100]) as value_bucket'''
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN")
        assert_valid_sql(sql)


class TestBucketRealWorldExamples:
    """Test bucket function with real-world examples from the spec."""
    
    def test_grade_buckets(self) -> None:
        """Test grading example from spec."""
        asql = """from students
select *,
  bucket(score, [0, 60, 70, 80, 90, 100], ['F', 'D', 'C', 'B', 'A']) as grade"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE")
        assert_sql_contains(sql, "WHEN", "score", ">=", "0", "AND", "score", "<", "60", "THEN", "F")
        assert_sql_contains(sql, "WHEN", "score", ">=", "90", "AND", "score", "<=", "100", "THEN", "A")
        assert_valid_sql(sql)
    
    def test_age_demographics(self) -> None:
        """Test age demographics bucketing."""
        asql = """from users
select
  name,
  age,
  bucket(age, [0, 13, 20, 30, 40, 50, 60, 100], 
         ['child', 'teen', 'twenties', 'thirties', 'forties', 'fifties', 'senior']) as demographic"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "age")
        assert_sql_contains(sql, "child", "teen", "twenties", "thirties")
        assert_valid_sql(sql)
    
    def test_revenue_tiers(self) -> None:
        """Test revenue tier bucketing."""
        asql = """from companies
select
  name,
  annual_revenue,
  bucket(annual_revenue, [0, 1000000, 10000000, 100000000, 1000000000],
         ['startup', 'small', 'medium', 'large']) as company_size"""
        sql = compile(asql)
        
        assert_sql_contains(sql, "CASE", "WHEN", "annual_revenue")
        assert_sql_contains(sql, "startup", "small", "medium", "large")
        assert_valid_sql(sql)
