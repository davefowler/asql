"""Semantic graph: the dbt-metrics ``graph.yaml`` format, read by ASQL.

The graph declares entities (typed keys), models (tables with grains,
relationships to entities, and metrics). Input is validated strictly:
unknown keys, dangling references, and shapes ASQL cannot compile safely raise
``ASQLResolutionError`` at load time.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sqlglot
import yaml
from sqlglot import exp
from sqlglot.errors import SqlglotError

from asql.errors import ASQLResolutionError

_GRAPH_KEYS = ("config", "entities", "models")
_CONFIG_KEYS = ("dialect",)
_ENTITY_KEYS = ("description", "key")
_MODEL_KEYS = ("description", "schema", "grains", "relationships", "metrics")
_RELATIONSHIP_KEYS = ("description", "entity", "key", "attributes", "default")
_EXPRESSION_KEYS = ("expression", "description", "grain")


@dataclass(frozen=True)
class Entity:
    name: str
    key: dict[str, str]


@dataclass(frozen=True)
class GraphRelationship:
    """How a model's columns satisfy an entity's key.

    ``key`` maps entity key fields to this model's columns, or is a raw SQL
    predicate (e.g. an SCD2 interval join), which ASQL loads but cannot traverse.
    """

    name: str
    entity: str
    key: dict[str, str] | str
    attributes: dict[str, exp.Expr]


@dataclass(frozen=True)
class Metric:
    name: str
    model: str
    expression: exp.Expr


@dataclass(frozen=True)
class Model:
    name: str
    schema: dict[str, str]
    grains: list[tuple[str, ...]]
    relationships: dict[str, GraphRelationship]

    def single_grain(self) -> GraphRelationship | None:
        """The relationship that alone makes rows unique, if the grain is one entity."""
        if len(self.grains) == 1 and len(self.grains[0]) == 1:
            return self.relationships[self.grains[0][0]]
        return None


@dataclass(frozen=True)
class SemanticGraph:
    dialect: str | None
    entities: dict[str, Entity]
    models: dict[str, Model]
    metrics: dict[str, Metric]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticGraph:
        data = _check_keys(data, _GRAPH_KEYS, "the graph")
        config = _check_keys(data.get("config"), _CONFIG_KEYS, "config")
        dialect = config.get("dialect")

        entities = {
            name: _parse_entity(name, spec)
            for name, spec in _mapping(data.get("entities"), "entities").items()
        }
        models: dict[str, Model] = {}
        metrics: dict[str, Metric] = {}
        for name, spec in _mapping(data.get("models"), "models").items():
            model, model_metrics = _parse_model(name, spec, entities, dialect)
            models[model.name] = model
            for metric in model_metrics:
                if metric.name in metrics:
                    raise ASQLResolutionError(
                        f'Metric "{metric.name}" is defined on both models '
                        f'"{metrics[metric.name].model}" and "{model.name}".'
                    )
                metrics[metric.name] = metric

        if not models:
            raise ASQLResolutionError("The graph declares no models.")
        graph = cls(dialect=dialect, entities=entities, models=models, metrics=metrics)
        for metric in metrics.values():
            _validate_metric(metric, graph)
        _check_metric_cycles(graph)
        return graph


def load_graph(path: str | Path) -> SemanticGraph:
    """Load a dbt-metrics ``graph.yaml`` file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Graph file not found: {path}")
    return SemanticGraph.from_dict(yaml.safe_load(path.read_text()))


def metric_references(metric: Metric, graph: SemanticGraph) -> set[str]:
    """Metrics a metric's expression references as bare names.

    A bare name that is a column of the metric's own model is that column, even
    when another model defines a metric of the same name.
    """
    own_schema = graph.models[metric.model].schema
    return {
        name
        for column in metric.expression.find_all(exp.Column)
        if not column.table
        and (name := column.name.lower()) in graph.metrics
        and name not in own_schema
    }


