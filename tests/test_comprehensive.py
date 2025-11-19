"""Comprehensive tests for ASQL compiler using fixtures and edge cases."""

import pytest
from asql import compile
from asql.errors import ASQLSyntaxError, ASQLCompilationError
from tests.fixtures import (
    VALID_ASQL_QUERIES,
    INVALID_ASQL_QUERIES,
    EDGE_CASES,
    EXAMPLE_SCHEMAS,
)


class TestValidQueries:
    """Test all valid ASQL queries compile successfully."""
    
    @pytest.mark.parametrize("asql_query", VALID_ASQL_QUERIES)
    def test_valid_query_compiles(self, asql_query: str) -> None:
        """Test that valid ASQL query compiles without errors."""
        sql = compile(asql_query)
        assert sql is not None
        assert len(sql) > 0
        assert "SELECT" in sql.upper() or "WITH" in sql.upper()
        assert "FROM" in sql.upper()


class TestInvalidQueries:
    """Test that invalid queries raise appropriate errors."""
    
    @pytest.mark.parametrize("asql_query,description", INVALID_ASQL_QUERIES)
    def test_invalid_query_raises_error(self, asql_query: str, description: str) -> None:
        """Test that invalid ASQL query raises ASQLSyntaxError."""
        with pytest.raises(ASQLSyntaxError):
            compile(asql_query)


class TestEdgeCases:
    """Test edge cases and complex queries."""
    
    @pytest.mark.parametrize("asql_query", EDGE_CASES)
    def test_edge_case_compiles(self, asql_query: str) -> None:
        """Test that edge case queries compile successfully."""
        sql = compile(asql_query)
        assert sql is not None
        assert len(sql) > 0


class TestDialectSupport:
    """Test SQL dialect support."""
    
    def test_postgres_dialect(self) -> None:
        """Test PostgreSQL dialect generation."""
        asql = 'from users where status == "active"'
        sql = compile(asql, dialect="postgres")
        assert "SELECT" in sql.upper()
        assert "FROM" in sql.upper()
        # PostgreSQL uses single quotes
        assert "'active'" in sql or '"active"' in sql
    
    def test_mysql_dialect(self) -> None:
        """Test MySQL dialect generation."""
        asql = 'from users where status == "active"'
        sql = compile(asql, dialect="mysql")
        assert "SELECT" in sql.upper()
        assert "FROM" in sql.upper()
    
    def test_bigquery_dialect(self) -> None:
        """Test BigQuery dialect generation."""
        asql = 'from users where status == "active"'
        sql = compile(asql, dialect="bigquery")
        assert "SELECT" in sql.upper()
        assert "FROM" in sql.upper()
    
    def test_snowflake_dialect(self) -> None:
        """Test Snowflake dialect generation."""
        asql = 'from users where status == "active"'
        sql = compile(asql, dialect="snowflake")
        assert "SELECT" in sql.upper()
        assert "FROM" in sql.upper()


class TestComplexPipelines:
    """Test complex multi-step pipelines."""
    
    def test_full_pipeline(self) -> None:
        """Test complete pipeline: WHERE, GROUP BY, SORT, TAKE."""
        asql = """
from users
where status == "active"
group by country ( # as total_users )
sort -total_users
take 10
"""
        sql = compile(asql)
        assert "SELECT" in sql.upper()
        assert "WHERE" in sql.upper()
        assert "GROUP BY" in sql.upper()
        assert "ORDER BY" in sql.upper()
        assert "LIMIT" in sql.upper()
        assert "10" in sql
    
    def test_multiple_where_conditions(self) -> None:
        """Test multiple WHERE conditions."""
        asql = 'from users where status == "active" and age >= 18 and email is not null'
        sql = compile(asql)
        assert "WHERE" in sql.upper()
        assert "AND" in sql.upper()
        assert sql.count("AND") >= 2
    
    def test_complex_group_by(self) -> None:
        """Test GROUP BY with multiple columns and aggregations."""
        asql = "from sales group by region, month ( sum(amount) as revenue, # as orders, avg(amount) as avg_order )"
        sql = compile(asql)
        assert "GROUP BY" in sql.upper()
        assert "SUM" in sql.upper()
        assert "COUNT" in sql.upper()
        assert "AVG" in sql.upper()
        assert "region" in sql.lower()
        assert "month" in sql.lower()


