"""Audit C4, C7, C8: list comprehensions, spine bounds from data, fanout and ON."""

from __future__ import annotations

import duckdb

import asql
from asql.schema import Column, Relationship, Schema, Table

from .fixtures import transpile


# C4 ---------------------------------------------------------------------------
def test_duckdb_list_comprehension_keeps_nested_parentheses() -> None:
    assert transpile(
        "from data select [x * 2 for x in numbers if abs(x) > 1] as d"
    ) == ("SELECT [x * 2 FOR x IN numbers IF ABS(x) > 1] AS d FROM data")
    assert transpile(
        "from data select [coalesce(x, 0) for x in numbers if (x > 0)] as d"
    ) == ("SELECT [COALESCE(x, 0) FOR x IN numbers IF (x > 0)] AS d FROM data")


def test_duckdb_list_comprehension_over_a_qualified_array() -> None:
    assert transpile("from data select [x for x in data.numbers] as d") == (
        "SELECT [x FOR x IN data.numbers] AS d FROM data"
    )


def test_list_comprehension_elsewhere_is_array_select() -> None:
    assert transpile(
        "from data select [x * 2 for x in numbers] as d", dialect="postgres"
    ) == ("SELECT ARRAY(SELECT x * 2 FROM UNNEST(numbers) AS x) AS d FROM data")


# C7 ---------------------------------------------------------------------------
def test_data_bounded_date_spine_on_bigquery_and_snowflake() -> None:
    bq = transpile(
        "from orders spine by month(order_date) (sum(amount) as s)", dialect="bigquery"
    )
    assert (
        "GENERATE_DATE_ARRAY" in bq
        and "MIN(order_date)" in bq
        and "DISTINCT DATE_TRUNC(order_date" not in bq
    )
    sf = transpile(
        "from orders spine by month(order_date) (sum(amount) as s)", dialect="snowflake"
    )
    assert "GENERATOR" in sf and "MIN(order_date)" in sf


def test_data_bounded_date_spine_is_a_series_everywhere() -> None:
    for dialect in ("mysql", "spark", "trino", "postgres"):
        sql = transpile(
            "from orders spine by month(order_date) (sum(amount) as s)", dialect=dialect
        )
        assert "MIN(order_date)" in sql and "DISTINCT DATE_TRUNC" not in sql.replace(
            "DISTINCT DATE_TRUNC(d", ""
        )


# C8 ---------------------------------------------------------------------------
def _chain_schema() -> Schema:
    schema = Schema()
    orders = Table(name="orders")
    orders.add_column(Column(name="order_id", primary_key=True))
    schema.add_table(orders)
    items = Table(name="order_items")
    for name in ("order_id", "product_id", "quantity"):
        items.add_column(Column(name=name))
    schema.add_table(items)
    products = Table(name="products")
    products.add_column(Column(name="id", primary_key=True))
    products.add_column(Column(name="name"))
    schema.add_table(products)
    schema.add_relationship(
        Relationship(
            from_table="order_items",
            from_column="order_id",
            to_table="orders",
            to_column="order_id",
            source="explicit",
        )
    )
    schema.add_relationship(
        Relationship(
            from_table="order_items",
            from_column="product_id",
            to_table="products",
            to_column="id",
            source="explicit",
        )
    )
    return schema


def test_fanout_keeps_columns_a_later_join_needs() -> None:
    con = duckdb.connect()
    con.sql("create table orders as select * from (values (1), (2)) t(order_id)")
    con.sql(
        "create table products as select * from (values (10, 'a'), (11, 'b')) t(id, name)"
    )
    con.sql(
        "create table order_items as select * from (values (1, 10, 2), (1, 11, 1), (2, 10, 3)) "
        "t(order_id, product_id, quantity)"
    )
    sql = asql.transpile(
        "from orders join order_items on orders.order_id = order_items.order_id "
        "join products on order_items.product_id = products.id "
        "group by products.name (sum(order_items.quantity) as qty)",
        write="duckdb",
        schema=_chain_schema(),
    )[0]
    assert sorted(con.sql(sql).fetchall()) == [("a", 5), ("b", 1)]


def test_timestamp_literal_is_a_cast_on_postgres() -> None:
    """PostgreSQL has no TIMESTAMP(...) function; the literal must be a cast."""
    sql = asql.transpile("from t where ts < @2024-01-03T06:00:00", write="postgres")[0]
    assert sql == "SELECT * FROM t WHERE ts < CAST('2024-01-03 06:00:00' AS TIMESTAMP)"
