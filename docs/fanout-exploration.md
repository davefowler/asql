# Fanout Exploration: Warehouse Support and ASQL Opportunities

## Purpose

Explore:

1. What data warehouses already provide (in SQL) to reduce or control fanout risk.
2. What ASQL already improves.
3. What ASQL could add to make fanout-safe querying more automatic.

This complements Nimble's grain-first guidance, not replaces it.

---

## 1) What Fanout Is (Quickly)

Fanout happens when a join multiplies rows beyond the intended base grain.

- Base grain: `orders` (1 row per `order_id`)
- Join to `order_items` (1:N)
- Result grain becomes item-level
- Summing order-level measures after that join inflates totals

`GROUP BY` alone does not fix this unless metrics are first computed at the correct grain.

---

## 2) Do Warehouses Have Native SQL Help?

Short answer: **partially**. Warehouses provide useful primitives, but no universal "fanout-safe aggregate" semantics.

## 2.1 Useful SQL Primitives That Help

1. `QUALIFY` + window ranking for "pick one row per key" dedupe patterns.
2. `SEMI JOIN` / `ANTI JOIN` (or equivalent `EXISTS`/`IN`) for existence filtering without row multiplication.
3. `DISTINCT ON` (PostgreSQL) for deterministic first-row-per-key selection.
4. `ANY_VALUE` (BigQuery) for carrying representative dimension attributes through grouped queries.

These reduce accidental duplication patterns, but they are not complete fanout safety.

## 2.2 What They Do Not Solve

1. They do not know a metric's natural grain.
2. They do not automatically separate metric computation by grain before join.
3. They do not guarantee correctness across arbitrary join paths.

So the warehouse gives building blocks, not a complete contract.

---

## 3) Current Warehouse Feature Snapshot

## 3.1 Broadly useful today

1. BigQuery: `QUALIFY`, `GROUP BY ALL`, `ANY_VALUE`, and explicit guidance to aggregate before joins.
2. Snowflake: `QUALIFY`.
3. Databricks SQL: `QUALIFY`.
4. Redshift: `QUALIFY`.
5. PostgreSQL: `DISTINCT ON`.
6. Spark SQL: `SEMI` and `ANTI` joins.
7. DuckDB: `SEMI` / `ANTI` joins.

## 3.2 Important nuance

None of these features, by themselves, provide:

1. Metric-home semantics ("this metric is order-grain").
2. Automatic compile-time rewrites to preserve metric grain through joins.
3. Safety checks tied to declared relationship cardinality.

---

## 4) Does ASQL Already Help?

Yes, but mostly in **ergonomics**, not hard guarantees.

ASQL already helps teams write clearer multi-step SQL (pipes, window helpers, dedupe patterns). That lowers query authoring friction and can improve consistency.

But currently ASQL does not yet have first-class fanout semantics like:

1. Declared metric grain
2. Join cardinality contracts
3. Automatic fanout-safe rewrites
4. Compile-time fanout linting

So ASQL helps write safer patterns, but does not yet enforce them.

---

## 5) ASQL Direction: Practical Fanout MVP

Goal: keep scope small and useful. Avoid building a full semantic engine first.

## 5.1 Add grain annotations for measures

Proposed concept:

- Declare the measure's home grain explicitly (query-local first; model-level later).

Example sketch:

```asql
from orders o
  measure sum(o.order_total) at grain(o.order_id) as revenue
  & order_items i on o.order_id = i.order_id
  group by o.customer_id
```

Compiler behavior:

1. Compute `revenue` in an order-grain subquery first.
2. Join outward only after measure is stabilized.

## 5.2 Add fanout-safe join mode

Proposed options:

1. `join ... fanout safe`
2. `SET fanout_mode = 'strict'`

`strict` mode:

1. Detect when a measure from left grain is aggregated after a potential 1:N join.
2. Fail compilation with actionable error and rewrite suggestion.

