"""Tests for fanout protection rewrites."""

from asql.config import CompileSettings
from asql.schema import Column, Relationship, Schema, Table

from ..validator import ASQLValidator


def _fanout_schema() -> Schema:
    schema = Schema()

    orders = Table(name="orders")
    orders.add_column(Column(name="order_id", primary_key=True))
    orders.add_column(Column(name="customer_id"))
    orders.add_column(Column(name="shipping_cost"))
    schema.add_table(orders)

    order_items = Table(name="order_items")
    order_items.add_column(Column(name="order_id"))
    order_items.add_column(Column(name="item_id"))
    order_items.add_column(Column(name="quantity"))
    schema.add_table(order_items)

    customers = Table(name="customers")
    customers.add_column(Column(name="customer_id", primary_key=True))
    customers.add_column(Column(name="state"))
    schema.add_table(customers)

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
            from_table="orders",
            from_column="customer_id",
            to_table="customers",
            to_column="customer_id",
            source="explicit",
        )
    )

    return schema


def _fanout_schema_with_returns() -> Schema:
    schema = _fanout_schema()

    returns = Table(name="returns")
    returns.add_column(Column(name="order_id"))
    returns.add_column(Column(name="return_id"))
    schema.add_table(returns)

    schema.add_relationship(
        Relationship(
            from_table="returns",
            from_column="order_id",
            to_table="orders",
            to_column="order_id",
            source="explicit",
        )
    )

    return schema


