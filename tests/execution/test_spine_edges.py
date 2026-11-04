"""Lesser spine findings from ai_notes/audit-2026-10-21.md, executed on DuckDB."""

from __future__ import annotations

import duckdb
import pytest

import asql
from asql.errors import ASQLCompilationError


def _run(con: duckdb.DuckDBPyConnection, query: str, **kw):
    sql = asql.transpile(query, write="duckdb", **kw)[0]
    return con.sql(sql).fetchall()


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.sql(
        "create table tickets as select * from (values ('a'), (NULL), (NULL)) t(status)"
    )
    con.sql(
        "create table orders as select * from (values "
        "(timestamp '2024-01-03 01:30', 10), (timestamp '2024-01-03 04:10', 20), "
        "(timestamp '2024-03-24 00:00', 5)) t(ts, amount)"
    )
    return con


# C9 ---------------------------------------------------------------------------
def test_categorical_spine_counts_the_null_group(con) -> None:
    rows = _run(con, "from tickets spine by status (count(*) as n)")
    assert sorted(rows, key=lambda r: (r[0] is None, r[0])) == [("a", 1), (None, 2)]


# year(d), month(d) -------------------------------------------------------------
def test_two_date_spines_on_one_column_do_not_cross_join(con) -> None:
    rows = _run(
        con,
        "from orders where ts >= @2023-11-01 and ts < @2024-04-01 "
        "spine by year(ts), month(ts) (sum(amount) as rev)",
    )
    assert len(rows) == 5  # Nov 2023 .. Mar 2024, not 2 years x 5 months
    by_month = {(y.year, m.month): rev for y, m, rev in rows}
    assert by_month[(2023, 11)] is None
    assert by_month[(2024, 1)] == 30
    assert by_month[(2024, 2)] is None
    assert by_month[(2024, 3)] == 5
    assert {y.year for y, _, _ in rows} == {2023, 2024}


def test_week_and_month_spines_on_one_column_raise(con) -> None:
    with pytest.raises(ASQLCompilationError, match="week"):
        _run(con, "from orders spine by month(ts), week(ts) (sum(amount) as rev)")


def test_categorical_and_date_spines_still_cross_join(con) -> None:
    con.sql(
        "create table s as select * from (values "
        "(date '2024-01-03', 'a', 10), (date '2024-03-24', 'b', 5)) t(d, k, amount)"
    )
    rows = _run(
        con,
        "from s where d >= @2024-01-01 and d < @2024-04-01 "
        "spine by k, month(d) (sum(amount) as rev)",
    )
    assert len(rows) == 6


# spine by hour ----------------------------------------------------------------
def test_hour_spine_fills_missing_hours(con) -> None:
    rows = _run(
        con,
        "from orders where ts >= @2024-01-03 and ts < @2024-01-03T06:00:00 "
        "spine by hour(ts) (sum(amount) as rev)",
    )
    assert len(rows) == 6
    # Data bounds: every hour from the first row (Jan 3 01:00) to the last (Mar 24 00:00)
    assert len(_run(con, "from orders spine by hour(ts) (sum(amount) as rev)")) == 1944
    by_hour = {h.hour: rev for h, rev in rows}
    assert by_hour[1] == 10
    assert by_hour[2] is None
    assert by_hour[4] == 20


def test_timestamp_exclusive_bound_ends_the_spine_before_it(con) -> None:
    rows = _run(
        con,
        "from orders where ts >= @2024-01-01 and ts < @2024-03-01T00:00:00 "
        "spine by month(ts) (sum(amount) as rev)",
    )
    assert len(rows) == 2


# spine on a subquery FROM -----------------------------------------------------
def test_spine_on_a_subquery_source_still_fills_gaps(con) -> None:
    rows = _run(
        con,
        "from orders where ts >= @2024-01-01 and ts < @2024-04-01 "
        "select ts, amount * 2 as doubled "
        "spine by month(ts) (sum(doubled) as rev)",
    )
    assert len(rows) == 3
    assert sorted(r[1] for r in rows if r[1] is not None) == [10, 60]


def test_spine_after_a_join_stage_raises_or_fills(con) -> None:
    con.sql("create table regions as select * from (values (1, 'us')) t(id, name)")
    con.sql(
        "create table sales as select * from (values "
        "(date '2024-01-03', 1, 10), (date '2024-03-24', 1, 5)) t(d, region_id, amount)"
    )
    try:
        rows = _run(
            con,
            "from sales & regions on sales.region_id = regions.id "
            "where d >= @2024-01-01 and d < @2024-04-01 "
            "spine by month(d) (sum(amount) as rev)",
        )
    except ASQLCompilationError:
        return
    assert len(rows) == 3
