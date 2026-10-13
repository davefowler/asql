"""Tests for ASQL spine feature.

Spine provides explicit gap-filling for date truncation columns in GROUP BY,
ensuring all dates appear in results.

Usage:
    from orders spine by month(created_at) (sum(amount))
    from orders group by spine(month(created_at)), region (sum(amount))
"""

import pytest
import sqlglot

from asql.compiler.spine_helpers import (
    find_non_date_group_by_columns,
)

from .fixtures import transpile


class TestSpineBySyntax:
    """Test the 'spine by' syntax for explicit gap-filling."""

    def test_spine_by_basic(self):
        """Test basic spine by syntax."""
        asql = "from orders spine by month(created_at) (sum(amount))"
        sql = transpile(asql, dialect="duckdb")

        # Should generate spine CTE
        assert "spine" in sql.lower()
        assert "sum" in sql.lower() or "SUM" in sql

    def test_spine_by_with_where(self):
        """Test spine by with WHERE clause."""
        asql = """
        from orders
        where created_at >= @2024-01-01
        spine by month(created_at) (sum(amount))
        """
        sql = transpile(asql, dialect="duckdb")

        assert "spine" in sql.lower()

    def test_spine_by_multiple_aggs(self):
        """Test spine by with multiple aggregations."""
        asql = """
        from orders
        spine by month(created_at) (
            sum(amount) as revenue,
            count(*) as order_count
        )
        """
        sql = transpile(asql, dialect="duckdb")

        assert "spine" in sql.lower()
        assert "sum" in sql.lower() or "SUM" in sql
        assert "count" in sql.lower() or "COUNT" in sql


class TestSpineFunctionInGroupBy:
    """Test the spine() function in regular GROUP BY."""

    def test_spine_function_in_group_by(self):
        """Test spine() function wrapping a column in GROUP BY."""
        asql = "from orders group by spine(month(created_at)) (sum(amount))"
        sql = transpile(asql, dialect="duckdb")

        # Should generate spine CTE
        assert "spine" in sql.lower()

    def test_mixed_spine_and_regular_group_by(self):
        """Test mixing spine() with regular GROUP BY columns."""
        asql = """
        from orders
        group by spine(month(created_at)), region (
            sum(amount) as revenue
        )
        """
        sql = transpile(asql, dialect="duckdb")

        # Should generate spine CTE for date but not for region
        assert "spine" in sql.lower()
        assert "region" in sql.lower()


class TestGroupByWithoutSpine:
    """Test that regular GROUP BY doesn't add spine."""

    def test_group_by_no_spine(self):
        """Regular GROUP BY shouldn't add spine CTEs."""
        asql = "from orders group by month(created_at) (sum(amount))"
        sql = transpile(asql, dialect="duckdb")

        # Should NOT have spine CTE
        assert "_spine" not in sql.lower()

    def test_group_by_categorical(self):
        """Categorical GROUP BY shouldn't add spine."""
        asql = "from orders group by region (sum(amount))"
        sql = transpile(asql, dialect="duckdb")

        # Should NOT have spine CTE
        assert "_spine" not in sql.lower()


class TestMixedGroupByHandling:
    """Test detection of non-date columns in GROUP BY."""

    def test_find_non_date_columns_in_mixed_group_by(self):
        """Test finding non-date columns in mixed GROUP BY."""
        stmt = sqlglot.parse_one(
            "SELECT month(created_at) as m, status FROM orders GROUP BY month(created_at), status"
        )
        non_date_cols = find_non_date_group_by_columns(stmt)

        # Should find 'status' as a non-date column
        assert len(non_date_cols) == 1
        alias, _ = non_date_cols[0]
        assert alias == "status"

    def test_pure_date_group_by_no_non_date(self):
        """Test that pure date GROUP BY has no non-date columns."""
        stmt = sqlglot.parse_one(
            "SELECT month(created_at) as m FROM orders GROUP BY month(created_at)"
        )
        non_date_cols = find_non_date_group_by_columns(stmt)

        assert len(non_date_cols) == 0

    def test_only_non_date_group_by(self):
        """Test GROUP BY with only non-date columns."""
        stmt = sqlglot.parse_one(
            "SELECT region, status FROM orders GROUP BY region, status"
        )
        non_date_cols = find_non_date_group_by_columns(stmt)

        # Should find both as non-date columns
        assert len(non_date_cols) == 2

    def test_no_group_by(self):
        """Test query without GROUP BY returns empty."""
        stmt = sqlglot.parse_one("SELECT * FROM orders")
        non_date_cols = find_non_date_group_by_columns(stmt)

        assert len(non_date_cols) == 0