class TestFanoutProtection(ASQLValidator):
    """Test fanout protection via many-side pre-aggregation."""

    def test_preaggregates_many_side_before_join(self) -> None:
        settings = CompileSettings(
            schema=_fanout_schema(),
            fanout_protection=True,
            include_transpilation_comments=False,
        )

        asql = """
        from orders
          & order_items on orders.order_id = order_items.order_id
          & customers on orders.customer_id = customers.customer_id
          group by customers.state (
            sum(orders.shipping_cost) as shipping_cost,
            sum(order_items.quantity) as quantity
          )
        """

        expected = """
        SELECT
          customers.state,
          SUM(orders.shipping_cost) AS shipping_cost,
          SUM(order_items.__fanout_sum_quantity_1) AS quantity
        FROM orders
        INNER JOIN (
          SELECT
            order_items.order_id,
            SUM(order_items.quantity) AS __fanout_sum_quantity_1
          FROM order_items
          GROUP BY order_items.order_id
        ) AS order_items
          ON orders.order_id = order_items.order_id
        INNER JOIN customers
          ON orders.customer_id = customers.customer_id
        GROUP BY customers.state
        """

        self.validate_asql(asql, expected, settings=settings)

    def test_cross_table_aggregate_is_left_unchanged(self) -> None:
        settings = CompileSettings(
            schema=_fanout_schema(),
            fanout_protection=True,
            include_transpilation_comments=False,
        )

        asql = """
        from orders
          & order_items on orders.order_id = order_items.order_id
          group by orders.customer_id (
            sum(orders.shipping_cost * order_items.quantity) as blended
          )
        """

        sql = self.validate_contains(
            asql,
            "SUM(orders.shipping_cost * order_items.quantity)",
            settings=settings,
        )
        assert "SELECT order_items.order_id" not in sql

    def test_avg_many_side_rewrites_to_weighted_outer_average(self) -> None:
        settings = CompileSettings(
            schema=_fanout_schema(),
            fanout_protection=True,
            include_transpilation_comments=False,
        )

        asql = """
        from orders
          & order_items on orders.order_id = order_items.order_id
          & customers on orders.customer_id = customers.customer_id
          group by customers.state (
            avg(order_items.quantity) as avg_quantity
          )
        """

        sql = self.validate_contains(
            asql,
            "SUM(order_items.__fanout_sum_quantity_1)",
            "SUM(COALESCE(order_items.__fanout_count_quantity_1, 0))",
            "NULLIF",
            settings=settings,
        )
        assert "AVG(order_items.quantity)" not in sql

    def test_min_many_side_rewrites(self) -> None:
        settings = CompileSettings(
            schema=_fanout_schema(),
            fanout_protection=True,
            include_transpilation_comments=False,
        )

        sql = self.validate_contains(
            """
            from orders
              & order_items on orders.order_id = order_items.order_id
              & customers on orders.customer_id = customers.customer_id
              group by customers.state (
                min(order_items.quantity) as min_quantity
              )
            """,
            "MIN(order_items.__fanout_min_quantity_1)",
            "MIN(order_items.quantity) AS __fanout_min_quantity_1",
            settings=settings,
        )
        assert "MIN(order_items.quantity) AS min_quantity" not in sql

    def test_max_many_side_rewrites(self) -> None:
        settings = CompileSettings(
            schema=_fanout_schema(),
            fanout_protection=True,
            include_transpilation_comments=False,
        )

        sql = self.validate_contains(
            """
            from orders
              & order_items on orders.order_id = order_items.order_id
              & customers on orders.customer_id = customers.customer_id
              group by customers.state (
                max(order_items.quantity) as max_quantity
              )
            """,
            "MAX(order_items.__fanout_max_quantity_1)",
            "MAX(order_items.quantity) AS __fanout_max_quantity_1",
            settings=settings,
        )
        assert "MAX(order_items.quantity) AS max_quantity" not in sql

    def test_count_many_side_rewrites(self) -> None:
        settings = CompileSettings(
            schema=_fanout_schema(),
            fanout_protection=True,
            include_transpilation_comments=False,
        )

        sql = self.validate_contains(
            """
            from orders
              & order_items on orders.order_id = order_items.order_id
              group by orders.customer_id (
                count(order_items.quantity) as item_rows
              )
            """,
            "__fanout_count_quantity_1",
            "SUM(COALESCE(order_items.__fanout_count_quantity_1, 0))",
            settings=settings,
        )
        assert "COUNT(order_items.quantity) AS __fanout_count_quantity_1" in sql

    def test_conditional_sum_many_side_rewrites(self) -> None:
        settings = CompileSettings(
            schema=_fanout_schema(),
            fanout_protection=True,
            include_transpilation_comments=False,
        )

        sql = self.validate_contains(
            """
            from orders
              & order_items on orders.order_id = order_items.order_id
              group by orders.customer_id (
                sum(case when order_items.item_id = 'apple' then order_items.quantity else 0 end) as apple_quantity
              )
            """,
            "SUM(order_items.__fanout_sum_quantity_1)",
            "SUM(CASE WHEN order_items.item_id = 'apple' THEN order_items.quantity ELSE 0 END) AS __fanout_sum_quantity_1",
            settings=settings,
        )
        assert (
            "SUM(CASE WHEN order_items.item_id = 'apple' THEN order_items.quantity ELSE 0 END) AS apple_quantity"
            not in sql
        )

    def test_conditional_avg_many_side_rewrites(self) -> None:
        settings = CompileSettings(
            schema=_fanout_schema(),
            fanout_protection=True,
            include_transpilation_comments=False,
        )

        sql = self.validate_contains(
            """
            from orders
              & order_items on orders.order_id = order_items.order_id
              group by orders.customer_id (
                avg(case when order_items.item_id = 'apple' then order_items.quantity end) as apple_avg_quantity
              )
            """,
            "__fanout_sum_quantity_1",
            "__fanout_count_quantity_1",
            "NULLIF",
            settings=settings,
        )
        assert (
            "AVG(CASE WHEN order_items.item_id = 'apple' THEN order_items.quantity END)"
            not in sql
        )

    def test_conditional_count_many_side_rewrites(self) -> None:
        settings = CompileSettings(
            schema=_fanout_schema(),
            fanout_protection=True,
            include_transpilation_comments=False,
        )

        sql = self.validate_contains(
            """
            from orders
              & order_items on orders.order_id = order_items.order_id
              group by orders.customer_id (
                count(case when order_items.item_id = 'apple' then order_items.quantity end) as apple_item_rows
              )
            """,
            "__fanout_count_quantity_1",
            "SUM(COALESCE(order_items.__fanout_count_quantity_1, 0))",
            settings=settings,
        )
        assert (
            "COUNT(CASE WHEN order_items.item_id = 'apple' THEN order_items.quantity END) AS apple_item_rows"
            not in sql
        )

    def test_count_star_is_left_unchanged(self) -> None:
        settings = CompileSettings(
            schema=_fanout_schema(),
            fanout_protection=True,
            include_transpilation_comments=False,
        )

        sql = self.validate_contains(
            """
            from orders
              & order_items on orders.order_id = order_items.order_id
              group by orders.customer_id (
                count(*) as rows_seen
              )
            """,
            "COUNT(*)",
            settings=settings,
        )
        assert "__fanout_count" not in sql

    def test_left_join_many_side_is_rewritten(self) -> None:
        settings = CompileSettings(
            schema=_fanout_schema(),
            fanout_protection=True,
            include_transpilation_comments=False,
        )

        self.validate_contains(
            """
            from orders
              &? order_items on orders.order_id = order_items.order_id
              group by orders.customer_id (
                sum(orders.shipping_cost) as shipping_cost,
                sum(order_items.quantity) as quantity
              )
            """,
            "LEFT JOIN (SELECT order_items.order_id",
            "__fanout_sum_quantity_1",
            settings=settings,
        )

    def test_multiple_many_side_tables_both_rewrite(self) -> None:
        settings = CompileSettings(
            schema=_fanout_schema_with_returns(),
            fanout_protection=True,
            include_transpilation_comments=False,
        )

        sql = self.validate_contains(
            """
            from orders
              & order_items on orders.order_id = order_items.order_id
              & returns on orders.order_id = returns.order_id
              group by orders.customer_id (
                sum(order_items.quantity) as quantity,
                count(returns.return_id) as return_count
              )
            """,
            "__fanout_sum_quantity_1",
            "__fanout_count_return_id_1",
            settings=settings,
        )
        assert sql.count("SELECT") >= 3

    def test_disabled_setting_leaves_query_unchanged(self) -> None:
        settings = CompileSettings(
            schema=_fanout_schema(),
            fanout_protection=False,
            include_transpilation_comments=False,
        )

        sql = self.validate_contains(
            """
            from orders
              & order_items on orders.order_id = order_items.order_id
              group by orders.customer_id (
                sum(order_items.quantity) as quantity
              )
            """,
            "SUM(order_items.quantity)",
            settings=settings,
        )
        assert "__fanout_sum_quantity_1" not in sql

    def test_missing_schema_leaves_query_unchanged(self) -> None:
        settings = CompileSettings(
            fanout_protection=True,
            include_transpilation_comments=False,
        )

        sql = self.validate_contains(
            """
            from orders
              & order_items on orders.order_id = order_items.order_id
              group by orders.customer_id (
                sum(order_items.quantity) as quantity
              )
            """,
            "SUM(order_items.quantity)",
            settings=settings,
        )
        assert "__fanout_sum_quantity_1" not in sql

    def test_group_by_many_side_column_skips_rewrite(self) -> None:
        settings = CompileSettings(
            schema=_fanout_schema(),
            fanout_protection=True,
            include_transpilation_comments=False,
        )

        sql = self.validate_contains(
            """
            from orders
              & order_items on orders.order_id = order_items.order_id
              group by order_items.item_id (
                sum(order_items.quantity) as quantity
              )
            """,
            "SUM(order_items.quantity)",
            settings=settings,
        )
        assert "__fanout_sum_quantity_1" not in sql

    def test_having_on_many_side_skips_rewrite(self) -> None:
        settings = CompileSettings(
            schema=_fanout_schema(),
            fanout_protection=True,
            include_transpilation_comments=False,
        )

        sql = self.validate_contains(
            """
            from orders
              & order_items on orders.order_id = order_items.order_id
              group by orders.customer_id (
                sum(order_items.quantity) as quantity
              )
              having sum(order_items.quantity) > 1
            """,
            "SUM(order_items.quantity)",
            settings=settings,
        )
        assert "__fanout_sum_quantity_1" not in sql


