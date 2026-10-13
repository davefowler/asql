"""Resolve `# <name>` count shorthand: a column count or a distinct entity count.

The parser tags every bare `# name` / `#name` count with `ENTITY_CANDIDATE`
because it cannot tell a column from a table. Entity inference needs a schema
that proves `name` is a table; without a schema `# name` is always `COUNT(name)`.

With a schema, over the tables of the counting SELECT (FROM + joins):

- `name` is a column of a table known to the schema: `COUNT(name)`
- `name` is a schema table: `COUNT(DISTINCT <entity key>)`
- otherwise: `COUNT(name)` if some query table is unknown to the schema (a CTE,
  derived table, or partial schema: it may own the column), else
  ASQLResolutionError

`#(name)` is never tagged, so it is always the column count.
"""

from __future__ import annotations

from sqlglot import exp

from asql.config import CompileSettings
from asql.errors import ASQLResolutionError
from asql.schema import Schema, Table, singularize

ENTITY_CANDIDATE = "entity_candidate"

_HINT = "use #(distinct <column>) to name the key explicitly"


def resolve_count_entities(stmt: exp.Expr, settings: CompileSettings) -> exp.Expr:
    """Rewrite tagged `# <name>` counts into COUNT(col) or COUNT(DISTINCT key)."""
    schema = settings.schema
    for count in list(stmt.find_all(exp.Count)):
        if not count.args.pop(ENTITY_CANDIDATE, False) or schema is None:
            continue
        select = count.find_ancestor(exp.Select)
        if select is None:
            continue
        name = count.this.name
        sources = _query_sources(select)
        known = [
            (alias, tbl)
            for alias, table_name in sources
            if table_name is not None
            and (tbl := schema.get_table(table_name)) is not None
        ]
        has_unknown = len(known) < len(sources)

        if any(tbl.has_column(name) for _, tbl in known):
            continue
        if not schema.has_table(name):
            if has_unknown:
                continue
            raise ASQLResolutionError(
                f"Cannot resolve '# {name}': it is neither a column of the query "
                f"tables ({', '.join(a for a, _ in known)}) nor a schema table; "
                "use #(col) to count a column or #(distinct col) to count "
                "distinct values."
            )

        resolved = _entity_key(name, known, schema, has_unknown)
        if resolved is None:
            continue
        alias, key = resolved
        qualifier = alias if len(sources) > 1 else None
        count.set("this", exp.Distinct(expressions=[exp.column(key, table=qualifier)]))
    return stmt


def _query_sources(select: exp.Select) -> list[tuple[str, str | None]]:
    """(alias-or-name, table name or None for non-table sources) per FROM/JOIN."""
    from_clause = select.args.get("from_") or select.args.get("from")
    nodes = [from_clause.this] if from_clause is not None else []
    nodes += [j.this for j in select.args.get("joins") or []]
    return [
        (n.alias or n.name, n.name) if isinstance(n, exp.Table) else (n.alias, None)
        for n in nodes
    ]


def _entity_key(
    entity: str,
    known: list[tuple[str, Table]],
    schema: Schema,
    has_unknown: bool,
) -> tuple[str, str] | None:
    """(table alias, column) in the query that identifies one `entity` row.

    None means the key is not provable but an unknown query table (CTE, derived
    table) might own it, so the caller keeps `COUNT(name)`.
    """
    own = [(a, t) for a, t in known if t.name.lower() == entity.lower()]
    if len(own) > 1:
        raise ASQLResolutionError(
            f"Ambiguous '# {entity}': the table appears as "
            f"{', '.join(a for a, _ in own)}; {_HINT}."
        )
    if own:
        alias, tbl = own[0]
        pk = tbl.get_primary_key()
        if pk is None:
            raise ASQLResolutionError(
                f"Cannot resolve '# {entity}': table '{tbl.name}' has no "
                f"primary key; {_HINT}."
            )
        return alias, pk

    for tier in ("explicit", "inferred"):
        found = {
            (alias, rel.from_column)
            for alias, tbl in known
            for rel in schema.find_all_relationships(tbl.name, entity)
            if rel.source == tier
        }
        if len(found) == 1:
            return found.pop()
        if found:
            via = ", ".join(sorted(f"{a}.{c}" for a, c in found))
            raise ASQLResolutionError(
                f"Ambiguous '# {entity}': relationships via {via}; {_HINT}."
            )

    convention = f"{singularize(entity)}_id"
    owners = [(a, convention) for a, tbl in known if tbl.has_column(convention)]
    if len(owners) == 1:
        return owners[0]
    if has_unknown and not owners:
        return None
    raise ASQLResolutionError(
        f"Cannot resolve '# {entity}': no relationship from "
        f"({', '.join(a for a, _ in known)}) and "
        f"{'several tables have' if owners else 'no query table has'} "
        f"'{convention}'; {_HINT}."
    )
