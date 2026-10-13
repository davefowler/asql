"""Unit functions (`month(x)`, `year(x)`, ...) truncate to the start of the unit.

Extraction (`EXTRACT(MONTH FROM x)`) would merge Jan 2024 with Jan 2025, so the
documented contract (docs/syntax/dates.md) is truncation on every dialect.
"""

from __future__ import annotations

import json
from typing import Any

import duckdb
import pytest
import sqlglot

import asql
from asql.dialect import ASQL
from asql.errors import ASQLCompilationError

DIALECTS = ("duckdb", "postgres", "snowflake", "bigquery")

DATE_UNITS = ("year", "quarter", "month", "day")
TIME_UNITS = ("hour", "minute", "second")


def _sql(query: str, dialect: str, week_start: str | None = None) -> str:
    kwargs: dict[str, Any] = {"week_start": week_start} if week_start else {}
    return asql.transpile(query, write=dialect, **kwargs)[0].replace("\n", " ")


def _expected_trunc(function: str, unit: str, column: str, dialect: str) -> str:
    unit_sql = unit.upper()
    if dialect == "bigquery":
        return f"{function}({column}, {unit_sql})"
    return f"{function}('{unit_sql}', {column})"


@pytest.mark.parametrize("dialect", DIALECTS)
@pytest.mark.parametrize("unit", DATE_UNITS)
def test_date_unit_truncates_with_date_trunc(unit: str, dialect: str) -> None:
    sql = _sql(f"from orders select {unit}(created_at)", dialect)
    expected = _expected_trunc("DATE_TRUNC", unit, "created_at", dialect)
    assert f"{expected} AS {unit}_created_at" in sql
    assert "EXTRACT" not in sql


@pytest.mark.parametrize("dialect", DIALECTS)
@pytest.mark.parametrize("unit", TIME_UNITS)
def test_time_unit_truncates_as_timestamp(unit: str, dialect: str) -> None:
    sql = _sql(f"from orders select {unit}(created_at)", dialect)
    function = "TIMESTAMP_TRUNC" if dialect == "bigquery" else "DATE_TRUNC"
    expected = _expected_trunc(function, unit, "created_at", dialect)
    assert f"{expected} AS {unit}_created_at" in sql


@pytest.mark.parametrize(
    ("dialect", "expected"),
    [
        ("duckdb", "DATE_TRUNC('WEEK', created_at)"),
        ("postgres", "DATE_TRUNC('WEEK', created_at)"),
        ("snowflake", "DATE_TRUNC('WEEK', created_at)"),
        ("bigquery", "DATE_TRUNC(created_at, WEEK(MONDAY))"),
    ],
)
def test_week_defaults_to_monday(dialect: str, expected: str) -> None:
    sql = _sql("from orders select week(created_at)", dialect)
    assert f"{expected} AS week_created_at" in sql


@pytest.mark.parametrize(
    ("dialect", "expected"),
    [
        (
            "duckdb",
            "DATE_TRUNC('WEEK', created_at + INTERVAL '1' DAY) - INTERVAL '1' DAY",
        ),
        (
            "postgres",
            "DATE_TRUNC('WEEK', created_at + INTERVAL '1 DAY') - INTERVAL '1 DAY'",
        ),
        (
            "snowflake",
            "DATE_TRUNC('WEEK', created_at + INTERVAL '1 DAY') - INTERVAL '1 DAY'",
        ),
        (
            "bigquery",
            "DATE_TRUNC(created_at + INTERVAL '1' DAY, WEEK(MONDAY)) - INTERVAL '1' DAY",
        ),
    ],
)
def test_week_start_sunday_setting(dialect: str, expected: str) -> None:
    sql = _sql("from orders select week(created_at)", dialect, week_start="sunday")
    assert f"({expected}) AS week_created_at" in sql


def test_week_start_set_statement() -> None:
    sql = _sql(
        "SET week_start = 'sunday';\nfrom orders select week(created_at)", "bigquery"
    )
    assert "INTERVAL '1' DAY" in sql