class TestFanoutRiskDiagnostics(ASQLValidator):
    """Warnings for provable fanout risk the compiler does not rewrite."""

    def _settings(self, comments: bool = True) -> CompileSettings:
        return CompileSettings(
            schema=_fanout_schema(),
            fanout_protection=True,
            include_transpilation_comments=comments,
        )

    def test_reverse_direction_stage2_rewrites(self) -> None:
        sql = self.validate_contains(
            """
            from order_items
              & orders on order_items.order_id = orders.order_id
              group by orders.customer_id (
                sum(orders.shipping_cost) as shipping
              )
            """,
            "MAX(orders.shipping_cost) AS __fanout_one_shipping_cost_1",
            "GROUP BY order_items.order_id",
            "SUM(__fanout_one_shipping_cost_1) AS shipping",
            "ASQL fanout protection: re-aggregated through order_items.order_id",
            settings=self._settings(),
        )
        assert "ASQL fanout warning" not in sql

    def test_reverse_direction_mixed_sides_stage2_rewrites(self) -> None:
        self.validate_contains(
            """
            from order_items
              & orders on order_items.order_id = orders.order_id
              group by orders.customer_id (
                sum(orders.shipping_cost) as shipping,
                sum(order_items.quantity) as quantity
              )
            """,
            "MAX(orders.shipping_cost) AS __fanout_one_shipping_cost_1",
            "SUM(order_items.quantity) AS __fanout_sum_quantity_2",
            "SUM(__fanout_sum_quantity_2) AS quantity",
            settings=self._settings(),
        )

    def test_reverse_direction_with_having_still_warns(self) -> None:
        sql = self.validate_contains(
            """
            from order_items
              & orders on order_items.order_id = orders.order_id
              group by orders.customer_id (
                sum(orders.shipping_cost) as shipping
              )
              having sum(orders.shipping_cost) > 1
            """,
            "ASQL fanout warning: order_items fans out orders",
            settings=self._settings(),
        )
        assert "__fanout_" not in sql

    def test_reverse_direction_count_distinct_still_warns(self) -> None:
        sql = self.validate_contains(
            """
            from order_items
              & orders on order_items.order_id = orders.order_id
              group by orders.customer_id (
                sum(orders.shipping_cost) as shipping,
                count(distinct orders.shipping_cost) as distinct_costs
              )
            """,
            "ASQL fanout warning: order_items fans out orders",
            settings=self._settings(),
        )
        assert "__fanout_" not in sql

    def test_join_as_filter_collapses_to_distinct_keys(self) -> None:
        sql = self.validate_contains(
            """
            from orders
              & order_items on orders.order_id = order_items.order_id
              group by orders.customer_id (
                sum(orders.shipping_cost) as shipping
              )
            """,
            "SELECT DISTINCT order_items.order_id FROM order_items",
            "ASQL fanout protection: collapsed order_items to DISTINCT order_id",
            settings=self._settings(),
        )
        assert "ASQL fanout warning" not in sql

    def test_bare_count_star_warns_when_unrewritten(self) -> None:
        self.validate_contains(
            """
            from orders
              & order_items on orders.order_id = order_items.order_id
              group by orders.customer_id (
                count(*) as n
              )
            """,
            "ASQL fanout warning: COUNT(*) counts joined rows",
            settings=self._settings(),
        )

    def test_bare_count_star_warns_even_when_rewritten(self) -> None:
        sql = self.validate_contains(
            """
            from orders
              & order_items on orders.order_id = order_items.order_id
              group by orders.customer_id (
                sum(order_items.quantity) as quantity,
                count(*) as n
              )
            """,
            "ASQL fanout protection: pre-aggregated order_items",
            "ASQL fanout warning: COUNT(*) counts joined rows",
            settings=self._settings(),
        )
        assert "__fanout_sum_quantity_1" in sql

    def test_count_of_column_is_not_bare(self) -> None:
        sql = self.validate_contains(
            """
            from orders
              & order_items on orders.order_id = order_items.order_id
              group by orders.customer_id (
                count(order_items.quantity) as n
              )
            """,
            settings=self._settings(),
        )
        assert "COUNT(*) counts joined rows" not in sql

    def test_forward_protected_shape_has_no_warning(self) -> None:
        sql = self.validate_contains(
            """
            from orders
              & order_items on orders.order_id = order_items.order_id
              group by orders.customer_id (
                sum(order_items.quantity) as quantity,
                sum(orders.shipping_cost) as shipping
              )
            """,
            "ASQL fanout protection: pre-aggregated order_items",
            settings=self._settings(),
        )
        assert "ASQL fanout warning" not in sql

    def test_single_table_group_has_no_warning(self) -> None:
        sql = self.validate_contains(
            """
            from orders
              group by orders.customer_id (
                sum(orders.shipping_cost) as shipping
              )
            """,
            settings=self._settings(),
        )
        assert "ASQL fanout warning" not in sql

    def test_comments_off_suppresses_warnings(self) -> None:
        sql = self.validate_contains(
            """
            from order_items
              & orders on order_items.order_id = orders.order_id
              group by orders.customer_id (
                sum(orders.shipping_cost) as shipping
              )
            """,
            settings=self._settings(comments=False),
        )
        assert "fanout warning" not in sql.lower()

    def test_reverse_direction_count_star_does_not_warn(self) -> None:
        sql = self.validate_contains(
            """
            from order_items
              & orders on order_items.order_id = orders.order_id
              group by orders.customer_id (
                count(*) as n
              )
            """,
            settings=self._settings(),
        )
        assert "COUNT(*) counts joined rows" not in sql


