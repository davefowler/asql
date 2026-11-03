"""The parser must reject what it cannot parse rather than drop it.

Audit 2026-10-21, P1/P2/P-A1: tokens left over after a transform payload were
silently discarded, which turned typos and unsupported syntax into queries
with a different meaning.
"""

from __future__ import annotations

import pytest
import sqlglot
from sqlglot import exp

from asql.errors import ASQLCompilationError, ASQLSyntaxError

from .fixtures import transpile


@pytest.mark.parametrize(
    "query",
    [
        "from t where x = 1 foo bar baz",
        "from t select a, , b",
        "from t select a, b bogus tokens here order by a",
        "from t where x = 1 and",
        "from t select a +",
        "from t select a, order by a",
    ],
)
def test_leftover_tokens_raise(query: str) -> None:
    with pytest.raises(ASQLSyntaxError):
        transpile(query)


def test_when_result_can_be_a_binary_expression() -> None:
    sql = transpile('from t select when status is "a" then y + 1, otherwise 0 as z')
    assert sql == "SELECT CASE WHEN status = 'a' THEN y + 1 ELSE 0 END AS z FROM t"


def test_when_result_can_be_a_coalesce() -> None:
    sql = transpile("from t select when x then a ?? b, otherwise c as v")
    assert sql == "SELECT CASE WHEN x THEN COALESCE(a, b) ELSE c END AS v FROM t"


def test_when_branches_still_split_on_commas() -> None:
    sql = transpile(
        "from t select when n < 10 then n * 2, n < 100 then n * 3, otherwise n as v"
    )
    assert sql == (
        "SELECT CASE WHEN n < 10 THEN n * 2 WHEN n < 100 THEN n * 3 ELSE n END "
        "AS v FROM t"
    )


def test_over_column_partitions_the_window() -> None:
    """`over <col>` is ASQL shorthand for `over (partition by <col>)`."""
    sql = transpile(
        "from t select *, first(x order by y) over g as f, "
        "running_sum(v) over g / 2 as h order by y"
    )
    windows = list(sqlglot.parse_one(sql, read="duckdb").find_all(exp.Window))
    assert len(windows) == 2
    for window in windows:
        assert [c.name for c in window.args["partition_by"]] == ["g"]
        assert window.args.get("alias") is None
    assert "AS f" in sql and "AS h" in sql


def test_first_with_explicit_over_merges_into_its_window() -> None:
    sql = transpile("from t select first(x order by y) over (partition by a) as f")
    assert sql == (
        "SELECT FIRST_VALUE(x) OVER (PARTITION BY a ORDER BY y NULLS FIRST) AS f FROM t"
    )


def test_over_column_on_a_partitioned_window_is_an_error() -> None:
    with pytest.raises(ASQLCompilationError, match="already has one"):
        transpile("from t select sum(x) over (partition by a) over b as s")


def test_sql_named_window_is_left_alone() -> None:
    sql = transpile("SELECT SUM(x) OVER w AS s FROM t WINDOW w AS (PARTITION BY a)")
    assert "OVER w" in sql
    assert "WINDOW w AS (PARTITION BY a)" in sql


def test_rename_directly_after_select_parses() -> None:
    sql = transpile("from t select a, b rename b as c")
    assert "b AS c" in sql
