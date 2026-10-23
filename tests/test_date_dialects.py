"""Relative dates, date arithmetic, `now()` and timezone casts compile per dialect.

Each dialect has its own interval and timezone spelling; one Postgres-style
string (`INTERVAL '7 days'`) is a syntax error on BigQuery, MySQL and Trino.
The BigQuery strings below were checked with a BigQuery dry run.
"""

from __future__ import annotations

import datetime as dt

import duckdb
import pytest

import asql

from .fixtures import transpile

DIALECTS = [
    "duckdb",
    "postgres",
    "mysql",
    "snowflake",
    "bigquery",
    "redshift",
    "databricks",
    "trino",
]

NOW = {
    "duckdb": "CURRENT_TIMESTAMP",
    "postgres": "CURRENT_TIMESTAMP",
    "mysql": "CURRENT_TIMESTAMP()",
    "snowflake": "CURRENT_TIMESTAMP()",
    "bigquery": "CURRENT_TIMESTAMP()",
    "redshift": "GETDATE()",
    "databricks": "CURRENT_TIMESTAMP()",
    "trino": "CURRENT_TIMESTAMP",
}

# Postgres-family dialects spell the unit inside the string.
_UNIT_IN_STRING = {"postgres", "snowflake", "redshift"}


def _interval(dialect: str, number: str, unit: str) -> str:
    if dialect in _UNIT_IN_STRING:
        return f"INTERVAL '{number} {unit}'"
    return f"INTERVAL '{number}' {unit}"


@pytest.mark.parametrize("dialect", DIALECTS)
def test_now_is_the_current_timestamp(dialect: str) -> None:
    assert transpile("from t select now() as x", dialect) == (
        f"SELECT {NOW[dialect]} AS x FROM t"
    )


@pytest.mark.parametrize("dialect", DIALECTS)
@pytest.mark.parametrize(
    ("phrase", "op", "number", "unit"),
    [
        ("12 months ago", "-", "12", "MONTH"),
        ("7 days ago", "-", "7", "DAY"),
        ("1 week ago", "-", "1", "WEEK"),
        ("3 days from now", "+", "3", "DAY"),
        ("2 hours from now", "+", "2", "HOUR"),
    ],
)
def test_relative_dates(
    dialect: str, phrase: str, op: str, number: str, unit: str
) -> None:
    interval = _interval(dialect, number, unit)
    if dialect == "trino" and unit == "WEEK":  # Trino has no WEEK interval
        interval = f"({number} * INTERVAL '7' DAY)"
    expected = f"SELECT * FROM t WHERE c >= {NOW[dialect]} {op} {interval}"
    assert transpile(f"from t where c >= {phrase}", dialect) == expected


@pytest.mark.parametrize("dialect", DIALECTS)
@pytest.mark.parametrize(
    ("arith", "op", "number", "unit"),
    [
        ("c + 7 days", "+", "7", "DAY"),
        ("c - 1 month", "-", "1", "MONTH"),
        ("c + 24 hours", "+", "24", "HOUR"),
        ("c - 2 years", "-", "2", "YEAR"),
    ],
)
def test_date_arithmetic(
    dialect: str, arith: str, op: str, number: str, unit: str
) -> None:
    expected = f"SELECT c {op} {_interval(dialect, number, unit)} AS x FROM t"
    assert transpile(f"from t select {arith} as x", dialect) == expected


TZ = {
    "duckdb": "c AT TIME ZONE '{tz}'",
    "postgres": "c AT TIME ZONE '{tz}'",
    "mysql": "CONVERT_TZ(c, 'UTC', '{tz}')",
    "snowflake": "CONVERT_TIMEZONE('{tz}', c)",
    "bigquery": "TIMESTAMP(DATETIME(c, '{tz}'))",
    "redshift": "CONVERT_TIMEZONE('{tz}', c)",
    "databricks": "CONVERT_TIMEZONE('{tz}', c)",
    "trino": "AT_TIMEZONE(c, '{tz}')",
}


@pytest.mark.parametrize("dialect", DIALECTS)
@pytest.mark.parametrize(
    ("written", "tz"),
    [
        ('c::"America/Los_Angeles"', "America/Los_Angeles"),
        ('c::"Europe/London"', "Europe/London"),
        ("c::PST", "America/Los_Angeles"),
        ("c::pt", "America/Los_Angeles"),
        ("c::EST", "America/New_York"),
        ("c::CST", "America/Chicago"),
        ("c::MST", "America/Denver"),
        ("c::UTC", "UTC"),
    ],
)
def test_timezone_conversion(dialect: str, written: str, tz: str) -> None:
    expected = TZ[dialect].format(tz=tz)
    assert transpile(f"from t select {written} as x", dialect) == (
        f"SELECT {expected} AS x FROM t"
    )


def test_timezone_composes_with_truncation_and_arithmetic() -> None:
    assert transpile("from t select month(c::PST) as x", "bigquery") == (
        "SELECT DATE_TRUNC(TIMESTAMP(DATETIME(c, 'America/Los_Angeles')), MONTH) "
        "AS x FROM t"
    )
    assert transpile("from t select c::UTC + 7 days as x", "postgres") == (
        "SELECT c AT TIME ZONE 'UTC' + INTERVAL '7 DAY' AS x FROM t"
    )


def test_type_casts_are_untouched() -> None:
    assert transpile("from t select c::DATE as x, c::INT as y") == (
        "SELECT CAST(c AS DATE) AS x, CAST(c AS INT) AS y FROM t"
    )


def test_relative_dates_execute_on_duckdb() -> None:
    sql = transpile(
        "from (from range(1) select now() - 7 days as c) as t "
        "select c >= 8 days ago and c <= 6 days ago as in_window, "
        "c + 7 days - now() < 1 minutes from now - now() as round_trips",
    )
    in_window, round_trips = duckdb.sql(sql).fetchone()  # type: ignore[misc]
    assert in_window is True
    assert round_trips is True


def test_timezone_executes_on_duckdb() -> None:
    sql = transpile(
        "from (from range(1) select @2024-07-01T12:00:00::TIMESTAMPTZ as c) as t "
        'select c::"America/Los_Angeles" as la'
    )
    con = duckdb.connect()
    con.sql("SET TimeZone = 'UTC'")
    (la,) = con.sql(sql).fetchone()  # type: ignore[misc]
    assert la == dt.datetime(2024, 7, 1, 5, 0)


@pytest.mark.parametrize(
    ("dialect", "today"),
    [
        ("bigquery", "CURRENT_DATE"),
        ("postgres", "CURRENT_DATE"),
        ("snowflake", "CURRENT_DATE"),
    ],
)
def test_relative_date_type_date_counts_from_today(dialect: str, today: str) -> None:
    sql = asql.transpile(
        "from t where d >= 7 days ago", write=dialect, relative_date_type="date"
    )[0]
    assert (
        sql == f"SELECT * FROM t WHERE d >= {today} - {_interval(dialect, '7', 'DAY')}"
    )