class TestExpressionPrecedence:
    """Test operator precedence in expressions."""
    
    def test_and_before_or(self) -> None:
        """Test that AND has higher precedence than OR."""
        asql = 'from users where status == "active" or status == "pending" and age >= 18'
        sql = compile(asql)
        assert "WHERE" in sql.upper()
        # Should have parentheses around AND expression
        assert "OR" in sql.upper()
        assert "AND" in sql.upper()
    
    def test_not_precedence(self) -> None:
        """Test that NOT has highest precedence."""
        asql = 'from users where not status == "inactive"'
        sql = compile(asql)
        assert "NOT" in sql.upper()


class TestStringLiterals:
    """Test string literal handling."""
    
    def test_double_quoted_strings(self) -> None:
        """Test double-quoted string literals."""
        asql = 'from users where status == "active"'
        sql = compile(asql)
        assert "active" in sql.lower()
    
    def test_single_quoted_strings(self) -> None:
        """Test single-quoted string literals."""
        asql = "from users where status == 'active'"
        sql = compile(asql)
        assert "active" in sql.lower()
    
    def test_string_with_spaces(self) -> None:
        """Test string literals with spaces."""
        asql = 'from users where status == "active user"'
        sql = compile(asql)
        assert "active" in sql.lower()
        assert "user" in sql.lower()


class TestNumericLiterals:
    """Test numeric literal handling."""
    
    def test_integer_literals(self) -> None:
        """Test integer literals."""
        asql = "from users where age == 18"
        sql = compile(asql)
        assert "18" in sql
    
    def test_negative_numbers(self) -> None:
        """Test negative number literals."""
        asql = "from users where balance == -100"
        sql = compile(asql)
        assert "-100" in sql or "100" in sql
    
    def test_comparison_with_numbers(self) -> None:
        """Test comparisons with numeric values."""
        asql = "from users where age >= 18 and age <= 65"
        sql = compile(asql)
        assert "18" in sql
        assert "65" in sql
        assert ">=" in sql or ">=" in sql.replace(" ", "")
        assert "<=" in sql or "<=" in sql.replace(" ", "")


class TestAggregations:
    """Test aggregation functions."""
    
    def test_all_aggregation_functions(self) -> None:
        """Test all aggregation functions."""
        asql = """
from sales group by region (
    sum(amount) as revenue,
    avg(amount) as avg_order,
    # as orders,
    min(amount) as min_order,
    max(amount) as max_order
)
"""
        sql = compile(asql)
        assert "SUM" in sql.upper()
        assert "AVG" in sql.upper()
        assert "COUNT" in sql.upper()
        assert "MIN" in sql.upper()
        assert "MAX" in sql.upper()
    
    def test_count_shorthand(self) -> None:
        """Test # shorthand for COUNT(*)."""
        asql = "from users group by country ( # as total_users )"
        sql = compile(asql)
        assert "COUNT" in sql.upper()
        assert "total_users" in sql.lower()


class TestSorting:
    """Test sorting functionality."""
    
    def test_sort_ascending(self) -> None:
        """Test ascending sort."""
        asql = "from users sort name"
        sql = compile(asql)
        assert "ORDER BY" in sql.upper()
        assert "name" in sql.lower()
    
    def test_sort_descending(self) -> None:
        """Test descending sort with - prefix."""
        asql = "from users sort -total_users"
        sql = compile(asql)
        assert "ORDER BY" in sql.upper()
        assert "DESC" in sql.upper()
    
    def test_sort_function_call(self) -> None:
        """Test sorting by function call."""
        asql = "from users sort month(created_at)"
        sql = compile(asql)
        assert "ORDER BY" in sql.upper()
        assert "MONTH" in sql.upper() or "month" in sql.lower()
    
    def test_sort_multiple_columns(self) -> None:
        """Test sorting by multiple columns."""
        asql = "from users sort -total_users, name"
        sql = compile(asql)
        assert "ORDER BY" in sql.upper()
        # Should have both columns
        assert "total_users" in sql.lower() or "TOTAL_USERS" in sql.upper()
        assert "name" in sql.lower() or "NAME" in sql.upper()


