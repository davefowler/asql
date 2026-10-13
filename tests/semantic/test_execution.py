"""Semantic queries executed on DuckDB, checked against hand-written SQL."""

from pathlib import Path
from typing import Any

import pytest

from asql.config import CompileSettings
from asql.schema import Schema
from asql.semantic import load_graph

from ..fixtures import transpile

duckdb = pytest.importorskip("duckdb")

GRAPH_PATH = Path(__file__).parent / "marketplace.graph.yaml"

SEED = """
CREATE TABLE user_profiles (user_id INT, email TEXT, country TEXT);
INSERT INTO user_profiles VALUES
  (1, 'a@x.com', 'US'), (2, 'b@x.com', 'CN'), (3, 'c@x.com', 'US');
CREATE TABLE user_settings (user_id INT, theme TEXT);
INSERT INTO user_settings VALUES (1, 'dark'), (2, 'light');
CREATE TABLE transactions (
  transaction_id INT, created_at TIMESTAMP, buyer_id INT, seller_id INT,
  amount INT, status TEXT
);
INSERT INTO transactions VALUES
  (1, '2026-01-05', 1, 2, 100, 'completed'),
  (2, '2026-01-20', 2, 1, 50, 'completed'),
  (3, '2026-02-03', 2, 3, 30, 'refunded'),
  (4, '2026-02-10', 3, 1, 70, 'completed'),
  (5, '2026-02-11', 99, 1, 20, 'completed');
CREATE TABLE line_items (line_item_id INT, transaction_id INT, quantity INT);
INSERT INTO line_items VALUES
  (1, 1, 2), (2, 1, 1), (3, 2, 5), (4, 4, 1), (5, 4, 1), (6, 4, 3);
"""


@pytest.fixture(scope="module")
def con() -> Any:
    connection = duckdb.connect()
    connection.execute(SEED)
    return connection


def _settings() -> CompileSettings:
    return CompileSettings(schema=Schema.from_graph(load_graph(GRAPH_PATH)))


def _rows(con: Any, sql: str) -> list[tuple[Any, ...]]:
    return sorted(con.execute(sql).fetchall(), key=repr)


def _assert_same(con: Any, query: str, expected_sql: str) -> None:
    actual = _rows(con, transpile(query, settings=_settings()))
    assert actual == _rows(con, expected_sql)


def test_grand_total(con: Any) -> None:
    _assert_same(
        con,
        "from transactions select volume, transaction_count, aov",
        "SELECT SUM(amount), COUNT(*), SUM(amount) / COUNT(*) FROM transactions",
    )


def test_by_buyer_country_keeps_unmatched_buyers(con: Any) -> None:
    _assert_same(
        con,
        "from transactions group by buyer.country ( volume, aov )",
        """
        SELECT p.country, SUM(t.amount), SUM(t.amount) / COUNT(*)
        FROM transactions t LEFT JOIN user_profiles p ON t.buyer_id = p.user_id
        GROUP BY p.country
        """,
    )
    total = transpile("from transactions select volume", settings=_settings())
    by_country = transpile(
        "from transactions group by buyer.country ( volume )", settings=_settings()
    )
    grand = con.execute(total).fetchone()[0]
    assert sum(row[1] for row in con.execute(by_country).fetchall()) == grand


def test_buyer_and_seller_country(con: Any) -> None:
    _assert_same(
        con,
        "from transactions group by buyer.country, seller.country ( volume )",
        """
        SELECT b.country, s.country, SUM(t.amount)
        FROM transactions t
        LEFT JOIN user_profiles b ON t.buyer_id = b.user_id
        LEFT JOIN user_profiles s ON t.seller_id = s.user_id
        GROUP BY b.country, s.country
        """,
    )


def test_attributes_from_two_models_of_one_entity(con: Any) -> None:
    _assert_same(
        con,
        "from transactions group by buyer.country, buyer.theme ( volume )",
        """
        SELECT p.country, st.theme, SUM(t.amount)
        FROM transactions t
        LEFT JOIN user_profiles p ON t.buyer_id = p.user_id
        LEFT JOIN user_settings st ON t.buyer_id = st.user_id
        GROUP BY p.country, st.theme
        """,
    )


def test_filtered_metric(con: Any) -> None:
    _assert_same(
        con,
        "from transactions group by status ( cn_volume, volume )",
        """
        SELECT t.status,
               SUM(t.amount) FILTER (WHERE p.country = 'CN'),
               SUM(t.amount)
        FROM transactions t LEFT JOIN user_profiles p ON t.buyer_id = p.user_id
        GROUP BY t.status
        """,
    )


def test_pre_aggregation_filter_on_attribute(con: Any) -> None:
    _assert_same(
        con,
        'from transactions where buyer.country = "US" group by status ( volume )',
        """
        SELECT t.status, SUM(t.amount)
        FROM transactions t LEFT JOIN user_profiles p ON t.buyer_id = p.user_id
        WHERE p.country = 'US'
        GROUP BY t.status
        """,
    )


def test_user_join_to_many_side_does_not_inflate_metric(con: Any) -> None:
    _assert_same(
        con,
        "from transactions & line_items "
        "on transactions.transaction_id = line_items.transaction_id "
        "group by buyer.country ( volume )",
        """
        SELECT p.country, SUM(t.amount)
        FROM transactions t LEFT JOIN user_profiles p ON t.buyer_id = p.user_id
        WHERE t.transaction_id IN (SELECT transaction_id FROM line_items)
        GROUP BY p.country
        """,
    )


def test_derived_of_derived(con: Any) -> None:
    _assert_same(
        con,
        "from transactions group by status ( aov_x100 )",
        "SELECT status, (SUM(amount) / COUNT(*)) * 100 FROM transactions "
        "GROUP BY status",
    )


def test_star_with_except_and_attribute_filter(con: Any) -> None:
    _assert_same(
        con,
        'from transactions where buyer.country = "US" except buyer_id',
        """
        SELECT t.transaction_id, t.created_at, t.seller_id, t.amount, t.status
        FROM transactions t LEFT JOIN user_profiles p ON t.buyer_id = p.user_id
        WHERE p.country = 'US'
        """,
    )


def test_count_metric_over_many_side_join_counts_home_rows(con: Any) -> None:
    _assert_same(
        con,
        "from transactions & line_items "
        "on transactions.transaction_id = line_items.transaction_id "
        "group by status ( transaction_count )",
        """
        SELECT t.status, COUNT(*) FROM transactions t
        WHERE t.transaction_id IN (SELECT transaction_id FROM line_items)
        GROUP BY t.status
        """,
    )
