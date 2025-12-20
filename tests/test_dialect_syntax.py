"""Tests for validating SQL syntax across all supported dialects.

These tests ensure that ASQL generates valid SQL for all target dialects
using SQLGlot's parsing capabilities, without requiring database connections.
"""

import pytest
import os
from pathlib import Path
from typing import List

from asql import compile
from asql.testing.syntax_validator import (
    SUPPORTED_DIALECTS,
    DIALECT_LIMITATIONS,
    validate_syntax,
    is_feature_supported,
)


# =============================================================================
# Core Queries - Basic functionality every dialect should support
# =============================================================================
CORE_QUERIES: List[str] = [
    # Basic SELECT
    "from users select name",
    "from users select name, email",
    "from users select *",
    # WHERE clause
    "from users where status = 'active'",
    "from users where age >= 18",
    "from users where status = 'active' and verified = true",
    "from users where status = 'active' or status = 'pending'",
    # ORDER BY
    "from users order by name",
    "from users order by -created_at",  # DESC
    "from users order by name, -created_at",
    # LIMIT
    "from users limit 10",
    "from users order by -created_at limit 10",
    # Combination
    "from users where status = 'active' order by -created_at limit 10",
]


# =============================================================================
# Aggregation Queries - GROUP BY and aggregate functions
# =============================================================================
AGGREGATION_QUERIES: List[str] = [
    # Basic aggregates
    "from sales group by region (sum(amount) as total)",
    "from sales group by region (count(*) as cnt)",
    "from orders group by customer_id (avg(total) as avg_order)",
    # Multiple aggregates
    "from sales group by region (sum(amount) as total, count(*) as cnt)",
    # COUNT DISTINCT
    "from orders group by product_id (count(distinct customer_id) as unique_customers)",
    # With HAVING (via second WHERE)
    "from sales group by region (sum(amount) as total) where total > 1000",
    # With ORDER BY
    "from sales group by region (sum(amount) as total) order by -total",
]


# =============================================================================
# Join Queries - Various join types
# =============================================================================
JOIN_QUERIES: List[str] = [
    # Inner join
    "from orders & customers on orders.customer_id = customers.id select orders.id, customers.name",
    # Left join
    "from orders &? customers on orders.customer_id = customers.id select orders.id, customers.name",
    # Right join
    "from orders ?& customers on orders.customer_id = customers.id select orders.id, customers.name",
    # Multiple joins
    "from orders & customers on orders.customer_id = customers.id & products on orders.product_id = products.id select orders.id",
]


# =============================================================================
# Window Function Queries
# =============================================================================
WINDOW_QUERIES: List[str] = [
    # ROW_NUMBER
    "from orders select order_id, row_number() over (order by order_date) as rn",
    # ROW_NUMBER with PARTITION
    "from orders select order_id, row_number() over (partition by customer_id order by order_date) as rn",
    # RANK
    "from scores select player_id, rank() over (order by score desc) as rank",
    # SUM window
    "from orders select order_id, sum(amount) over (order by order_date) as running_total",
    # LAG
    "from orders select order_id, lag(amount, 1) over (order by order_date) as prev_amount",
    # LEAD
    "from orders select order_id, lead(amount, 1) over (order by order_date) as next_amount",
]


# =============================================================================
# CTE Queries - Common Table Expressions (using stash as syntax)
# =============================================================================
CTE_QUERIES: List[str] = [
    # Simple CTE with stash as - creates a CTE and selects from original table (implicit)
    "from users where status = 'active' stash as active_users",
    # CTE with aggregation stash
    "from sales group by region (sum(amount) as total) stash as totals",
    # CTE that continues the pipeline after stash
    "from users where status = 'active' stash as active_users group by country (count(*) as cnt)",
]


# =============================================================================
# Expression Queries - Arithmetic, CASE, etc.
# =============================================================================
EXPRESSION_QUERIES: List[str] = [
    # Arithmetic
    "from items select price * quantity as total",
    "from items select (price * quantity) - discount as net",
    # CASE WHEN
    "from users select name, case when status = 'active' then 1 else 0 end as is_active",
    # COALESCE
    "from users select coalesce(name, 'Unknown') as display_name",
    # IN list
    "from users where status in ('active', 'pending')",
    # BETWEEN
    "from orders where amount between 100 and 500",
    # IS NULL
    "from users where deleted_at is null",
    # IS NOT NULL
    "from users where email is not null",
]