class TestSpineDialects:
    """Test spine generation for different dialects."""

    def test_spine_duckdb(self):
        """Test spine generation for DuckDB."""
        asql = "from orders spine by month(created_at) (sum(amount))"
        sql = transpile(asql, dialect="duckdb")

        assert "generate_series" in sql.lower() or "spine" in sql.lower()

    def test_spine_snowflake(self):
        """Test spine generation for Snowflake."""
        asql = """
        from orders
        where created_at >= @2024-01-01
        spine by month(created_at) (sum(amount))
        """
        sql = transpile(asql, dialect="snowflake")

        assert "spine" in sql.lower()

    def test_spine_postgres(self):
        """Test spine generation for PostgreSQL."""
        asql = """
        from orders
        where created_at >= @2024-01-01
        spine by month(created_at) (sum(amount))
        """
        sql = transpile(asql, dialect="postgres")

        # PostgreSQL should use generate_series
        assert "generate_series" in sql.lower() or "spine" in sql.lower()


class TestSpineWithDateFunctions:
    """Test spine with different date truncation functions."""

    def test_spine_with_year(self):
        """Test spine with year() truncation."""
        asql = "from orders spine by year(created_at) (sum(amount))"
        sql = transpile(asql, dialect="duckdb")

        assert "spine" in sql.lower()
        # Year should use INTERVAL '1 year'
        assert "year" in sql.lower()

    def test_spine_with_week(self):
        """Test spine with week() truncation."""
        asql = "from orders spine by week(created_at) (sum(amount))"
        sql = transpile(asql, dialect="duckdb")

        assert "spine" in sql.lower()

    def test_spine_with_day(self):
        """Test spine with day() truncation."""
        asql = """
        from orders
        where created_at >= @2024-01-01 and created_at < @2024-01-10
        spine by day(created_at) (sum(amount))
        """
        sql = transpile(asql, dialect="duckdb")

        assert "spine" in sql.lower()


class TestSpinePredicateHandling:
    """Test that WHERE predicates are properly used for spine bounds."""

    def test_spine_uses_where_dates(self):
        """Test that spine uses dates from WHERE clause for bounds."""
        asql = """
        from orders
        where created_at >= @2024-01-01 and created_at < @2024-04-01
        spine by month(created_at) (sum(amount))
        """
        sql = transpile(asql, dialect="duckdb")

        # Should contain the date bounds in the spine CTE
        assert "2024-01-01" in sql
        assert "2024-04-01" in sql or "2024-03-01" in sql

    def test_spine_without_where_uses_data_bounds(self):
        """Test that spine without WHERE uses MIN/MAX from data."""
        asql = "from orders spine by month(created_at) (sum(amount))"
        sql = transpile(asql, dialect="duckdb")

        # Should use subquery to get MIN/MAX if no explicit bounds
        # The spine CTE should exist even without WHERE
        assert "spine" in sql.lower()


class TestSpineEdgeCases:
    """Test edge cases and error handling for spine."""

    def test_spine_with_join(self):
        """Test spine with a JOIN clause."""
        asql = """
        from orders
        join customers on orders.customer_id = customers.id
        spine by month(created_at) (
            sum(amount) as total
        )
        """
        sql = transpile(asql, dialect="duckdb")

        assert "spine" in sql.lower()
        assert "join" in sql.lower()

    def test_multiple_spine_columns(self):
        """Test multiple spine columns in same GROUP BY."""
        asql = """
        from orders
        group by spine(month(created_at)), spine(category) (
            sum(amount)
        )
        """
        sql = transpile(asql, dialect="duckdb")

        # Should generate spine CTEs for both columns
        assert "spine" in sql.lower()

    def test_spine_with_complex_where(self):
        """Test spine with complex WHERE clause."""
        asql = """
        from orders
        where status = 'completed'
          and created_at >= @2024-01-01
          and created_at < @2024-04-01
        spine by month(created_at) (sum(amount))
        """
        sql = transpile(asql, dialect="duckdb")

        assert "spine" in sql.lower()
        assert "completed" in sql.lower()


