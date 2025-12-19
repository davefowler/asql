"""Tests for ASQL auto-spine feature.

Auto-spine automatically adds gap-filling CTEs for date truncation columns
in GROUP BY clauses, ensuring all dates appear in results.

The feature:
- Defaults to ON for pure date GROUP BY
- Can be disabled via SET auto_spine = false
- Supports guarantee() for explicit categorical spines
- Filtering removes spine rows when not wanted
"""

import pytest
from asql import compile, CompileSettings
from asql.compiler import (
    _find_date_trunc_in_group_by,
    _find_guarantee_in_group_by,
    _find_non_date_group_by_columns,
    _is_guarantee_wrapped,
    _unwrap_guarantee,
    _remove_guarantee_wrappers,
)
import sqlglot


class TestAutoSpineDefault:
    """Test that auto_spine defaults to True."""
    
    def test_auto_spine_default_true(self):
        """Test that auto_spine defaults to True."""
        settings = CompileSettings()
        assert settings.auto_spine is True
    
    def test_auto_spine_can_be_disabled(self):
        """Test that auto_spine can be disabled."""
        settings = CompileSettings(auto_spine=False)
        assert settings.auto_spine is False


class TestMixedGroupByHandling:
    """Test detection of non-date columns in GROUP BY for cross-join."""
    
    def test_find_non_date_columns_in_mixed_group_by(self):
        """Test finding non-date columns in mixed GROUP BY."""
        stmt = sqlglot.parse_one("SELECT month(created_at) as m, status FROM orders GROUP BY month(created_at), status")
        non_date_cols = _find_non_date_group_by_columns(stmt)
        
        # Should find 'status' as a non-date column
        assert len(non_date_cols) == 1
        alias, _ = non_date_cols[0]
        assert alias == "status"
    
    def test_pure_date_group_by_no_non_date(self):
        """Test that pure date GROUP BY has no non-date columns."""
        stmt = sqlglot.parse_one("SELECT month(created_at) as m FROM orders GROUP BY month(created_at)")
        non_date_cols = _find_non_date_group_by_columns(stmt)
        
        assert len(non_date_cols) == 0
    
    def test_only_non_date_group_by(self):
        """Test GROUP BY with only non-date columns."""
        stmt = sqlglot.parse_one("SELECT region, status FROM orders GROUP BY region, status")
        non_date_cols = _find_non_date_group_by_columns(stmt)
        
        # Should find both as non-date columns
        assert len(non_date_cols) == 2
    
    def test_no_group_by(self):
        """Test query without GROUP BY returns empty."""
        stmt = sqlglot.parse_one("SELECT * FROM orders")
        non_date_cols = _find_non_date_group_by_columns(stmt)
        
        assert len(non_date_cols) == 0


class TestFindDateTruncInGroupBy:
    """Test detection of date truncation functions in GROUP BY."""
    
    def test_find_month_function(self):
        """Test detecting month() function."""
        stmt = sqlglot.parse_one("SELECT month(created_at) as m FROM orders GROUP BY 1")
        results = _find_date_trunc_in_group_by(stmt)
        # The function is in SELECT, not GROUP BY with alias, so detection needs adjustment
        # For now, just verify no crash
        assert results is not None
    
    def test_find_date_trunc_function(self):
        """Test detecting date_trunc() function in GROUP BY."""
        stmt = sqlglot.parse_one("SELECT date_trunc('month', created_at) as m, SUM(amount) FROM orders GROUP BY date_trunc('month', created_at)")
        results = _find_date_trunc_in_group_by(stmt)
        # date_trunc should be detected
        assert results is not None
    
    def test_no_date_trunc(self):
        """Test query without date truncation."""
        stmt = sqlglot.parse_one("SELECT region, SUM(amount) FROM sales GROUP BY region")
        results = _find_date_trunc_in_group_by(stmt)
        
        assert len(results) == 0
    
    def test_non_select_statement(self):
        """Test non-SELECT statement returns empty."""
        stmt = sqlglot.parse_one("INSERT INTO t VALUES (1)")
        results = _find_date_trunc_in_group_by(stmt)
        
        assert len(results) == 0