@pytest.mark.parametrize("dialect", ["duckdb", "bigquery"])
def test_explicit_week_monday_and_sunday(dialect: str) -> None:
    monday = _sql(
        "from orders select week_monday(created_at)", dialect, week_start="sunday"
    )
    sunday = _sql("from orders select week_sunday(created_at)", dialect)
    assert monday != sunday
    if dialect == "bigquery":
        assert "WEEK(MONDAY)" in monday
        assert "INTERVAL '1' DAY" in sunday


@pytest.mark.parametrize(
    "spelling",
    [
        "month(created_at)",
        "month created_at",
        "month of created_at",
    ],
)
def test_all_spellings_truncate(spelling: str) -> None:
    sql = _sql(f"from orders select {spelling}", "postgres")
    assert "DATE_TRUNC('MONTH', created_at)" in sql
    assert "EXTRACT" not in sql


def test_underscore_shorthand_truncates() -> None:
    sql = _sql("from orders select month_created_at", "postgres")
    assert "DATE_TRUNC('MONTH', created_at) AS month_created_at" in sql


def test_auto_alias_name_unchanged() -> None:
    sql = _sql("from orders group by month(created_at) (# as n)", "duckdb")
    assert sql.startswith("SELECT DATE_TRUNC('MONTH', created_at) AS month_created_at")
    assert "GROUP BY DATE_TRUNC('MONTH', created_at)" in sql


@pytest.mark.parametrize(
    ("spelling", "expected"),
    [
        ("day of month", 14),
        ("day of year", 45),
        ("week of year", 7),
        ("month of year", 2),
        ("quarter of year", 1),
    ],
)
def test_documented_extraction_forms_return_integers(
    spelling: str, expected: int
) -> None:
    sql = _sql(f"from orders select {spelling} created_at as part", "duckdb")
    assert "DATE_TRUNC" not in sql
    conn = duckdb.connect()
    conn.execute("CREATE TABLE orders (created_at TIMESTAMP)")
    conn.execute("INSERT INTO orders VALUES ('2025-02-14 10:30:00')")
    assert conn.execute(sql).fetchone() == (expected,)


def test_standard_extract_is_untouched() -> None:
    sql = _sql("from orders select extract(month from created_at) as m", "postgres")
    assert "EXTRACT(MONTH FROM created_at) AS m" in sql


def test_spine_joins_on_truncated_expression_both_sides() -> None:
    sql = _sql("from orders spine by month(created_at) (# as n)", "duckdb")
    assert "DATE_TRUNC('MONTH', created_at)" in sql
    assert "MONTH(created_at)" not in sql.replace("DATE_TRUNC('MONTH', created_at)", "")
    assert "LEFT JOIN" in sql


@pytest.mark.parametrize(
    ("dialect", "week_start", "expected"),
    [
        ("bigquery", "monday", "DATE_TRUNC(d, WEEK(MONDAY))"),
        ("bigquery", "sunday", "DATE_TRUNC(d + INTERVAL '1' DAY, WEEK(MONDAY))"),
        ("duckdb", "monday", "DATE_TRUNC('WEEK', d)"),
        ("duckdb", "sunday", "DATE_TRUNC('WEEK', d + INTERVAL '1' DAY)"),
    ],
)
def test_week_spine_side_matches_query_week_start(
    dialect: str, week_start: str, expected: str
) -> None:
    sql = _sql(
        "from orders where created_at >= '2024-01-01' and created_at <= '2024-12-31' "
        "spine by week(created_at) (# as n)",
        dialect,
        week_start=week_start,
    )
    assert expected in sql


def test_duckdb_groups_same_month_of_different_years_apart() -> None:
    sql = _sql(
        "from orders group by month(created_at) (sum(amount) as revenue) order by month_created_at",
        "duckdb",
    )
    conn = duckdb.connect()
    conn.execute("CREATE TABLE orders (created_at TIMESTAMP, amount INT)")
    conn.execute(
        "INSERT INTO orders VALUES "
        "('2024-01-05', 1), ('2024-01-20', 2), ('2025-01-05', 10), ('2025-02-01', 100)"
    )
    rows = conn.execute(sql).fetchall()
    assert [(str(r[0])[:10], r[1]) for r in rows] == [
        ("2024-01-01", 3),
        ("2025-01-01", 10),
        ("2025-02-01", 100),
    ]


