# 2026-01-08 — Investigation: collapsing pipeline CTEs (Issue #140)

Context: ASQL pipeline transforms can introduce intermediate CTEs for correctness and composability. This is fine, but can produce verbose SQL. We want an **optional** post-parse pass that **collapses unnecessary CTEs** using SQLGlot’s AST, without fragile string manipulation.

Issue: `https://github.com/davefowler/asql/issues/140`

## Goal

Provide a conservative AST rewrite which:

- Removes **trivial passthrough CTE layers** (e.g. `SELECT * FROM __tmpN`) when safe.
- Optionally merges **projection-only** layers into fewer `SELECT` blocks when provably safe.
- Never changes semantics; if uncertain, do nothing.

## Why this should be an AST transform (not parser / not regex)

- This is not syntax; it’s an **output-shaping optimization**.
- SQLGlot already models query structure precisely; we can reason about:
  - `WITH` dependencies
  - CTE reference counts
  - whether a SELECT layer is a pure projection vs changes row set / ordering
- This fits the “optimizer pass” mental model: **parse → rewrite AST → generate**.

## Candidate transformations (ordered by safety)

### 1) Inline single-use passthrough CTEs (very safe)

Pattern:

- `WITH t AS (<subquery>) SELECT * FROM t`
- where:
  - `t` is referenced exactly once (only by that `FROM t`)
  - outer select has no additional clauses beyond `SELECT * FROM` (no WHERE/GROUP/HAVING/ORDER/LIMIT, no DISTINCT)

Rewrite:

- Replace outer `SELECT * FROM t` with `<subquery>` directly (preserving any `WITH` that <subquery> itself needs).

This is essentially removing the “`SELECT * FROM __tmpN` wrapper” that exists just to represent a pipeline stage boundary.

### 2) Inline single-use CTE when outer layer is projection-only (safe but more conditions)

Pattern:

- `WITH t AS (SELECT ... FROM base) SELECT <projection-only> FROM t`
- where outer layer:
  - has no WHERE/GROUP/HAVING/QUALIFY/ORDER/LIMIT
  - is only a SELECT projection (expressions, aliases, `* EXCEPT`, etc.)

Rewrite:

- Inline `t` into outer `FROM`, then merge projection lists if it remains a pure projection chain.

This is similar to “projection pushdown / merge projections”.

### 3) Merge consecutive projection-only SELECTs (use cautiously)

We can collapse:

- `SELECT <proj2> FROM (SELECT <proj1> FROM base)`

…only if:

- `proj1` contains no computed columns that `proj2` depends on by name *unless* we can safely substitute expressions
- no ambiguous `*` expansion is involved (or schema is available and we can expand deterministically)
- no window scoping surprises (windows in `proj1` can be referenced by alias in `proj2` depending on dialect rules)

This is where complexity rises fast, so the first implementation should likely **not** attempt this unless it’s narrowly scoped.

## Semantics hazards / “do not collapse if”

Avoid collapsing when any of these are present in either layer:

- **Row-set changing ops**: JOIN changes, DISTINCT, GROUP BY, HAVING, QUALIFY, LIMIT/OFFSET, ORDER BY (ordering may matter under LIMIT)
- **Sampling**: TABLESAMPLE / ORDER BY RAND LIMIT patterns
- **Lateral / correlated subqueries** (risk of changing correlation scope)
- **Multiple references to a CTE** (classic “inline duplicates work and may change semantics for non-deterministic funcs”)
- **Non-deterministic functions** in the inlined subtree (even single-use can change evaluation timing in some engines; be conservative)

## How to implement cleanly (SQLGlot-ish)

- Implement in `asql/compiler/` as a transform:
  - `collapse_ctes(stmt: exp.Expression, dialect: str | None, settings: CompileSettings) -> exp.Expression`
- Operate on `exp.With` / `exp.CTE` and `exp.Select`.
- Compute CTE reference counts by walking `exp.Table` nodes and matching `.name` against CTE aliases.
- Prefer structural checks (presence/absence of args) over string comparisons.
- Always preserve CTE ordering and dependencies when keeping `WITH`.

## Testing strategy

Start with snapshot-style tests that validate:

- Collapses happen only for simple passthrough wrappers.
- Queries remain equivalent by comparing:
  - generated SQL for a stable dialect (e.g. DuckDB)
  - and/or AST structure (e.g., no `WITH __tmpN` remains)

Suggested test cases:

- `from users extend upper(name) as name_upper` → previously might be `WITH __tmp1 ... SELECT * FROM __tmp1`; collapse to single SELECT.
- Ensure *no collapse* for:
  - `sample`, `limit`, `order by`
  - `group by` / `having`
  - `qualify`
  - multiple references to the same stash/CTE

## Recommendation for first pass

Implement only **Transformation #1** initially (passthrough wrapper removal). It’s high-value, low-risk, and keeps the code non-magical.

Then iterate to #2/#3 only if tests + real-world SQL output show strong benefit.