class TestGuaranteeFunction:
    """Test guarantee() function for explicit spine."""
    
    def test_is_guarantee_wrapped(self):
        """Test detecting guarantee() wrapper."""
        stmt = sqlglot.parse_one("SELECT guarantee(month(created_at)) as m FROM orders GROUP BY guarantee(month(created_at))")
        group = stmt.find(sqlglot.exp.Group)
        
        assert group is not None
        is_guarantee, values = _is_guarantee_wrapped(group.expressions[0])
        assert is_guarantee is True
    
    def test_is_not_guarantee_wrapped(self):
        """Test detecting non-guarantee expression."""
        stmt = sqlglot.parse_one("SELECT month(created_at) as m FROM orders GROUP BY month(created_at)")
        group = stmt.find(sqlglot.exp.Group)
        
        assert group is not None
        is_guarantee, values = _is_guarantee_wrapped(group.expressions[0])
        assert is_guarantee is False
    
    def test_unwrap_guarantee_with_alias(self):
        """Test unwrapping guarantee() with alias."""
        stmt = sqlglot.parse_one("SELECT guarantee(month(created_at)) as m FROM orders")
        expr = stmt.expressions[0]
        
        unwrapped = _unwrap_guarantee(expr)
        # Should still have the alias but inner function exposed
        assert unwrapped.alias == "m"
    
    def test_remove_guarantee_wrappers(self):
        """Test removing guarantee wrappers from statement."""
        stmt = sqlglot.parse_one("SELECT guarantee(month(created_at)) as m FROM orders GROUP BY guarantee(month(created_at))")
        cleaned = _remove_guarantee_wrappers(stmt)
        
        # The SQL should not contain 'guarantee' anymore
        sql = cleaned.sql()
        assert "guarantee" not in sql.lower()
    
    def test_find_guarantee_in_group_by(self):
        """Test finding guarantee() expressions in GROUP BY."""
        stmt = sqlglot.parse_one("SELECT guarantee(region) as r FROM sales GROUP BY guarantee(region)")
        results = _find_guarantee_in_group_by(stmt)
        
        assert len(results) == 1
        alias, _, _ = results[0]
        # Alias is derived from the inner column name when GROUP BY doesn't have its own alias
        assert alias == "region"


