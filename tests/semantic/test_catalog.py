"""Metrics and attributes surface through ``information_schema.columns``."""

from typing import Any

import duckdb
import pytest

from asql.config import CompileSettings
from asql.schema import Schema

from ..fixtures import transpile
from .test_execution import SEED, _rows, _settings

TRANSACTIONS_COLUMNS = [
    ("transaction_id", "INTEGER"),
    ("created_at", "TIMESTAMP"),
    ("buyer_id", "INTEGER"),
    ("seller_id", "INTEGER"),
    ("amount", "INTEGER"),
    ("status", "VARCHAR"),
    ("volume", "METRIC"),
    ("transaction_count", "METRIC"),
    ("cn_volume", "METRIC"),
    ("aov", "METRIC"),
    ("aov_x100", "METRIC"),
    ("buyer.email", "TEXT"),
    ("buyer.country", "TEXT"),
    ("buyer.country_lower", "UNKNOWN"),
    ("buyer.theme", "TEXT"),
    ("seller.email", "TEXT"),
    ("seller.country", "TEXT"),
    ("seller.country_lower", "UNKNOWN"),
    ("seller.theme", "TEXT"),
]


@pytest.fixture(scope="module")
def con() -> Any:
    connection = duckdb.connect()
    connection.execute(SEED)
    return connection


def _run(con: Any, query: str, dialect: str = "duckdb") -> list[tuple[Any, ...]]:
    return _rows(con, transpile(query, dialect=dialect, settings=_settings()))


def test_columns_of_a_model_include_metrics_and_attributes(con: Any) -> None:
    rows = _run(
        con,
        'from information_schema.columns where table_name == "transactions" '
        "select column_name, data_type",
    )
    assert rows == sorted(TRANSACTIONS_COLUMNS, key=repr)


def test_virtual_rows_count_toward_group_by(con: Any) -> None:
    rows = _run(
        con,
        'from information_schema.columns where table_schema == "main" '
        "group by table_name ( # as n )",
    )
    assert rows == sorted(
        [
            ("transactions", 19),
            ("user_profiles", 4),
            ("user_settings", 5),
            ("line_items", 4),
        ],
        key=repr,
    )


def test_order_and_limit_apply_to_virtual_rows(con: Any) -> None:
    sql = transpile(
        'from information_schema.columns where table_name == "transactions" '
        "select column_name order by column_name limit 3",
        settings=_settings(),
    )
    assert con.execute(sql).fetchall() == [("amount",), ("aov",), ("aov_x100",)]


def test_alias_and_select_star_keep_working(con: Any) -> None:
    rows = _run(
        con,
        'from information_schema.columns as c where c.table_name == "line_items"',
    )
    names = sorted(row[3] for row in rows)
    assert names == ["item_count", "line_item_id", "quantity", "transaction_id"]
    assert all(len(row) == 8 for row in rows)


def test_virtual_rows_inherit_catalog_and_schema(con: Any) -> None:
    rows = _run(
        con,
        'from information_schema.columns where column_name == "volume" '
        "select table_catalog, table_schema, table_name, is_nullable",
    )
    assert rows == [("memory", "main", "transactions", "YES")]


def test_qualified_information_schema_keeps_qualifier() -> None:
    sql = transpile(
        "from mydataset.INFORMATION_SCHEMA.COLUMNS",
        dialect="bigquery",
        settings=_settings(),
    )
    assert "FROM mydataset.INFORMATION_SCHEMA.COLUMNS" in sql
    assert "FROM mydataset.INFORMATION_SCHEMA.TABLES AS t" in sql
    assert "AS COLUMNS" in sql


def test_tables_view_and_graphless_schema_are_untouched() -> None:
    assert (
        transpile("from information_schema.tables", settings=_settings())
        == "SELECT * FROM information_schema.tables"
    )
    plain = CompileSettings(schema=Schema.from_dict({"tables": {"t": ["a"]}}))
    assert (
        transpile("from information_schema.columns", settings=plain)
        == "SELECT * FROM information_schema.columns"
    )
