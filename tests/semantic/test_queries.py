"""Metric names and relationship.attribute references in ASQL queries."""

from pathlib import Path

import pytest
import yaml

from asql.config import CompileSettings
from asql.errors import ASQLResolutionError
from asql.schema import Schema
from asql.semantic import SemanticGraph, load_graph

from ..fixtures import transpile
from ..validator import ASQLValidator

GRAPH_PATH = Path(__file__).parent / "marketplace.graph.yaml"

BUYER_JOIN = "LEFT JOIN user_profiles AS buyer ON transactions.buyer_id = buyer.user_id"
SELLER_JOIN = (
    "LEFT JOIN user_profiles AS seller ON transactions.seller_id = seller.user_id"
)


def _settings() -> CompileSettings:
    return CompileSettings(schema=Schema.from_graph(load_graph(GRAPH_PATH)))


def _compile(query: str) -> str:
    return transpile(query, settings=_settings())


class TestMetricResolution(ASQLValidator):
    target_dialect = "duckdb"

    def setUp(self) -> None:
        self.settings = _settings()

    def test_leaf_metric(self) -> None:
        self.validate_asql(
            "from transactions group by status ( volume )",
            "SELECT transactions.status, SUM(transactions.amount) AS volume "
            "FROM transactions GROUP BY transactions.status",
        )

    def test_derived_metric_expands_leaves(self) -> None:
        self.validate_asql(
            "from transactions group by status ( aov )",
            "SELECT transactions.status, "
            "SUM(transactions.amount) / COUNT(*) AS aov "
            "FROM transactions GROUP BY transactions.status",
        )

    def test_derived_of_derived_keeps_precedence(self) -> None:
        self.validate_asql(
            "from transactions group by status ( aov_x100 )",
            "SELECT transactions.status, "
            "(SUM(transactions.amount) / COUNT(*)) * 100 AS aov_x100 "
            "FROM transactions GROUP BY transactions.status",
        )

    def test_metric_inside_expression(self) -> None:
        self.validate_asql(
            "from transactions group by status ( volume / 100 as v )",
            "SELECT transactions.status, SUM(transactions.amount) / 100 AS v "
            "FROM transactions GROUP BY transactions.status",
        )

    def test_metric_without_group_by_is_grand_total(self) -> None:
        self.validate_asql(
            "from transactions select volume, transaction_count",
            "SELECT SUM(transactions.amount) AS volume, COUNT(*) AS transaction_count "
            "FROM transactions",
        )

    def test_order_by_projected_metric_keeps_alias(self) -> None:
        self.validate_asql(
            "from transactions group by status ( volume ) order by -volume",
            "SELECT transactions.status, SUM(transactions.amount) AS volume "
            "FROM transactions GROUP BY transactions.status ORDER BY volume DESC",
        )

    def test_order_by_unprojected_metric_expands(self) -> None:
        self.validate_asql(
            "from transactions group by status ( transaction_count ) order by -volume",
            "SELECT transactions.status, COUNT(*) AS transaction_count "
            "FROM transactions GROUP BY transactions.status "
            "ORDER BY SUM(transactions.amount) DESC",
        )

    def test_post_aggregation_where_on_metric(self) -> None:
        self.validate_asql(
            "from transactions group by status ( volume ) where volume > 10",
            "WITH __tmp1 AS (SELECT transactions.status, "
            "SUM(transactions.amount) AS volume FROM transactions "
            "GROUP BY transactions.status) "
            "SELECT * FROM __tmp1 WHERE volume > 10",
        )

    def test_select_alias_shadows_metric(self) -> None:
        self.validate_asql(
            "from transactions group by status ( sum(amount) * 2 as volume ) "
            "order by -volume",
            "SELECT status, SUM(amount) * 2 AS volume FROM transactions "
            "GROUP BY status ORDER BY volume DESC",
        )

    def test_query_without_semantic_references_is_unchanged(self) -> None:
        self.validate_asql(
            "from transactions where amount > 1 select amount",
            "SELECT amount FROM transactions WHERE amount > 1",
        )

    def test_non_model_table_is_unchanged(self) -> None:
        self.validate_asql(
            "from refunds group by status ( volume )",
            "SELECT status, volume FROM refunds GROUP BY status",
        )