def _one_to_one_schema(profile_key_unique: bool = True, via_pk: bool = False) -> Schema:
    """orders 1:1 order_profiles, the FK column's uniqueness declared per flags."""
    schema = Schema()

    orders = Table(name="orders")
    orders.add_column(Column(name="order_id", primary_key=True))
    orders.add_column(Column(name="region"))
    orders.add_column(Column(name="shipping_cost"))
    schema.add_table(orders)

    profiles = Table(name="order_profiles")
    profiles.add_column(
        Column(
            name="order_id",
            primary_key=via_pk,
            unique=profile_key_unique and not via_pk,
        )
    )
    profiles.add_column(Column(name="margin"))
    schema.add_table(profiles)

    schema.add_relationship(
        Relationship(
            from_table="order_profiles",
            from_column="order_id",
            to_table="orders",
            to_column="order_id",
            source="explicit",
        )
    )
    return schema


class TestUniquenessSkip(ASQLValidator):
    """A join whose FK column is declared unique is 1:1 - protection skips."""

    def _settings(self, schema: Schema) -> CompileSettings:
        return CompileSettings(
            schema=schema,
            fanout_protection=True,
            include_transpilation_comments=True,
        )

    def test_unique_fk_skips_preagg(self) -> None:
        sql = self.validate_contains(
            """
            from orders
              & order_profiles on orders.order_id = order_profiles.order_id
              group by orders.region (
                sum(order_profiles.margin) as margin
              )
            """,
            "SUM(order_profiles.margin)",
            settings=self._settings(_one_to_one_schema()),
        )
        assert "__fanout" not in sql
        assert "fanout" not in sql.lower() or "warning" not in sql.lower()

    def test_pk_as_fk_implies_unique(self) -> None:
        sql = self.validate_contains(
            """
            from orders
              & order_profiles on orders.order_id = order_profiles.order_id
              group by orders.region (
                sum(order_profiles.margin) as margin
              )
            """,
            "SUM(order_profiles.margin)",
            settings=self._settings(_one_to_one_schema(via_pk=True)),
        )
        assert "__fanout" not in sql

    def test_unique_fk_skips_stage2(self) -> None:
        sql = self.validate_contains(
            """
            from order_profiles
              & orders on order_profiles.order_id = orders.order_id
              group by orders.region (
                sum(orders.shipping_cost) as shipping
              )
            """,
            "SUM(orders.shipping_cost)",
            settings=self._settings(_one_to_one_schema()),
        )
        assert "__fanout" not in sql
        assert "ASQL fanout warning" not in sql

    def test_unique_fk_skips_filter_collapse(self) -> None:
        sql = self.validate_contains(
            """
            from orders
              & order_profiles on orders.order_id = order_profiles.order_id
              group by orders.region (
                sum(orders.shipping_cost) as shipping
              )
            """,
            "SUM(orders.shipping_cost)",
            settings=self._settings(_one_to_one_schema()),
        )
        assert "SELECT DISTINCT" not in sql
        assert "ASQL fanout warning" not in sql

    def test_undeclared_key_still_protected(self) -> None:
        sql = self.validate_contains(
            """
            from orders
              & order_profiles on orders.order_id = order_profiles.order_id
              group by orders.region (
                sum(order_profiles.margin) as margin
              )
            """,
            "__fanout_sum_margin_1",
            settings=self._settings(_one_to_one_schema(profile_key_unique=False)),
        )
        assert "pre-aggregated order_profiles" in sql


