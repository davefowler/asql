# Early Signs of “Transformational SQL” in Existing Tools

## Purpose

This note looks at a few “weak signals” in the modern SQL ecosystem that *feel adjacent* to Stage 5 (“transformational SQL languages”), but don’t quite cross the line into a coherent transformation language. For each signal, it extracts the **big gain** (what actually changed day-to-day work) and then asks: **Should ASQL integrate this? If yes, how could it land in `docs/spec.md`?**

Scope is intentionally *language-level* (syntax + semantics + compilation). Orchestration/build/runtime concerns are discussed only to clarify “out of scope.”

Relevant ASQL reference: `docs/spec.md` (v0.3 draft, Dec 2025).

---

## What “counts” as an early sign

A feature is an “early sign” of Stage 5 if it:

- **Moves modeling intent closer to the query** (grain, time semantics, relationships, completeness, reuse)
- **Reduces boilerplate via semantics (not templates)** (i.e., compiler picks dialect strategy)
- **Improves inspectability** (the intent-to-SQL mapping is predictable and debuggable)

A feature is *not* a Stage 5 sign if it’s mostly:

- A vendor-only convenience that doesn’t generalize
- A DSL that makes SQL *more opaque* (Stage 3 vibes)
- Orchestration/state tooling around SQL, not *in* SQL

---

## 1) DuckDB SQL extensions (LIST/STRUCT + macros)

### Big gains

- **First-class nested types in “regular SQL”**:
  - `LIST` and `STRUCT` let you keep semi-structured data in-table without immediately shredding it.
  - Makes a lot of analytics workflows feel closer to Python/pandas: “arrays of things,” “object-ish records,” etc.
- **Macros as lightweight reuse**:
  - DuckDB macros make it easier to encapsulate repeated SQL expressions without a full UDF lifecycle.

### Where ASQL already aligns

- **Arrays / nested-ish workflows**:
  - `explode` already abstracts dialect-specific UNNEST/FLATTEN patterns (see `docs/spec.md` “Explode”).
  - “Nested results” are explicitly called out as an optional future feature (inspired by EdgeQL).
- **Reuse**:
  - ASQL already specifies `func` for scalar and table functions, expanded inline during compilation (see `docs/spec.md` “Functions”).

### Integration ideas for `docs/spec.md`

- **Add explicit “complex type” ergonomics (portable surface area)**
  - *Goal*: standardize just enough to let analysts work with arrays/structs portably.
  - Potential spec additions:
    - **Indexing / element access**: align on `arr[i]` semantics (some of this already appears via slice syntax for strings; extend carefully to arrays).
    - **Struct/record field access**: prefer `col.field` when `col` is a struct-like value.
    - **Array construction + aggregation**: portable `array_agg()` / `list_agg()` semantics as a stdlib target.
  - Key constraint: keep these as *operators/stdlib* that compile to dialect equivalents; do not rely on one engine’s type system.

- **Clarify “ASQL functions” vs “warehouse UDFs”**
  - ASQL `func` today is effectively a *compile-time macro* (inline substitution).
  - Consider adding a spec note:
    - **Default**: `func` expands inline (portable).
    - **Optional**: allow emitting warehouse UDFs only when target dialect supports it and user opts in (likely out-of-scope for core language).

### What not to pull in

- DuckDB-specific convenience syntax that can’t be preserved elsewhere.
- Anything that reduces inspectability (e.g., overly magical rewriting without a clear expansion).

---

## 2) Snowflake / BigQuery analytic extensions (QUALIFY, arrays, SAFE/TRY casts, UDFs)

### Big gains

- **`QUALIFY`** (especially in Snowflake/BigQuery):
  - Lets you filter on window functions without a nested subquery.
  - Dramatically simplifies dedup/ranking patterns.
- **Array operations + UNNEST ergonomics**:
  - BigQuery’s `UNNEST`, arrays, and struct types make event-style data pleasant.
- **Safe casting**:
  - `SAFE_CAST` / `TRY_CAST` are huge for messy data.
- **UDF ecosystems**:
  - Teams create “utility layers” for repeated business logic.

### Where ASQL already aligns

- **Deduplication abstraction**:
  - ASQL `deduplicate` already compiles to `QUALIFY ROW_NUMBER()...=1` *when available* and falls back to a CTE otherwise (`docs/spec.md` “Deduplicate”). This is exactly the right “semantic layer” pattern.
- **Array explosion**:
  - `explode` already abstracts BigQuery vs Snowflake vs Postgres/DuckDB implementations (`docs/spec.md` “Explode”).
- **Safe casting**:
  - `::type?` explicitly maps to `SAFE_CAST`/`TRY_CAST` when present (`docs/spec.md` “Safe Casting”).

### Integration ideas for `docs/spec.md`

- **Generalize “capability-aware compilation” as a first-class design principle**
  - ASQL already does this in a few spots (deduplicate, explode, safe cast). It might be worth a single spec section (or “Compilation” subsection) that standardizes:
    - capability detection
    - preferred strategy (e.g., `QUALIFY`)
    - deterministic fallback strategy (e.g., CTE + filter)

- **Introduce a portable “window-filtering” operator (optional)**
  - If `deduplicate` expands, other common patterns benefit from `QUALIFY` too.
  - Example conceptual operator: `qualify <expr>` as pipeline step.
  - Caveat: may be redundant if ASQL stays focused on higher-level operators (`deduplicate`, `per`, etc.).

