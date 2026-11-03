"""On BigQuery a relative date compared with a DATE or DATETIME counts from today.

`7 days ago` is a TIMESTAMP, and BigQuery has no `DATE >= TIMESTAMP` or
`DATETIME >= TIMESTAMP`. Against a DATE column it means `CURRENT_DATE - 7
days`, against a DATETIME `CURRENT_DATETIME() - 7 days` — what
`relative_date_type="date"` does globally, chosen per comparison from the
column's type. Only ASQL's own relative dates are rewritten; comparing a DATE
with some other TIMESTAMP is left for BigQuery to reject.
"""

from __future__ import annotations

from typing import Any

import pytest

import asql

SCHEMA: dict[str, Any] = {
    "tables": {
        "t": {"columns": {"c": "TIMESTAMP", "d": "DATE", "x": "DATETIME"}},
    }
}


def bigquery(query: str) -> str:
    return asql.transpile(query, write="bigquery", schema=SCHEMA)[0]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "from t where d >= 7 days ago",
            "SELECT * FROM t WHERE d >= CURRENT_DATE - INTERVAL '7' DAY",
        ),
        (
            "from t where d >= 12 months ago",
            "SELECT * FROM t WHERE d >= CURRENT_DATE - INTERVAL '12' MONTH",
        ),
        (
            "from t where 7 days ago <= d",
            "SELECT * FROM t WHERE CURRENT_DATE - INTERVAL '7' DAY <= d",
        ),
        (
            "from t where d < now()",
            "SELECT * FROM t WHERE d < CURRENT_DATE",
        ),
        (
            "from t where d between 30 days ago and now()",
            "SELECT * FROM t WHERE d BETWEEN CURRENT_DATE - INTERVAL '30' DAY "
            "AND CURRENT_DATE",
        ),
        (
            "from t where x >= 7 days ago",
            "SELECT * FROM t WHERE x >= CURRENT_DATETIME() - INTERVAL '7' DAY",
        ),
        (
            "from t where x < 2 years from now",
            "SELECT * FROM t WHERE x < CURRENT_DATETIME() + INTERVAL '2' YEAR",
        ),
    ],
)
def test_relative_dates_follow_the_compared_column(query: str, expected: str) -> None:
    assert bigquery(query) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "from t where c >= 7 days ago",
            "SELECT * FROM t WHERE c >= CURRENT_TIMESTAMP() - INTERVAL '7' DAY",
        ),
        (
            "from t where u >= 7 days ago",
            "SELECT * FROM t WHERE u >= CURRENT_TIMESTAMP() - INTERVAL '7' DAY",
        ),
        ("from t where d >= c", "SELECT * FROM t WHERE d >= c"),
    ],
)
def test_timestamps_unknown_types_and_user_columns_are_untouched(
    query: str, expected: str
) -> None:
    assert bigquery(query) == expected


def test_other_dialects_are_untouched() -> None:
    assert asql.transpile(
        "from t where d >= 7 days ago", write="postgres", schema=SCHEMA
    )[0].endswith("WHERE t.d >= CURRENT_TIMESTAMP - INTERVAL '7 DAY'")
