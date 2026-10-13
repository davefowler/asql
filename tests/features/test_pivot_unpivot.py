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

from ..validator import ASQLValidator


class TestPivotParsing(ASQLValidator):
    """Test that ASQL pivot syntax parses into valid SQLGlot PIVOT AST."""

    def test_pivot_native_duckdb(self) -> None:
        """DuckDB supports native PIVOT - verify output contains PIVOT."""
        self.validate_contains(
            "from sales pivot sum(amount) by category values ('A', 'B')",
            "PIVOT",
            dialect="duckdb",
        )

    def test_pivot_native_snowflake(self) -> None:
        """Snowflake supports native PIVOT."""
        self.validate_contains(
            "from sales pivot sum(amount) by category values ('A', 'B')",
            "PIVOT",
            dialect="snowflake",
        )

    def test_pivot_native_bigquery(self) -> None:
        """BigQuery supports native PIVOT."""
        self.validate_contains(
            "from sales pivot sum(amount) by category values ('A', 'B')",
            "PIVOT",
            dialect="bigquery",
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
            dialect="postgres",
        )
        # We don't assert specific output - SQLGlot handles (or drops) PIVOT


class TestDynamicPivot(ASQLValidator):
    """Test dynamic pivot (without explicit values)."""

    def test_dynamic_pivot_duckdb(self) -> None:
        """DuckDB supports dynamic pivot natively."""
        self.validate_contains(
            "from sales pivot sum(amount) by category", "PIVOT", dialect="duckdb"
        )

    def test_dynamic_pivot_snowflake(self) -> None:
        """Snowflake supports dynamic pivot natively."""
        self.validate_contains(
            "from sales pivot sum(amount) by category", "PIVOT", dialect="snowflake"
        )


class TestUnpivot(ASQLValidator):
    """Test unpivot syntax."""

    def test_unpivot_native_duckdb(self) -> None:
        """DuckDB supports native UNPIVOT."""
        self.validate_contains(
            "from metrics unpivot jan, feb, mar into month, value",
            "UNPIVOT",
            dialect="duckdb",
        )

    def test_unpivot_native_snowflake(self) -> None:
        """Snowflake supports native UNPIVOT."""
        self.validate_contains(
            "from metrics unpivot jan, feb, mar into month, value",
            "UNPIVOT",
            dialect="snowflake",
        )


class TestPivotWithGroupBy(ASQLValidator):
    """Test pivot combined with GROUP BY."""

    def test_pivot_with_group_by_duckdb(self) -> None:
        """Pivot with GROUP BY: the key is projected beside the pivot columns."""
        self.validate_contains(
            "from sales pivot sum(amount) by category values ('X', 'Y') group by region",
            "SELECT region, amount, category FROM sales",
            "PIVOT",
            dialect="duckdb",
        )


class TestPivotGroupByExecution:
    """`pivot ... group by k` groups the pivot by k (docs/syntax/pivot-unpivot.md)."""

    def _run(self, asql: str):
        import duckdb

        from ..fixtures import transpile

        conn = duckdb.connect(":memory:")
        conn.execute(
            "CREATE TABLE orders (id INT, customer_id INT, status VARCHAR, amount INT)"
        )
        conn.execute(
            "INSERT INTO orders VALUES (1, 1, 'pending', 10), "
            "(2, 1, 'shipped', 20), (3, 1, 'pending', 5), (4, 2, 'delivered', 7)"
        )
        try:
            cur = conn.execute(transpile(asql, dialect="duckdb"))
            cols = [d[0] for d in cur.description]
            return cols, sorted(cur.fetchall(), key=lambda r: r[0])
        finally:
            conn.close()

    def test_pivot_group_by_groups_by_key_columns(self) -> None:
        cols, rows = self._run(
            "from orders pivot sum(amount) by status "
            'values ("pending", "shipped", "delivered") group by customer_id'
        )
        assert cols[0] == "customer_id"
        assert len(cols) == 4
        assert rows == [(1, 15, 20, None), (2, None, None, 7)]

    def test_pivot_group_by_does_not_emit_outer_group_by(self) -> None:
        from ..fixtures import transpile

        sql = transpile(
            "from orders pivot sum(amount) by status values ('a', 'b') "
            "group by customer_id",
            dialect="duckdb",
        )
        assert "GROUP BY" not in sql
        assert "PIVOT" in sql

    def test_pivot_group_by_expression_is_an_error(self) -> None:
        import pytest

        from asql.errors import ASQLCompilationError

        from ..fixtures import transpile

        with pytest.raises(ASQLCompilationError, match="pivot"):
            transpile(
                "from orders pivot sum(amount) by status values ('a') "
                "group by month(created_at)",
                dialect="duckdb",
            )

    def test_pivot_group_by_with_aggregate_block_is_an_error(self) -> None:
        import pytest

        from asql.errors import ASQLCompilationError

        from ..fixtures import transpile

        with pytest.raises(ASQLCompilationError, match="aggregate block"):
            transpile(
                "from orders pivot sum(amount) by status values ('a') "
                "group by customer_id (count(*) as n)",
                dialect="duckdb",
            )

    def test_pivot_group_by_with_select_list_is_an_error(self) -> None:
        import pytest

        from asql.errors import ASQLCompilationError

        from ..fixtures import transpile

        with pytest.raises(ASQLCompilationError, match="select list"):
            transpile(
                "from orders pivot sum(amount) by status values ('a') "
                "group by customer_id select customer_id",
                dialect="duckdb",
            )
