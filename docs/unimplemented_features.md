# Unimplemented Features Tracking

This document tracks **features that are specified but NOT implemented**.

- **Source of truth for current syntax**: `docs/spec.md`
- **Future ideas / “maybe” features** (design-only): `docs/spec_future.md`

If a feature is implemented, it should live in `docs/spec.md` and **be removed from this list**.

**Last Updated**: December 2025

---

## High Priority

### 1. `when` conditional expressions
- **Status**: ❌ Not implemented
- **Spec**: `docs/spec.md` §4.7
- **What it is**: A readable replacement for SQL `CASE` expressions (both “simple case” and “searched case”).
- **Current workaround**: Use SQL `CASE WHEN ... THEN ... ELSE ... END` directly in ASQL expressions.
- **Why it matters**: This unlocks a lot of real-world “labeling / bucketing / business logic” without dropping to raw SQL.
- **Recommendation to remove from this list**:
  - **Create issue + implement soon** (this is core ergonomics).
  - After implementation: move the full docs/examples into `docs/spec.md` and delete this entry.

---

## Medium Priority

### 2. Dynamic pivot (values from subquery)
- **Status**: ❌ Not implemented
- **Spec**: `docs/spec.md` §13.3
- **What it is**: `pivot ... values (<subquery>)` where the pivot values come from data.
- **Current behavior**: Pivot requires an explicit values list (static pivot).
- **Why it matters**: Great for “wide custom fields” style schemas, but it’s also inherently tricky because most warehouses require dynamic SQL for true dynamic pivots.
- **Recommendation to remove from this list**:
  - If we really want it: **create an issue** and implement as “compile-time expansion” only when the subquery can be evaluated safely (likely requires database access / execution) — otherwise this probably belongs as **future design**.
  - If we do *not* want to support it in the compiler: **move the idea to `docs/spec_future.md` and remove from this list**.

### 3. `deduplicate by ...`
- **Status**: ❌ Not implemented
- **Spec**: `docs/spec.md` §13.2
- **What it is**: A convenience operator for the common “one row per key” pattern.
- **Current workaround**:
  - Use `per <cols> first by -<order_col>` (this compiles to `QUALIFY ROW_NUMBER() ... = 1`).
  - Or write explicit window functions + `QUALIFY`.
- **Important nuance**: This is mostly sugar over existing capabilities — `per ... first by ...` is the underlying primitive.
- **Recommendation to remove from this list**:
  - **Create issue + implement soon** as syntax sugar that rewrites to the existing `per ... first by ...` transformation.
  - Once implemented: add to `docs/spec.md` and remove this entry.

### 4. User-defined functions (`func ... = ...`)
- **Status**: ❌ Not implemented
- **Spec**: `docs/spec.md` §12
- **What it is**: Define reusable scalar/table functions inside ASQL.
- **Why it matters**: Powerful, but it’s a real feature (needs scoping, substitution rules, hygiene, recursion rules, etc.).
- **Recommendation to remove from this list**:
  - **Move to `docs/spec_future.md`** unless we’re actively prioritizing implementation work.
  - If we prioritize it: create issues for “scalar functions” and “table/macro functions” separately.

---

## Lower Priority / Future Work

### 5. Table sources: `date_spine(...)` / `series(...)`
- **Status**: ❌ Not implemented
- **Spec**: `docs/spec.md` §13.4
- **What it is**: A table-producing function you can `from date_spine(...)` / `from series(...)`.
- **Important nuance**: This is **different** from today’s `auto_spine` behavior, which already gap-fills grouped results by default (see `auto_spine` in compiler settings).
- **Recommendation to remove from this list**:
  - For most analytics use cases: **do not implement**; `auto_spine` already covers the “fill gaps” intent.
  - If we need it for “generate rows without any source table”: **move to `docs/spec_future.md`** (or create an issue only when a concrete use case appears).

### 6. Schema-aligned `union(...)`
- **Status**: ❌ Not implemented
- **Spec**: `docs/spec.md` §13.5
- **What it is**: Union multiple tables while aligning columns and filling missing ones automatically.
- **Recommendation to remove from this list**: likely **future** (`docs/spec_future.md`) unless there’s an immediate product need.

### 7. `key(...)` surrogate keys
- **Status**: ❌ Not implemented
- **Spec**: `docs/spec.md` §13.6
- **What it is**: Stable, cross-dialect surrogate key helper (hashing + null handling).
- **Recommendation to remove from this list**: **future** (`docs/spec_future.md`) unless you want to standardize this now.

### 10. Nested result shapes (`select { ... }`)
- **Status**: ❌ Not implemented
- **Spec**: `docs/spec.md` §16
- **What it is**: EdgeQL/Malloy-like nested result shaping.
- **Recommendation to remove from this list**: **future** (`docs/spec_future.md`) unless ASQL is going to own result-shaping semantics (big scope).

---

## “Maybe” features (design-only)

These are tracked in `docs/spec_future.md` (this doc stays focused on concrete “not implemented” items).