def test_duckdb_week_start_executes_to_requested_weekday() -> None:
    conn = duckdb.connect()
    conn.execute("CREATE TABLE orders (created_at TIMESTAMP)")
    conn.execute("INSERT INTO orders VALUES ('2025-01-15 10:30:00')")  # Wednesday
    monday = conn.execute(
        _sql("from orders select week(created_at)", "duckdb")
    ).fetchall()
    sunday = conn.execute(
        _sql("from orders select week(created_at)", "duckdb", week_start="sunday")
    ).fetchall()
    assert str(monday[0][0])[:10] == "2025-01-13"
    assert str(sunday[0][0])[:10] == "2025-01-12"


def test_duckdb_spine_query_keeps_years_apart() -> None:
    sql = _sql(
        "from orders spine by month(created_at) (sum(amount) as revenue) order by month_created_at",
        "duckdb",
    )
    conn = duckdb.connect()
    conn.execute("CREATE TABLE orders (created_at TIMESTAMP, amount INT)")
    conn.execute(
        "INSERT INTO orders VALUES ('2024-01-05', 1), ('2025-01-05', 5), ('2025-01-06', 6)"
    )
    rows = conn.execute(sql).fetchall()
    gaps = [(f"2024-{m:02d}-01", None) for m in range(2, 13)]
    assert [(str(r[0])[:10], r[1]) for r in rows] == [
        ("2024-01-01", 1),
        *gaps,
        ("2025-01-01", 11),
    ]


# --- SQL -> ASQL: the generator must not turn extraction into truncation ---


def _to_asql(sql: str, read: str) -> str:
    return sqlglot.transpile(sql, read=read, write="asql")[0]


def _rows(sql: str) -> list[tuple[Any, ...]]:
    conn = duckdb.connect()
    conn.execute("CREATE TABLE t (x TIMESTAMP)")
    conn.execute(
        "INSERT INTO t VALUES ('2024-01-05 10:30:45'), ('2025-02-14 23:01:02')"
    )
    return conn.execute(sql).fetchall()


@pytest.mark.parametrize(
    ("source", "read"),
    [
        ("SELECT MONTH(x) AS v FROM t", "duckdb"),
        ("SELECT YEAR(x) AS v FROM t", "duckdb"),
        ("SELECT QUARTER(x) AS v FROM t", "duckdb"),
        ("SELECT DAY(x) AS v FROM t", "duckdb"),
        ("SELECT HOUR(x) AS v FROM t", "duckdb"),
        ("SELECT MINUTE(x) AS v FROM t", "duckdb"),
        ("SELECT SECOND(x) AS v FROM t", "duckdb"),
        ("SELECT DAYOFYEAR(x) AS v FROM t", "duckdb"),
        ("SELECT DAYOFMONTH(x) AS v FROM t", "duckdb"),
        ("SELECT WEEKOFYEAR(x) AS v FROM t", "duckdb"),
        ("SELECT EXTRACT(MONTH FROM x) AS v FROM t", "postgres"),
        ("SELECT DATE_TRUNC('month', x) AS v FROM t", "duckdb"),
        ("SELECT DATE_TRUNC('year', x) AS v FROM t", "postgres"),
        ("SELECT DATE_TRUNC('hour', x) AS v FROM t", "duckdb"),
        ("SELECT DATE_TRUNC('week', x) AS v FROM t", "duckdb"),
    ],
)
def test_sql_to_asql_round_trip_preserves_meaning(source: str, read: str) -> None:
    asql_text = _to_asql(source, read)
    round_tripped = asql.transpile(asql_text, write="duckdb")[0]
    expected = _rows(sqlglot.transpile(source, read=read, write="duckdb")[0])
    assert _rows(round_tripped) == expected, (asql_text, round_tripped)


