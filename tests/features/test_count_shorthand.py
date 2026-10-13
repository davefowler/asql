"""Tests for # count shorthand syntax in ASQL.

The # symbol is a shorthand for COUNT in ASQL.
Variations:
- # → COUNT(*)
- #col or # col → COUNT(col)
- ##col or ## col → COUNT(DISTINCT col)
- #(col) → COUNT(col)
- #(distinct col) → COUNT(DISTINCT col)
- uniq(col) or uniq col → COUNT(DISTINCT col)
"""

from typing import Any

import pytest

from asql.errors import ASQLResolutionError

from ..fixtures import transpile
from ..validator import ASQLValidator


class TestCountShorthandBasic(ASQLValidator):
    """Test basic # count shorthand."""

    def test_standalone_hash_to_count_star(self) -> None:
        """# becomes COUNT(*) - may be auto-aliased as 'num'."""
        for dialect in [
            "duckdb",
            "postgres",
            "mysql",
            "sqlite",
            "bigquery",
            "snowflake",
        ]:
            self.validate_contains(
                "from users select #", "COUNT(*)", "FROM", "users", dialect=dialect
            )

    def test_hash_with_alias(self) -> None:
        """# as alias becomes COUNT(*) AS alias."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite"]:
            self.validate_contains(
                "from users select # as total",
                "COUNT(*)",
                "AS",
                "total",
                "FROM",
                "users",
                dialect=dialect,
            )

    def test_hash_in_group_by(self) -> None:
        """# in GROUP BY aggregate block."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite"]:
            self.validate_contains(
                "from users group by country ( # as total )",
                "country",
                "COUNT(*)",
                "total",
                "GROUP BY",
                dialect=dialect,
            )


class TestCountShorthandColumn(ASQLValidator):
    """Test #col count shorthand for COUNT(col)."""

    def test_hash_column_no_space(self) -> None:
        """#col becomes COUNT(col)."""
        self.validate_contains(
            "from users select #email as has_email", "COUNT", "email", "has_email"
        )

    def test_hash_column_with_space(self) -> None:
        """# col becomes COUNT(col)."""
        self.validate_contains(
            "from users select # email as has_email", "COUNT", "email", "has_email"
        )

    def test_hash_parens(self) -> None:
        """#(col) becomes COUNT(col)."""
        self.validate_contains(
            "from users select #(email) as has_email", "COUNT", "email", "has_email"
        )


class TestCountDistinctShorthand(ASQLValidator):
    """Test ##col count distinct shorthand."""

    def test_double_hash_no_space(self) -> None:
        """##col becomes COUNT(DISTINCT col)."""
        self.validate_contains(
            "from orders select ##user_id as unique_customers",
            "COUNT",
            "DISTINCT",
            "user_id",
            "unique_customers",
        )

    def test_double_hash_with_space(self) -> None:
        """## col becomes COUNT(DISTINCT col)."""
        self.validate_contains(
            "from orders select ## user_id as unique_customers",
            "COUNT",
            "DISTINCT",
            "user_id",
            "unique_customers",
        )

    def test_hash_parens_distinct(self) -> None:
        """#(distinct col) becomes COUNT(DISTINCT col)."""
        self.validate_contains(
            "from orders select #(distinct user_id) as unique_customers",
            "COUNT",
            "DISTINCT",
            "user_id",
        )


class TestUniqFunction(ASQLValidator):
    """Test uniq() function for COUNT(DISTINCT col)."""

    def test_uniq_with_parens(self) -> None:
        """uniq(col) becomes COUNT(DISTINCT col)."""
        self.validate_contains(
            "from orders select uniq(user_id) as unique_customers",
            "COUNT",
            "DISTINCT",
            "user_id",
            "unique_customers",
        )

    def test_uniq_space_notation(self) -> None:
        """uniq col becomes COUNT(DISTINCT col)."""
        self.validate_contains(
            "from orders select uniq user_id as unique_customers",
            "COUNT",
            "DISTINCT",
            "user_id",
            "unique_customers",
        )

    def test_uniq_in_group_by(self) -> None:
        """uniq in GROUP BY aggregate block."""
        self.validate_contains(
            "from orders group by region ( uniq(user_id) as unique_customers )",
            "COUNT",
            "DISTINCT",
            "user_id",
            "unique_customers",
            "GROUP BY",
        )


