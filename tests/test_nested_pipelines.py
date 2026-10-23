"""A parenthesized `from ...` is a full ASQL pipeline, in any step order.

The generator writes nested queries as `(from t where ... select ...)`, so
every SQL → ASQL conversion with a subquery depends on this parsing.
"""

from __future__ import annotations

import pytest
import sqlglot

import asql

from .fixtures import transpile


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "from t where a in (from u where b select a)",
            "SELECT * FROM t WHERE a IN (SELECT a FROM u WHERE b)",
        ),
        (
            "from t where a in (from u where b order by a limit 3 select a)",
            "SELECT * FROM t WHERE a IN (SELECT a FROM u WHERE b ORDER BY a NULLS FIRST LIMIT 3)",
        ),
        (
            "from t where exists (from u where u.a = t.a select a)",
            "SELECT * FROM t WHERE EXISTS(SELECT a FROM u WHERE u.a = t.a)",
        ),
        (
            "from t select (from u where b select max(a)) as m",
            "SELECT (SELECT MAX(a) AS max_a FROM u WHERE b) AS m FROM t",
        ),
        (
            "from (from u where b select a) as s",
            "SELECT * FROM (SELECT a FROM u WHERE b) AS s",
        ),
        (
            "from t & (from u where b select a) as s on t.a = s.a",
            "SELECT * FROM t INNER JOIN (SELECT a FROM u WHERE b) AS s ON t.a = s.a",
        ),
        (
            "from t where a in (from u group by a (sum(x) as total) where total > 0 select a)",
            "SELECT * FROM t WHERE a IN (WITH __tmp2 AS (SELECT a, SUM(x) AS total "
            "FROM u GROUP BY a) SELECT a FROM __tmp2 WHERE total > 0)",
        ),
        (
            "from t where a in (\n  from u\n  where b\n  select a\n)",
            "SELECT * FROM t WHERE a IN (SELECT a FROM u WHERE b)",
        ),
        (
            "from t where a in (from u where a in (from v where c select a) select a)",
            "SELECT * FROM t WHERE a IN (SELECT a FROM u WHERE a IN "
            "(SELECT a FROM v WHERE c))",
        ),
    ],
)
def test_nested_pipeline_compiles(query: str, expected: str) -> None:
    assert transpile(query) == expected


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM t WHERE a IN (SELECT a FROM u WHERE b)",
        "SELECT * FROM t WHERE EXISTS(SELECT a FROM u WHERE u.a = t.a)",
        "SELECT (SELECT MAX(a) AS m FROM u WHERE b) AS m FROM t",
        "SELECT * FROM (SELECT a FROM u WHERE b LIMIT 3) AS s",
        "WITH r AS (SELECT * FROM t WHERE a IN (SELECT a FROM u WHERE b)) "
        "SELECT r.a, v.c FROM r LEFT JOIN v ON r.a = v.a",
    ],
)
def test_sql_with_subqueries_round_trips_through_asql(sql: str) -> None:
    written = sqlglot.transpile(sql, read="duckdb", write="asql")[0]
    assert transpile(written) == sqlglot.transpile(sql, read="duckdb")[0], written


def test_bigquery_null_guarded_filter_round_trips() -> None:
    sql = (
        "WITH revenue AS (SELECT * FROM `p`.d.revenue WHERE (NULL IS NULL OR "
        "salesforce_account_id IN (SELECT salesforce_account_id FROM `p`.d.revenue "
        "WHERE is_active_start AND month = DATE_TRUNC(DATE(NULL), MONTH)))) "
        "SELECT revenue.month, COUNT(*) AS n FROM revenue GROUP BY 1"
    )
    written = asql.transpile(sql, read="bigquery", write="asql")[0]
    back = asql.transpile(written, read="asql", write="bigquery")[0]
    assert "IN (SELECT salesforce_account_id FROM `p`.d.revenue WHERE" in back, back
