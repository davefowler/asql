"""Tests for JOIN syntax in ASQL.

Join operators:
- & → INNER JOIN
- &? → LEFT JOIN
- ?& → RIGHT JOIN
- ?&? → FULL OUTER JOIN
- * → CROSS JOIN

Also supports traditional JOIN keywords.
"""

from ..validator import ASQLValidator


class TestJoinOperators(ASQLValidator):
    """Test new ASQL join operator syntax."""

    def test_inner_join_operator(self) -> None:
        """& operator for INNER JOIN."""
        # JOIN may generate table-qualified SELECT (users.*, orders.*)
        for dialect in ["duckdb", "postgres", "mysql"]:
            self.validate_contains(
                "from users & orders on users.id = orders.user_id",
                "JOIN",
                "users",
                "orders",
                "ON",
                "users.id",
                "orders.user_id",
                dialect=dialect,
            )

    def test_left_join_operator(self) -> None:
        """&? operator for LEFT JOIN."""
        self.validate_contains(
            "from users &? orders on users.id = orders.user_id",
            "LEFT",
            "JOIN",
            "users",
            "orders",
            "ON",
        )

    def test_right_join_operator(self) -> None:
        """?& operator for RIGHT JOIN."""
        self.validate_contains(
            "from users ?& orders on users.id = orders.user_id", "RIGHT", "JOIN"
        )

    def test_full_outer_join_operator(self) -> None:
        """?&? operator for FULL OUTER JOIN."""
        self.validate_contains(
            "from users ?&? orders on users.id = orders.user_id", "FULL"
        )

    def test_cross_join_operator(self) -> None:
        """* operator for CROSS JOIN."""
        self.validate_contains("from users * roles", "CROSS JOIN", "users", "roles")


class TestJoinWithAlias(ASQLValidator):
    """Test joins with table aliases."""

    def test_left_join_with_alias(self) -> None:
        """LEFT JOIN with AS alias."""
        self.validate_contains(
            "from accounts &? users as owner on accounts.owner_id = owner.id",
            "LEFT",
            "JOIN",
            "users",
            "AS",
            "owner",
        )

    def test_self_join_with_aliases(self) -> None:
        """Self-join with different aliases."""
        self.validate_contains(
            "from employees as e1 &? employees as e2 on e1.manager_id = e2.id",
            "LEFT",
            "JOIN",
            "employees",
        )


class TestChainedJoins(ASQLValidator):
    """Test multiple joins in a single query."""

    def test_chained_inner_joins(self) -> None:
        """Multiple INNER JOINs."""
        self.validate_contains(
            "from orders & customers on orders.customer_id = customers.id & order_items on orders.id = order_items.order_id",
            "JOIN",
            "customers",
            "order_items",
        )

    def test_mixed_join_types(self) -> None:
        """Mix of INNER and LEFT joins."""
        self.validate_contains(
            "from orders & customers on orders.customer_id = customers.id &? shipping on orders.id = shipping.order_id",
            "JOIN",
            "LEFT",
            "JOIN",
        )


class TestJoinWithClauses(ASQLValidator):
    """Test joins combined with other clauses."""

    def test_join_with_where(self) -> None:
        """JOIN with WHERE clause."""
        self.validate_contains(
            'from users &? orders on users.id = orders.user_id where orders.status = "active"',
            "LEFT",
            "JOIN",
            "WHERE",
            "status",
        )

    def test_join_with_group_by(self) -> None:
        """JOIN with GROUP BY."""
        self.validate_contains(
            "from users &? orders on users.id = orders.user_id group by users.country (sum(orders.amount) as total)",
            "LEFT",
            "JOIN",
            "GROUP BY",
            "SUM",
        )


class TestFKColumnShorthand(ASQLValidator):
    """Test FK column shorthand syntax.

    Note: Without schema, FK shorthand just preserves the column reference.
    Full expansion (e.g., owner_id → accounts.owner_id = users.id) requires schema.
    See TestSchemaAwareFKShorthand for schema-aware tests.
    """

    def test_fk_column_without_schema_raises(self) -> None:
        """Without a schema or infer_join_keys, `on <col>` is never guessed."""
        import pytest

        from asql.errors import ASQLResolutionError

        from ..fixtures import transpile

        for query in (
            "from accounts & users on owner_id",
            "from accounts &? users as u on owner_id",
        ):
            with pytest.raises(ASQLResolutionError) as excinfo:
                transpile(query)
            message = str(excinfo.value)
            assert "owner_id" in message and "infer_join_keys" in message, message

    def test_fk_column_with_infer_join_keys_resolves_direction(self) -> None:
        import pytest

        from asql.config import CompileSettings
        from asql.errors import ASQLResolutionError

        from ..fixtures import transpile

        settings = CompileSettings(infer_join_keys=True)
        for query, on in [
            ("from orders & users on user_id", "orders.user_id = users.id"),
            ("from users & orders on user_id", "orders.user_id = users.id"),
        ]:
            assert f"ON {on}" in transpile(query, settings=settings), query
        # Neither table name matches the column prefix: ambiguous, so error.
        with pytest.raises(ASQLResolutionError):
            transpile("from accounts & users on owner_id", settings=settings)