class TestFanoutProtectionDefaultOn(ASQLValidator):
    """fanout_protection is the language default: with schema, every provable
    shape is either rewritten or loudly diagnosed - never silently fanned."""

    def _settings(self) -> CompileSettings:
        return CompileSettings(schema=_fanout_schema())

    def test_forward_shape_rewrites_by_default(self) -> None:
        self.validate_contains(
            """
            from orders
              & order_items on orders.order_id = order_items.order_id
              group by orders.customer_id (
                sum(order_items.quantity) as quantity
              )
            """,
            "__fanout_sum_quantity_1",
            settings=self._settings(),
        )

    def test_no_shape_is_both_unrewritten_and_undiagnosed(self) -> None:
        shapes = {
            "forward": """
                from orders
                  & order_items on orders.order_id = order_items.order_id
                  group by orders.customer_id (sum(order_items.quantity) as q)
            """,
            "one_side_only": """
                from orders
                  & order_items on orders.order_id = order_items.order_id
                  group by orders.customer_id (sum(orders.shipping_cost) as s)
            """,
            "reverse": """
                from order_items
                  & orders on order_items.order_id = orders.order_id
                  group by orders.customer_id (sum(orders.shipping_cost) as s)
            """,
            "reverse_having": """
                from order_items
                  & orders on order_items.order_id = orders.order_id
                  group by orders.customer_id (sum(orders.shipping_cost) as s)
                  having sum(orders.shipping_cost) > 1
            """,
            "cross_table": """
                from orders
                  & order_items on orders.order_id = order_items.order_id
                  group by orders.customer_id (
                    sum(orders.shipping_cost * order_items.quantity) as blended
                  )
            """,
            "bare_count_star": """
                from orders
                  & order_items on orders.order_id = order_items.order_id
                  group by orders.customer_id (count(*) as n)
            """,
        }
        for name, asql in shapes.items():
            sql = self.validate_contains(asql, settings=self._settings())
            rewritten = "__fanout" in sql or "SELECT DISTINCT" in sql
            diagnosed = "ASQL fanout" in sql
            assert rewritten or diagnosed, f"shape {name} is silent:\n{sql}"

    def test_opt_out_still_works(self) -> None:
        sql = self.validate_contains(
            """
            set fanout_protection = false;
            from orders
              & order_items on orders.order_id = order_items.order_id
              group by orders.customer_id (
                sum(order_items.quantity) as quantity
              )
            """,
            "SUM(order_items.quantity) AS quantity",
            settings=self._settings(),
        )
        assert "__fanout" not in sql


