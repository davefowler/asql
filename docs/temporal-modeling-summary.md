# Temporal Modeling + ASQL + Profiler: Summary

## Problem We Are Solving

Temporal analytics gets hard when questions require:

1. Entity existence over time (`active at ts`)
2. Attribute-at-the-time correctness (SCD2 slicing)
3. Relationship-at-the-time correctness (ownership/membership changes)
4. Dual-time logic (different timestamps in one query)
5. Backfill/late-arrival handling (valid time vs load time)

Examples:

- "How many active accounts did we have by month?"
- "For each sync, which account owned the connection when the sync ran?"
- "Syncs active at T, but accounts active at U."

## Core Conclusion

ASQL can help materially, but should not replace physical temporal modeling.

Best split:

1. **Physical truth in dbt/warehouse**: SCD2, relationship history, PIT/snapshots
2. **ASQL as temporal query surface**: cleaner, safer temporal queries over that truth

## What ASQL Already Helps With

Today, ASQL helps with authoring and readability:

1. Cleaner pipeline syntax for complex SQL
2. Cleaner window-function patterns for manual temporal logic
3. Better consistency in query style

But it does **not** yet provide first-class temporal correctness semantics.

## ASQL Temporal MVP (Recommended)

Implement a small, high-ROI feature set:

1. `valid at <ts>`
2. `active at <ts>` (sugar over valid/predicate logic)
3. `asof join`

Design principles:

1. Compile to native dialect syntax where available
2. Fallback to portable SQL (`ROW_NUMBER`/subquery patterns) where not available
3. Never silently guess ambiguous keys/paths; fail with clear error

## "Do We Need a Full Semantic Model?"

Not for MVP. Use a lightweight **temporal registry** instead of a heavy ontology engine.

Registry needs:

1. Entity key
2. Validity columns (`valid_from`, `valid_to`)
3. Optional `active` predicate override
4. Optional relationship defaults for `asof join`

If missing or ambiguous, require explicit query arguments.

## How a Schema Profiler Changes the Game

An external schema profiler can already detect useful temporal/key signals:

1. Temporal semantic types (`created_at`, `updated_at`, `deleted_at`, etc.)
2. Primary date column and incrementality signals
3. Key-role heuristics (`primary_key`, `foreign_key`)
4. Uniqueness/null/distinct/min/max/top-values stats
5. Existing FK inference plan in docs

This is enough to **auto-bootstrap** temporal metadata and reduce manual setup.

## What Profiler Still Needs for Full Automation

Add profile outputs for:

1. Confirmed cross-table relationship graph (Layer 6)
2. Business/valid-time vs load/system-time classification
3. Relationship-change signals (ownership/membership changes over time)
4. Late-arrival/backfill signals (event time vs load time lag stats)
5. Dual-time candidacy flags

## Auto-Construction Pipeline (Agent or Deterministic Code)

Given enriched profile + FK graph:

1. Generate temporal registry candidates
2. Identify SCD2 candidates (mutable attrs + temporal signals)
3. Build entity history tables (`valid_from`, `valid_to`, `is_current`)
4. Build temporal relationship history tables (for ownership/membership changes)
5. Build PIT tables at chosen grain (`monthly` first, optional event-time PIT)
6. Generate tests:
   - No overlapping validity windows per key
   - Exactly one current row per key
   - As-of FK integrity
   - Backfill lag SLA checks

## Practical Decision Rule

1. If 80% of usage is day/month dashboards:
   - Prioritize monthly snapshots + PIT
2. If many arbitrary timestamp joins/ad hoc users:
   - Add temporal relationship history + event-time support + ASQL `asof` features

## Risk Management

Avoid "hack for a hack" by keeping boundaries clear:

1. Physical models own historical truth and performance
2. ASQL owns ergonomic, portable temporal query semantics
3. Profiler bootstraps defaults and safety checks, not hidden magic

## Suggested Next Steps

1. Implement ASQL MVP syntax + compiler behavior (`valid at`, `active at`, `asof join`)
2. Define temporal registry schema and ambiguity/error rules
3. Extend profiler inspect output with relationship + dual-time/backfill signals
4. Build first deterministic generator for SCD2 + relationship history + monthly PIT