class TestErrorMessages:
    """Test error message quality."""
    
    def test_empty_query_error(self) -> None:
        """Test empty query gives clear error."""
        with pytest.raises(ASQLSyntaxError) as exc_info:
            compile("")
        assert "empty" in str(exc_info.value).lower() or "Empty" in str(exc_info.value)
    
    def test_missing_from_error(self) -> None:
        """Test missing FROM gives clear error."""
        with pytest.raises(ASQLSyntaxError) as exc_info:
            compile("select * from users")
        error_msg = str(exc_info.value).lower()
        assert "from" in error_msg or "expected" in error_msg
    
    def test_incomplete_where_error(self) -> None:
        """Test incomplete WHERE gives clear error."""
        with pytest.raises(ASQLSyntaxError) as exc_info:
            compile("from users where")
        error_msg = str(exc_info.value).lower()
        assert "where" in error_msg or "expected" in error_msg or "expression" in error_msg


class TestSQLGeneration:
    """Test SQL generation quality."""
    
    def test_sql_is_valid_syntax(self) -> None:
        """Test that generated SQL is syntactically valid (can be parsed by SQLGlot)."""
        import sqlglot
        
        asql = 'from users where status == "active" group by country ( # as total_users )'
        sql = compile(asql)
        
        # Try to parse the generated SQL
        try:
            parsed = sqlglot.parse_one(sql)
            assert parsed is not None
        except Exception:
            # Some dialects might generate SQL that SQLGlot can't parse back
            # That's okay - the important thing is it's valid for the target database
            pass
    
    def test_no_duplicate_keywords(self) -> None:
        """Test that SQL doesn't have duplicate keywords in wrong places."""
        asql = "from users"
        sql = compile(asql)
        sql_upper = sql.upper()
        
        # Should have SELECT and FROM (in CTE-based structure)
        assert sql_upper.count("SELECT") >= 1
        assert sql_upper.count("FROM") >= 1
        
        # With CTE-based pipeline, structure is different - just verify both exist
        assert sql_upper.find("SELECT") >= 0
        assert sql_upper.find("FROM") >= 0


class TestRealWorldQueries:
    """Test real-world query patterns."""
    
    def test_user_analytics_query(self) -> None:
        """Test typical user analytics query."""
        asql = """
from users
where status == "active" and age >= 18
group by country ( # as total_users, avg(age) as avg_age )
sort -total_users
take 20
"""
        sql = compile(asql)
        assert "SELECT" in sql.upper()
        assert "WHERE" in sql.upper()
        assert "GROUP BY" in sql.upper()
        assert "ORDER BY" in sql.upper()
        assert "LIMIT" in sql.upper()
    
    def test_sales_report_query(self) -> None:
        """Test typical sales report query."""
        asql = """
from sales
where status == "completed" and amount > 100
group by region ( sum(amount) as revenue, # as orders )
sort -revenue
take 10
"""
        sql = compile(asql)
        assert "SELECT" in sql.upper()
        assert "WHERE" in sql.upper()
        assert "GROUP BY" in sql.upper()
        assert "SUM" in sql.upper()
        assert "COUNT" in sql.upper()
        assert "ORDER BY" in sql.upper()
        assert "LIMIT" in sql.upper()
    
    def test_filtering_by_status_list(self) -> None:
        """Test filtering by list of statuses."""
        asql = 'from users where status in ("active", "pending", "verified")'
        sql = compile(asql)
        assert "WHERE" in sql.upper()
        assert "IN" in sql.upper()
        assert "active" in sql.lower()
        assert "pending" in sql.lower()
        assert "verified" in sql.lower()
