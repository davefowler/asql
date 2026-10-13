"""Tests for aggregate block syntax in ASQL.

Aggregate blocks provide a cleaner GROUP BY syntax:
- `group by col (agg1, agg2)` → SELECT col, agg1, agg2 GROUP BY col
"""

import pytest

from ..validator import ASQLValidator


class TestAggregateBlocks(ASQLValidator):
    """Test aggregate block syntax."""

    def test_simple_aggregate_block(self) -> None:
        """group by col (agg) becomes SELECT col, agg GROUP BY col."""
        self.validate_contains(
            "from sales group by region (sum(amount) as revenue)",
            "SELECT",
            "GROUP BY",
            "region",
            "SUM",
        )

    def test_multiple_aggregates(self) -> None:
        """Multiple aggregates in block."""
        self.validate_contains(
            "from sales group by region (sum(amount) as revenue, count(*) as cnt)",
            "SUM",
            "COUNT",
            "GROUP BY",
        )


class TestAggregateBlocksCrossDialect(ASQLValidator):
    """Cross-dialect aggregate block tests."""

    def test_aggregate_block_all_dialects(self) -> None:
        """Test aggregate blocks across all dialects."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite"]:
            self.validate_contains(
                "from sales group by region (sum(amount) as revenue)",
                "SUM",
                "GROUP BY",
                dialect=dialect,
            )


class TestAggregateBlockExecution:
    """Execute on DuckDB: steps after an aggregate block read the block's output."""

    @staticmethod
    def _conn():
        import duckdb

        conn = duckdb.connect(":memory:")
        conn.execute("CREATE TABLE orders (id INT, region VARCHAR, amount INT)")
        conn.execute(
            "INSERT INTO orders VALUES (1, 'east', 10), (2, 'east', 20), "
            "(3, 'west', 5), (4, 'north', 7)"
        )
        conn.execute("CREATE TABLE customers (id INT, cohort_key INT)")
        conn.execute("INSERT INTO customers VALUES (1, 1), (2, 1), (3, 2)")
        return conn

    def _rows(self, asql: str):
        from ..fixtures import transpile

        conn = self._conn()
        try:
            return conn.execute(transpile(asql, dialect="duckdb")).fetchall()
        finally:
            conn.close()

    def test_select_star_plus_window_after_block_keeps_aggregates(self) -> None:
        rows = self._rows(
            "from orders group by region ( sum(amount) as revenue ) "
            "select *, running_sum(revenue) over (order by region) as cum "
            "order by region"
        )
        assert rows == [("east", 30, 30), ("north", 7, 37), ("west", 5, 42)]

    def test_extend_after_block_reads_aggregates(self) -> None:
        rows = self._rows(
            "from orders group by region ( sum(amount) as revenue ) "
            "extend revenue * 2 as double_rev order by region"
        )
        assert rows == [("east", 30, 60), ("north", 7, 14), ("west", 5, 10)]

    def test_select_subset_after_block(self) -> None:
        rows = self._rows(
            "from orders group by region ( sum(amount) as revenue ) "
            "select region, revenue * 2 as doubled order by region"
        )
        assert rows == [("east", 60), ("north", 14), ("west", 10)]

    def test_where_after_block_filters_aggregates(self) -> None:
        rows = self._rows(
            "from orders group by region ( sum(amount) as revenue ) "
            "where revenue > 6 order by region"
        )
        assert rows == [("east", 30), ("north", 7)]

    def test_cohort_running_sum_after_joined_block(self) -> None:
        rows = self._rows(
            "from orders join customers on orders.id = customers.id "
            "group by customers.cohort_key as cohort ( sum(amount) as revenue ) "
            "select *, running_sum(revenue) over (partition by 1 order by cohort) "
            "as cumulative_rev order by cohort"
        )
        assert rows == [(1, 30, 30), (2, 5, 35)]


class TestAliasedShorthandExpansion:
    """`sum_amount as rev` expands to `SUM(amount) AS rev` (user alias wins)."""

    def test_aliased_underscore_shorthand_in_group_block(self) -> None:
        from ..fixtures import transpile

        sql = transpile("from t group by region ( sum_amount as rev )")
        assert "SUM(amount) AS rev" in sql
        assert "sum_amount" not in sql

    def test_aliased_underscore_shorthand_executes(self) -> None:
        import duckdb

        from ..fixtures import transpile

        conn = duckdb.connect(":memory:")
        conn.execute("CREATE TABLE t (region VARCHAR, amount INT)")
        conn.execute("INSERT INTO t VALUES ('a', 1), ('a', 2), ('b', 5)")
        sql = transpile(
            "from t group by region ( sum_amount as rev, avg_amount as mean ) "
            "order by region"
        )
        assert conn.execute(sql).fetchall() == [("a", 3, 1.5), ("b", 5, 5.0)]


