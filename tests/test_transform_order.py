"""Transform ordering and settings isolation (audit C3, C6, C10, C11, C12)."""

from __future__ import annotations

import duckdb
import sqlglot
from sqlglot import exp

import asql
from asql.dialect import ASQL

from .fixtures import transpile


def _run_as_duckdb(con: duckdb.DuckDBPyConnection, sql: str, dialect: str):
    return con.sql(sqlglot.transpile(sql, read=dialect, write="duckdb")[0]).fetchall()


# C3 ---------------------------------------------------------------------------
def test_categorical_spine_count_compiles_off_duckdb() -> None:
    con = duckdb.connect()
    con.sql(
        "create table tickets as select * from (values ('open'), ('open'), ('done')) "
        "t(status)"
    )
    sql = asql.transpile(
        "from tickets spine by status (count(*) as ticket_count)", write="postgres"
    )[0]
    assert "_alias" not in sql  # no alias-reuse chain was triggered
    assert sorted(_run_as_duckdb(con, sql, "postgres")) == [("done", 1), ("open", 2)]


# C6 ---------------------------------------------------------------------------
def test_aliased_spine_key_still_builds_a_spine() -> None:
    for query in (
        "from orders group by spine(month(order_date)) as m (sum(amount) as s)",
        "from orders spine by month(order_date) as m (sum(amount) as s)",
    ):
        sql = transpile(query)
        assert "SPINE(" not in sql
        assert "GENERATE_SERIES" in sql
        assert " AS m" in sql


# C12 --------------------------------------------------------------------------
def test_running_window_resolves_order_by_alias() -> None:
    sql = transpile("from t select x, x * 2 as dbl, running_sum(x) as rs order by dbl")
    window = sqlglot.parse_one(sql, read="duckdb").find(exp.Window)
    assert window is not None
    assert window.args["order"].expressions[0].this.sql() == "x * 2"


def test_running_window_cannot_order_by_itself() -> None:
    import pytest

    from asql.errors import ASQLCompilationError

    with pytest.raises(ASQLCompilationError, match="itself"):
        transpile("from t select x, running_sum(x) as rs order by rs")


# C10 --------------------------------------------------------------------------
def test_inline_set_reaches_the_compile_stage_without_kwargs() -> None:
    sql = asql.transpile(
        "SET include_transpilation_comments = false;\n"
        "from orders where d >= @2024-01-01 and d < @2024-03-01 "
        "spine by month(d) (sum(amount) as s)"
    )[0]
    assert "Date spine" not in sql


def test_inline_set_passthrough_comments_without_kwargs() -> None:
    sql = asql.transpile(
        "SET passthrough_comments = false;\n-- a comment\nfrom orders where x = 1"
    )[0]
    assert "a comment" not in sql


# C11 --------------------------------------------------------------------------
def test_a_caller_dialect_is_not_mutated() -> None:
    read = ASQL()
    before = dict(read.settings)
    asql.transpile("SET week_start = sunday; from users", read=read)
    asql.transpile(
        "from users", read=read, schema={"tables": {"users": {"columns": ["id"]}}}
    )
    assert read.settings == before
    sql = asql.transpile("from t group by week(d) ( # as n )", read=read)[0]
    assert "INTERVAL" not in sql  # Monday weeks: no Sunday shift