def _mapping(value: Any, where: str) -> dict[str, Any]:
    """A YAML mapping with case-insensitive (lowercased) keys; an absent one is empty."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ASQLResolutionError(f"Expected a mapping for {where}.")
    result: dict[str, Any] = {}
    for key, item in value.items():
        name = str(key).lower()
        if name in result:
            raise ASQLResolutionError(
                f'Duplicate name "{name}" in {where}; names are case-insensitive.'
            )
        result[name] = item
    return result


def _check_keys(spec: Any, allowed: tuple[str, ...], where: str) -> dict[str, Any]:
    result = _mapping(spec, where)
    for key in result:
        if key not in allowed:
            raise ASQLResolutionError(
                f'Unknown key "{key}" in {where}; expected one of: '
                f"{', '.join(allowed)}."
            )
    return result


def _parse_entity(name: str, spec: Any) -> Entity:
    spec = _check_keys(spec, _ENTITY_KEYS, f"entities.{name}")
    key = _mapping(spec.get("key"), f"entities.{name}.key")
    if not key:
        raise ASQLResolutionError(f'Entity "{name}" needs a non-empty key mapping.')
    return Entity(
        name=name,
        key={
            field: _type_name(dtype, f"entities.{name}.key.{field}")
            for field, dtype in key.items()
        },
    )


def _parse_model(
    name: str,
    spec: Any,
    entities: dict[str, Entity],
    dialect: str | None,
) -> tuple[Model, list[Metric]]:
    where = f"models.{name}"
    spec = _check_keys(spec, _MODEL_KEYS, where)
    schema = {
        col: _type_name(dtype, f"{where}.schema.{col}")
        for col, dtype in _mapping(spec.get("schema"), f"{where}.schema").items()
    }

    relationships = {
        rel: _parse_relationship(rel, rel_spec, name, schema, entities, dialect)
        for rel, rel_spec in _mapping(
            spec.get("relationships"), f"{where}.relationships"
        ).items()
    }

    raw_grains = spec.get("grains")
    if raw_grains is not None and not isinstance(raw_grains, list):
        raise ASQLResolutionError(f"{where}.grains must be a list.")
    grains: list[tuple[str, ...]] = []
    for grain in raw_grains or []:
        parts = tuple(part.strip().lower() for part in str(grain).split(","))
        for part in parts:
            if part not in relationships:
                raise ASQLResolutionError(
                    f'Model "{name}" declares grain "{part}", which is not one of '
                    "its relationships."
                )
        grains.append(parts)

    in_grain = {part for grain in grains for part in grain}
    for rel in relationships.values():
        if rel.attributes and rel.name not in in_grain:
            raise ASQLResolutionError(
                f'Relationship "{rel.name}" on model "{name}" declares attributes, '
                "but only relationships in the model's grain can expose attributes."
            )

    metrics: list[Metric] = []
    for metric_name, metric_spec in _mapping(
        spec.get("metrics"), f"{where}.metrics"
    ).items():
        if metric_name in schema:
            raise ASQLResolutionError(
                f'Metric "{metric_name}" on model "{name}" has the same name as one '
                "of its columns; rename the metric."
            )
        metrics.append(
            Metric(
                name=metric_name,
                model=name,
                expression=_parse_expression(
                    metric_spec, f"{where}.metrics.{metric_name}", dialect, metric_name
                ),
            )
        )

    model = Model(name=name, schema=schema, grains=grains, relationships=relationships)
    return model, metrics


def _parse_relationship(
    name: str,
    spec: Any,
    model: str,
    schema: dict[str, str],
    entities: dict[str, Entity],
    dialect: str | None,
) -> GraphRelationship:
    where = f"models.{model}.relationships.{name}"
    spec = _check_keys(spec, _RELATIONSHIP_KEYS, where)
    if "default" in spec:
        raise ASQLResolutionError(
            f'Relationship "{name}" on model "{model}": `default` is not supported yet.'
        )
    entity_name = str(spec.get("entity", name)).lower()
    entity = entities.get(entity_name)
    if entity is None:
        raise ASQLResolutionError(
            f'Relationship "{name}" on model "{model}" refers to unknown entity '
            f'"{entity_name}".'
        )

    raw_key = spec.get("key")
    key: dict[str, str] | str
    if isinstance(raw_key, str):
        key = raw_key
    elif isinstance(raw_key, dict):
        key = {
            field: str(column).lower()
            for field, column in _mapping(raw_key, f"{where}.key").items()
        }
        if set(key) != set(entity.key):
            raise ASQLResolutionError(
                f'Relationship "{name}" on model "{model}" has key fields '
                f'{sorted(key)}, but entity "{entity.name}" has key fields '
                f"{sorted(entity.key)}."
            )
        for column in key.values():
            if column not in schema:
                raise ASQLResolutionError(
                    f'Relationship "{name}" on model "{model}" keys on "{column}", '
                    f'which is not in the schema of model "{model}".'
                )
    else:
        raise ASQLResolutionError(
            f'Relationship "{name}" on model "{model}" needs a key: a mapping of '
            "entity key fields to columns, or a SQL predicate."
        )

    attributes = {
        attr: _parse_attribute(attr, attr_spec, where, model, schema, dialect)
        for attr, attr_spec in _mapping(
            spec.get("attributes"), f"{where}.attributes"
        ).items()
    }
    return GraphRelationship(
        name=name, entity=entity.name, key=key, attributes=attributes
    )


def _type_name(dtype: Any, where: str) -> str:
    if not isinstance(dtype, str) or not dtype.strip():
        raise ASQLResolutionError(f"{where} needs a type name.")
    return dtype


def _parse_attribute(
    name: str,
    spec: Any,
    where: str,
    model: str,
    schema: dict[str, str],
    dialect: str | None,
) -> exp.Expr:
    expression = _parse_expression(spec, f"{where}.attributes.{name}", dialect, None)
    if expression.find(exp.AggFunc, exp.Window):
        raise ASQLResolutionError(
            f'Attribute "{name}" on {where} must be a row-level expression, not an '
            "aggregate or window."
        )
    for column in expression.find_all(exp.Column):
        if column.table or column.name.lower() not in schema:
            raise ASQLResolutionError(
                f'Attribute "{name}" on {where} references "{column.sql()}", which is '
                f'not a column of model "{model}".'
            )
    return expression


def _parse_expression(
    spec: Any, where: str, dialect: str | None, metric_name: str | None
) -> exp.Expr:
    if isinstance(spec, dict):
        spec = _check_keys(spec, _EXPRESSION_KEYS, where)
        if "grain" in spec:
            if metric_name is None:
                raise ASQLResolutionError(f'Unknown key "grain" in {where}.')
            raise ASQLResolutionError(
                f'Metric "{metric_name}": per-metric grain is not supported yet.'
            )
        spec = spec.get("expression")
    if not isinstance(spec, str) or not spec.strip():
        raise ASQLResolutionError(f"{where} needs a SQL expression.")
    try:
        return sqlglot.parse_one(spec, read=dialect)
    except (SqlglotError, ValueError) as error:
        raise ASQLResolutionError(f"Cannot parse {where}: {error}") from error


def _validate_metric(metric: Metric, graph: SemanticGraph) -> None:
    model = graph.models[metric.model]
    references = metric_references(metric, graph)
    for column in metric.expression.find_all(exp.Column):
        name = column.name.lower()
        if not column.table and name in references:
            if column.find_ancestor(exp.AggFunc):
                raise ASQLResolutionError(
                    f'Metric "{metric.name}" aggregates the metric "{name}"; metrics '
                    "can only be combined with arithmetic."
                )
            continue
        if column.table:
            rel = column.table.lower()
            if rel not in model.relationships:
                raise ASQLResolutionError(
                    f'Metric "{metric.name}" references "{rel}.{name}", but "{rel}" '
                    f'is not a relationship on model "{model.name}".'
                )
        elif name not in model.schema:
            raise ASQLResolutionError(
                f'Metric "{metric.name}" references "{name}", which is neither a '
                f'column of model "{model.name}" nor a metric.'
            )
        if not column.find_ancestor(exp.AggFunc, exp.Filter, exp.WithinGroup):
            raise ASQLResolutionError(
                f'Metric "{metric.name}" must be an aggregate or arithmetic over other '
                f'metrics; "{column.sql()}" is used outside an aggregate.'
            )
    if metric.expression.find(exp.Window):
        raise ASQLResolutionError(
            f'Metric "{metric.name}" uses a window function; metrics must be '
            "aggregates or arithmetic over other metrics."
        )
    if not references and not metric.expression.find(exp.AggFunc):
        raise ASQLResolutionError(
            f'Metric "{metric.name}" must be an aggregate or arithmetic over other '
            "metrics."
        )


def _check_metric_cycles(graph: SemanticGraph) -> None:
    done: set[str] = set()

    def visit(name: str, path: list[str]) -> None:
        if name in path:
            cycle = path[path.index(name) :] + [name]
            raise ASQLResolutionError(f"Metric cycle: {' -> '.join(cycle)}.")
        if name in done:
            return
        for ref in sorted(metric_references(graph.metrics[name], graph)):
            visit(ref, [*path, name])
        done.add(name)

    for name in graph.metrics:
        visit(name, [])
