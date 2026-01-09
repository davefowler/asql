"""Tests for pivot and unpivot syntax in ASQL.

Pivot syntax:
- pivot agg(col) by pivot_col values ('a', 'b') → native PIVOT or CASE/WHEN fallback
- pivot agg(col) by pivot_col → dynamic pivot (dialect-specific)

Unpivot syntax:
- unpivot col1, col2, col3 into name_col, value_col → UNION ALL of columns
"""

from tests.validator import ASQLValidator, ASQLCompilationError


class TestPivotWithValues(ASQLValidator):
    """Test pivot with explicit values (most portable)."""
    
    def test_pivot_native_duckdb(self) -> None:
        """DuckDB uses native PIVOT syntax."""
        self.validate_contains(
            "from sales pivot sum(amount) by category values ('A', 'B')",
            "PIVOT",
            dialect="duckdb"
        )
    
    def test_pivot_native_snowflake(self) -> None:
        """Snowflake uses native PIVOT syntax."""
        self.validate_contains(
            "from sales pivot sum(amount) by category values ('A', 'B')",
            "PIVOT",
            dialect="snowflake"
        )
    
    def test_pivot_native_bigquery(self) -> None:
        """BigQuery uses native PIVOT syntax."""
        self.validate_contains(
            "from sales pivot sum(amount) by category values ('A', 'B')",
            "PIVOT",
            dialect="bigquery"
        )
    
    def test_pivot_fallback_postgres(self) -> None:
        """PostgreSQL uses CASE/WHEN fallback."""
        self.validate_contains(
            "from sales pivot sum(amount) by category values ('A', 'B')",
            "CASE WHEN",
            dialect="postgres"
        )
    
    def test_pivot_fallback_mysql(self) -> None:
        """MySQL uses CASE/WHEN fallback."""
        self.validate_contains(
            "from sales pivot sum(amount) by category values ('A', 'B')",
            "CASE WHEN",
            dialect="mysql"
        )
    
    def test_pivot_fallback_sqlite(self) -> None:
        """SQLite uses CASE/WHEN fallback."""
        self.validate_contains(
            "from sales pivot sum(amount) by category values ('A', 'B')",
            "CASE WHEN",
            dialect="sqlite"
        )


class TestDynamicPivot(ASQLValidator):
    """Test dynamic pivot (without explicit values)."""
    
    def test_dynamic_pivot_duckdb(self) -> None:
        """DuckDB supports dynamic pivot natively."""
        self.validate_contains(
            "from sales pivot sum(amount) by category",
            "PIVOT",
            dialect="duckdb"
        )
    
    def test_dynamic_pivot_snowflake(self) -> None:
        """Snowflake supports dynamic pivot natively."""
        self.validate_contains(
            "from sales pivot sum(amount) by category",
            "PIVOT",
            dialect="snowflake"
        )
    
    def test_dynamic_pivot_error_postgres(self) -> None:
        """PostgreSQL raises error for dynamic pivot."""
        self.validate_error(
            "from sales pivot sum(amount) by category",
            ASQLCompilationError,
            dialect="postgres",
            error_contains="Dynamic pivot"
        )
    
    def test_dynamic_pivot_error_mysql(self) -> None:
        """MySQL raises error for dynamic pivot."""
        self.validate_error(
            "from sales pivot sum(amount) by category",
            ASQLCompilationError,
            dialect="mysql",
            error_contains="Dynamic pivot"
        )


class TestUnpivot(ASQLValidator):
    """Test unpivot syntax."""
    
    def test_unpivot_basic(self) -> None:
        """unpivot cols into name, value creates UNION ALL."""
        self.validate_contains(
            "from metrics unpivot jan, feb, mar into month, value",
            "UNION ALL",
            dialect="postgres"
        )
    
    def test_unpivot_two_columns(self) -> None:
        """Unpivot with two columns."""
        self.validate_contains(
            "from data unpivot col_a, col_b into name, val",
            "UNION ALL",
            dialect="postgres"
        )
    
    def test_unpivot_creates_subquery(self) -> None:
        """Unpivot wraps result in subquery."""
        self.validate_contains(
            "from metrics unpivot jan, feb into month, value",
            "__unpivot__",
            dialect="postgres"
        )


class TestPivotWithGroupBy(ASQLValidator):
    """Test pivot combined with GROUP BY."""
    
    def test_pivot_with_group_by(self) -> None:
        """Pivot with explicit GROUP BY."""
        self.validate_contains(
            "from sales pivot sum(amount) by category values ('X', 'Y') group by region",
            "GROUP BY",
            dialect="postgres"
        )