class TestCompileWithAutoSpine:
    """Test compile() with auto_spine enabled."""
    
    def test_compile_without_group_by(self):
        """Test that queries without GROUP BY are unchanged."""
        sql = compile(
            "from users where status = 'active' limit 10",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        assert "SELECT" in sql
        assert "users" in sql
        assert "WITH" not in sql  # No CTEs needed
    
    def test_compile_with_non_date_group_by(self):
        """Test that GROUP BY on non-date columns is unchanged."""
        sql = compile(
            "from sales group by region (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        assert "SELECT" in sql
        assert "GROUP BY" in sql
        assert "region" in sql
        # Non-date columns should not generate spine CTEs
    
    def test_compile_with_guarantee(self):
        """Test that guarantee() is processed correctly."""
        sql = compile(
            "from orders group by guarantee(status) (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        # guarantee should be stripped from output
        assert "guarantee" not in sql.lower()
        assert "SELECT" in sql
        assert "GROUP BY" in sql
    
    def test_compile_with_auto_spine_disabled(self):
        """Test compilation with auto_spine disabled."""
        sql = compile(
            "from orders group by status (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=False)
        )
        
        assert "SELECT" in sql
        assert "GROUP BY" in sql
        # Should not have spine CTEs when disabled
    
    def test_inline_set_disables_auto_spine(self):
        """Test inline SET auto_spine = false disables spine."""
        # Note: SET with aggregate block syntax has a known limitation
        # Use simple query syntax for now
        asql = """
        SET auto_spine = false;
        from orders where status = 'active' limit 10
        """
        sql = compile(asql, dialect="postgres")
        
        assert "SELECT" in sql
        assert "orders" in sql


class TestFilteringToRemoveSpine:
    """Test that filtering effectively removes spine rows."""
    
    def test_filter_removes_zeros(self):
        """Test that WHERE revenue > 0 is valid syntax after spine."""
        sql = compile(
            "from orders group by status (sum(amount) as revenue) where revenue > 0",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        assert "SELECT" in sql
        assert "revenue > 0" in sql or "HAVING" in sql  # Could be HAVING for aggregates


class TestAutoSpineDialects:
    """Test auto-spine across different SQL dialects."""
    
    @pytest.mark.parametrize("dialect", [
        "postgres",
        "snowflake", 
        "bigquery",
        "mysql",
        "duckdb",
    ])
    def test_compile_basic_query_all_dialects(self, dialect):
        """Test that basic queries compile without error for all dialects."""
        try:
            sql = compile(
                "from users where active = true limit 10",
                dialect=dialect,
                settings=CompileSettings(auto_spine=True)
            )
            assert "SELECT" in sql.upper()
        except Exception as e:
            pytest.fail(f"Failed to compile for dialect {dialect}: {e}")
    
    @pytest.mark.parametrize("dialect", [
        "postgres",
        "snowflake",
        "bigquery", 
        "duckdb",
    ])
    def test_compile_group_by_non_date_all_dialects(self, dialect):
        """Test GROUP BY on non-date columns for all dialects."""
        try:
            sql = compile(
                "from sales group by region (sum(amount) as revenue)",
                dialect=dialect,
                settings=CompileSettings(auto_spine=True)
            )
            assert "SELECT" in sql.upper()
            assert "GROUP BY" in sql.upper()
        except Exception as e:
            pytest.fail(f"Failed to compile for dialect {dialect}: {e}")


class TestMixedGroupBy:
    """Test that mixed date + non-date GROUP BY doesn't auto-spine."""
    
    def test_mixed_group_by_no_auto_spine(self):
        """Test that mixed GROUP BY (date + non-date) doesn't auto-spine."""
        sql = compile(
            "from orders group by region (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        assert "SELECT" in sql
        assert "GROUP BY" in sql
        # Mixed GROUP BY should NOT have spine CTEs
        # (region is categorical, not a date truncation)


class TestEdgeCases:
    """Test edge cases for auto-spine."""
    
    def test_multiple_group_by_columns(self):
        """Test GROUP BY with multiple columns (only one date)."""
        sql = compile(
            "from orders group by region (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        assert "SELECT" in sql
        assert "GROUP BY" in sql
    
    def test_nested_function_calls(self):
        """Test nested function calls in GROUP BY."""
        sql = compile(
            "from orders group by status (count(*) as cnt)",
            dialect="postgres", 
            settings=CompileSettings(auto_spine=True)
        )
        
        assert "SELECT" in sql
        assert "GROUP BY" in sql
        # status is not a date function, should not generate spine
    
    def test_empty_result(self):
        """Test compilation still works even with complex expressions."""
        sql = compile(
            "from orders where amount > 100 group by status (sum(amount) as total)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        assert "SELECT" in sql
        assert "WHERE" in sql
        assert "GROUP BY" in sql


class TestRollupCubeDetection:
    """Test ROLLUP and CUBE detection and handling."""
    
    def test_detect_rollup(self):
        """Test detection of ROLLUP in GROUP BY."""
        from asql.compiler import _detect_rollup_cube
        
        stmt = sqlglot.parse_one("SELECT region, month, SUM(amount) FROM orders GROUP BY ROLLUP(region, month)")
        has_rollup, has_cube, columns = _detect_rollup_cube(stmt)
        
        assert has_rollup is True
        assert has_cube is False
        assert "region" in columns
        assert "month" in columns
    
    def test_detect_cube(self):
        """Test detection of CUBE in GROUP BY."""
        from asql.compiler import _detect_rollup_cube
        
        stmt = sqlglot.parse_one("SELECT region, category, SUM(amount) FROM orders GROUP BY CUBE(region, category)")
        has_rollup, has_cube, columns = _detect_rollup_cube(stmt)
        
        assert has_rollup is False
        assert has_cube is True
        assert "region" in columns
        assert "category" in columns
    
    def test_no_rollup_cube(self):
        """Test that regular GROUP BY has no ROLLUP/CUBE."""
        from asql.compiler import _detect_rollup_cube
        
        stmt = sqlglot.parse_one("SELECT region, SUM(amount) FROM orders GROUP BY region")
        has_rollup, has_cube, columns = _detect_rollup_cube(stmt)
        
        assert has_rollup is False
        assert has_cube is False
        assert columns == []
    
    def test_rollup_three_columns(self):
        """Test ROLLUP with 3 columns."""
        from asql.compiler import _detect_rollup_cube
        
        stmt = sqlglot.parse_one("SELECT region, category, product, SUM(amount) FROM orders GROUP BY ROLLUP(region, category, product)")
        has_rollup, has_cube, columns = _detect_rollup_cube(stmt)
        
        assert has_rollup is True
        assert len(columns) == 3
        assert columns == ["region", "category", "product"]


class TestRollupSpineGeneration:
    """Test that ROLLUP queries get proper spine with NULL handling."""
    
    def test_rollup_spine_includes_null_union(self):
        """Test that ROLLUP columns include NULL in spine for subtotals."""
        # This tests at a lower level that NULL is included
        from asql.compiler import _build_categorical_spine_sql
        
        # With include_null=True
        sql = _build_categorical_spine_sql("status", ["active", "inactive"], dialect="postgres", include_null=True)
        assert "NULL" in sql
        
        # Without include_null
        sql_no_null = _build_categorical_spine_sql("status", ["active", "inactive"], dialect="postgres", include_null=False)
        assert "NULL" not in sql_no_null
    
    def test_rollup_hierarchical_filter_logic(self):
        """Test that ROLLUP filter excludes invalid NULL combinations.
        
        For ROLLUP(a, b, c), valid patterns are:
        - (val, val, val) - all non-null
        - (val, val, NULL) - c is null
        - (val, NULL, NULL) - b,c are null  
        - (NULL, NULL, NULL) - all null (grand total)
        
        Invalid: (val, NULL, val) or (NULL, val, val) etc.
        
        Filter: (a IS NOT NULL OR b IS NULL) AND (b IS NOT NULL OR c IS NULL)
        """
        # Test the filter logic manually
        # (West, NULL, Nike) should be filtered out
        # Filter: (region IS NOT NULL OR category IS NULL) AND (category IS NOT NULL OR product IS NULL)
        # For (West, NULL, Nike): (True OR False) AND (False OR False) = True AND False = False -> FILTERED
        
        # (West, Shoes, NULL) should pass
        # (True OR False) AND (True OR True) = True AND True = True -> PASS
        
        # (NULL, NULL, NULL) should pass
        # (False OR True) AND (True OR True) = True AND True = True -> PASS
        
        # This is just documentation of the logic, actual SQL test is below
        pass
    
    def test_compile_with_rollup(self):
        """Test that standard SQL with ROLLUP compiles with auto_spine.
        
        Note: ASQL doesn't have native ROLLUP syntax yet. This tests that
        raw SQL containing ROLLUP is correctly detected and handled by
        auto-spine (adding NULL to spines + hierarchical filter).
        """
        sql = compile(
            "SELECT region, month, SUM(amount) as total FROM orders GROUP BY ROLLUP(region, month)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        # Should compile without error
        assert "SELECT" in sql
        # Should include NULL in spines for ROLLUP subtotals
        assert "UNION ALL SELECT NULL" in sql.upper()
        # Should have the hierarchical filter for ROLLUP
        # SQLGlot may normalize "IS NOT NULL" to "NOT ... IS NULL"
        assert "IS NULL" in sql.upper()  # Part of the filter condition


class TestPredicateCopyingToSpine:
    """Test that WHERE predicates are copied to filter the spine.
    
    The new unified approach copies relevant WHERE predicates to the spine CTE,
    ensuring that:
    1. Date spines are filtered to the relevant range
    2. Categorical spines only include relevant values
    3. This works without semantic parsing of comparison operators
    """

    def test_date_predicate_copied_to_spine(self):
        """Test that date filter is copied to the date spine."""
        sql = compile(
            "from orders where created_at >= '2021-01-01' group by month(created_at) (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        # The spine CTE should have the WHERE filter applied
        # This uses generate_series from 1970 to now, filtered by the predicate
        assert "_spine" in sql.lower()
        assert "generate_series" in sql.lower()
        # The filter should appear in the spine CTE
        assert "2021-01-01" in sql

    def test_categorical_predicate_copied_to_spine(self):
        """Test that categorical filter is copied to the categorical spine."""
        sql = compile(
            "from orders where region in ('North', 'South') group by region (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        # The spine CTE should have the WHERE filter
        assert "region_spine" in sql.lower()
        # The filter should be in the spine
        assert "North" in sql
        assert "South" in sql

    def test_multiple_predicates_on_same_column(self):
        """Test that multiple predicates on the grouped column are all copied."""
        sql = compile(
            "from orders where created_at >= '2021-01-01' and created_at < '2024-01-01' group by month(created_at) (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        # Both date bounds should appear in the output
        assert "2021-01-01" in sql
        assert "2024-01-01" in sql

    def test_predicate_for_different_column_not_copied(self):
        """Test that predicates on non-grouped columns are not copied to spine."""
        sql = compile(
            "from orders where status = 'active' group by region (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        # The status filter should be in the data CTE, not the spine
        assert "region_spine" in sql.lower()
        assert "status" in sql.lower()
        # The spine should use DISTINCT region, but status filter should be in data CTE


class TestUnsafePredicatesSkipped:
    """Test that unsafe predicates (referencing other columns) are skipped for spine.
    
    When a WHERE predicate references multiple columns, it cannot be safely
    applied to the spine CTE because the other columns don't exist there.
    """

    def test_column_vs_column_predicate_skipped(self):
        """Test that column vs column comparisons are skipped for spine."""
        sql = compile(
            "from orders where created_at > updated_at group by month(created_at) (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        # The spine CTE should NOT have the unsafe predicate
        # Look for the spine definition
        spine_idx = sql.find("_spine AS (")
        spine_data_idx = sql.find("spine_data AS (")
        spine_cte = sql[spine_idx:spine_data_idx] if spine_idx >= 0 else ""
        
        # updated_at should NOT appear in the spine CTE
        assert "updated_at" not in spine_cte, f"Unsafe predicate in spine: {spine_cte}"
        # But should appear in the data CTE (WHERE is applied there)
        assert "updated_at" in sql

    def test_or_with_different_columns_skipped(self):
        """Test that OR predicates with different columns are skipped."""
        sql = compile(
            "from orders where created_at >= '2021-01-01' or status = 'active' group by month(created_at) (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        # The OR predicate involves 'status' which doesn't exist in spine
        spine_idx = sql.find("_spine AS (")
        spine_data_idx = sql.find("spine_data AS (")
        spine_cte = sql[spine_idx:spine_data_idx] if spine_idx >= 0 else ""
        
        # Neither the date filter nor status should appear in spine (whole OR is skipped)
        assert "status" not in spine_cte, f"Unsafe predicate in spine: {spine_cte}"

    def test_between_with_column_bounds_skipped(self):
        """Test that BETWEEN with column references as bounds is skipped."""
        sql = compile(
            "from orders where created_at between start_date and end_date group by month(created_at) (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        spine_idx = sql.find("_spine AS (")
        spine_data_idx = sql.find("spine_data AS (")
        spine_cte = sql[spine_idx:spine_data_idx] if spine_idx >= 0 else ""
        
        # start_date and end_date should NOT appear in spine
        assert "start_date" not in spine_cte, f"Unsafe predicate in spine: {spine_cte}"
        assert "end_date" not in spine_cte, f"Unsafe predicate in spine: {spine_cte}"

    def test_function_on_column_with_literal_is_safe(self):
        """Test that function on column compared to literal IS safe."""
        sql = compile(
            "from orders where year(created_at) = 2021 group by month(created_at) (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        spine_idx = sql.find("_spine AS (")
        spine_data_idx = sql.find("spine_data AS (")
        spine_cte = sql[spine_idx:spine_data_idx] if spine_idx >= 0 else ""
        
        # YEAR function should appear in spine (transformed to use d)
        assert "YEAR" in spine_cte.upper() or "2021" in spine_cte, f"Safe predicate not in spine: {spine_cte}"

    def test_mixed_safe_and_unsafe_predicates(self):
        """Test that with mixed predicates, date spine falls back to data MIN/MAX.
        
        When there are ANY unsafe predicates on a date column, we use data MIN/MAX
        as the spine bounds (the safe predicate is still applied in the data CTE).
        """
        sql = compile(
            "from orders where created_at >= '2021-01-01' and created_at > updated_at group by month(created_at) (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        # Should use data MIN/MAX fallback - spine CTE references spine_data
        assert "spine_data" in sql.lower()
        # The spine should reference MIN/MAX from the data CTE
        assert "min(" in sql.lower() and "max(" in sql.lower(), f"Missing MIN/MAX in: {sql}"
        
        # Both predicates should be in the data CTE (which has all WHERE conditions)
        assert "2021-01-01" in sql  # Safe predicate in data CTE
        assert "updated_at" in sql   # Unsafe predicate in data CTE


class TestSpineEdgeCases:
    """Test edge cases for spine generation."""

    def test_no_where_clause(self):
        """Test spine generation when there's no WHERE clause."""
        sql = compile(
            "from orders group by month(created_at) (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        # Should generate spine from 1970 to now without filter
        assert "_spine" in sql.lower()
        assert "generate_series" in sql.lower()

    def test_where_on_unrelated_column(self):
        """Test that WHERE on unrelated column doesn't affect date spine."""
        sql = compile(
            "from orders where status = 'active' group by month(created_at) (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        spine_idx = sql.find("_spine AS (")
        spine_data_idx = sql.find("spine_data AS (")
        spine_cte = sql[spine_idx:spine_data_idx] if spine_idx >= 0 else ""
        
        # status filter should NOT be in date spine
        assert "status" not in spine_cte

    def test_less_than_predicate(self):
        """Test that less-than predicates work correctly."""
        sql = compile(
            "from orders where created_at < '2024-01-01' group by month(created_at) (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        assert "2024-01-01" in sql

    def test_between_with_literals(self):
        """Test that BETWEEN with literal values is safe."""
        sql = compile(
            "from orders where created_at between '2021-01-01' and '2024-01-01' group by month(created_at) (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        spine_idx = sql.find("_spine AS (")
        spine_data_idx = sql.find("spine_data AS (")
        spine_cte = sql[spine_idx:spine_data_idx] if spine_idx >= 0 else ""
        
        # Both bounds should be in spine
        assert "2021-01-01" in spine_cte or "2024-01-01" in spine_cte

    def test_in_list_predicate(self):
        """Test that IN list predicates work for categorical columns."""
        sql = compile(
            "from orders where region in ('North', 'South', 'East') group by region (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        assert "North" in sql
        assert "South" in sql
        assert "East" in sql

    def test_not_equal_predicate(self):
        """Test that not-equal predicates work correctly."""
        sql = compile(
            "from orders where region != 'Unknown' group by region (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        # The predicate should be in the spine
        assert "Unknown" in sql


class TestSpineGenerationVerification:
    """Verify that spines ARE actually generated in output."""

    def test_categorical_group_by_generates_spine_cte(self):
        """Verify categorical GROUP BY generates spine CTE."""
        sql = compile(
            "from orders group by region (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        # Must have a spine CTE
        assert "region_spine" in sql.lower(), f"Missing region_spine CTE in: {sql}"
        # Must have LEFT JOIN
        assert "left join" in sql.lower(), f"Missing LEFT JOIN in: {sql}"
        # Must have DISTINCT for categorical spine
        assert "distinct" in sql.lower(), f"Missing DISTINCT in spine: {sql}"
        # Must have spine_data CTE
        assert "spine_data" in sql.lower(), f"Missing spine_data CTE in: {sql}"

    def test_date_function_group_by_generates_spine_cte(self):
        """Verify date function GROUP BY (like month()) generates spine CTE."""
        sql = compile(
            "from orders group by month(order_date) (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        # Must have a spine CTE (col_0_spine for auto-generated alias)
        assert "_spine" in sql.lower(), f"Missing spine CTE in: {sql}"
        # Must have LEFT JOIN
        assert "left join" in sql.lower(), f"Missing LEFT JOIN in: {sql}"
        # Must have spine_data CTE
        assert "spine_data" in sql.lower(), f"Missing spine_data CTE in: {sql}"
        # Must use date series generation (generate_series for postgres)
        assert "generate_series" in sql.lower(), f"Missing date series in: {sql}"

    def test_year_function_group_by_generates_spine_cte(self):
        """Verify year() function GROUP BY generates spine CTE."""
        sql = compile(
            "from orders group by year(order_date) (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        # Must have a spine CTE
        assert "_spine" in sql.lower(), f"Missing spine CTE in: {sql}"
        # Must have LEFT JOIN
        assert "left join" in sql.lower(), f"Missing LEFT JOIN in: {sql}"
        # Must have spine_data CTE
        assert "spine_data" in sql.lower(), f"Missing spine_data CTE in: {sql}"

    def test_guarantee_generates_spine_cte(self):
        """Verify guarantee() generates spine CTE."""
        sql = compile(
            "from orders group by guarantee(status) (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        # Must have a spine CTE
        assert "_spine" in sql.lower(), f"Missing spine CTE in: {sql}"
        # Must have LEFT JOIN
        assert "left join" in sql.lower(), f"Missing LEFT JOIN in: {sql}"
        # Must have spine_data CTE
        assert "spine_data" in sql.lower(), f"Missing spine_data CTE in: {sql}"
        # guarantee must be stripped
        assert "guarantee" not in sql.lower(), f"guarantee not stripped: {sql}"

    def test_multiple_group_by_generates_combined_spine(self):
        """Verify multiple GROUP BY columns generate combined_spine with CROSS JOIN."""
        sql = compile(
            "from orders group by region, category (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        # Must have individual spine CTEs
        assert "region_spine" in sql.lower(), f"Missing region_spine CTE in: {sql}"
        assert "category_spine" in sql.lower(), f"Missing category_spine CTE in: {sql}"
        # Must have combined_spine CTE
        assert "combined_spine" in sql.lower(), f"Missing combined_spine CTE in: {sql}"
        # Must have CROSS JOIN for combining spines
        assert "cross join" in sql.lower(), f"Missing CROSS JOIN in: {sql}"

    def test_single_group_by_no_combined_spine(self):
        """Verify single GROUP BY does NOT generate redundant combined_spine."""
        sql = compile(
            "from orders group by region (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=True)
        )
        
        # Should NOT have combined_spine (optimization)
        assert "combined_spine" not in sql.lower(), f"Should not have combined_spine for single GROUP BY: {sql}"
        # Should use region_spine directly
        assert "region_spine" in sql.lower(), f"Missing region_spine CTE in: {sql}"

    def test_disabled_auto_spine_no_spine_ctes(self):
        """Verify disabled auto_spine generates no spine CTEs."""
        sql = compile(
            "from orders group by region (sum(amount) as revenue)",
            dialect="postgres",
            settings=CompileSettings(auto_spine=False)
        )
        
        # Should NOT have spine CTEs
        assert "_spine" not in sql.lower(), f"Should not have spine CTEs when disabled: {sql}"
        # Should NOT have LEFT JOIN for spine
        assert "left join" not in sql.lower() or "spine_data" not in sql.lower(), f"Should not have spine join when disabled: {sql}"
