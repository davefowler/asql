"""Resolve semantic-graph references in queries over graph models.

In a SELECT whose FROM is a model of the schema's semantic graph:

- a bare metric name expands to its expression (derived metrics recursively),
  with the model's columns qualified by the FROM alias;
- ``relationship.attribute`` becomes the attribute expression on a LEFT JOIN to
  the model whose grain is exactly the relationship's entity. That grain proves
  the join is many-to-one, so it cannot multiply FROM rows, and every metric
  stays exact in a single grouped SELECT.
"""

from __future__ import annotations

import typing as t
from dataclasses import dataclass

from sqlglot import exp

from asql.compiler.fanout import FROM_KEY, adds_unmatched_rows, equi_join_columns
from asql.errors import ASQLResolutionError
from asql.semantic import GraphRelationship, Model, SemanticGraph, metric_references

if t.TYPE_CHECKING:
    from asql.config import CompileSettings


@dataclass(frozen=True)
class _AttributeTarget:
    relationship: str
    model: str
    on: list[tuple[str, str]]  # (FROM-model column, target-model column)
    expression: exp.Expr


def resolve_semantic_references(ast: exp.Expr, settings: CompileSettings) -> exp.Expr:
    graph = settings.schema.graph if settings.schema else None
    if graph is None:
        return ast
    cte_names = {cte.alias_or_name.lower() for cte in ast.find_all(exp.CTE)}
    for select in list(ast.find_all(exp.Select)):
        _resolve_select(select, graph, settings, cte_names)
    return ast


def check_metric_fanout(ast: exp.Expr) -> None:
    """Raise when a metric's select keeps a join that can add or multiply rows:
    an outer join, or one neither proven many-to-one nor rewritten by fanout."""
    for select in ast.find_all(exp.Select):
        joins = select.meta.get("metric_joins")
        if not joins:
            continue
        rewritten = select.meta.get("fanout_rewritten", set())
        unsafe = [
            alias
            for alias, proven, outer in joins
            if outer or (not proven and alias not in rewritten)
        ]
        if unsafe:
            raise ASQLResolutionError(
                f"Metrics {', '.join(select.meta['semantic_metrics'])} cannot be "
                f"computed over the join to {', '.join(unsafe)}: ASQL can only prove "
                "a join safe when it follows a declared many-to-one relationship or "
                "fanout protection rewrites it, and the join adds no unmatched rows. "
                "Aggregate the metric in its own step and join the result instead."
            )


def _resolve_select(
    select: exp.Select,
    graph: SemanticGraph,
    settings: CompileSettings,
    cte_names: set[str],
) -> None:
    from_clause = select.args.get(FROM_KEY)
    if from_clause is None or not isinstance(from_clause.this, exp.Table):
        return
    name = from_clause.this.name.lower()
    model = None if name in cte_names else graph.models.get(name)
    if model is None:
        return
    from_alias = from_clause.this.alias_or_name

    projection_aliases = {
        e.alias.lower() for e in select.expressions if isinstance(e, exp.Alias)
    }
    projected_metrics = {
        e.name.lower()
        for e in select.expressions
        if _is_metric_ref(e, graph, model, projection_aliases)
    }
    where = select.args.get("where")
    for column in _own_columns(select):
        if (
            where is not None
            and column.find_ancestor(exp.Where) is where
            and _is_metric_ref(column, graph, model, projection_aliases)
        ):
            raise ASQLResolutionError(
                f'Metric "{column.name.lower()}" is an aggregate and cannot be used '
                "in a where before group by; filter after the group by block."
            )

    metric_refs = [
        column
        for column in _own_columns(select)
        if _is_metric_ref(column, graph, model, projection_aliases)
        and (column.parent is select or column.name.lower() not in projected_metrics)
    ]
    has_relationship_refs = any(
        column.table.lower() in model.relationships for column in _own_columns(select)
    )
    if not metric_refs and not has_relationship_refs:
        return

    user_joins = list(select.args.get("joins") or [])
    if metric_refs and user_joins:
        if not select.args.get("group") or not settings.fanout_protection:
            raise ASQLResolutionError(
                "Metrics over a join need a group by with fanout protection on, so "
                "the join cannot multiply the metric's rows; aggregate the metric in "
                "its own step and join the result instead."
            )
        select.meta["semantic_metrics"] = sorted(
            {column.name.lower() for column in metric_refs}
        )
        select.meta["metric_joins"] = [
            (
                join.this.alias_or_name.lower(),
                _declared_many_to_one(join, model, from_alias, settings, cte_names),
                adds_unmatched_rows(join),
            )
            for join in user_joins
        ]

    for column in metric_refs:
        name = column.name.lower()
        expansion = _expand_metric(name, graph, model, from_alias)
        if column.parent is select:
            column.replace(exp.alias_(expansion, name))
        else:
            _replace(column, expansion)

    # With user joins, a bare name may belong to a joined table ASQL can't see.
    reserved = projection_aliases | projected_metrics
    for column in [] if user_joins else _own_columns(select):
        name = column.name.lower()
        if (
            not column.table
            and name in model.schema
            and name not in reserved
            and not column.find_ancestor(exp.Star)
        ):
            column.set("table", exp.to_identifier(from_alias))

    _resolve_attributes(select, graph, model, from_alias)


