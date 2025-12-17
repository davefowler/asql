"""Tests for the ASQL SQLGlot dialect.

The ASQL dialect handles expression-level ASQL syntax that fits within
SQLGlot's extension model (custom tokens, function parsers, etc.).
"""

import pytest
import sqlglot
from sqlglot import exp
from asql.dialect import ASQL, ASQLDialect, register_asql_dialect


# Ensure dialect is registered
register_asql_dialect()


class TestDialectRegistration:
    """Test that the ASQL dialect is properly registered."""
    
    def test_dialect_is_registered(self):
        """ASQL dialect is registered with SQLGlot."""
        from sqlglot.dialects.dialect import Dialect
        # Should not raise
        dialect = Dialect.get_or_raise("asql")
        assert dialect is not None
    
    def test_dialect_has_tokenizer(self):
        """ASQL dialect has custom tokenizer."""
        assert hasattr(ASQL, "Tokenizer")
        assert ASQL.Tokenizer is not None
    
    def test_dialect_has_parser(self):
        """ASQL dialect has custom parser."""
        assert hasattr(ASQL, "Parser")
        assert ASQL.Parser is not None
    
    def test_dialect_has_generator(self):
        """ASQL dialect has custom generator."""
        assert hasattr(ASQL, "Generator")
        assert ASQL.Generator is not None


class TestBasicParsing:
    """Test basic SQL parsing with ASQL dialect."""
    
    def test_simple_select(self):
        """Parse simple SELECT."""
        sql = "SELECT * FROM users"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        assert isinstance(ast, exp.Select)
    
    def test_select_with_where(self):
        """Parse SELECT with WHERE."""
        sql = "SELECT * FROM users WHERE status = 'active'"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        assert ast.find(exp.Where) is not None
    
    def test_select_with_order(self):
        """Parse SELECT with ORDER BY."""
        sql = "SELECT * FROM users ORDER BY created_at DESC"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        assert ast.find(exp.Order) is not None
    
    def test_select_with_limit(self):
        """Parse SELECT with LIMIT."""
        sql = "SELECT * FROM users LIMIT 10"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        assert ast.find(exp.Limit) is not None
    
    def test_select_with_group_by(self):
        """Parse SELECT with GROUP BY."""
        sql = "SELECT region, COUNT(*) FROM sales GROUP BY region"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        assert ast.find(exp.Group) is not None


class TestAggregates:
    """Test aggregate function parsing."""
    
    def test_sum(self):
        """Parse SUM function."""
        sql = "SELECT SUM(amount) FROM sales"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        sum_expr = ast.find(exp.Sum)
        assert sum_expr is not None
    
    def test_avg(self):
        """Parse AVG function."""
        sql = "SELECT AVG(price) FROM products"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        avg_expr = ast.find(exp.Avg)
        assert avg_expr is not None
    
    def test_count(self):
        """Parse COUNT function."""
        sql = "SELECT COUNT(*) FROM users"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        count_expr = ast.find(exp.Count)
        assert count_expr is not None
    
    def test_count_distinct(self):
        """Parse COUNT(DISTINCT col)."""
        sql = "SELECT COUNT(DISTINCT user_id) FROM orders"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        count_expr = ast.find(exp.Count)
        assert count_expr is not None


class TestWindowFunctions:
    """Test window function parsing."""
    
    def test_row_number(self):
        """Parse ROW_NUMBER window function."""
        sql = "SELECT ROW_NUMBER() OVER (ORDER BY id) FROM users"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        window = ast.find(exp.Window)
        assert window is not None
    
    def test_row_number_with_partition(self):
        """Parse ROW_NUMBER with PARTITION BY."""
        sql = "SELECT ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) FROM orders"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        window = ast.find(exp.Window)
        assert window is not None
    
    def test_rank(self):
        """Parse RANK window function."""
        sql = "SELECT RANK() OVER (ORDER BY score DESC) FROM scores"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        window = ast.find(exp.Window)
        assert window is not None
    
    def test_dense_rank(self):
        """Parse DENSE_RANK window function."""
        sql = "SELECT DENSE_RANK() OVER (PARTITION BY dept ORDER BY salary DESC) FROM employees"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        window = ast.find(exp.Window)
        assert window is not None
    
    def test_lag(self):
        """Parse LAG window function."""
        sql = "SELECT LAG(value, 1) OVER (ORDER BY date) FROM metrics"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        window = ast.find(exp.Window)
        assert window is not None
    
    def test_lead(self):
        """Parse LEAD window function."""
        sql = "SELECT LEAD(value, 1) OVER (ORDER BY date) FROM metrics"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        window = ast.find(exp.Window)
        assert window is not None


