"""Lesser fanout findings from ai_notes/audit-2026-10-21.md, executed on DuckDB."""

from __future__ import annotations

import duckdb
import pytest

import asql

from .test_execution import _fanout_schema

_JOIN = "from orders & order_items on orders.order_id = order_items.order_id "
_REVERSE = "from order_items & orders on order_items.order_id = orders.order_id "


def _sql(query: str) -> str:
    return asql.transpile(query, write="duckdb", schema=_fanout_schema())[0]


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.sql(
        "create table orders as select * from (values (1, 10, 5.0), (2, 10, 7.0), "
        "(3, 20, 1.0)) t(order_id, customer_id, shipping_cost)"
    )
    con.sql(
        "create table order_items as select * from (values (1, 1, 2), (1, 2, 3), "
        "(2, 3, 1)) t(order_id, item_id, quantity)"
    )
    return con


def test_collapsed_join_still_warns_about_count_star(con) -> None:
    """Collapsing the many side to DISTINCT keys changes what `count(*)`
    counts (orders, not joined rows), so the COUNT(*) warning stays."""
    sql = _sql(_JOIN + "group by orders.customer_id (count(*) as n)")
    assert "collapsed order_items" in sql
    assert "COUNT(*) counts joined rows" in sql
    assert "multiplies rows" not in sql
    assert dict(con.sql(sql).fetchall()) == {10: 2}


def test_collapsed_join_does_not_warn_about_multiplying(con) -> None:
    sql = _sql(_JOIN + "group by orders.customer_id (sum(orders.shipping_cost) as s)")
    assert "collapsed order_items" in sql
    assert "multiplies rows" not in sql
    assert dict(con.sql(sql).fetchall()) == {10: 12.0}


def test_skipped_protection_still_warns_about_inflation(con) -> None:
    sql = _sql(
        _JOIN + "group by orders.customer_id, order_items.item_id "
        "(sum(orders.shipping_cost) as s)"
    )
    assert "protection skipped" in sql
    assert "join to order_items multiplies rows" in sql


def test_stage2_protection_sees_through_group_key_aliases(con) -> None:
    plain = _sql(
        _REVERSE + "group by orders.customer_id (sum(orders.shipping_cost) as ship, "
        "sum(order_items.quantity) as qty)"
    )
    aliased = _sql(
        _REVERSE
        + "group by orders.customer_id as cust (sum(orders.shipping_cost) as ship, "
        "sum(order_items.quantity) as qty)"
    )
    assert "re-aggregated through order_items.order_id" in aliased
    assert con.sql(aliased).columns == ["cust", "ship", "qty"]
    assert sorted(con.sql(aliased).fetchall()) == sorted(con.sql(plain).fetchall())
    assert sorted(con.sql(aliased).fetchall()) == [(10, 12.0, 6)]
