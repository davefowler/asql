"""Audit P4, P5, P6, P9: auto-alias, first() in aggregate blocks, except after
a join, and `when … is null`."""

from __future__ import annotations

import pytest

from asql.errors import ASQLCompilationError, ASQLDialectError

from .fixtures import transpile


# P4 ---------------------------------------------------------------------------
def test_auto_alias_stays_out_of_function_arguments() -> None:
    assert transpile('from t select concat(upper(first), " ", last) as n') == (
        "SELECT UPPER(first) || ' ' || last AS n FROM t"
    )


def test_auto_alias_stays_out_of_string_operator_arguments() -> None:
    assert transpile("from t where name contains lower(other)") == (
        "SELECT * FROM t WHERE name LIKE '%' || LOWER(other) || '%'"
    )


def test_auto_alias_stays_out_of_in_lists_and_explode() -> None:
    assert transpile('from t where name in (lower(a), "b")') == (
        "SELECT * FROM t WHERE name IN (LOWER(a), 'b')"
    )
    assert transpile("from posts explode split(tags_csv, ',') as tag select tag") == (
        "SELECT tag FROM posts CROSS JOIN UNNEST(STR_SPLIT(tags_csv, ',')) AS tag"
    )


def test_auto_alias_still_names_projections_and_pivot_aggregates() -> None:
    assert transpile("from t select upper(name)") == (
        "SELECT UPPER(name) AS upper_name FROM t"
    )
    assert "AS sum_amount" in transpile(
        'from orders pivot sum(amount) by status values ("a", "b") group by customer_id'
    )


# P5 ---------------------------------------------------------------------------
def test_first_in_an_aggregate_block_is_an_aggregate() -> None:
    assert transpile(
        "from t group by customer_id ( first(order_id order by -order_date) as latest, # as n )"
    ) == (
        "SELECT customer_id, ARG_MAX(order_id, order_date) AS latest, COUNT(*) AS n "
        "FROM t GROUP BY customer_id"
    )
    assert (
        transpile(
            "from t group by customer_id ( last(order_id order by -order_date) as earliest )"
        )
        == "SELECT customer_id, ARG_MIN(order_id, order_date) AS earliest FROM t GROUP BY customer_id"
    )
    assert (
        transpile(
            "from t group by customer_id ( arg_max(order_id, order_date) as latest )"
        )
        == "SELECT customer_id, ARG_MAX(order_id, order_date) AS latest FROM t GROUP BY customer_id"
    )


def test_first_in_an_aggregate_block_on_postgres_uses_array_agg() -> None:
    assert transpile(
        "from t group by customer_id ( first(order_id order by -order_date) as latest )",
        dialect="postgres",
    ) == (
        "SELECT customer_id, (ARRAY_AGG(order_id ORDER BY order_date DESC NULLS LAST))[1] "
        "AS latest FROM t GROUP BY customer_id"
    )


def test_first_in_an_aggregate_block_on_mysql_is_refused() -> None:
    with pytest.raises(ASQLDialectError, match="arg_max"):
        transpile(
            "from t group by customer_id ( first(order_id order by -order_date) as latest )",
            dialect="mysql",
        )


def test_first_outside_an_aggregate_block_is_still_a_window() -> None:
    assert transpile("from t select first(x order by y) over g as f") == (
        "SELECT FIRST_VALUE(x) OVER (PARTITION BY g ORDER BY y NULLS FIRST) AS f FROM t"
    )


# P6 ---------------------------------------------------------------------------
def test_except_after_a_join_keeps_its_qualifier() -> None:
    assert transpile(
        "from users & orders on users.id = orders.user_id "
        "except users.password_hash, orders.internal_notes"
    ) == (
        "SELECT users.* EXCLUDE (password_hash), orders.* EXCLUDE (internal_notes) "
        "FROM users INNER JOIN orders ON users.id = orders.user_id"
    )


def test_rename_after_a_join_keeps_its_qualifier() -> None:
    assert transpile(
        "from users & orders on users.id = orders.user_id rename users.id as user_id"
    ) == (
        "SELECT users.* EXCLUDE (id), orders.*, users.id AS user_id "
        "FROM users INNER JOIN orders ON users.id = orders.user_id"
    )


def test_unqualified_except_after_a_join_is_an_error() -> None:
    with pytest.raises(ASQLCompilationError, match="which table"):
        transpile(
            "from users & orders on users.id = orders.user_id except password_hash"
        )


# P9 ---------------------------------------------------------------------------
def test_when_is_null() -> None:
    assert transpile("from t select when status is null then 1, otherwise 0 as z") == (
        "SELECT CASE WHEN status IS NULL THEN 1 ELSE 0 END AS z FROM t"
    )
    assert (
        transpile("from t select when status is not null then 1, otherwise 0 as z")
        == "SELECT CASE WHEN NOT status IS NULL THEN 1 ELSE 0 END AS z FROM t"
    )


def test_when_base_can_be_any_expression() -> None:
    assert transpile(
        'from t select when upper(status) is "A" then 1, is "B" then 2, otherwise 0 as z'
    ) == (
        "SELECT CASE WHEN UPPER(status) = 'A' THEN 1 WHEN UPPER(status) = 'B' THEN 2 "
        "ELSE 0 END AS z FROM t"
    )
    assert transpile('from t select when a.b is "x" then 1, otherwise 0 as z') == (
        "SELECT CASE WHEN a.b = 'x' THEN 1 ELSE 0 END AS z FROM t"
    )