class TestTraditionalJoinSyntax(ASQLValidator):
    """Test backward compatibility with traditional JOIN keywords."""

    def test_traditional_join(self) -> None:
        """Traditional JOIN keyword."""
        self.validate_contains(
            "from users join orders on users.id = orders.user_id",
            "JOIN",
            "users",
            "orders",
        )

    def test_traditional_left_join(self) -> None:
        """Traditional LEFT JOIN keyword."""
        self.validate_contains(
            "from users left join orders on users.id = orders.user_id", "LEFT", "JOIN"
        )


class TestSchemaAwareFKShorthand(ASQLValidator):
    """Test schema-aware FK column expansion in JOIN conditions."""

    def test_fk_uses_schema_pk_not_id(self) -> None:
        """FK shorthand uses actual primary key from schema, not just 'id'."""
        from asql.config import CompileSettings
        from asql.schema import Column, Schema, Table

        from ..fixtures import transpile

        # Create schema where users has user_id as PK (not 'id')
        schema = Schema()
        users = Table(name="users")
        users.add_column(Column(name="user_id", primary_key=True))
        users.add_column(Column(name="name"))
        schema.add_table(users)

        orders = Table(name="orders")
        orders.add_column(Column(name="id"))
        orders.add_column(Column(name="user_id"))  # FK to users
        schema.add_table(orders)

        settings = CompileSettings(schema=schema)
        sql = transpile("from orders & users on user_id", settings=settings)

        # Should use user_id (the actual PK) not assume 'id'
        assert "users.user_id" in sql.lower(), f"Expected users.user_id in: {sql}"
        assert "orders.user_id" in sql.lower(), f"Expected orders.user_id in: {sql}"

    def test_fk_detects_column_on_right_table(self) -> None:
        """Schema helps detect when FK is on the right table, not left."""
        from asql.config import CompileSettings
        from asql.schema import Column, Schema, Table

        from ..fixtures import transpile

        schema = Schema()
        users = Table(name="users")
        users.add_column(Column(name="id", primary_key=True))
        users.add_column(Column(name="name"))
        schema.add_table(users)

        customers = Table(name="customers")
        customers.add_column(Column(name="id", primary_key=True))
        customers.add_column(Column(name="user_id"))  # FK to users - on the RIGHT table
        schema.add_table(customers)

        settings = CompileSettings(schema=schema)
        sql = transpile("from users & customers on user_id", settings=settings)

        # Schema should detect that user_id is on customers (right), not users (left)
        assert "customers.user_id" in sql.lower(), (
            f"Expected customers.user_id in: {sql}"
        )
        assert "users.id" in sql.lower(), f"Expected users.id in: {sql}"

    def test_fk_without_schema_raises(self) -> None:
        """Without schema, FK shorthand is not guessed."""
        import pytest

        from asql.errors import ASQLResolutionError

        from ..fixtures import transpile

        with pytest.raises(ASQLResolutionError, match="user_id"):
            transpile("from orders & users on user_id")

    def test_fk_schema_with_custom_pk_name(self) -> None:
        """FK shorthand with non-standard primary key name."""
        from asql.config import CompileSettings
        from asql.schema import Column, Schema, Table

        from ..fixtures import transpile

        schema = Schema()
        products = Table(name="products")
        products.add_column(Column(name="pk", primary_key=True))
        products.add_column(Column(name="name"))
        schema.add_table(products)

        order_items = Table(name="order_items")
        order_items.add_column(Column(name="id", primary_key=True))
        order_items.add_column(Column(name="product_pk"))  # FK uses pk naming
        schema.add_table(order_items)

        settings = CompileSettings(schema=schema)
        sql = transpile("from order_items & products on product_pk", settings=settings)

        # Should use 'pk' as the primary key, not 'id'
        assert "products.pk" in sql.lower(), f"Expected products.pk in: {sql}"
        assert "order_items.product_pk" in sql.lower(), (
            f"Expected order_items.product_pk in: {sql}"
        )


