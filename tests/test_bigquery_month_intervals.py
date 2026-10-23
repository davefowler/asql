"""BigQuery rejects TIMESTAMP ± INTERVAL n MONTH/YEAR at run time.

The query type-checks (a dry run passes) and then fails with "TIMESTAMP +/-
INTERVAL is not supported for intervals with non-zero MONTH or YEAR part".
DATE and DATETIME accept those intervals, so a TIMESTAMP base goes through
DATETIME and back. A column whose type is unknown can't be routed safely: a
DATE wrapped the same way becomes a TIMESTAMP and no longer compares with
DATE columns.
"""

from __future__ import annotations

from typing import Any

import pytest

import asql
from asql.errors import ASQLDialectError

SCHEMA: dict[str, Any] = {
    "tables": {
        "t": {
            "columns": {"c": "TIMESTAMP", "d": "DATE", "x": "DATETIME", "n": "INT64"}
        },
    }
}


def bigquery(query: str, **kwargs: Any) -> str:
    return asql.transpile(query, write="bigquery", **kwargs)[0]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "from t where c >= 12 months ago",
            "SELECT * FROM t WHERE c >= "
            "TIMESTAMP(DATETIME(CURRENT_TIMESTAMP()) - INTERVAL '12' MONTH)",
        ),
        (
            "from t where c <= 2 years from now",
            "SELECT * FROM t WHERE c <= "
            "TIMESTAMP(DATETIME(CURRENT_TIMESTAMP()) + INTERVAL '2' YEAR)",
        ),
        (
            "from t select c - 1 month as a",
            "SELECT TIMESTAMP(DATETIME(c) - INTERVAL '1' MONTH) AS a FROM t",
        ),
        (
            "from t select c::TIMESTAMPTZ + 3 years as a",
            "SELECT TIMESTAMP(DATETIME(CAST(c AS TIMESTAMP)) + INTERVAL '3' YEAR) "
            "AS a FROM t",
        ),
        (
            'from t where c >= month(now()::"America/Los_Angeles") - 12 months',
            "SELECT * FROM t WHERE c >= TIMESTAMP(DATETIME(DATE_TRUNC("
            "TIMESTAMP(DATETIME(CURRENT_TIMESTAMP(), 'America/Los_Angeles')), MONTH))"
            " - INTERVAL '12' MONTH)",
        ),
    ],
)
def test_timestamp_month_and_year_arithmetic_goes_through_datetime(
    query: str, expected: str
) -> None:
    assert bigquery(query, schema=SCHEMA) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("from t select d - 1 month as a", "SELECT d - INTERVAL '1' MONTH AS a FROM t"),
        ("from t select x + 2 years as a", "SELECT x + INTERVAL '2' YEAR AS a FROM t"),
        (
            # ASQL TIMESTAMP is the naive (ANSI) type: BigQuery DATETIME.
            "from t select c::TIMESTAMP + 3 years as a",
            "SELECT CAST(c AS DATETIME) + INTERVAL '3' YEAR AS a FROM t",
        ),
        (
            "from t select c::DATE - 1 month as a",
            "SELECT CAST(c AS DATE) - INTERVAL '1' MONTH AS a FROM t",
        ),
        (
            "from t where c >= 7 days ago",
            "SELECT * FROM t WHERE c >= CURRENT_TIMESTAMP() - INTERVAL '7' DAY",
        ),
        ("from t select c + 2 hours as a", "SELECT c + INTERVAL '2' HOUR AS a FROM t"),
    ],
)
def test_date_datetime_and_sub_month_intervals_are_untouched(
    query: str, expected: str
) -> None:
    assert bigquery(query, schema=SCHEMA) == expected


def test_relative_date_type_date_is_untouched() -> None:
    assert bigquery("from t where d >= 12 months ago", relative_date_type="date") == (
        "SELECT * FROM t WHERE d >= CURRENT_DATE - INTERVAL '12' MONTH"
    )


def test_now_based_intervals_need_no_schema() -> None:
    assert bigquery("from t where c >= 1 year ago") == (
        "SELECT * FROM t WHERE c >= "
        "TIMESTAMP(DATETIME(CURRENT_TIMESTAMP()) - INTERVAL '1' YEAR)"
    )


@pytest.mark.parametrize(
    ("query", "kwargs"),
    [
        ("from t select c - 1 month as a", {}),
        ("from t select u - 1 month as a", {"schema": SCHEMA}),
    ],
)
def test_unknown_type_month_arithmetic_is_an_error(
    query: str, kwargs: dict[str, Any]
) -> None:
    with pytest.raises(ASQLDialectError, match=r"month/year arithmetic on BigQuery"):
        bigquery(query, **kwargs)


def test_other_dialects_need_no_types() -> None:
    assert asql.transpile("from t select c - 1 month as a", write="postgres")[0] == (
        "SELECT c - INTERVAL '1 MONTH' AS a FROM t"
    )