class TestCountShorthandStar(ASQLValidator):
    """Test explicit * count shorthand."""

    def test_hash_explicit_star(self) -> None:
        """# * becomes COUNT(*) (explicit row count)."""
        self.validate_contains("from orders select # * as row_count", "COUNT(*)")

    def test_hash_star_no_space(self) -> None:
        """#* becomes COUNT(*)."""
        self.validate_contains("from orders select #* as row_count", "COUNT(*)")

    def test_hash_star_implicit_alias(self) -> None:
        """`#* name` aliases the count; the star is never a cross-join operator.

        Regression: the `* <table>` cross-join hook once intercepted this
        star, so `#* n` parsed as `COUNT(*) * n`.
        """
        self.validate_contains("from orders select #* n", "COUNT(*) AS n")
        self.validate_contains("from orders select ##* n", "COUNT(DISTINCT *) AS n")


class TestCountShorthandOrderBy(ASQLValidator):
    """Test # in ORDER BY clause."""

    def test_order_by_count_hash(self) -> None:
        """ORDER BY -# for descending count order."""
        self.validate_contains(
            "from users group by country ( # ) order by -#", "ORDER BY", "COUNT", "DESC"
        )

    def test_order_by_count_hash_alias(self) -> None:
        """ORDER BY -alias where alias is from # as alias."""
        self.validate_contains(
            "from users group by country ( # as cnt ) order by -cnt",
            "ORDER BY",
            "cnt",
            "DESC",
        )


class TestCountShorthandCrossDialect(ASQLValidator):
    """Cross-dialect tests for count shorthand."""

    def test_group_by_with_count_and_sum(self) -> None:
        """Test # combined with other aggregates."""
        for dialect in ["duckdb", "postgres", "mysql"]:
            self.validate_contains(
                "from sales group by region ( # as orders, sum(amount) as revenue )",
                "region",
                "COUNT(*)",
                "orders",
                "SUM",
                "amount",
                "revenue",
                "GROUP BY",
                dialect=dialect,
            )

    def test_double_hash_cross_dialect(self) -> None:
        """Test ## works across dialects."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite"]:
            self.validate_contains(
                "from orders select ##user_id as uniq_users",
                "COUNT",
                "DISTINCT",
                "user_id",
                dialect=dialect,
            )

    def test_uniq_cross_dialect(self) -> None:
        """Test uniq() works across dialects."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite"]:
            self.validate_contains(
                "from orders select uniq(user_id) as uniq_users",
                "COUNT",
                "DISTINCT",
                "user_id",
                dialect=dialect,
            )


def _schema() -> Any:
    from asql.schema import Column, Schema, Table

    schema = Schema()
    for name, cols in {
        "users": ["id", "name"],
        "products": ["id", "title"],
        "orders": ["id", "user_id", "status"],
        "order_items": ["id", "order_id", "product_id", "category"],
        "events": ["id", "actor", "items"],
    }.items():
        schema.add_table(Table(name=name, columns={c: Column(name=c) for c in cols}))
    schema.infer_relationships()
    return schema


def _t(query: str, schema: Any = None) -> str:
    from asql.config import CompileSettings

    return transpile(query, settings=CompileSettings(schema=schema or _schema()))