- **Sampling as a portability layer (ties to BigQuery/Snowflake differences)**
  - Not in the prompt’s list, but it’s a real “dialect gap” class similar to `QUALIFY`.
  - If ASQL adds `sample`, it fits the same pattern: use native sampling when available, otherwise fallback to `ORDER BY random()` + `LIMIT`.

### What not to pull in

- Vendor-specific functions that can’t be made semantically stable.
- “UDF libraries” as the primary reuse mechanism; ASQL `func` is more inspectable and more portable.

---

## 3) MetricFlow / semantic layers (Stage 3-ish… but with valuable semantics)

### Big gains

- **Centralized metric definitions**:
  - Metrics are named, versioned concepts with explicit grain, dimensions, filters, and time windows.
  - Strong consistency across dashboards and ad-hoc analysis.
- **Metric-aware query planning**:
  - A good semantic layer can enforce correct join paths and grain alignment.

### Why this isn’t “Stage 5” by itself

- The semantics live **outside** SQL (YAML/DSL), and the generated SQL can be opaque.
- Debugging often becomes “why did the semantic layer do *that*?”

### Where ASQL already aligns

- **Optional model metadata** (`docs/spec.md` “Models (Optional Metadata)”):
  - Relationships, default time fields, and dbt `schema.yml` compatibility are already in-scope.
- **Language-level semantics for time series correctness**:
  - `guarantee()` and auto-spine behavior exist in the spec for grouped outputs.
- **Reusable logic**:
  - `func` already covers a big chunk of what many metric layers do for “expression reuse.”

### Integration ideas for `docs/spec.md`

- **Add “measures/metrics” as optional, query-native declarations**
  - Keep it close to the query language rather than an external YAML DSL.
  - Possible directions (sketches only):
    - `measure revenue = sum(amount)`
    - `metric active_users = #(distinct user_id)`
    - `from orders select metric(revenue) by month(created_at)`
  - This should reuse existing ASQL aggregation semantics and compile predictably.

- **Formalize “grain” and “join path” validation**
  - Many semantic layers mainly provide guardrails.
  - ASQL could adopt a “compile-time warnings/errors” section:
    - Detect mixed grains without explicit aggregation
    - Detect ambiguous join paths when dot traversal can’t decide

### What not to pull in

- Full semantic-layer query planner behavior that rewrites aggressively.
- A separate DSL that becomes “the real source of truth” while ASQL becomes a thin emitter.

---

## 4) SQLMesh (state-aware orchestration)

### Big gains

- **Statefulness + planning**:
  - Knows what has changed, what needs recomputation, and how to do incremental backfills.
  - Makes large SQL model graphs safer.
- **First-class environments**:
  - Better workflows for dev/prod parity.

### Why this isn’t “Stage 5” (language) by itself

- SQLMesh’s core innovation is **around SQL** (planning + state), not “a new SQL dialect.”
- You can keep SQL exactly as-is and still benefit.

### Where ASQL should integrate (lightly)

- **Dependency/lineage metadata as compiler output**
  - ASQL compilation could expose:
    - referenced relations
    - inferred join edges
    - required columns
    - “query shape” hashes
  - This supports SQLMesh/dbt-style planners without baking orchestration into ASQL.

- **Deterministic compilation**
  - If ASQL aims to cooperate with state-aware tools, deterministic SQL output matters.

### What not to pull in

- Orchestration primitives (environments, planning, backfill) into `docs/spec.md` core language.
- Materialization semantics inside ASQL (dbt/SQLMesh own that layer).

---

## A simple mapping table: signal → ASQL posture

| Signal | The real gain | ASQL posture | Spec touchpoint |
|---|---|---|---|
| DuckDB LIST/STRUCT | Nested data ergonomics | Adopt a small portable surface | `explode`, nested results (future), add array/struct access rules |
| DuckDB macros | Reuse without ceremony | Already covered via `func` | `Functions` |
| Snowflake/BigQuery QUALIFY | Window filtering without subqueries | Use when available, fallback otherwise | `deduplicate` (already does this) |
| BigQuery arrays/UNNEST | Event-style analytics | Already covered via `explode`; expand portability | `explode` + potential array access spec |
| SAFE/TRY cast | Robustness on dirty data | Already first-class | `::type?` |
| Semantic layers (MetricFlow) | Metric consistency + grain rules | Adopt semantics *in language* (optional) | `Models`, potential “Metrics” section |
| SQLMesh | State + incremental planning | Keep out of language; emit metadata | `Compilation & Transpilation` (metadata) |

---

## Takeaway (and why “Stage 5 started ~2023” is plausible)

Stage 5 “started” not because a single tool crossed the line, but because the ecosystem converged on the same pattern: **encode analytic intent once, compile to dialect-specific SQL with predictable fallbacks**.

ASQL’s current spec already implements several of the strongest “early signs” as first-class language semantics (e.g., `deduplicate`, `explode`, safe casts, relationship traversal, guaranteed groups). The remaining opportunity is to:

- make complex types (arrays/structs) feel *portable* and *inspectable*, and
- optionally bring “metric semantics” into the language without becoming an opaque external DSL.
