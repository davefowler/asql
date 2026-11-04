"""Audit C4, C7, C8: list comprehensions, spine bounds from data, fanout and ON."""

from __future__ import annotations

import duckdb
import pytest
import sqlglot

import asql
from asql.errors import ASQLCompilationError
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


def test_alias_chain_keeps_one_star_and_no_duplicate_outputs() -> None:
    """The CTE chain for non-DuckDB dialects projected the user's `*` next to
    its own (`SELECT *, *`) and re-selected every alias after a `*` that
    already carried it."""
    sql = asql.transpile(
        "from users select *, upper(name) as n, n || 'x' as nx", write="postgres"
    )[0]
    assert "*, *" not in sql
    con = duckdb.connect()
    con.sql("create table users as select 1 as id, 'a' as name, 'e' as email")
    rel = con.sql(sqlglot.transpile(sql, read="postgres", write="duckdb")[0])
    assert rel.columns == ["id", "name", "email", "n", "nx"]
    assert rel.fetchall() == [(1, "a", "e", "A", "Ax")]


def test_alias_chain_keeps_the_star_override_on_the_base() -> None:
    """`select *, upper(name) as name` excludes the source `name`; the chain's
    base must carry that exclusion or the CTE has two `name` columns."""
    sql = asql.transpile(
        "from users select *, upper(name) as name, name || '!' as shout",
        write="postgres",
        schema=_users_schema(),
    )[0]
    con = duckdb.connect()
    con.sql("create table users as select 1 as id, 'a' as name, 'e' as email")
    rel = con.sql(sqlglot.transpile(sql, read="postgres", write="duckdb")[0])
    assert rel.columns == ["id", "email", "name", "shout"]
    assert rel.fetchall() == [(1, "e", "A", "A!")]


def test_except_then_alias_chain_expands_on_postgres() -> None:
    """With a schema, nothing `EXCEPT`-shaped may survive to PostgreSQL."""
    sql = asql.transpile(
        "from users select *, upper(name) as n, n || 'x' as nx except email",
        write="postgres",
        schema=_users_schema(),
    )[0]
    assert "EXCEPT" not in sql.upper()
    con = duckdb.connect()
    con.sql("create table users as select 1 as id, 'a' as name, 'e' as email")
    rel = con.sql(sqlglot.transpile(sql, read="postgres", write="duckdb")[0])
    assert rel.columns == ["id", "name", "n", "nx"]


def _users_schema() -> Schema:
    return Schema.from_dict(
        {
            "tables": {
                "users": {
                    "columns": {"id": "INT", "name": "VARCHAR", "email": "VARCHAR"}
                }
            }
        }
    )


def test_strict_lower_bound_on_a_date_column_starts_the_spine_next_day() -> None:
    schema = Schema.from_dict(
        {
            "tables": {
                "orders": {"columns": {"d": "DATE", "ts": "TIMESTAMP", "amount": "INT"}}
            }
        }
    )
    con = duckdb.connect()
    con.sql(
        "create table orders as select date '2024-01-03' as d, timestamp '2024-01-01 09:00' as ts, 1 as amount"
    )
    sql = asql.transpile(
        "from orders where d > @2024-01-01 and d < @2024-01-05 spine by day(d) (sum(amount) as rev)",
        write="duckdb",
        schema=schema,
    )[0]
    assert len(con.sql(sql).fetchall()) == 3  # Jan 2, 3, 4
    # A timestamp column has rows later on the bound's day, so it keeps the day.
    sql = asql.transpile(
        "from orders where ts > @2024-01-01 and ts < @2024-01-05 spine by day(ts) (sum(amount) as rev)",
        write="duckdb",
        schema=schema,
    )[0]
    assert len(con.sql(sql).fetchall()) == 4


def test_spine_bounds_ignore_a_subquery_where() -> None:
    sql = asql.transpile(
        "from orders where exists (from x where d >= @2020-01-01) "
        "spine by month(d) (sum(amount) as rev)",
        write="duckdb",
    )[0]
    # Bounds come from the data, not from the subquery's own filter
    assert "GENERATE_SERIES(CAST(DATE_TRUNC('MONTH', CAST(min_d" in sql


def test_prior_and_next_take_the_query_ordering() -> None:
    """LAG/LEAD only exist as window functions; a bare `prior(x)` was invalid SQL."""
    sql = asql.transpile(
        "from sales order by sale_date select sale_date, revenue, "
        "prior(revenue) as prev, next(revenue, 2) as after",
        write="duckdb",
    )[0]
    assert "LAG(revenue, 1) OVER (ORDER BY sale_date" in sql
    assert "LEAD(revenue, 2) OVER (ORDER BY sale_date" in sql
    con = duckdb.connect()
    con.sql(
        "create table sales as select * from (values (date '2024-01-01', 1), (date '2024-01-02', 2), (date '2024-01-03', 3)) t(sale_date, revenue)"
    )
    assert [r[2] for r in con.sql(sql).fetchall()] == [None, 1, 2]


def test_prior_without_an_ordering_raises() -> None:
    with pytest.raises(ASQLCompilationError, match="prior\\(\\) needs an ordering"):
        asql.transpile(
            "from sales select revenue, prior(revenue) as prev", write="duckdb"
        )


def test_prior_with_an_explicit_over_is_kept() -> None:
    sql = asql.transpile(
        "from sales select revenue, prior(revenue) over (partition by region order by sale_date) as prev",
        write="duckdb",
    )[0]
    assert "LAG(revenue, 1) OVER (PARTITION BY region ORDER BY sale_date" in sql


def test_non_aggregate_pivot_uses_max() -> None:
    """Spec: a bare column pivots with MAX, which also works for strings."""
    sql = asql.transpile(
        "from user_settings pivot value by setting_name values ('theme', 'language') group by user_id",
        write="duckdb",
    )[0]
    assert "MAX(value)" in sql
    assert "SUM(" not in sql