def _declared_many_to_one(
    join: exp.Join,
    model: Model,
    from_alias: str,
    settings: CompileSettings,
    cte_names: set[str],
) -> bool:
    """A plain equi-join from the FROM model along a declared relationship, whose
    target grain is the join key, so it cannot multiply FROM rows."""
    columns = equi_join_columns(join)
    if columns is None or settings.schema is None:
        return False
    joined = join.this
    if joined.name.lower() in cte_names:
        return False
    for local, remote in (columns, columns[::-1]):
        if (
            local.table.lower() == from_alias.lower()
            and remote.table.lower() == joined.alias_or_name.lower()
        ):
            return any(
                rel.source == "explicit"
                and rel.from_column == local.name.lower()
                and rel.to_column == remote.name.lower()
                for rel in settings.schema.find_all_relationships(
                    model.name, joined.name
                )
            )
    return False


def _is_metric_ref(
    node: exp.Expr, graph: SemanticGraph, model: Model, aliases: set[str]
) -> bool:
    if not isinstance(node, exp.Column) or node.table:
        return False
    name = node.name.lower()
    return name in graph.metrics and name not in model.schema and name not in aliases


def _own_columns(select: exp.Select) -> list[exp.Column]:
    return [
        column
        for column in select.find_all(exp.Column)
        if column.find_ancestor(exp.Select) is select
    ]


def _replace(node: exp.Expr, expansion: exp.Expr) -> None:
    if isinstance(expansion, exp.Binary) and isinstance(
        node.parent, (exp.Binary, exp.Unary)
    ):
        expansion = exp.paren(expansion, copy=False)
    node.replace(expansion)


def _expand_metric(
    name: str, graph: SemanticGraph, model: Model, from_alias: str
) -> exp.Expr:
    metric = graph.metrics[name]
    expression = metric.expression.copy()
    references = metric_references(metric, graph)
    unqualified = [c for c in expression.find_all(exp.Column) if not c.table]
    own_columns = [c for c in unqualified if c.name.lower() not in references]
    if metric.model != model.name and (own_columns or expression.find(exp.AggFunc)):
        raise ASQLResolutionError(
            f'Metric "{metric.name}" is defined on model "{metric.model}", not '
            f'"{model.name}"; query it from {metric.model}.'
        )
    for column in own_columns:
        column.set("table", exp.to_identifier(from_alias))
    for count in expression.find_all(exp.Count):
        count.meta["semantic_metric"] = True
    for column in unqualified:
        if column.name.lower() in references:
            _replace(
                column, _expand_metric(column.name.lower(), graph, model, from_alias)
            )
    return expression