class TestCountEntityInference(ASQLValidator):
    """`# <table>` counts distinct entities via the entity's key column."""

    def test_no_schema_never_infers_entities(self) -> None:
        for name in ("clicks", "sessions", "users", "order_status"):
            sql = transpile(f"from orders select # {name}")
            assert f"COUNT({name})" in sql, sql
            assert "DISTINCT" not in sql

    def test_entity_no_space(self) -> None:
        assert "COUNT(DISTINCT user_id) AS u" in _t("from orders select #users as u")

    def test_multiple_entities(self) -> None:
        sql = _t(
            "from order_items group by category "
            "( # as lines, # orders as o, # products as p )"
        )
        assert "COUNT(*) AS lines" in sql
        assert "COUNT(DISTINCT order_id) AS o" in sql
        assert "COUNT(DISTINCT product_id) AS p" in sql

    def test_entity_auto_alias_follows_distinct_count_alias(self) -> None:
        assert "AS num_user_id" in transpile("from orders select #(distinct user_id)")
        assert "AS num_user_id" in _t("from orders select # users")

    def test_entity_with_schema_uses_relationship(self) -> None:
        from asql.config import CompileSettings

        sql = transpile(
            "from order_items select # orders",
            settings=CompileSettings(schema=_schema()),
        )
        assert "COUNT(DISTINCT order_id)" in sql

    def test_entity_with_schema_explicit_relationship_column(self) -> None:
        from asql.config import CompileSettings
        from asql.schema import Relationship

        schema = _schema()
        schema.relationships.clear()
        schema.add_relationship(
            Relationship(
                from_table="orders",
                from_column="status",
                to_table="users",
                to_column="id",
                source="explicit",
            )
        )
        sql = transpile(
            "from orders select # users", settings=CompileSettings(schema=schema)
        )
        assert "COUNT(DISTINCT status)" in sql

    def test_from_table_itself_counts_distinct_primary_key(self) -> None:
        from asql.config import CompileSettings

        assert "COUNT(DISTINCT id)" in transpile(
            "from users group by name ( # users )",
            settings=CompileSettings(schema=_schema()),
        )

    def test_schema_column_wins_over_table_name(self) -> None:
        """`items` is a column of events, so `# items` stays COUNT(items)."""
        from asql.config import CompileSettings

        sql = transpile(
            "from events select # items", settings=CompileSettings(schema=_schema())
        )
        assert "COUNT(items)" in sql
        assert "DISTINCT" not in sql

    def test_singular_name_is_column_count_without_schema(self) -> None:
        assert "COUNT(email)" in transpile("from users select # email")

    def test_cte_source_keeps_column_count(self) -> None:
        sql = _t("from orders stash as base select # status")
        assert "COUNT(status)" in sql and "DISTINCT" not in sql

    def test_schema_table_name_over_unknown_source_keeps_column_count(self) -> None:
        for query in (
            "from orders stash as base select # users",
            "from orders extend amount * 2 as dbl group by status ( # users )",
        ):
            sql = _t(query)
            assert "COUNT(users)" in sql and "DISTINCT" not in sql, sql

    def test_self_join_entity_is_ambiguous(self) -> None:
        with pytest.raises(ASQLResolutionError, match="Ambiguous.*u, m"):
            _t("from users u & users m on u.id = m.id select # users")

    def test_partial_schema_unknown_table_keeps_column_count(self) -> None:
        from asql.config import CompileSettings
        from asql.schema import Column, Schema, Table

        schema = Schema()
        schema.add_table(Table(name="orders", columns={"id": Column(name="id")}))
        sql = transpile(
            "from orders & mystery on id select # foo",
            settings=CompileSettings(schema=schema),
        )
        assert "COUNT(foo)" in sql

    def test_explicit_relationship_beats_inferred(self) -> None:
        from asql.schema import Relationship

        schema = _schema()
        schema.add_relationship(
            Relationship(
                from_table="orders",
                from_column="status",
                to_table="users",
                to_column="id",
                source="explicit",
            )
        )
        assert "COUNT(DISTINCT status)" in _t(
            "from orders select # users", schema=schema
        )

    def test_ambiguous_same_tier_errors(self) -> None:
        from asql.schema import Relationship

        schema = _schema()
        schema.relationships.clear()
        for col in ("user_id", "status"):
            schema.add_relationship(
                Relationship("orders", col, "users", "id", source="explicit")
            )
        with pytest.raises(ASQLResolutionError, match="Ambiguous"):
            _t("from orders select # users", schema=schema)

    def test_key_owned_by_joined_table_is_qualified(self) -> None:
        sql = _t("from users & orders on users.id = orders.user_id select # orders")
        assert "COUNT(DISTINCT orders.id)" in sql
        sql = _t(
            "from users & order_items on users.id = order_items.order_id "
            "select # orders"
        )
        assert "COUNT(DISTINCT order_items.order_id)" in sql

    def test_parenthesized_name_is_always_a_column(self) -> None:
        assert "COUNT(users)" in transpile("from orders select #(users)")

    def test_explicit_distinct_still_works(self) -> None:
        self.validate_contains(
            "from orders select #(distinct product_id) as p",
            "COUNT(DISTINCT product_id)",
        )

    def test_entity_missing_key_with_schema_errors(self) -> None:
        from asql.config import CompileSettings

        with pytest.raises(ASQLResolutionError, match=r"products.*#\(distinct"):
            transpile(
                "from orders select # products",
                settings=CompileSettings(schema=_schema()),
            )

    def test_unknown_name_with_schema_errors(self) -> None:
        from asql.config import CompileSettings

        with pytest.raises(
            ASQLResolutionError, match=r"typo.*orders.*#\(col\).*#\(distinct"
        ):
            transpile(
                "from orders select # typo",
                settings=CompileSettings(schema=_schema()),
            )

    def test_entity_with_joins_qualifies_key(self) -> None:
        sql = _t("from orders & users on orders.user_id = users.id select # users as n")
        assert "COUNT(DISTINCT users.id)" in sql


class TestCountEntityExecution:
    def test_distinct_entities_counted(self) -> None:
        import duckdb

        conn = duckdb.connect(":memory:")
        conn.execute("CREATE TABLE orders (id INT, user_id INT, status TEXT)")
        conn.execute(
            "INSERT INTO orders VALUES (1,10,'a'),(2,10,'a'),(3,11,'a'),(4,12,'b')"
        )
        sql = _t(
            "from orders group by status "
            "( # as total_orders, # users as unique_customers ) order by status"
        )
        assert conn.execute(sql).fetchall() == [("a", 3, 2), ("b", 1, 1)]
        conn.close()
