"""A step must read the output of the step before it (audit P3, P7, P8, P12)."""

from __future__ import annotations

import pytest
import sqlglot
from sqlglot import exp

from .fixtures import transpile


def _final_select(sql: str) -> exp.Select:
    tree = sqlglot.parse_one(sql, read="duckdb")
    assert isinstance(tree, exp.Select)
    return tree


# P3: underscore shorthand must not re-aggregate an earlier stage's output ----
def test_shorthand_does_not_expand_an_earlier_stage_alias() -> None:
    sql = transpile(
        'from users where status = "active" group by country ( # as total_users ) '
        "select country, total_users stash as revenue\n\nfrom revenue order by -total_users"
    )
    assert "SUM(users)" not in sql
    assert "SELECT country, total_users FROM __tmp1" in sql


def test_shorthand_does_not_expand_a_stash_output_column() -> None:
    sql = transpile(
        "from orders group by customer_id ( sum(amount) as total_spent ) stash as s\n\n"
        "from s where total_spent > 100 select customer_id, total_spent"
    )
    assert "SUM(spent)" not in sql
    assert sql.endswith(
        "SELECT customer_id, total_spent FROM s WHERE total_spent > 100"
    )


def test_shorthand_still_expands_over_a_base_table() -> None:
    assert transpile("from t group by a ( sum_amount )") == (
        "SELECT a, SUM(amount) AS sum_amount FROM t GROUP BY a"
    )


# P12: `select *, x as y` only excludes y when y is being overridden ----------
def test_star_plus_new_column_does_not_exclude_it() -> None:
    assert transpile("from users select *, 1 as flag") == (
        "SELECT *, 1 AS flag FROM users"
    )


def test_star_plus_override_still_excludes_the_column() -> None:
    assert transpile("from users select *, upper(name) as name") == (
        "SELECT * EXCLUDE (name), UPPER(name) AS name FROM users"
    )


def test_star_plus_new_column_compiles_on_postgres_without_a_schema() -> None:
    assert transpile("from users select *, 1 as flag", dialect="postgres") == (
        "SELECT *, 1 AS flag FROM users"
    )


# P7: steps after limit/offset read the limited rows --------------------------
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "from orders limit 10 where x = 1",
            "WITH __tmp1 AS (SELECT * FROM orders LIMIT 10) "
            "SELECT * FROM __tmp1 WHERE x = 1",
        ),
        (
            "from t limit 10 group by x ( # as n )",
            "WITH __tmp1 AS (SELECT * FROM t LIMIT 10) "
            "SELECT x, COUNT(*) AS n FROM __tmp1 GROUP BY x",
        ),
        (
            "from t limit 10 order by x",
            "WITH __tmp1 AS (SELECT * FROM t LIMIT 10) "
            "SELECT * FROM __tmp1 ORDER BY x NULLS FIRST",
        ),
        (
            "from t order by x limit 10 offset 5",
            "SELECT * FROM t ORDER BY x NULLS FIRST LIMIT 10 OFFSET 5",
        ),
    ],
)
def test_steps_after_limit_read_the_limited_rows(query: str, expected: str) -> None:
    assert transpile(query) == expected


# P8: a step after a fixed projection reads that projection -------------------
def test_second_select_reads_the_first() -> None:
    assert transpile("from t select a + 1 as c select c, 2 as d") == (
        "WITH __tmp1 AS (SELECT a + 1 AS c FROM t) SELECT c, 2 AS d FROM __tmp1"
    )


def test_extend_after_select_keeps_the_projection() -> None:
    assert transpile("from t select a, b extend a + b as c") == (
        "WITH __tmp1 AS (SELECT a, b FROM t), __tmp2 AS (SELECT *, a + b AS c FROM __tmp1) "
        "SELECT * FROM __tmp2"
    )


def test_where_after_aliased_select_filters_the_alias() -> None:
    sql = transpile("from t select a + 1 as c where c > 1", dialect="postgres")
    assert sql == (
        "WITH __tmp1 AS (SELECT a + 1 AS c FROM t) SELECT * FROM __tmp1 WHERE c > 1"
    )


def test_order_and_limit_after_select_stay_on_the_same_stage() -> None:
    assert transpile("from t select a, b order by -a limit 5") == (
        "SELECT a, b FROM t ORDER BY a DESC LIMIT 5"
    )


def test_select_after_except_reads_the_excluded_projection() -> None:
    """`except email` fixes the projection as much as `rename` does: a later
    `select *` reads that stage rather than replacing it (the exclusion was
    silently dropped)."""
    sql = transpile("from users except email select *, upper(name) as n")
    assert sql == (
        "WITH __tmp1 AS (SELECT * EXCLUDE (email) FROM users) "
        "SELECT *, UPPER(name) AS n FROM __tmp1"
    )