def test_sql_to_asql_spellings() -> None:
    assert "month(x)" in _to_asql("SELECT DATE_TRUNC('month', x) FROM t", "duckdb")
    assert "month of year x" in _to_asql("SELECT MONTH(x) FROM t", "duckdb")
    assert "month(x)" not in _to_asql("SELECT MONTH(x) FROM t", "duckdb")
    assert "day of month x" in _to_asql("SELECT DAYOFMONTH(x) FROM t", "duckdb")


# --- WeekTrunc generator -----------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("from orders select week(created_at)", "week(created_at)"),
        ("from orders select week_monday(created_at)", "week_monday(created_at)"),
        ("from orders select week_sunday(created_at)", "week_sunday(created_at)"),
    ],
)
def test_week_round_trips_asql_to_asql(source: str, expected: str) -> None:
    normalized = sqlglot.transpile(source, read="asql", write="asql")[0]
    assert expected in normalized
    assert "WEEK_TRUNC" not in normalized
    assert normalized.count(expected) >= 1


@pytest.mark.parametrize("dialect", DIALECTS)
def test_plain_sqlglot_transpile_of_week_trunc(dialect: str) -> None:
    sql = sqlglot.transpile(
        "from orders select week_sunday(created_at)", read="asql", write=dialect
    )[0]
    assert "WEEK_TRUNC" not in sql.upper()
    assert "created_at" in sql


# --- week_start normalization and validation ---------------------------------


@pytest.mark.parametrize("dialect", ["duckdb", "postgres", "snowflake"])
def test_set_week_start_is_case_insensitive(dialect: str) -> None:
    sql = _sql(
        "SET week_start = 'Monday';\nfrom orders select week(created_at)", dialect
    )
    assert "DATE_TRUNC('WEEK', created_at) AS week_created_at" in sql


def test_set_week_start_uppercase_sunday_on_bigquery() -> None:
    sql = _sql(
        "SET week_start = 'SUNDAY';\nfrom orders select week(created_at)", "bigquery"
    )
    assert "INTERVAL '1' DAY" in sql


def test_kwarg_week_start_is_normalized() -> None:
    sql = _sql("from orders select week(created_at)", "bigquery", week_start="Sunday")
    assert "INTERVAL '1' DAY" in sql


def test_kwarg_week_start_unknown_raises() -> None:
    with pytest.raises(ValueError, match="week_start"):
        _sql("from orders select week(created_at)", "duckdb", week_start="tuesday")


def test_set_week_start_unknown_raises() -> None:
    with pytest.raises(ValueError, match="week_start"):
        _sql(
            "SET week_start = 'tuesday';\nfrom orders select week(created_at)", "duckdb"
        )


# --- extraction forms across dialects ----------------------------------------


def _extract_sql(part: str, column: str, dialect: str) -> str:
    return {
        "snowflake": f"DATE_PART({part}, {column})",
    }.get(dialect, f"EXTRACT({part} FROM {column})")


@pytest.mark.parametrize("dialect", DIALECTS)
@pytest.mark.parametrize(
    ("spelling", "parts"),
    [
        ("day of year", dict.fromkeys(DIALECTS, "DAYOFYEAR") | {"postgres": "DOY"}),
        ("day of month", dict.fromkeys(DIALECTS, "DAY")),
        ("week of year", dict.fromkeys(DIALECTS, "WEEK")),
        ("month of year", dict.fromkeys(DIALECTS, "MONTH")),
        ("quarter of year", dict.fromkeys(DIALECTS, "QUARTER")),
    ],
)
def test_extraction_forms_use_valid_part_per_dialect(
    spelling: str, parts: dict[str, str], dialect: str
) -> None:
    sql = _sql(f"from orders select {spelling} created_at as part", dialect)
    assert _extract_sql(parts[dialect], "created_at", dialect) in sql
    assert "DOY" not in sql or dialect == "postgres"


# --- numeric comparison guard -------------------------------------------------