class TestAutoJoin(ASQLValidator):
    """Test automatic join condition inference."""

    def test_auto_join_with_infer_join_keys(self) -> None:
        """infer_join_keys guesses `{table}_id` = `id` when there is no schema."""
        from asql.config import CompileSettings

        from ..fixtures import transpile

        settings = CompileSettings(infer_join_keys=True)
        sql = transpile("from orders & users", settings=settings)

        assert "ON orders.user_id = users.id" in sql, sql

    def test_auto_join_with_schema_relationship(self) -> None:
        """Auto-infer join condition from schema relationship."""
        from asql.config import CompileSettings
        from asql.schema import Relationship, Schema, Table

        from ..fixtures import transpile

        schema = Schema()
        schema.add_table(Table.from_column_list("orders", ["id", "customer_id"]))
        schema.add_table(Table.from_column_list("customers", ["id", "name"]))
        schema.add_relationship(
            Relationship(
                from_table="orders",
                from_column="customer_id",
                to_table="customers",
                to_column="id",
                source="explicit",
            )
        )

        settings = CompileSettings(schema=schema)
        sql = transpile("from orders & customers", settings=settings)

        # Should use explicit relationship
        assert "JOIN" in sql.upper()
        assert "orders.customer_id" in sql.lower()
        assert "customers.id" in sql.lower()

    def test_auto_join_with_inferred_relationship(self) -> None:
        """Auto-infer join from inferred schema relationship."""
        from asql.config import CompileSettings
        from asql.schema import Schema, Table

        from ..fixtures import transpile

        schema = Schema()
        schema.add_table(Table.from_column_list("orders", ["id", "user_id"]))
        schema.add_table(Table.from_column_list("users", ["id", "name"]))
        schema.infer_relationships()

        settings = CompileSettings(schema=schema)
        sql = transpile("from orders & users", settings=settings)

        # Should use inferred relationship
        assert "JOIN" in sql.upper()
        assert "orders.user_id" in sql.lower()
        assert "users.id" in sql.lower()

    def test_uninferable_join_raises(self) -> None:
        """No `on`, no schema relationship, no convention setting: error, not a cross join."""
        import pytest

        from asql.errors import ASQLResolutionError

        from ..fixtures import transpile

        for query in (
            "from events join users",
            "from events & users",
            "from events &? users",
            "from events left join users",
        ):
            with pytest.raises(ASQLResolutionError) as excinfo:
                transpile(query)
            message = str(excinfo.value)
            assert "events" in message and "users" in message, message
            assert "on" in message and "infer_join_keys" in message, message

    def test_schema_without_relationship_raises(self) -> None:
        import pytest

        from asql.config import CompileSettings
        from asql.errors import ASQLResolutionError
        from asql.schema import Schema, Table

        from ..fixtures import transpile

        schema = Schema()
        schema.add_table(Table.from_column_list("events", ["id", "kind"]))
        schema.add_table(Table.from_column_list("users", ["id", "name"]))
        with pytest.raises(ASQLResolutionError, match="events.*users"):
            transpile("from events & users", settings=CompileSettings(schema=schema))

    def test_infer_join_keys_uses_naming_convention(self) -> None:
        from asql.config import CompileSettings

        from ..fixtures import transpile

        sql = transpile(
            "from events join users", settings=CompileSettings(infer_join_keys=True)
        )
        assert "INNER JOIN users ON events.user_id = users.id" in sql, sql

    def test_explicit_on_needs_no_inference(self) -> None:
        from ..fixtures import transpile

        sql = transpile("from events & users on events.who = users.id")
        assert "ON events.who = users.id" in sql, sql

    def test_sql_first_plain_join_is_untouched(self) -> None:
        from ..fixtures import transpile

        sql = transpile("select * from a join b")
        assert "FROM a, b" in sql, sql

    def test_explicit_cross_join_keeps_working(self) -> None:
        from ..fixtures import transpile

        for query in ("from events * users", "from events cross join users"):
            assert "CROSS JOIN users" in transpile(query), query

    def test_cross_join_operator_keyword_named_table(self) -> None:
        """`*` stays a CROSS JOIN when the left table is also a SQL keyword.

        Regression: a keyword-named table (`date`, `left`, `view`, ...) is not a
        VAR token, so a token-kind guard on the `*` hook let sqlglot eat the
        star as Postgres's wildcard suffix and alias the right-hand table.
        """
        from ..fixtures import transpile

        for table in ("date", "left", "view", "filter"):
            sql = transpile(f"from {table} * orders")
            assert f"FROM {table} CROSS JOIN orders" in sql, sql

    def test_cross_join_no_auto_condition(self) -> None:
        """CROSS JOIN should not get auto-inferred condition."""
        from asql.config import CompileSettings

        from ..fixtures import transpile

        settings = CompileSettings(infer_join_keys=True)
        sql = transpile("from orders * users", settings=settings)

        # Cross join shouldn't have ON condition
        assert "CROSS JOIN" in sql.upper()
        # Should NOT have an ON clause inferred - check both conditions
        assert " on " not in sql.lower(), f"CROSS JOIN should not have ON clause: {sql}"

    def test_chained_auto_joins(self) -> None:
        """Chained joins each infer a condition from the naming convention."""
        from asql.config import CompileSettings

        from ..fixtures import transpile

        settings = CompileSettings(infer_join_keys=True)
        sql = transpile("from orders & users & products", settings=settings)

        # All tables should be referenced
        assert "orders" in sql.lower()
        assert "users" in sql.lower()
        assert "products" in sql.lower()


