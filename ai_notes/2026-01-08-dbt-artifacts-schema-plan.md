# 2026-01-08 — Plan: schema loading via dbt artifacts (dbt-asql)

Goal: get **high-quality schema + relationships** for ASQL features (join inference, star expansion, optimizer rules) without building a bespoke DB introspector.

Key decision: **let dbt do the heavy lifting** (parsing project + querying warehouse for catalogs), and have dbt-asql read dbt artifacts from `target/`.

## What dbt artifacts we should use

### 1) `target/manifest.json` (cheap, always available after `dbt parse`)

Use for:
- model/source graph (dependencies)
- column names (sometimes types)
- dbt tests metadata (especially `relationships` tests)
- compiled metadata (node identifiers, names, etc.)

Pros:
- fast to produce (`dbt parse`)
- doesn’t require warehouse connectivity in many setups (parsing only)

Cons:
- may not have real column types (depends on dbt version/adapter + where metadata is populated)

### 2) `target/catalog.json` (richer, requires `dbt docs generate`)

Use for:
- actual column types and table metadata (more reliable for optimizer/type logic)
- (optionally) column visibility and descriptions

Pros:
- best source of “real” database column metadata

Cons:
- requires warehouse connectivity
- more expensive (invokes introspection queries via dbt adapter)

### 3) Fallback: `schema.yml` files in repo (no artifacts)

Use for:
- explicit relationships via `relationships` tests
- declared columns (names)

This is useful when a project doesn’t have `target/` artifacts checked in and you don’t want to run dbt.

## Recommended dbt-asql behavior

### CLI behavior (artifact-first, shell-out fallback)

- **Default**: if artifacts exist, read them. If missing, generate them.
- Commands:
  - Ensure manifest: `dbt parse`
  - Ensure catalog (optional flag): `dbt docs generate`

Suggested flags:
- `--schema-source=manifest|catalog|manifest_then_catalog|yml_only`
  - default: `manifest_then_catalog` (use catalog if present; otherwise manifest)
- `--generate-artifacts` (default: true)
  - if true: run dbt commands when artifacts are missing/stale
  - if false: error with a helpful message pointing to `dbt parse` / `dbt docs generate`
- `--prefer-catalog` (default: false unless requested)
  - if true: require `catalog.json` and fail if missing

### How to locate the dbt project + target dir

Given a path (model file, project root, etc.):
- walk up directories until finding `dbt_project.yml`
- define:
  - `project_dir = ...`
  - `target_dir = project_dir/target` (dbt default; allow override via flags/env)

### Staleness / caching

In dbt-asql, treat artifacts as stale if:
- `manifest.json` missing or older than `dbt_project.yml` / `packages.yml` / any `models/**/*.sql|yml`
- `catalog.json` missing or older than `manifest.json` (or older than any model file)

Pragmatic first version:
- if missing → generate
- if present → trust (skip expensive “is it stale?” checks)

## How to translate dbt artifacts into ASQL needs

We have 2 consumers:

1) **SQLGlot schema mapping** (tables → columns/types) for:
   - star expansion (`qualify_columns(..., expand_stars=True)`)
   - SQLGlot optimizer rules that need schema

2) **Relationship graph** for:
   - join inference / FK shorthand
   - cohort join-key inference

### A) SQLGlot schema mapping

Output shape:
- `{table: {column: type_str_or_none}}` (or nested `{db:{table:{col:type}}}` if needed)

Sources:
- From `catalog.json` if present: use dbt’s catalog relation entries to fill column types.
- Else from `manifest.json`: fill columns with `None` types (names only).

### B) Relationship graph

Sources (in priority order):
- Relationship tests in `manifest.json` (resource_type=test / test_metadata.name == relationships)
- YAML `schema.yml` relationship tests (if we scan those)
- Optional inferred convention edges (only if user opts in)

Output:
- simple list of edges:
  - `(from_table, from_col) -> (to_table, to_col)`
  - optional `alias` (derived from `{name}_id`)

## Integration into ASQL compilation

Short-term (minimal disruption):
- dbt-asql builds:
  - `sqlglot_schema` mapping/object
  - `relationship_graph` list
- ASQL `compile()` accepts:
  - `schema=` as SQLGlot schema mapping/object (for optimizer/star expansion)
  - `relationships=` as a separate optional sidecar (for join inference)

Long-term:
- once SQLGlot schema supports relationships (see `davefowler/sqlglot#2`), merge the sidecar into SQLGlot Schema.

## Why we should not write our own DB introspector

dbt already:
- knows the configured adapter (Snowflake/BigQuery/Postgres/etc.)
- already has stable logic to query the warehouse for catalog metadata
- already writes normalized artifacts

So dbt-asql should **shell out to dbt** and read artifacts; ASQL core stays independent.

## Test plan (for dbt-asql)

Unit tests (no warehouse):
- given a fixture `manifest.json`, build:
  - SQLGlot schema mapping (columns exist)
  - relationship graph extracted from relationship tests
- ensure path discovery finds project root/target dir
- ensure “missing artifacts” triggers correct dbt commands (mock subprocess)

Integration tests (optional):
- run `dbt parse` in a tiny example project fixture and ensure artifacts are produced and ingested

## Implementation sketch

- `dbt_asql/schema_loader.py`
  - `find_dbt_project_root(path) -> Path`
  - `ensure_manifest(project_dir) -> Path` (runs `dbt parse` if needed)
  - `ensure_catalog(project_dir) -> Path` (runs `dbt docs generate` if needed)
  - `load_manifest(path) -> dict`
  - `load_catalog(path) -> dict`
  - `build_sqlglot_schema(manifest, catalog=None) -> dict|MappingSchema`
  - `build_relationships(manifest) -> list[Edge]`

This keeps “shelling out” entirely inside dbt-asql, not ASQL core.