class TestRelationshipAttributes(ASQLValidator):
    target_dialect = "duckdb"

    def setUp(self) -> None:
        self.settings = _settings()

    def test_attribute_adds_left_join(self) -> None:
        self.validate_asql(
            "from transactions group by buyer.country ( volume, aov )",
            "SELECT buyer.country AS buyer_country, "
            "SUM(transactions.amount) AS volume, "
            "SUM(transactions.amount) / COUNT(*) AS aov "
            f"FROM transactions {BUYER_JOIN} GROUP BY buyer.country",
        )

    def test_attribute_with_date_dimension(self) -> None:
        self.validate_asql(
            "from transactions group by buyer.country, month(created_at) ( volume )",
            "SELECT buyer.country AS buyer_country, "
            "DATE_TRUNC('MONTH', transactions.created_at) AS month_created_at, "
            "SUM(transactions.amount) AS volume "
            f"FROM transactions {BUYER_JOIN} "
            "GROUP BY buyer.country, DATE_TRUNC('MONTH', transactions.created_at)",
        )

    def test_attribute_expression(self) -> None:
        self.validate_asql(
            "from transactions group by buyer.country_lower ( volume )",
            "SELECT LOWER(buyer.country) AS buyer_country_lower, "
            "SUM(transactions.amount) AS volume "
            f"FROM transactions {BUYER_JOIN} GROUP BY LOWER(buyer.country)",
        )

    def test_user_alias_on_attribute_is_kept(self) -> None:
        self.validate_asql(
            "from transactions group by buyer.country as c ( volume )",
            "SELECT buyer.country AS c, SUM(transactions.amount) AS volume "
            f"FROM transactions {BUYER_JOIN} GROUP BY c",
        )

    def test_two_attributes_one_relationship_one_join(self) -> None:
        self.validate_asql(
            "from transactions group by buyer.country, buyer.email ( volume )",
            "SELECT buyer.country AS buyer_country, buyer.email AS buyer_email, "
            "SUM(transactions.amount) AS volume "
            f"FROM transactions {BUYER_JOIN} GROUP BY buyer.country, buyer.email",
        )

    def test_two_relationships_same_entity_two_joins(self) -> None:
        self.validate_asql(
            "from transactions group by buyer.country, seller.country ( volume )",
            "SELECT buyer.country AS buyer_country, "
            "seller.country AS seller_country, "
            "SUM(transactions.amount) AS volume "
            f"FROM transactions {BUYER_JOIN} {SELLER_JOIN} "
            "GROUP BY buyer.country, seller.country",
        )

    def test_one_relationship_two_models_get_distinct_aliases(self) -> None:
        self.validate_asql(
            "from transactions group by buyer.country, buyer.theme ( volume )",
            "SELECT buyer__user_profiles.country AS buyer_country, "
            "buyer__user_settings.theme AS buyer_theme, "
            "SUM(transactions.amount) AS volume "
            "FROM transactions "
            "LEFT JOIN user_profiles AS buyer__user_profiles "
            "ON transactions.buyer_id = buyer__user_profiles.user_id "
            "LEFT JOIN user_settings AS buyer__user_settings "
            "ON transactions.buyer_id = buyer__user_settings.user_id "
            "GROUP BY buyer__user_profiles.country, buyer__user_settings.theme",
        )

    def test_attribute_in_pre_aggregation_where(self) -> None:
        self.validate_asql(
            'from transactions where buyer.country = "US" group by status ( volume )',
            "SELECT transactions.status, SUM(transactions.amount) AS volume "
            f"FROM transactions {BUYER_JOIN} "
            "WHERE buyer.country = 'US' GROUP BY transactions.status",
        )

    def test_filtered_metric_traverses_relationship(self) -> None:
        self.validate_asql(
            "from transactions group by status ( cn_volume )",
            "SELECT transactions.status, "
            "SUM(transactions.amount) FILTER(WHERE buyer.country = 'CN') AS cn_volume "
            f"FROM transactions {BUYER_JOIN} GROUP BY transactions.status",
        )

    def test_from_alias_qualifies_columns_and_join(self) -> None:
        self.validate_asql(
            "from transactions as t group by buyer.country ( volume )",
            "SELECT buyer.country AS buyer_country, SUM(t.amount) AS volume "
            "FROM transactions AS t "
            "LEFT JOIN user_profiles AS buyer ON t.buyer_id = buyer.user_id "
            "GROUP BY buyer.country",
        )

    def test_star_keeps_only_from_model_columns(self) -> None:
        self.validate_asql(
            'from transactions where buyer.country = "US"',
            f"SELECT transactions.* FROM transactions {BUYER_JOIN} "
            "WHERE buyer.country = 'US'",
        )

    def test_star_keeps_except_modifier(self) -> None:
        self.validate_asql(
            'from transactions where buyer.country = "US" except buyer_id',
            "SELECT transactions.* EXCLUDE (buyer_id) "
            f"FROM transactions {BUYER_JOIN} WHERE buyer.country = 'US'",
        )

    def test_join_hint_picks_one_of_several_relationships(self) -> None:
        self.validate_asql(
            "from transactions & user_profiles on seller_id "
            "group by user_profiles.country ( volume )",
            "SELECT user_profiles.country, SUM(transactions.amount) AS volume "
            "FROM transactions INNER JOIN user_profiles "
            "ON transactions.seller_id = user_profiles.user_id "
            "GROUP BY user_profiles.country",
        )

    def test_own_column_wins_over_other_models_metric(self) -> None:
        data = yaml.safe_load(GRAPH_PATH.read_text())
        data["models"]["line_items"]["schema"]["volume"] = "INT"
        data["models"]["line_items"]["metrics"]["item_volume"] = "SUM(volume)"
        self.validate_asql(
            "from line_items select item_volume",
            "SELECT SUM(line_items.volume) AS item_volume FROM line_items",
            settings=CompileSettings(
                schema=Schema.from_graph(SemanticGraph.from_dict(data))
            ),
        )

    def test_attribute_without_metric(self) -> None:
        self.validate_asql(
            "from transactions select transaction_id, buyer.email",
            "SELECT transactions.transaction_id, buyer.email AS buyer_email "
            f"FROM transactions {BUYER_JOIN}",
        )