@pytest.mark.parametrize(
    "condition",
    [
        "year(created_at) = 2024",
        "2024 = year(created_at)",
        "month(created_at) <> 1",
        "quarter(created_at) < 3",
        "month(created_at) >= 6",
        "month(created_at) in (1, 2)",
        "month(created_at) between 1 and 3",
        "week(created_at) = 10",
        "hour(created_at) > 12",
    ],
)
def test_truncating_unit_compared_with_number_raises(condition: str) -> None:
    with pytest.raises(ASQLCompilationError, match="extract"):
        _sql(f"from orders where {condition}", "duckdb")


@pytest.mark.parametrize(
    "condition",
    [
        "year(created_at) = @2024-01-01",
        "extract(year from created_at) = 2024",
        "month of year created_at = 1",
        "created_at >= @2024-01-01 and created_at < @2025-01-01",
        "month(created_at) = month(updated_at)",
    ],
)
def test_valid_unit_comparisons_still_compile(condition: str) -> None:
    assert _sql(f"from orders where {condition}", "duckdb")


# --- Sunday weeks must be right outside asql.transpile too -------------------

_WEEK_DAYS = [
    ("2025-01-12 08:00:00", "2025-01-12"),  # Sunday stays
    ("2025-01-15 10:30:00", "2025-01-12"),  # Wednesday
    ("2025-01-18 23:59:59", "2025-01-12"),  # Saturday
    ("2025-01-19 00:00:00", "2025-01-19"),  # next Sunday
]


def _sunday_boundaries(sql: str) -> list[tuple[str, str]]:
    conn = duckdb.connect()
    conn.execute("CREATE TABLE orders (created_at TIMESTAMP)")
    for day, _ in _WEEK_DAYS:
        conn.execute(f"INSERT INTO orders VALUES ('{day}')")
    return [(str(r[0])[:10], str(r[1])[:10]) for r in conn.execute(sql).fetchall()]


@pytest.mark.parametrize("via", ["asql", "sqlglot"])
def test_sunday_week_boundary_on_duckdb(via: str) -> None:
    query = "SET week_start = 'sunday';\nfrom orders select week(created_at) as w, created_at as c"
    if via == "asql":
        sql = asql.transpile(query, write="duckdb")[0]
    else:
        sql = sqlglot.transpile(query, read="asql", write="duckdb")[0]
    rows = sorted(_sunday_boundaries(sql), key=lambda r: r[1])
    assert [r[0] for r in rows] == [d for _, d in _WEEK_DAYS]


@pytest.mark.parametrize("via", ["asql", "sqlglot"])
@pytest.mark.parametrize("dialect", ["postgres", "snowflake"])
def test_week_sunday_is_shifted_on_every_path(via: str, dialect: str) -> None:
    query = "from orders select week_sunday(created_at)"
    if via == "asql":
        sql = asql.transpile(query, write=dialect)[0]
    else:
        sql = sqlglot.transpile(query, read="asql", write=dialect)[0]
    assert "DATE_TRUNC('WEEK', created_at + INTERVAL '1" in sql
    assert "week_sunday_created_at" in sql


def test_week_sunday_round_trips_to_asql_name() -> None:
    normalized = sqlglot.transpile(
        "from orders select week_sunday(created_at)", read="asql", write="asql"
    )[0]
    assert "week_sunday(created_at)" in normalized


def test_week_sunday_spine_reads_start_day() -> None:
    sql = _sql("from orders spine by week_sunday(created_at) (# as n)", "duckdb")
    assert "d + INTERVAL '1' DAY" in sql


# --- Sunday weeks as operands, standalone, in spines, and in the visual JSON --


def _exec_one(sql: str, rows: list[tuple[str, ...]], columns: str) -> Any:
    conn = duckdb.connect()
    conn.execute(f"CREATE TABLE orders ({columns})")
    for row in rows:
        conn.execute(f"INSERT INTO orders VALUES ({', '.join(repr(v) for v in row)})")
    return conn.execute(sql).fetchall()