class TestSpineExecution:
    """Execute spine SQL on DuckDB: the spine must actually fill the gaps."""

    @pytest.fixture
    def conn(self):
        import duckdb

        conn = duckdb.connect(":memory:")
        conn.execute(
            "CREATE TABLE orders (id INT, created_at DATE, region VARCHAR, amount INT)"
        )
        conn.execute(
            "INSERT INTO orders VALUES "
            "(1, '2024-01-15', 'east', 10), (2, '2024-01-20', 'west', 5), "
            "(3, '2024-02-10', 'east', 20), (4, '2024-04-30', 'east', 40)"
        )
        yield conn
        conn.close()

    def test_spine_by_fills_gap_month(self, conn):
        sql = transpile(
            "from orders spine by month(created_at) "
            "( sum(amount) as revenue ) order by 1",
            dialect="duckdb",
        )
        rows = conn.execute(sql).fetchall()
        assert [(str(r[0]), r[1]) for r in rows] == [
            ("2024-01-01", 15),
            ("2024-02-01", 20),
            ("2024-03-01", None),
            ("2024-04-01", 40),
        ]

    def test_spine_by_with_where_bounds_and_filter(self, conn):
        sql = transpile(
            "from orders where created_at >= @2024-01-01 and region = 'east' "
            "spine by month(created_at) ( sum(amount) as revenue ) order by 1",
            dialect="duckdb",
        )
        rows = conn.execute(sql).fetchall()
        assert [r[1] for r in rows] == [10, 20, None, 40]

    def test_spine_by_gap_start_mid_month_does_not_skip_month(self, conn):
        conn.execute(
            "DELETE FROM orders; INSERT INTO orders VALUES "
            "(1, '2024-01-31', 'east', 1), (2, '2024-03-05', 'east', 2)"
        )
        sql = transpile(
            "from orders spine by month(created_at) ( sum(amount) as revenue ) "
            "order by 1",
            dialect="duckdb",
        )
        rows = conn.execute(sql).fetchall()
        assert [(str(r[0]), r[1]) for r in rows] == [
            ("2024-01-01", 1),
            ("2024-02-01", None),
            ("2024-03-01", 2),
        ]

    def test_group_by_spine_function_form(self, conn):
        sql = transpile(
            "from orders where created_at >= @2024-01-01 "
            "group by spine(month(created_at)), region "
            "( sum_amount, # as order_count ) order by 1, 2",
            dialect="duckdb",
        )
        assert "SPINE(" not in sql.upper()
        rows = conn.execute(sql).fetchall()
        months = {str(r[0]) for r in rows}
        assert months == {"2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"}
        march = [r for r in rows if str(r[0]) == "2024-03-01"]
        assert march == [(march[0][0], None, None, 0)]
        jan_east = [r for r in rows if str(r[0]) == "2024-01-01" and r[1] == "east"]
        assert [(r[2], r[3]) for r in jan_east] == [(10, 1)]

    def test_spine_by_with_join_keeps_gap(self, conn):
        conn.execute("CREATE TABLE customers (id INT, name VARCHAR)")
        conn.execute("INSERT INTO customers VALUES (1, 'a'), (2, 'b'), (3, 'c')")
        sql = transpile(
            "from orders join customers on orders.id = customers.id "
            "spine by month(created_at) ( sum(amount) as revenue ) order by 1",
            dialect="duckdb",
        )
        rows = conn.execute(sql).fetchall()
        # April's only order has no customer, so it drops out of the inner join
        # but its month stays in the spine.
        assert [r[1] for r in rows] == [15, 20, None, None]

    def test_where_after_spine_block_filters_output(self, conn):
        sql = transpile(
            "from orders spine by month(created_at) ( sum(amount) as revenue ) "
            "where revenue > 0 order by 1",
            dialect="duckdb",
        )
        assert [r[1] for r in conn.execute(sql).fetchall()] == [15, 20, 40]

    @staticmethod
    def _months(conn, asql: str):
        rows = conn.execute(transpile(asql, dialect="duckdb")).fetchall()
        return [(str(r[0]), r[1]) for r in rows]

    def test_half_open_range_has_no_phantom_period(self, conn):
        got = self._months(
            conn,
            "from orders where created_at >= @2024-01-01 and created_at < @2024-04-01 "
            "spine by month(created_at) ( sum(amount) as revenue ) order by 1",
        )
        assert got == [
            ("2024-01-01", 15),
            ("2024-02-01", 20),
            ("2024-03-01", None),
        ]

    def test_inclusive_range_keeps_last_period(self, conn):
        got = self._months(
            conn,
            "from orders where created_at >= @2024-01-01 and created_at <= @2024-04-30 "
            "spine by month(created_at) ( sum(amount) as revenue ) order by 1",
        )
        assert [m for m, _ in got] == [
            "2024-01-01",
            "2024-02-01",
            "2024-03-01",
            "2024-04-01",
        ]

    def test_strict_lower_bound_is_not_shifted(self, conn):
        got = self._months(
            conn,
            "from orders where created_at > @2024-01-31 and created_at < @2024-04-01 "
            "spine by month(created_at) ( sum(amount) as revenue ) order by 1",
        )
        # A leading empty period is harmless; dropping a timestamp row is not.
        assert got == [("2024-01-01", None), ("2024-02-01", 20), ("2024-03-01", None)]

    def test_range_bounds_fill_tail_beyond_data(self, conn):
        got = self._months(
            conn,
            "from orders where created_at >= @2024-01-01 and created_at < @2024-07-01 "
            "spine by month(created_at) ( sum(amount) as revenue ) order by 1",
        )
        assert [m for m, _ in got][-2:] == ["2024-05-01", "2024-06-01"]

    def test_count_star_in_earlier_stage_is_untouched(self, conn):
        asql = (
            "from orders group by created_at, region ( # as n ) "
            "spine by month(created_at) ( sum(n) as total ) order by 1"
        )
        sql = transpile(asql, dialect="duckdb")
        assert "COUNT(*)" in sql
        rows = conn.execute(sql).fetchall()
        assert [(str(r[0]), r[1]) for r in rows] == [
            ("2024-01-01", 2),
            ("2024-02-01", 1),
            ("2024-03-01", None),
            ("2024-04-01", 1),
        ]

    def test_categorical_spine_keeps_output_name(self, conn):
        sql = transpile(
            "from orders spine by region ( sum(amount) as revenue ) order by region",
            dialect="duckdb",
        )
        cur = conn.execute(sql)
        assert [d[0] for d in cur.description] == ["region", "revenue"]
        assert cur.fetchall() == [("east", 70), ("west", 5)]

    def test_categorical_spine_keeps_null_key_rows(self, conn):
        conn.execute("INSERT INTO orders VALUES (9, '2024-02-02', NULL, 3)")
        sql = transpile(
            "from orders spine by region ( sum(amount) as revenue ) order by 1",
            dialect="duckdb",
        )
        got = dict(conn.execute(sql).fetchall())
        assert got == {"east": 70, "west": 5, None: 3}

    def test_strict_lower_bound_keeps_timestamp_rows(self, conn):
        conn.execute("CREATE TABLE ev (ts TIMESTAMP, amount INT)")
        conn.execute(
            "INSERT INTO ev VALUES ('2024-01-31 12:00:00', 7), ('2024-02-10', 3)"
        )
        sql = transpile(
            "from ev where ts > @2024-01-31 and ts < @2024-03-01 "
            "spine by month(ts) ( sum(amount) as total ) order by 1",
            dialect="duckdb",
        )
        got = [(str(r[0])[:10], r[1]) for r in conn.execute(sql).fetchall()]
        assert got == [("2024-01-01", 7), ("2024-02-01", 3)]

    def test_unaliased_expression_key_projection_uses_spine(self, conn):
        from asql.compiler.spine import transform_spine_expressions
        from asql.config import CompileSettings

        stmt = sqlglot.parse_one(
            "SELECT created_at + INTERVAL 1 DAY, SUM(amount) AS s FROM orders "
            "GROUP BY created_at + INTERVAL 1 DAY",
            dialect="duckdb",
        )
        from asql.expressions import Spine

        group = stmt.args["group"]
        group.set("expressions", [Spine(this=group.expressions[0].copy())])
        out = transform_spine_expressions(stmt, "duckdb", CompileSettings())
        sql = out.sql("duckdb")
        assert (
            out.args["expressions"][0]
            .sql("duckdb")
            .startswith("spine_col_0_spine.spine_col_0_key")
        )
        conn.execute(sql)


def test_bigquery_exclusive_upper_bound_is_a_plain_date_literal():
    sql = transpile(
        "from orders where created_at >= @2024-01-01 and created_at < @2024-04-01 "
        "spine by month(created_at) ( sum(amount) as revenue )",
        dialect="bigquery",
    )
    assert "GENERATE_DATE_ARRAY" in sql
    assert "'2024-03-31'" in sql
    assert "INTERVAL" not in sql.split("GENERATE_DATE_ARRAY")[1].split(")")[0]