## 5.3 Add relationship/cardinality hints

Proposed syntax:

```asql
& order_items i on o.order_id = i.order_id cardinality one_to_many
```

or metadata-driven via schema registry.

Usage:

1. Cardinality informs linting.
2. Compiler can decide when pre-aggregation is mandatory.

## 5.4 Add explicit existence-join operator

Since `SEMI` joins are fanout-safe for existence filters, expose them directly:

```asql
from orders o
  semi join order_items i on o.order_id = i.order_id
```

Compile:

1. Native `SEMI JOIN` where supported.
2. `WHERE EXISTS (...)` fallback elsewhere.

## 5.5 Add deterministic "pick one" helper

Common need: collapse right side to one row per key before join.

Example sketch:

```asql
from order_items
  pick one per order_id by -updated_at
```

Compile:

1. `QUALIFY ROW_NUMBER() = 1` where supported.
2. Subquery with row_number fallback.
3. `DISTINCT ON` for PostgreSQL target when appropriate.

---

## 6) Agent + Deterministic Safety Checks

Even without full semantic modeling, ASQL can combine:

1. Existing schema/FK metadata
2. Optional relationship cardinality config
3. Profile stats (uniqueness ratios)

to add fanout guardrails:

1. Warn when joining from unique key to non-unique key and summing left-grain measure.
2. Warn when a right table has duplicate join keys but query assumes one-to-one.
3. Offer auto-rewrite: pre-aggregate right side or split metrics into separate CTEs.

---

## 7) Recommended Rollout

## Phase 1: High ROI, low risk

1. `semi join` / existence join syntax.
2. `pick one per key` syntax with `QUALIFY`/fallback compilation.
3. Lint warning for obvious fanout hazards (non-unique join key + left-grain sum).

## Phase 2: Stronger guarantees

1. Query-local `measure ... at grain(...)`.
2. `fanout_mode = 'strict'` compile-time errors.
3. Cardinality hints in join clauses or registry.

## Phase 3: Deeper integration

1. Registry-backed measure home and relationship metadata.
2. Auto-rewrite into fanout-safe CTE patterns by default.

---

## 8) Bottom Line

1. Warehouses provide useful primitives (`QUALIFY`, `SEMI/ANTI`, `DISTINCT ON`, `ANY_VALUE`) but not end-to-end fanout correctness.
2. ASQL's current pipe/window ergonomics help readability and consistency, but not guarantees.
3. A focused ASQL MVP can materially reduce fanout bugs with:
   - existence joins,
   - deterministic one-row-per-key helpers,
   - grain-aware linting,
   - and then optional strict grain semantics.

This keeps ASQL pragmatic: better correctness without requiring a full semantic platform on day one.

---

## Sources

- BigQuery Query syntax (`GROUP BY`, `QUALIFY`): https://cloud.google.com/bigquery/docs/reference/standard-sql/query-syntax
- BigQuery aggregate functions (`ANY_VALUE`): https://cloud.google.com/bigquery/docs/reference/standard-sql/aggregate_functions
- BigQuery best practice (aggregate before join): https://cloud.google.com/bigquery/docs/best-practices-performance-compute
- Snowflake `QUALIFY`: https://docs.snowflake.com/en/sql-reference/constructs/qualify
- Databricks SQL `QUALIFY`: https://docs.databricks.com/gcp/en/sql/language-manual/sql-ref-syntax-qry-select-qualify
- Redshift `QUALIFY`: https://docs.aws.amazon.com/redshift/latest/dg/r_QUALIFY_clause.html
- PostgreSQL `DISTINCT ON`: https://www.postgresql.org/docs/16/queries-select-lists.html
- Spark SQL join syntax (`SEMI` / `ANTI`): https://spark.apache.org/docs/4.0.0/sql-ref-syntax-qry-select-join.html
- DuckDB `SEMI` / `ANTI` joins: https://duckdb.org/docs/stable/sql/query_syntax/from.html
