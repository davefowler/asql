"""Tests for pivot and unpivot syntax in ASQL.

ASQL parses simplified pivot/unpivot syntax into SQLGlot's native exp.Pivot AST.
SQLGlot then generates dialect-specific SQL (or drops unsupported syntax).

Pivot syntax:
- pivot agg(col) by pivot_col values ('a', 'b') → exp.Pivot AST
- pivot agg(col) by pivot_col → dynamic pivot (no IN clause)

Unpivot syntax:
- unpivot col1, col2, col3 into name_col, value_col → exp.Pivot(unpivot=True)

Note: SQLGlot handles PIVOT generation for each dialect. Some dialects (postgres, mysql)
don't support PIVOT and SQLGlot will drop it with a warning. This is SQLGlot behavior,
not something ASQL attempts to fix with fallback transforms.
"""

from tests.validator import ASQLValidator


class TestPivotParsing(ASQLValidator):
    """Test that ASQL pivot syntax parses into valid SQLGlot PIVOT AST."""
    
    def test_pivot_native_duckdb(self) -> None:
        """DuckDB supports native PIVOT - verify output contains PIVOT."""
        self.validate_contains(
            "from sales pivot sum(amount) by category values ('A', 'B')",
            "PIVOT",
            dialect="duckdb"
        )
    
    def test_pivot_native_snowflake(self) -> None:
        """Snowflake supports native PIVOT."""
        self.validate_contains(
            "from sales pivot sum(amount) by category values ('A', 'B')",
            "PIVOT",
            dialect="snowflake"
        )
    
    def test_pivot_native_bigquery(self) -> None:
        """BigQuery supports native PIVOT."""
        self.validate_contains(
            "from sales pivot sum(amount) by category values ('A', 'B')",
            "PIVOT",
            dialect="bigquery"
        )
    
    def test_pivot_parses_for_postgres(self) -> None:
        """PostgreSQL: PIVOT parses but SQLGlot may not generate it.
        
        SQLGlot drops PIVOT for postgres (it doesn't support native PIVOT).
        This is expected SQLGlot behavior - we don't add a fallback transform.
        """
        # Just verify it compiles without error - validate_contains with no
        # substrings just checks compilation succeeds and returns the SQL
        self.validate_contains(
            "from sales pivot sum(amount) by category values ('A', 'B')",
            dialect="postgres"
        )
        # We don't assert specific output - SQLGlot handles (or drops) PIVOT


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


class TestUnpivot(ASQLValidator):
    """Test unpivot syntax."""
    
    def test_unpivot_native_duckdb(self) -> None:
        """DuckDB supports native UNPIVOT."""
        self.validate_contains(
            "from metrics unpivot jan, feb, mar into month, value",
            "UNPIVOT",
            dialect="duckdb"
        )
    
    def test_unpivot_native_snowflake(self) -> None:
        """Snowflake supports native UNPIVOT."""
        self.validate_contains(
            "from metrics unpivot jan, feb, mar into month, value",
            "UNPIVOT",
            dialect="snowflake"
        )


class TestPivotWithGroupBy(ASQLValidator):
    """Test pivot combined with GROUP BY."""
    
    def test_pivot_with_group_by_duckdb(self) -> None:
        """Pivot with GROUP BY on DuckDB (native PIVOT support)."""
        self.validate_contains(
            "from sales pivot sum(amount) by category values ('X', 'Y') group by region",
            "GROUP BY", "PIVOT",
            dialect="duckdb"
        )