class TestGroupByThenSelect:
    """Plain `group by k` (no block) followed by select stays a single grouped SELECT."""

    def test_group_by_then_select_executes(self) -> None:
        rows = TestAggregateBlockExecution()._rows(
            "from orders group by region select region, count(*) as n, "
            "sum(amount) as total order by region"
        )
        assert rows == [("east", 2, 30), ("north", 1, 7), ("west", 1, 5)]

    def test_reverse_translated_group_by_round_trips_and_executes(self) -> None:
        import asql

        sql = "SELECT region, COUNT(*) AS total FROM orders GROUP BY region"
        asql_query = asql.transpile(sql, read="duckdb", write="asql")[0]
        rows = TestAggregateBlockExecution()._rows(asql_query + " order by region")
        assert rows == [("east", 2), ("north", 1), ("west", 1)]


class TestStarOverrideAfterBlock:
    def test_override_block_column_after_unaliased_aggregate(self) -> None:
        rows = TestAggregateBlockExecution()._rows(
            "from orders group by region ( sum(amount) ) "
            "select *, sum_amount / 10 as sum_amount order by region"
        )
        assert rows == [("east", 3.0), ("north", 0.7), ("west", 0.5)]

    def test_override_block_column_after_aliased_aggregate(self) -> None:
        rows = TestAggregateBlockExecution()._rows(
            "from orders group by region ( sum(amount) as revenue ) "
            "select *, revenue * 2 as revenue order by region"
        )
        assert rows == [("east", 60), ("north", 14), ("west", 10)]

    def test_unknown_cte_projections_yield_no_known_columns(self) -> None:
        import sqlglot
        from sqlglot import exp

        from asql.dialect.parser import ASQLParser

        def known(sql: str) -> set[str] | None:
            query = sqlglot.parse_one(sql)
            assert isinstance(query, exp.Query)
            return ASQLParser._pipe_cte_output_columns(query)

        assert (
            known("WITH c AS (SELECT a FROM x UNION SELECT a FROM y) SELECT * FROM c")
            is None
        )
        assert known("WITH c AS (SELECT t.* FROM t) SELECT * FROM c") is None
        assert known("WITH c AS (SELECT SUM(a) FROM t) SELECT * FROM c") is None
        assert known("WITH c AS (SELECT a, SUM(b) AS s FROM t) SELECT * FROM c") == {
            "a",
            "s",
        }


class TestBareGroupByStepRules:
    """After a bare `group by k` only `select` is meaningful; other steps must say so."""

    @staticmethod
    def _compile(asql: str) -> str:
        from ..fixtures import transpile

        return transpile(asql, dialect="duckdb")

    @pytest.mark.parametrize(
        "asql",
        [
            "from orders group by region where amount > 5 select region",
            "from orders group by region join customers on orders.id = customers.id "
            "select region",
            "from orders group by region extend 1 as one select region",
            "from orders group by a group by b ( # as n )",
        ],
    )
    def test_non_select_step_after_bare_group_by_raises(self, asql: str) -> None:
        from asql.errors import ASQLCompilationError

        with pytest.raises(ASQLCompilationError, match="aggregate block or a select"):
            self._compile(asql)

    def test_group_by_after_aggregate_block_closes_the_block(self) -> None:
        rows = TestAggregateBlockExecution()._rows(
            "from orders group by region ( sum(amount) as revenue ) "
            "group by revenue ( # as n ) order by revenue"
        )
        assert rows == [(5, 1), (7, 1), (30, 1)]

    def test_where_after_bare_group_by_select_wraps(self) -> None:
        rows = TestAggregateBlockExecution()._rows(
            "from orders group by region select region, sum(amount) as total "
            "where total > 6 order by region"
        )
        assert rows == [("east", 30), ("north", 7)]

    def test_select_then_group_by_closes_the_select_first(self) -> None:
        rows = TestAggregateBlockExecution()._rows(
            "from orders select region, amount * 2 as doubled "
            "group by region ( sum(doubled) as total ) order by region"
        )
        assert rows == [("east", 60), ("north", 14), ("west", 10)]