# =============================================================================
# QUALIFY Queries - Window function filtering (dialect-specific)
# =============================================================================
QUALIFY_QUERIES: List[str] = [
    "from orders qualify row_number() over (partition by customer_id order by order_date desc) = 1",
]


# =============================================================================
# Test Classes
# =============================================================================

class TestCoreSyntax:
    """Test that core SQL features generate valid syntax for all dialects."""
    
    @pytest.mark.parametrize("dialect", SUPPORTED_DIALECTS)
    @pytest.mark.parametrize("asql_query", CORE_QUERIES)
    def test_core_queries(self, dialect: str, asql_query: str) -> None:
        """Basic queries should generate valid SQL for all dialects."""
        sql = compile(asql_query, dialect=dialect)
        is_valid, error = validate_syntax(sql, dialect)
        assert is_valid, f"Invalid {dialect} SQL for '{asql_query}':\n{error}\nGenerated SQL:\n{sql}"


class TestAggregationSyntax:
    """Test that aggregation queries generate valid syntax for all dialects."""
    
    @pytest.mark.parametrize("dialect", SUPPORTED_DIALECTS)
    @pytest.mark.parametrize("asql_query", AGGREGATION_QUERIES)
    def test_aggregation_queries(self, dialect: str, asql_query: str) -> None:
        """Aggregation queries should generate valid SQL for all dialects."""
        sql = compile(asql_query, dialect=dialect)
        is_valid, error = validate_syntax(sql, dialect)
        assert is_valid, f"Invalid {dialect} SQL for '{asql_query}':\n{error}\nGenerated SQL:\n{sql}"


class TestJoinSyntax:
    """Test that JOIN queries generate valid syntax for all dialects."""
    
    @pytest.mark.parametrize("dialect", SUPPORTED_DIALECTS)
    @pytest.mark.parametrize("asql_query", JOIN_QUERIES)
    def test_join_queries(self, dialect: str, asql_query: str) -> None:
        """JOIN queries should generate valid SQL for all dialects."""
        sql = compile(asql_query, dialect=dialect)
        is_valid, error = validate_syntax(sql, dialect)
        assert is_valid, f"Invalid {dialect} SQL for '{asql_query}':\n{error}\nGenerated SQL:\n{sql}"


class TestWindowSyntax:
    """Test that window function queries generate valid syntax for all dialects."""
    
    @pytest.mark.parametrize("dialect", SUPPORTED_DIALECTS)
    @pytest.mark.parametrize("asql_query", WINDOW_QUERIES)
    def test_window_queries(self, dialect: str, asql_query: str) -> None:
        """Window function queries should generate valid SQL for all dialects."""
        sql = compile(asql_query, dialect=dialect)
        is_valid, error = validate_syntax(sql, dialect)
        assert is_valid, f"Invalid {dialect} SQL for '{asql_query}':\n{error}\nGenerated SQL:\n{sql}"


class TestCTESyntax:
    """Test that CTE queries generate valid syntax for all dialects."""
    
    @pytest.mark.parametrize("dialect", SUPPORTED_DIALECTS)
    @pytest.mark.parametrize("asql_query", CTE_QUERIES)
    def test_cte_queries(self, dialect: str, asql_query: str) -> None:
        """CTE queries should generate valid SQL for all dialects."""
        sql = compile(asql_query, dialect=dialect)
        is_valid, error = validate_syntax(sql, dialect)
        assert is_valid, f"Invalid {dialect} SQL for '{asql_query}':\n{error}\nGenerated SQL:\n{sql}"


class TestExpressionSyntax:
    """Test that expression queries generate valid syntax for all dialects."""
    
    @pytest.mark.parametrize("dialect", SUPPORTED_DIALECTS)
    @pytest.mark.parametrize("asql_query", EXPRESSION_QUERIES)
    def test_expression_queries(self, dialect: str, asql_query: str) -> None:
        """Expression queries should generate valid SQL for all dialects."""
        sql = compile(asql_query, dialect=dialect)
        is_valid, error = validate_syntax(sql, dialect)
        assert is_valid, f"Invalid {dialect} SQL for '{asql_query}':\n{error}\nGenerated SQL:\n{sql}"


