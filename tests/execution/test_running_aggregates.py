"""Execution tests for running/rolling window aggregates.

These assert the actual cumulative numbers against a DuckDB run, using rows that
are inserted OUT of natural order. That is the only way to catch the bug where the
window frame carried no ORDER BY: a substring check for "OVER"/"AVG" passes on the
broken output, but the numbers are wrong.
"""

from typing import Any

import pytest

from asql.errors import ASQLCompilationError

from ..fixtures import transpile

# Rows deliberately inserted out of date order so an unordered window frame
# produces visibly wrong cumulative numbers.
_ROWS = [("2024-01-03", 30), ("2024-01-01", 10), ("2024-01-02", 20)]


@pytest.fixture
def txns() -> Any:
    import duckdb

    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE txns (d DATE, amount INT)")
    conn.executemany("INSERT INTO txns VALUES (?, ?)", _ROWS)
    yield conn
    conn.close()


def test_running_avg_uses_query_order(txns: Any) -> None:
    sql = transpile("from txns order by d select d, amount, running_avg(amount) as ra")
    rows = txns.execute(sql).fetchall()
    # ordered by date: (10), (10+20)/2=15, (10+20+30)/3=20
    assert [r[2] for r in rows] == [10.0, 15.0, 20.0]


def test_running_sum_uses_query_order(txns: Any) -> None:
    sql = transpile("from txns order by d select d, amount, running_sum(amount) as rs")
    rows = txns.execute(sql).fetchall()
    assert [r[2] for r in rows] == [10, 30, 60]


def test_rolling_avg_uses_query_order(txns: Any) -> None:
    sql = transpile(
        "from txns order by d select d, amount, rolling_avg(amount, 2) as ra2"
    )
    rows = txns.execute(sql).fetchall()
    # 2-row trailing avg over ordered rows: 10, (10+20)/2=15, (20+30)/2=25
    assert [r[2] for r in rows] == [10.0, 15.0, 25.0]


def test_running_avg_respects_group_by_grain(txns: Any) -> None:
    txns.execute("INSERT INTO txns VALUES ('2024-01-01', 5), ('2024-02-15', 100)")
    sql = transpile(
        """
        from txns
          group by month(d) as month (
            sum(amount) as revenue,
            running_avg(sum(amount)) as ra
          )
          order by month
        """
    )
    rows = txns.execute(sql).fetchall()
    # month grain: Jan revenue = 30+10+20+5 = 65, Feb revenue = 100
    # running avg over months: 65, (65+100)/2 = 82.5
    assert [r[2] for r in rows] == [65.0, 82.5]


def test_running_avg_without_order_by_raises() -> None:
    with pytest.raises(ASQLCompilationError):
        transpile("from txns select d, running_avg(amount) as ra")


def test_explicit_over_partition_single_over(txns: Any) -> None:
    txns.execute("ALTER TABLE txns ADD COLUMN grp TEXT")
    txns.execute("UPDATE txns SET grp = 'a'")
    txns.execute(
        "INSERT INTO txns VALUES ('2024-01-01', 100, 'b'), ('2024-01-02', 200, 'b')"
    )
    sql = transpile(
        "from txns select grp, d, running_sum(amount) over (partition by grp order by d) as cum"
    )
    # Exactly one window: no nested `OVER (...) OVER (...)`.
    assert sql.upper().count("OVER") == 1
    txns.execute(sql).fetchall()  # must not raise


def test_explicit_over_partition_only_inherits_query_order(txns: Any) -> None:
    # `over (partition by grp)` with no order in the OVER must still get an ordering,
    # inherited from the query — else the per-partition running sum is over arbitrary order.
    txns.execute("ALTER TABLE txns ADD COLUMN grp TEXT")
    txns.execute("UPDATE txns SET grp = 'a'")
    sql = transpile(
        "from txns order by d select grp, d, running_sum(amount) over (partition by grp) as cum"
    )
    assert "OVER (PARTITION BY GRP ORDER BY D" in sql.upper()
    rows = txns.execute(sql).fetchall()
    # group 'a' ordered by date: 10, 30, 60
    assert [r[2] for r in rows] == [10, 30, 60]


def test_explicit_over_partition_only_without_order_raises() -> None:
    # No ordering anywhere (neither OVER nor query) — a running total is undefined.
    with pytest.raises(ASQLCompilationError):
        transpile(
            "from txns select grp, running_sum(amount) over (partition by grp) as cum"
        )
