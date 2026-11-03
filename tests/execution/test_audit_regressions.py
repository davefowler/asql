"""Wrong-result findings from ai_notes/audit-2026-10-21.md, executed on DuckDB.

Each test compiles ASQL for the dialect under test, then runs the DuckDB
spelling of the same shape against small in-memory tables. For Postgres the
compiled SQL is re-read by sqlglot and emitted as DuckDB SQL, so the CTE chain
alias_reuse builds for non-DuckDB dialects is what gets executed.
"""

from __future__ import annotations

import datetime as dt

import duckdb
import pytest
import sqlglot

import asql


def _run(con: duckdb.DuckDBPyConnection, query: str, dialect: str = "duckdb", **kw):
    sql = asql.transpile(query, write=dialect, **kw)[0]
    if dialect != "duckdb":
        sql = sqlglot.transpile(sql, read=dialect, write="duckdb")[0]
    return con.sql(sql).fetchall()


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.sql(
        "create table orders as select * from (values "
        "(date '2024-01-03', 10), (date '2024-01-10', 20), (date '2024-01-24', 5)"
        ") t(d, amount)"
    )
    con.sql("create table t as select * from (values (1), (2), (3)) t(x)")
    con.sql(
        "create table g as select * from (values (1, 'a', 10), (2, 'a', 20), "
        "(3, 'b', 30)) t(x, a, v)"
    )
    con.sql(
        "create table o as select * from (values ('a', 1), (NULL, 2), "
        "('unknown', 3)) t(region, amount)"
    )
    return con


# C1 ---------------------------------------------------------------------------
def test_sunday_week_spine_joins_on_sunday_weeks(con) -> None:
    rows = _run(
        con,
        "from orders where d >= @2024-01-01 and d < @2024-02-01 "
        "spine by week(d) (sum(amount) as rev)",
        week_start="sunday",
    )
    by_week = {d.date() if isinstance(d, dt.datetime) else d: rev for d, rev in rows}
    assert by_week[dt.date(2023, 12, 31)] == 10
    assert by_week[dt.date(2024, 1, 7)] == 20
    assert by_week[dt.date(2024, 1, 14)] is None  # gap, filled
    assert by_week[dt.date(2024, 1, 21)] == 5


# C2 ---------------------------------------------------------------------------
def test_alias_chain_filters_before_the_window(con) -> None:
    rows = _run(
        con,
        "from t where x > 1 select row_number() over (order by x) as rn, rn * 2 as d",
        "postgres",
    )
    assert rows == [(1, 2), (2, 4)]


def test_alias_chain_keeps_group_by_and_having(con) -> None:
    rows = _run(
        con,
        "from g where x > 1 group by a (sum(v) as s, s * 2 as d) having s > 25",
        "postgres",
    )
    assert rows == [("b", 30, 60)]


# C5 ---------------------------------------------------------------------------
def test_group_key_alias_shadowing_a_column_groups_by_the_expression(con) -> None:
    rows = _run(
        con,
        "from o group by coalesce(region, 'unknown') as region (sum(amount) as s)",
    )
    assert sorted(rows) == [("a", 1), ("unknown", 5)]