@pytest.mark.parametrize("via", ["asql", "sqlglot"])
def test_week_sunday_as_subtraction_operand(via: str) -> None:
    query = "from orders select created_at - week_sunday(created_at) as since_week"
    if via == "asql":
        sql = asql.transpile(query, write="duckdb")[0]
    else:
        sql = sqlglot.transpile(query, read="asql", write="duckdb")[0]
    rows = _exec_one(sql, [("2025-01-15 10:30:00",)], "created_at TIMESTAMP")
    assert str(rows[0][0]) == "3 days, 10:30:00" or str(rows[0][0]) == "3 days 10:30:00"


def test_difference_of_two_week_sunday_calls() -> None:
    sql = _sql("from orders select week_sunday(a) - week_sunday(b) as gap", "duckdb")
    rows = _exec_one(
        sql,
        [("2025-01-19 10:00:00", "2025-01-15 10:00:00")],
        "a TIMESTAMP, b TIMESTAMP",
    )
    assert str(rows[0][0]).startswith("7 days")


def test_week_sunday_operand_round_trips_through_asql() -> None:
    source = "from orders select created_at - week_sunday(created_at) as d"
    normalized = sqlglot.transpile(source, read="asql", write="asql")[0]
    assert "week_sunday(created_at)" in normalized
    assert asql.transpile(normalized, write="duckdb") == asql.transpile(
        source, write="duckdb"
    )


@pytest.mark.parametrize("week_start", ["monday", "sunday"])
def test_bare_week_expression_as_whole_statement(week_start: str) -> None:
    dialect = ASQL(week_start=week_start)
    node = sqlglot.parse_one("week(d)", read=dialect)
    sql = node.sql("duckdb")
    assert "DATE_TRUNC" in sql
    assert ("INTERVAL" in sql) == (week_start == "sunday")


def test_week_sunday_compared_with_number_raises() -> None:
    with pytest.raises(ASQLCompilationError, match=r"extract\(week from created_at\)"):
        _sql("from orders where week_sunday(created_at) = 10", "duckdb")


def _spine_cte_values(sql: str) -> list[str]:
    parsed = sqlglot.parse_one(sql, read="duckdb")
    cte = parsed.args["with_"].expressions[0]
    probe = sqlglot.select("*").from_(cte.alias).with_(cte.alias, as_=cte.this)
    conn = duckdb.connect()
    conn.execute("CREATE TABLE orders (created_at TIMESTAMP)")
    conn.execute(
        "INSERT INTO orders VALUES ('2025-01-11 10:00:00'), ('2025-01-15 10:00:00'), ('2025-01-29 10:00:00')"
    )
    return sorted(str(r[0])[:10] for r in conn.execute(probe.sql("duckdb")).fetchall())


def test_week_sunday_spine_without_extractable_bounds_is_not_double_shifted() -> None:
    sql = _sql(
        "from orders where week_sunday(created_at) >= @2025-01-12 "
        "spine by week_sunday(created_at) (# as n)",
        "duckdb",
    )
    assert _spine_cte_values(sql) == ["2025-01-12", "2025-01-19", "2025-01-26"]


def test_week_sunday_spine_with_where_bounds() -> None:
    sql = _sql(
        "from orders where created_at >= '2025-01-01' and created_at <= '2025-01-31' "
        "spine by week_sunday(created_at) (# as n)",
        "duckdb",
    )
    assert _spine_cte_values(sql) == [
        "2024-12-29",
        "2025-01-05",
        "2025-01-12",
        "2025-01-19",
        "2025-01-26",
    ]


def test_visual_json_renders_unit_functions_as_function_nodes() -> None:
    out = json.loads(
        sqlglot.transpile(
            "from orders where week_sunday(created_at) >= @2025-01-01 "
            "select week_sunday(created_at) as w",
            read="asql",
            write="visual_asql",
        )[0]
    )
    steps = out[0]["transforms"]
    where = next(step for step in steps if step["type"] == "where")["condition"]
    assert where["left"] == {
        "type": "function",
        "name": "week_sunday",
        "args": [{"type": "column", "name": "created_at"}],
    }
    select = next(step for step in steps if step["type"] == "select")
    assert select["columns"][0]["expression"] == "week_sunday(created_at)"