class TestSemanticErrors:
    @pytest.mark.parametrize(
        ("query", "message"),
        [
            pytest.param(
                "from transactions & user_profiles as buyer "
                "on transactions.buyer_id = buyer.user_id "
                "group by buyer.country ( volume )",
                '"buyer" is both a relationship on model "transactions" and a '
                "table alias in this query; rename the alias.",
                id="alias-collision",
            ),
            pytest.param(
                "from transactions group by buyer.nickname ( volume )",
                'Relationship "buyer" (entity "user") has no attribute "nickname". '
                "Available: country, country_lower, email, theme.",
                id="unknown-attribute",
            ),
            pytest.param(
                "from user_profiles group by country ( volume )",
                'Metric "volume" is defined on model "transactions", not '
                '"user_profiles"; query it from transactions.',
                id="metric-on-other-model",
            ),
            pytest.param(
                "from line_items select transaction_count",
                'Metric "transaction_count" is defined on model "transactions", not '
                '"line_items"; query it from transactions.',
                id="column-free-metric-on-other-model",
            ),
            pytest.param(
                "from transactions & user_profiles group by status ( volume )",
                'Tables "transactions" and "user_profiles" are related several ways '
                "(buyer, seller); write the join condition with on.",
                id="ambiguous-explicit-join",
            ),
            pytest.param(
                "from transactions group by buyer.region ( volume )",
                'Attribute "region" of entity "user" is only declared on model '
                '"user_addresses", whose grain (user, as_of) does not make the '
                "join many-to-one; point-in-time joins are not supported yet.",
                id="compound-grain-attribute",
            ),
            pytest.param(
                "from user_addresses group by as_of.ts ( # )",
                'Relationship "as_of" on model "user_addresses" uses a predicate '
                "key; only equality-map keys can be traversed.",
                id="predicate-key",
            ),
            pytest.param(
                "from transactions where volume > 10 group by status ( volume )",
                'Metric "volume" is an aggregate and cannot be used in a where '
                "before group by; filter after the group by block.",
                id="metric-in-pre-aggregation-where",
            ),
        ],
    )
    def test_error(self, query: str, message: str) -> None:
        with pytest.raises(ASQLResolutionError) as excinfo:
            _compile(query)
        assert str(excinfo.value) == message


class TestFanoutFromGraph:
    """Grains and relationships from graph.yaml drive fan-out protection."""

    def test_many_side_join_is_protected(self) -> None:
        sql = _compile(
            "from transactions & line_items "
            "on transactions.transaction_id = line_items.transaction_id "
            "group by status ( sum(amount) as total )"
        )
        assert "SELECT DISTINCT" in sql
        assert "ASQL fanout protection" in sql

    def test_metric_query_with_user_join_is_protected(self) -> None:
        sql = _compile(
            "from transactions & line_items "
            "on transactions.transaction_id = line_items.transaction_id "
            "group by buyer.country ( volume )"
        )
        assert BUYER_JOIN in sql
        assert "SELECT DISTINCT" in sql


def test_attribute_declared_on_two_models_raises() -> None:
    data = yaml.safe_load(GRAPH_PATH.read_text())
    data["models"]["user_settings"]["relationships"]["user"]["attributes"][
        "country"
    ] = "theme"
    settings = CompileSettings(schema=Schema.from_graph(SemanticGraph.from_dict(data)))
    with pytest.raises(
        ASQLResolutionError,
        match='Attribute "country" of entity "user" is declared on several models '
        r"\(user_profiles, user_settings\); keep it on one.",
    ):
        transpile(
            "from transactions group by buyer.country ( volume )", settings=settings
        )


def test_other_dialect() -> None:
    sql = transpile(
        "from transactions group by buyer.country ( volume )",
        dialect="postgres",
        settings=_settings(),
    )
    assert sql == (
        "SELECT buyer.country AS buyer_country, SUM(transactions.amount) AS volume "
        f"FROM transactions {BUYER_JOIN} GROUP BY buyer.country"
    )