def _duckdb_rows(sql: str) -> list[tuple[object, ...]]:
    import duckdb

    con = duckdb.connect()
    con.execute("create table orders (id int, customer_id int, status varchar)")
    con.execute("create table customers (id int, country varchar)")
    con.execute(
        "insert into orders values (1, 1, 'x'), (2, 2, 'x'), (3, 1, 'y'), (4, 9, 'x')"
    )
    con.execute("insert into customers values (1, 'US'), (2, 'CA'), (3, 'MX')")
    return sorted(con.execute(sql).fetchall(), key=str)


class TestJoinAfterWhere:
    """A join operator opening a pipeline step after `where` is a join."""

    ON = "orders.customer_id = customers.id"

    def test_inner_join_after_where_keeps_on_clause(self) -> None:
        from ..fixtures import transpile

        sql = transpile(
            f'from orders where status = "x" & customers on {self.ON} '
            "select orders.id, customers.country"
        )
        assert "JOIN customers" in sql and "ON orders.customer_id" in sql, sql
        assert _duckdb_rows(sql) == [(1, "US"), (2, "CA")]

    def test_each_join_operator_after_where(self) -> None:
        from ..fixtures import transpile

        for op, keyword in [("&?", "LEFT"), ("?&", "RIGHT"), ("?&?", "FULL OUTER")]:
            sql = transpile(
                f'from orders where status = "x" {op} customers on {self.ON}'
            )
            assert f"{keyword} JOIN customers" in sql, sql
            _duckdb_rows(sql)

    def test_cross_join_after_where(self) -> None:
        from ..fixtures import transpile

        sql = transpile(
            'from orders where status = "x"\n  * customers select orders.id'
        )
        assert "CROSS JOIN customers" in sql, sql
        assert len(_duckdb_rows(sql)) == 9

    def test_filter_applies_before_right_and_full_join(self) -> None:
        """Rows removed by `where` must not reappear as null-extended join rows."""
        from ..fixtures import transpile

        for op, expected in [
            ("?&", [(1, "US"), (2, "CA"), (None, "MX")]),
            ("?&?", [(1, "US"), (2, "CA"), (4, None), (None, "MX")]),
        ]:
            sql = transpile(
                f'from orders where status = "x" {op} customers on {self.ON} '
                "select orders.id, customers.country"
            )
            assert _duckdb_rows(sql) == sorted(expected, key=str), sql

    def test_playground_join_with_aggregation(self) -> None:
        from ..fixtures import transpile

        sql = transpile(
            "from customers where customers.id >= 1 and country = 'US' "
            "& orders on customers.id = orders.customer_id "
            "group by customers.id, customers.country "
            "( sum(orders.id) as total, # as total_orders )"
        )
        assert "JOIN orders ON customers.id = orders.customer_id" in sql, sql
        assert _duckdb_rows(sql) == [(1, "US", 4, 2)]

    def test_bitwise_and_in_where_is_unchanged(self) -> None:
        from ..fixtures import transpile

        assert "WHERE id & 4 = 4" in transpile("from orders where id & 4 = 4")


