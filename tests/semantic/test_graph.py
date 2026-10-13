"""Loading a dbt-metrics graph.yaml and projecting it to an ASQL Schema."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from asql.errors import ASQLResolutionError
from asql.schema import Schema
from asql.semantic import SemanticGraph, load_graph

GRAPH_PATH = Path(__file__).parent / "marketplace.graph.yaml"


def _graph_dict() -> dict[str, Any]:
    return yaml.safe_load(GRAPH_PATH.read_text())


def _load(data: dict[str, Any]) -> SemanticGraph:
    return SemanticGraph.from_dict(data)


class TestLoadGraph:
    def test_entities_models_and_grains(self) -> None:
        graph = load_graph(GRAPH_PATH)

        assert graph.dialect == "duckdb"
        assert graph.entities["user"].key == {"id": "INT"}
        assert graph.models["transactions"].grains == [("transaction",)]
        assert graph.models["user_addresses"].grains == [("user", "as_of")]
        assert graph.models["transactions"].schema["amount"] == "INT"

    def test_relationships(self) -> None:
        transactions = load_graph(GRAPH_PATH).models["transactions"]

        buyer = transactions.relationships["buyer"]
        assert buyer.entity == "user"
        assert buyer.key == {"id": "buyer_id"}
        assert transactions.relationships["transaction"].entity == "transaction"

    def test_predicate_key_loads(self) -> None:
        as_of = load_graph(GRAPH_PATH).models["user_addresses"].relationships["as_of"]
        assert as_of.entity == "datetime"
        assert isinstance(as_of.key, str)
        assert "valid_from" in as_of.key

    def test_attributes_short_and_long_form(self) -> None:
        user = load_graph(GRAPH_PATH).models["user_profiles"].relationships["user"]

        assert user.attributes["email"].sql() == "email"
        assert user.attributes["country"].sql() == "country"
        assert user.attributes["country_lower"].sql() == "LOWER(country)"

    def test_metrics_indexed_globally_with_home_model(self) -> None:
        graph = load_graph(GRAPH_PATH)

        assert graph.metrics["volume"].model == "transactions"
        assert graph.metrics["volume"].expression.sql() == "SUM(amount)"
        assert graph.metrics["transaction_count"].expression.sql() == "COUNT(*)"
        assert graph.metrics["item_count"].model == "line_items"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_graph(tmp_path / "nope.yaml")

    def test_unknown_top_level_key_raises(self) -> None:
        data = _graph_dict()
        data["dimensions"] = {}
        with pytest.raises(ASQLResolutionError, match='Unknown key "dimensions"'):
            _load(data)

    def test_unknown_model_key_raises(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["measures"] = {}
        with pytest.raises(
            ASQLResolutionError,
            match='Unknown key "measures" in models.transactions; expected one of: ',
        ):
            _load(data)

    def test_unknown_relationship_key_raises(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["relationships"]["buyer"]["cardinality"] = "m:1"
        with pytest.raises(ASQLResolutionError, match='Unknown key "cardinality"'):
            _load(data)

    def test_duplicate_metric_name_raises(self) -> None:
        data = _graph_dict()
        data["models"]["line_items"]["metrics"]["volume"] = "SUM(quantity)"
        with pytest.raises(
            ASQLResolutionError,
            match='Metric "volume" is defined on both models "transactions" and "line_items"',
        ):
            _load(data)

    def test_metric_grain_not_supported(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["metrics"]["total_volume"] = {
            "expression": "SUM(amount)",
            "grain": [],
        }
        with pytest.raises(
            ASQLResolutionError,
            match='Metric "total_volume": per-metric grain is not supported yet.',
        ):
            _load(data)

    def test_unknown_entity_raises(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["relationships"]["buyer"]["entity"] = "person"
        with pytest.raises(ASQLResolutionError, match='unknown entity "person"'):
            _load(data)

    def test_key_fields_must_match_entity_key(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["relationships"]["buyer"]["key"] = {
            "uid": "buyer_id"
        }
        with pytest.raises(ASQLResolutionError, match="key fields"):
            _load(data)

    def test_key_column_must_exist_in_schema(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["relationships"]["buyer"]["key"] = {
            "id": "purchaser_id"
        }
        with pytest.raises(ASQLResolutionError, match='"purchaser_id"'):
            _load(data)

    def test_grain_must_name_a_relationship(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["grains"] = ["order"]
        with pytest.raises(ASQLResolutionError, match='grain "order"'):
            _load(data)


class TestSchemaFromGraph:
    def test_tables_and_columns(self) -> None:
        schema = Schema.from_graph(load_graph(GRAPH_PATH))

        transactions = schema.get_table("transactions")
        assert transactions is not None
        assert set(transactions.columns) == {
            "transaction_id",
            "created_at",
            "buyer_id",
            "seller_id",
            "amount",
            "status",
        }
        assert transactions.columns["amount"].type == "INT"

    def test_grain_key_is_primary_key(self) -> None:
        schema = Schema.from_graph(load_graph(GRAPH_PATH))

        transactions = schema.get_table("transactions")
        profiles = schema.get_table("user_profiles")
        assert transactions is not None and profiles is not None
        assert transactions.get_primary_key() == "transaction_id"
        assert profiles.get_primary_key() == "user_id"
        assert not transactions.is_column_unique("buyer_id")

    def test_compound_grain_has_no_primary_key_column(self) -> None:
        addresses = Schema.from_graph(load_graph(GRAPH_PATH)).get_table(
            "user_addresses"
        )
        assert addresses is not None
        assert not addresses.is_column_unique("user_id")

    def test_relationships_point_at_single_grain_models(self) -> None:
        schema = Schema.from_graph(load_graph(GRAPH_PATH))

        buyer = schema.find_all_relationships("transactions", "user_profiles")
        assert {(r.from_column, r.to_column, r.alias) for r in buyer} == {
            ("buyer_id", "user_id", "buyer"),
            ("seller_id", "user_id", "seller"),
        }
        assert all(r.source == "explicit" for r in buyer)

        items = schema.find_all_relationships("line_items", "transactions")
        assert [(r.from_column, r.to_column) for r in items] == [
            ("transaction_id", "transaction_id")
        ]

    def test_no_relationship_to_compound_grain_model(self) -> None:
        schema = Schema.from_graph(load_graph(GRAPH_PATH))
        assert schema.find_all_relationships("transactions", "user_addresses") == []

    def test_no_self_relationship_for_grain(self) -> None:
        schema = Schema.from_graph(load_graph(GRAPH_PATH))
        assert schema.find_all_relationships("transactions", "transactions") == []

    def test_schema_carries_graph(self) -> None:
        graph = load_graph(GRAPH_PATH)
        assert Schema.from_graph(graph).graph is graph


class TestMetricValidation:
    def test_metric_named_like_own_column_raises(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["metrics"]["amount"] = "SUM(amount)"
        with pytest.raises(
            ASQLResolutionError,
            match='Metric "amount" on model "transactions" has the same name as '
            "one of its columns; rename the metric.",
        ):
            _load(data)

    def test_metric_cycle_raises(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["metrics"]["a"] = "b + 1"
        data["models"]["transactions"]["metrics"]["b"] = "a + 1"
        with pytest.raises(ASQLResolutionError, match="Metric cycle: a -> b -> a."):
            _load(data)

    def test_unknown_reference_raises(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["metrics"]["bad"] = "SUM(price)"
        with pytest.raises(
            ASQLResolutionError,
            match='Metric "bad" references "price", which is neither a column of '
            'model "transactions" nor a metric.',
        ):
            _load(data)

    def test_row_level_metric_raises(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["metrics"]["doubled"] = "amount * 2"
        with pytest.raises(
            ASQLResolutionError,
            match='Metric "doubled" must be an aggregate or arithmetic over other '
            "metrics.",
        ):
            _load(data)

    def test_unknown_relationship_in_metric_raises(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["metrics"]["bad"] = (
            "SUM(amount) FILTER (WHERE payer.country = 'CN')"
        )
        with pytest.raises(
            ASQLResolutionError,
            match='Metric "bad" references "payer.country", but "payer" is not a '
            'relationship on model "transactions".',
        ):
            _load(data)


class TestLoaderShapes:
    def test_section_must_be_mapping(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["metrics"] = ["volume"]
        with pytest.raises(
            ASQLResolutionError,
            match="Expected a mapping for models.transactions.metrics.",
        ):
            _load(data)

    def test_grains_must_be_list(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["grains"] = "transaction"
        with pytest.raises(
            ASQLResolutionError, match="models.transactions.grains must be a list."
        ):
            _load(data)

    def test_case_insensitive_name_collision_raises(self) -> None:
        data = _graph_dict()
        data["models"]["Transactions"] = data["models"]["transactions"]
        with pytest.raises(
            ASQLResolutionError, match='Duplicate name "transactions" in models'
        ):
            _load(data)

    def test_unparsable_expression_names_location(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["metrics"]["bad"] = "SUM(amount"
        with pytest.raises(
            ASQLResolutionError, match="Cannot parse models.transactions.metrics.bad"
        ):
            _load(data)

    def test_entity_needs_key(self) -> None:
        data = _graph_dict()
        data["entities"]["user"] = {"description": "no key"}
        with pytest.raises(
            ASQLResolutionError, match='Entity "user" needs a non-empty key mapping.'
        ):
            _load(data)

    def test_relationship_needs_key(self) -> None:
        data = _graph_dict()
        del data["models"]["transactions"]["relationships"]["buyer"]["key"]
        with pytest.raises(ASQLResolutionError, match="needs a key"):
            _load(data)

    def test_attributes_only_on_grain_relationships(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["relationships"]["buyer"]["attributes"] = {
            "country": "status"
        }
        with pytest.raises(
            ASQLResolutionError,
            match='Relationship "buyer" on model "transactions" declares attributes, '
            "but only relationships in the model's grain can expose attributes.",
        ):
            _load(data)

    def test_aggregate_mixed_with_bare_column_raises(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["metrics"]["bad"] = "volume + amount"
        with pytest.raises(
            ASQLResolutionError, match='"amount" is used outside an aggregate'
        ):
            _load(data)

    def test_window_metric_raises(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["metrics"]["running"] = "SUM(amount) OVER ()"
        with pytest.raises(ASQLResolutionError, match="uses a window function"):
            _load(data)


def test_compound_keys_contribute_no_primary_key_or_relationship() -> None:
    data = _graph_dict()
    data["entities"]["account"] = {"key": {"org_id": "INT", "account_id": "INT"}}
    data["models"]["accounts"] = {
        "grains": ["account"],
        "schema": {"org_id": "INT", "account_id": "INT"},
        "relationships": {
            "account": {"key": {"org_id": "org_id", "account_id": "account_id"}}
        },
    }
    data["models"]["transactions"]["schema"]["org_id"] = "INT"
    data["models"]["transactions"]["schema"]["account_id"] = "INT"
    data["models"]["transactions"]["relationships"]["account"] = {
        "key": {"org_id": "org_id", "account_id": "account_id"}
    }
    schema = Schema.from_graph(_load(data))

    accounts = schema.get_table("accounts")
    assert accounts is not None
    assert not accounts.is_column_unique("org_id")
    assert not accounts.is_column_unique("account_id")
    assert schema.find_all_relationships("transactions", "accounts") == []


class TestAttributeAndMetricShapes:
    def test_attribute_column_must_exist(self) -> None:
        data = _graph_dict()
        data["models"]["user_profiles"]["relationships"]["user"]["attributes"][
            "email"
        ] = "emial"
        with pytest.raises(
            ASQLResolutionError,
            match='Attribute "email" on models.user_profiles.relationships.user '
            'references "emial", which is not a column of model "user_profiles".',
        ):
            _load(data)

    def test_aggregate_attribute_raises(self) -> None:
        data = _graph_dict()
        data["models"]["user_profiles"]["relationships"]["user"]["attributes"]["n"] = (
            "COUNT(*)"
        )
        with pytest.raises(ASQLResolutionError, match="must be a row-level expression"):
            _load(data)

    def test_metric_aggregating_a_metric_raises(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["metrics"]["bad"] = "SUM(volume)"
        with pytest.raises(
            ASQLResolutionError,
            match='Metric "bad" aggregates the metric "volume"',
        ):
            _load(data)

    def test_relationship_default_not_supported(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["relationships"]["buyer"]["default"] = True
        with pytest.raises(ASQLResolutionError, match="`default` is not supported yet"):
            _load(data)

    def test_empty_graph_raises(self) -> None:
        with pytest.raises(ASQLResolutionError, match="declares no models"):
            SemanticGraph.from_dict({})

    def test_column_type_must_be_a_string(self) -> None:
        data = _graph_dict()
        data["models"]["transactions"]["schema"]["amount"] = None
        with pytest.raises(
            ASQLResolutionError,
            match="models.transactions.schema.amount needs a type name",
        ):
            _load(data)