class TestMetricsOverUserJoins:
    """A metric over a user-written join is exact only when fan-out protection
    provably rewrites the join; everything else raises."""

    def test_ungrouped_metric_over_join_raises(self) -> None:
        with pytest.raises(
            ASQLResolutionError,
            match="Metrics over a join need a group by with fanout protection",
        ):
            _compile(
                "from transactions & line_items "
                "on transactions.transaction_id = line_items.transaction_id "
                "select volume"
            )

    def test_metric_over_join_with_fanout_protection_off_raises(self) -> None:
        settings = CompileSettings(
            schema=Schema.from_graph(load_graph(GRAPH_PATH)), fanout_protection=False
        )
        with pytest.raises(
            ASQLResolutionError,
            match="Metrics over a join need a group by with fanout protection",
        ):
            transpile(
                "from transactions & line_items "
                "on transactions.transaction_id = line_items.transaction_id "
                "group by status ( volume )",
                settings=settings,
            )

    @pytest.mark.parametrize(
        "join",
        [
            pytest.param(
                "& line_items on transactions.transaction_id = "
                "line_items.transaction_id and line_items.quantity > 0",
                id="compound-on",
            ),
            pytest.param(
                "& (from line_items) as items "
                "on transactions.transaction_id = items.transaction_id",
                id="subquery",
            ),
            pytest.param(
                "& refunds on transactions.transaction_id = refunds.transaction_id",
                id="undeclared-table",
            ),
            pytest.param(
                "?& user_profiles on transactions.buyer_id = user_profiles.user_id",
                id="right-join",
            ),
        ],
    )
    def test_metric_over_unprovable_join_raises(self, join: str) -> None:
        with pytest.raises(ASQLResolutionError, match="cannot be computed over"):
            _compile(f"from transactions {join} group by status ( volume )")

    @pytest.mark.parametrize("side", ["right", "full"])
    def test_metric_over_sql_style_outer_join_raises(self, side: str) -> None:
        with pytest.raises(ASQLResolutionError, match="cannot be computed over"):
            _compile(
                "select user_profiles.country, transaction_count from transactions "
                f"{side} join user_profiles "
                "on transactions.buyer_id = user_profiles.user_id "
                "group by user_profiles.country"
            )

    def test_metric_over_right_join_to_collapsed_many_side_raises(self) -> None:
        with pytest.raises(ASQLResolutionError, match="cannot be computed over"):
            _compile(
                "select status, transaction_count from transactions "
                "right join line_items "
                "on transactions.transaction_id = line_items.transaction_id "
                "group by status"
            )

    def test_metric_over_join_fanout_skipped_raises(self) -> None:
        with pytest.raises(ASQLResolutionError, match="cannot be computed over"):
            _compile(
                "from transactions & line_items "
                "on transactions.transaction_id = line_items.transaction_id "
                "group by line_items.quantity ( volume )"
            )

    def test_metric_over_declared_many_to_one_join_compiles(self) -> None:
        sql = _compile(
            "from transactions & user_profiles "
            "on transactions.buyer_id = user_profiles.user_id "
            "group by user_profiles.country ( volume )"
        )
        assert "SUM(transactions.amount) AS volume" in sql

    def test_count_metric_over_protected_join_compiles(self) -> None:
        sql = _compile(
            "from transactions & line_items "
            "on transactions.transaction_id = line_items.transaction_id "
            "group by status ( transaction_count )"
        )
        assert "SELECT DISTINCT line_items.transaction_id" in sql
        assert "COUNT(*) counts joined rows" not in sql

    def test_user_count_star_beside_metric_keeps_its_warning(self) -> None:
        sql = _compile(
            "from transactions & line_items "
            "on transactions.transaction_id = line_items.transaction_id "
            "group by status ( transaction_count, # as rows_seen )"
        )
        assert "COUNT(*) counts joined rows" in sql

    def test_metric_over_join_to_cte_named_like_a_model_raises(self) -> None:
        with pytest.raises(ASQLResolutionError, match="cannot be computed over"):
            _compile(
                "with user_profiles as (select transaction_id as user_id, "
                "quantity as country from line_items) "
                "select user_profiles.country, volume from transactions "
                "join user_profiles on transactions.buyer_id = user_profiles.user_id "
                "group by user_profiles.country"
            )

    def test_cte_named_like_a_model_is_not_resolved(self) -> None:
        sql = _compile(
            "with transactions as (select amount as volume from refunds) "
            "select volume from transactions"
        )
        assert "SUM(" not in sql

    def test_joined_subquery_alias_collision_raises(self) -> None:
        with pytest.raises(ASQLResolutionError, match="rename the alias"):
            _compile(
                "from transactions & (from user_profiles) as buyer "
                "on transactions.buyer_id = buyer.user_id "
                "group by buyer.country ( # as n )"
            )