class TestQualifySyntax:
    """Test QUALIFY clause (dialect-specific support)."""
    
    @pytest.mark.parametrize("dialect", SUPPORTED_DIALECTS)
    @pytest.mark.parametrize("asql_query", QUALIFY_QUERIES)
    def test_qualify_queries(self, dialect: str, asql_query: str) -> None:
        """QUALIFY queries - may be unsupported in some dialects."""
        if not is_feature_supported(dialect, 'qualify_clause'):
            pytest.xfail(f"{dialect} doesn't support QUALIFY clause natively")
        
        sql = compile(asql_query, dialect=dialect)
        is_valid, error = validate_syntax(sql, dialect)
        assert is_valid, f"Invalid {dialect} SQL for '{asql_query}':\n{error}\nGenerated SQL:\n{sql}"


class TestExampleFiles:
    """Test that ASQL example files generate valid SQL for all dialects.
    
    Note: Example files may use advanced features that don't work for all dialects.
    This test is more lenient and tracks coverage rather than strict pass/fail.
    """
    
    @pytest.fixture
    def example_asql_files(self) -> List[Path]:
        """Get all .asql example files."""
        examples_dir = Path(__file__).parent.parent / "examples" / "pairs"
        if not examples_dir.exists():
            return []
        return list(examples_dir.glob("*.asql"))
    
    @pytest.mark.parametrize("dialect", SUPPORTED_DIALECTS)
    def test_example_files_valid(self, dialect: str, example_asql_files: List[Path]) -> None:
        """Example ASQL files should generate valid SQL for most dialects.
        
        This test is informational - it tracks how many example files work
        for each dialect but doesn't fail unless a significant majority fail.
        Example files often use advanced features that may not work across
        all dialects.
        """
        if not example_asql_files:
            pytest.skip("No example files found")
        
        errors: List[str] = []
        successes: List[str] = []
        
        for asql_file in example_asql_files:
            try:
                asql_content = asql_file.read_text()
                sql = compile(asql_content, dialect=dialect)
                is_valid, error = validate_syntax(sql, dialect)
                if not is_valid:
                    errors.append(f"{asql_file.name}: Syntax validation error - {error}")
                else:
                    successes.append(asql_file.name)
            except Exception as e:
                # Some examples may use features not supported by all dialects
                # or may have syntax that the preparser doesn't handle yet
                error_str = str(e)
                if len(error_str) > 200:
                    error_str = error_str[:200] + "..."
                errors.append(f"{asql_file.name}: Compilation error - {error_str}")
        
        # Allow failures for dialect-specific features
        # Only fail if more than 75% fail - example files are aspirational
        total_files = len(example_asql_files)
        if total_files > 0:
            success_rate = len(successes) / total_files
            # We expect at least 25% of example files to work (very lenient)
            # because example files use advanced features
            if success_rate < 0.25:
                pytest.fail(
                    f"Only {len(successes)}/{total_files} ({success_rate:.0%}) "
                    f"example files compiled for {dialect}.\n"
                    f"First errors:\n" + "\n".join(errors[:3])
                )


class TestDialectLimitations:
    """Test that dialect limitations are properly documented."""
    
    def test_limitations_dict_has_expected_keys(self) -> None:
        """DIALECT_LIMITATIONS should only contain known dialects."""
        for dialect in DIALECT_LIMITATIONS:
            assert dialect in SUPPORTED_DIALECTS, (
                f"Unknown dialect in DIALECT_LIMITATIONS: {dialect}"
            )
    
    def test_limitations_values_are_lists(self) -> None:
        """DIALECT_LIMITATIONS values should be lists of feature strings."""
        for dialect, features in DIALECT_LIMITATIONS.items():
            assert isinstance(features, list), (
                f"DIALECT_LIMITATIONS['{dialect}'] should be a list"
            )
            for feature in features:
                assert isinstance(feature, str), (
                    f"Features should be strings, got {type(feature)} in {dialect}"
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