def _resolve_attributes(
    select: exp.Select, graph: SemanticGraph, model: Model, from_alias: str
) -> None:
    table_aliases = {from_alias.lower()} | {
        join.this.alias_or_name.lower() for join in select.args.get("joins") or []
    }

    refs: list[tuple[exp.Column, _AttributeTarget]] = []
    for column in _own_columns(select):
        rel_name = column.table.lower()
        relationship = model.relationships.get(rel_name)
        if relationship is None:
            continue
        if rel_name in table_aliases:
            raise ASQLResolutionError(
                f'"{rel_name}" is both a relationship on model "{model.name}" and a '
                "table alias in this query; rename the alias."
            )
        refs.append(
            (column, _attribute_target(relationship, column.name.lower(), graph, model))
        )

    targets_by_rel: dict[str, set[str]] = {}
    for _, target in refs:
        targets_by_rel.setdefault(target.relationship, set()).add(target.model)

    if refs:
        for star in select.expressions:
            if isinstance(star, exp.Star):
                star.replace(
                    exp.Column(this=star.copy(), table=exp.to_identifier(from_alias))
                )

    joined: set[str] = set()
    for column, target in refs:
        rel_name = target.relationship
        alias = (
            rel_name
            if len(targets_by_rel[rel_name]) == 1
            else f"{rel_name}__{target.model}"
        )
        if alias not in joined:
            joined.add(alias)
            select.join(
                exp.to_table(target.model).as_(alias),
                on=_join_condition(target, from_alias, alias),
                join_type="left",
                copy=False,
            )

        expression = target.expression.copy()
        for attr_column in expression.find_all(exp.Column):
            attr_column.set("table", exp.to_identifier(alias))
        if column.parent is select:
            column.replace(exp.alias_(expression, f"{rel_name}_{column.name.lower()}"))
        else:
            _replace(column, expression)


def _attribute_target(
    relationship: GraphRelationship, attribute: str, graph: SemanticGraph, model: Model
) -> _AttributeTarget:
    if isinstance(relationship.key, str):
        raise ASQLResolutionError(
            f'Relationship "{relationship.name}" on model "{model.name}" uses a '
            "predicate key; only equality-map keys can be traversed."
        )

    candidates: list[_AttributeTarget] = []
    available: set[str] = set()
    compound_owners: list[Model] = []
    for target in graph.models.values():
        grain = target.single_grain()
        if grain is not None:
            if grain.entity != relationship.entity or not isinstance(grain.key, dict):
                continue
            available.update(grain.attributes)
            if attribute in grain.attributes:
                candidates.append(
                    _AttributeTarget(
                        relationship=relationship.name,
                        model=target.name,
                        on=[
                            (column, grain.key[field])
                            for field, column in relationship.key.items()
                        ],
                        expression=grain.attributes[attribute],
                    )
                )
        elif any(
            rel.entity == relationship.entity and attribute in rel.attributes
            for rel in target.relationships.values()
        ):
            compound_owners.append(target)

    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        owners = ", ".join(c.model for c in candidates)
        raise ASQLResolutionError(
            f'Attribute "{attribute}" of entity "{relationship.entity}" is declared '
            f"on several models ({owners}); keep it on one."
        )
    if compound_owners:
        owner = compound_owners[0]
        grain_text = ", ".join(", ".join(g) for g in owner.grains)
        raise ASQLResolutionError(
            f'Attribute "{attribute}" of entity "{relationship.entity}" is only '
            f'declared on model "{owner.name}", whose grain ({grain_text}) does not make '
            "the join many-to-one; point-in-time joins are not supported yet."
        )
    raise ASQLResolutionError(
        f'Relationship "{relationship.name}" (entity "{relationship.entity}") has no '
        f'attribute "{attribute}". Available: {", ".join(sorted(available))}.'
    )


def _join_condition(target: _AttributeTarget, from_alias: str, alias: str) -> exp.Expr:
    return exp.and_(
        *(
            exp.EQ(
                this=exp.column(from_column, table=from_alias),
                expression=exp.column(target_column, table=alias),
            )
            for from_column, target_column in target.on
        )
    )