class TestSqlStyleOuterJoins:
    """SQL `right join`/`full join` keep forward many-side protection: each FROM row
    still meets at most one pre-aggregated row, so the rewrite stays exact."""

    @staticmethod
    def _rows(sql: str) -> list[tuple[object, ...]]:
        import duckdb

        con = duckdb.connect()
        con.execute(
            "create table orders (order_id int, customer_id int, shipping_cost int);"
            "insert into orders values (1, 11, 1), (2, 12, 10), (3, 12, 100), (4, 12, 1000);"
            "create table order_items (order_id int, item_id int, quantity int);"
            "insert into order_items values (1, 1, 1), (2, 1, 2), (2, 2, 1), (9, 3, 5);"
        )
        return sorted(con.execute(sql).fetchall(), key=repr)

    def test_right_and_full_joins_are_preaggregated(self) -> None:
        from asql import transpile

        for side in ("right", "full"):
            sql = transpile(
                "select orders.customer_id, sum(orders.shipping_cost) as ship, "
                "sum(order_items.quantity) as qty from orders "
                f"{side} join order_items on orders.order_id = order_items.order_id "
                "group by orders.customer_id",
                schema=_fanout_schema(),
                fanout_protection=True,
            )[0]
            expected = self._rows(
                "select o.customer_id, sum(o.shipping_cost), sum(i.qty) from orders o "
                f"{side} join (select order_id, sum(quantity) as qty from order_items "
                "group by order_id) i on o.order_id = i.order_id "
                "group by o.customer_id"
            )
            assert self._rows(sql) == expected, side

    def test_reverse_outer_join_is_not_stage2_rewritten(self) -> None:
        """From the many side, an outer join's unmatched one-side rows would share
        a NULL key in stage 2 and collapse; the rewrite is skipped and warns."""
        from asql import transpile

        asql_queries = {
            side: "from order_items "
            f"{join} orders on order_items.order_id = orders.order_id "
            "group by orders.customer_id ( sum(orders.shipping_cost) as ship )"
            for side, join in (
                ("right", "right join"),
                ("full", "full join"),
                ("?&", "?&"),
                ("?&?", "?&?"),
            )
        }
        sql_queries = {
            f"sql-{side}": "select orders.customer_id, "
            "sum(orders.shipping_cost) as ship from order_items "
            f"{side} join orders on order_items.order_id = orders.order_id "
            "group by orders.customer_id"
            for side in ("right", "full")
        }
        for side, query in {**asql_queries, **sql_queries}.items():
            sql = transpile(query, schema=_fanout_schema(), fanout_protection=True)[0]
            assert "__fanout_stage2" not in sql, side
            assert "ASQL fanout warning" in sql, side
            sql_side = {"?&": "right", "?&?": "full"}.get(side, side)
            sql_side = sql_side.removeprefix("sql-")
            raw = (
                "select o.customer_id, sum(o.shipping_cost) from order_items i "
                f"{sql_side} join orders o on i.order_id = o.order_id "
                "group by o.customer_id"
            )
            assert self._rows(sql) == self._rows(raw), side