class TestRightFullJoinAfterWhereGuards:
    ON = TestJoinAfterWhere.ON

    def test_earlier_joins_raise(self) -> None:
        import pytest

        from asql.errors import ASQLCompilationError

        from ..fixtures import transpile

        for query in (
            "from orders & customers on orders.customer_id = customers.id "
            'where orders.status = "x" ?& customers as c2 on c2.id = orders.customer_id',
            "from orders &? customers on orders.customer_id = customers.id "
            "where customers.id is null ?&? customers as c2 on c2.id = orders.id",
        ):
            with pytest.raises(ASQLCompilationError, match="stash"):
                transpile(query)

    def test_subquery_left_side_still_infers(self) -> None:
        import pytest

        from asql.config import CompileSettings
        from asql.errors import ASQLResolutionError

        from ..fixtures import transpile

        with pytest.raises(ASQLResolutionError, match="orders.*customers"):
            transpile('from orders where status = "x" ?& customers')
        settings = CompileSettings(infer_join_keys=True)
        sql = transpile(
            'from orders where status = "x" ?& customers on customer_id',
            settings=settings,
        )
        assert "ON orders.customer_id = customers.id" in sql, sql
        sql = transpile(
            'from orders where status = "x" ?& customers\n  & products',
            settings=settings,
        )
        assert "JOIN products ON customers.product_id = products.id" in sql, sql


class TestSubqueryFromJoins:
    SUB = "from (from orders select user_id, amount)"

    def _schema_settings(self):
        from asql.config import CompileSettings
        from asql.schema import Schema, Table

        schema = Schema()
        schema.add_table(Table.from_column_list("o", ["user_id", "amount"]))
        schema.add_table(Table.from_column_list("users", ["id", "name"]))
        return CompileSettings(schema=schema)

    def test_unaliased_subquery_needing_inference_raises(self) -> None:
        import pytest

        from asql.errors import ASQLResolutionError

        from ..fixtures import transpile

        for query in (f"{self.SUB} & users on user_id", f"{self.SUB} & users"):
            with pytest.raises(ASQLResolutionError, match="alias"):
                transpile(query, settings=self._schema_settings())

    def test_unaliased_subquery_with_explicit_on_passes(self) -> None:
        from ..fixtures import transpile

        sql = transpile(f"{self.SUB} & users on users.id = amount")
        assert "ON users.id = amount" in sql, sql

    def test_aliased_subquery_expands_shorthand(self) -> None:
        from ..fixtures import transpile

        sql = transpile(
            f"{self.SUB} as o & users on user_id", settings=self._schema_settings()
        )
        assert "ON o.user_id = users.id" in sql, sql


class TestNestedSelectJoins:
    """Each select resolves its own joins against its own FROM."""

    @staticmethod
    def _settings():
        from asql.config import CompileSettings
        from asql.schema import Schema, Table

        schema = Schema()
        schema.add_table(Table.from_column_list("orders", ["id", "user_id"]))
        schema.add_table(Table.from_column_list("users", ["id", "name"]))
        return CompileSettings(schema=schema)

    def _rows(self, sql: str) -> list[tuple[object, ...]]:
        import duckdb

        con = duckdb.connect()
        con.execute("create table orders (id int, user_id int)")
        con.execute("create table users (id int, name varchar)")
        con.execute("insert into orders values (1, 1), (2, 2)")
        con.execute("insert into users values (1, 'a')")
        return con.execute(sql).fetchall()

    def test_join_inside_aliased_from_subquery(self) -> None:
        from ..fixtures import transpile

        sql = transpile(
            "from (from orders join users on user_id select orders.id) as o select o.id",
            settings=self._settings(),
        )
        assert "ON orders.user_id = users.id" in sql, sql
        assert self._rows(sql) == [(1,)]

    def test_join_inside_unaliased_from_subquery(self) -> None:
        from ..fixtures import transpile

        sql = transpile(
            "from (from orders join users on user_id select orders.id) select id",
            settings=self._settings(),
        )
        assert "ON orders.user_id = users.id" in sql, sql
        assert self._rows(sql) == [(1,)]

    def test_join_inside_stash_stage(self) -> None:
        from ..fixtures import transpile

        sql = transpile(
            "from orders & users on user_id select orders.id stash as j\n  select id",
            settings=self._settings(),
        )
        assert "ON orders.user_id = users.id" in sql, sql
        assert self._rows(sql) == [(1,)]