class TestJoins:
    """Test JOIN parsing."""
    
    def test_inner_join(self):
        """Parse INNER JOIN."""
        sql = "SELECT * FROM orders JOIN customers ON orders.customer_id = customers.id"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        join = ast.find(exp.Join)
        assert join is not None
    
    def test_left_join(self):
        """Parse LEFT JOIN."""
        sql = "SELECT * FROM orders LEFT JOIN customers ON orders.customer_id = customers.id"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        join = ast.find(exp.Join)
        assert join is not None


class TestCTEs:
    """Test Common Table Expression (CTE) parsing."""
    
    def test_simple_cte(self):
        """Parse simple CTE."""
        sql = "WITH active_users AS (SELECT * FROM users WHERE active) SELECT * FROM active_users"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        cte = ast.find(exp.CTE)
        assert cte is not None
    
    def test_multiple_ctes(self):
        """Parse multiple CTEs."""
        sql = """
        WITH 
            active_users AS (SELECT * FROM users WHERE active),
            recent_orders AS (SELECT * FROM orders WHERE date > '2024-01-01')
        SELECT * FROM active_users JOIN recent_orders ON active_users.id = recent_orders.user_id
        """
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        ctes = list(ast.find_all(exp.CTE))
        assert len(ctes) == 2


class TestExpressions:
    """Test expression parsing."""
    
    def test_arithmetic(self):
        """Parse arithmetic expressions."""
        sql = "SELECT price * quantity AS total FROM items"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        mul = ast.find(exp.Mul)
        assert mul is not None
    
    def test_comparison(self):
        """Parse comparison expressions."""
        sql = "SELECT * FROM users WHERE age >= 18"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        gte = ast.find(exp.GTE)
        assert gte is not None
    
    def test_coalesce(self):
        """Parse COALESCE function."""
        sql = "SELECT COALESCE(name, 'Unknown') FROM users"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        coalesce = ast.find(exp.Coalesce)
        assert coalesce is not None
    
    def test_case_when(self):
        """Parse CASE WHEN expression."""
        sql = "SELECT CASE WHEN status = 'active' THEN 1 ELSE 0 END FROM users"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        case = ast.find(exp.Case)
        assert case is not None
    
    def test_in_list(self):
        """Parse IN list expression."""
        sql = "SELECT * FROM users WHERE status IN ('active', 'pending')"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        in_expr = ast.find(exp.In)
        assert in_expr is not None


class TestCasting:
    """Test type casting parsing."""
    
    def test_cast_function(self):
        """Parse CAST function."""
        sql = "SELECT CAST(value AS INTEGER) FROM data"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        cast = ast.find(exp.Cast)
        assert cast is not None
    
    def test_double_colon_cast(self):
        """Parse :: cast syntax (PostgreSQL style)."""
        sql = "SELECT value::INTEGER FROM data"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        cast = ast.find(exp.Cast)
        assert cast is not None


class TestDateFunctions:
    """Test date function parsing."""
    
    def test_date_trunc(self):
        """Parse DATE_TRUNC function."""
        sql = "SELECT DATE_TRUNC('month', created_at) FROM events"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
    
    def test_interval(self):
        """Parse INTERVAL expression."""
        sql = "SELECT created_at + INTERVAL '7 days' FROM events"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        interval = ast.find(exp.Interval)
        assert interval is not None


class TestSQLGeneration:
    """Test SQL generation from parsed AST."""
    
    def test_generate_postgres(self):
        """Generate PostgreSQL SQL."""
        sql = "SELECT * FROM users WHERE status = 'active'"
        ast = sqlglot.parse_one(sql, dialect="asql")
        result = ast.sql(dialect="postgres")
        assert "SELECT" in result.upper()
        assert "FROM USERS" in result.upper()
    
    def test_generate_mysql(self):
        """Generate MySQL SQL."""
        sql = "SELECT * FROM users WHERE status = 'active'"
        ast = sqlglot.parse_one(sql, dialect="asql")
        result = ast.sql(dialect="mysql")
        assert "SELECT" in result.upper()
    
    def test_generate_bigquery(self):
        """Generate BigQuery SQL."""
        sql = "SELECT * FROM users WHERE status = 'active'"
        ast = sqlglot.parse_one(sql, dialect="asql")
        result = ast.sql(dialect="bigquery")
        assert "SELECT" in result.upper()
    
    def test_generate_snowflake(self):
        """Generate Snowflake SQL."""
        sql = "SELECT * FROM users WHERE status = 'active'"
        ast = sqlglot.parse_one(sql, dialect="asql")
        result = ast.sql(dialect="snowflake")
        assert "SELECT" in result.upper()


class TestQualify:
    """Test QUALIFY clause parsing (for window function filtering)."""
    
    def test_qualify_clause(self):
        """Parse QUALIFY clause."""
        sql = "SELECT * FROM orders QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) = 1"
        ast = sqlglot.parse_one(sql, dialect="asql")
        assert ast is not None
        qualify = ast.find(exp.Qualify)
        assert qualify is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
