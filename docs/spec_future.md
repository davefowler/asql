# ASQL: Future Features & Considerations

This document contains features that are planned for future implementation, under consideration, or marked as "maybe" for v1.0.

**Note**: Features in this document are NOT implemented. See `docs/spec.md` for the current specification of implemented features.

---

---


## Ternary-Style Conditionals (Future Consideration)

ASQL may add support for concise ternary expressions in the future:

```asql
-- Potential future syntax (not yet decided)
amount == 0 ? null : amount           -- JS-style
null if amount == 0 else amount       -- Python-style
```

**Current**: Use ASQL `when` (or SQL `CASE WHEN ... THEN ... ELSE ... END`):
```asql
CASE WHEN amount == 0 THEN NULL ELSE amount END
```

**Priority**: Low - `when` syntax is already clear and readable. Ternary expressions are syntactic sugar.

---


## Shorthand Natural Language (50/50 on implementation)

For very simple exploratory queries, you can omit the `from` clause and infer it from the aggregation:

```asql
# of Users by country
Sum of revenue by region
Avg Users.age by country
```

**Note**: This shorthand is nice for a big percentage of exploratory queries, but it's different from other queries that start with `from`. In these examples, the `from` table is inferred from its use in `# of Users`. It's really nice shorthand, but also potentially confusing.

**Status**: Marked as 50/50 on implementation - may or may not make it into v1.0.

**Pros**:
- Very concise for exploratory queries
- Natural language feel

**Cons**:
- Different syntax from other queries
- Potentially confusing
- Requires inference logic

---


## Future Considerations

These are broader ideas that may or may not be implemented:

- **Visual SQL Editor**: ASQL's structure could enable a great visual query builder whose base could also be a text editor/IDE. Get the best of visual and text-based exploration.
- **dbt Integration**: Building ASQL into dbt out of the gate would make it immediately useful for the dbt community
- **Common Schema Format**: A shared schema/statistics library for cross-database compatibility
- **Query Optimization**: ASQL-specific optimizations before SQL generation
- **IDE Integration**: Full-featured editor with autocomplete, error checking, SQL preview
- **Testing Framework**: Query testing and validation tools

---

## Safe casting (`::type?`) (Future Consideration)

ASQL may add “safe cast” syntax that returns `NULL` on cast failure.

### Why it exists
- Dialects differ (`TRY_CAST`, `SAFE_CAST`, etc.)
- Real data often contains non-castable values (`\"N/A\"`, empty strings, mixed types)

### Proposed syntax

```asql
select value::integer? as value_int
select value::integer? ?? 0 as value_int
```

### Current
Use strict casts (`value::integer`) and/or dialect-specific SQL (`TRY_CAST`, `SAFE_CAST`) directly.

---

## Safe divide (`/?`) (Future Consideration)

ASQL may add a safe divide operator where divide-by-zero yields `NULL` (i.e., the result is “not required”).

### Proposed syntax

```asql
4 /? 3     -- normal division
4 /? 0     -- NULL (safe-divide)
```

### Current
Use SQL `CASE` / `NULLIF` patterns directly, e.g. `a / NULLIF(b, 0)` (dialect dependent).

---

## Table sources: `series(...)` / `date_spine(...)` (Future Consideration)

ASQL may add table-producing functions that can be used directly in `from`:

```asql
from series(1, 100)
from date_spine(start = @2024-01-01, end = @2024-12-31, grain = day)
```

**Why it exists**: Sometimes you want to generate rows without an existing source table (numbers/date dimension).

**Current**: Prefer compiler `auto_spine` (gap-filling for grouped date dimensions) where applicable, or use warehouse-native generators in raw SQL.

---

## Union relations: `from union(t1, t2, ...)` (Future Consideration)

ASQL may add a convenience table source for unioning a list of relations:

```asql
from union(users_2022, users_2023, users_2024)
```

Open design questions:
- schema alignment vs “union all as-is”
- `fill_missing = null` behavior
- dialect differences

---

## `slugify(expr)` (Future Consideration)

ASQL may add a helper to convert strings to URL-friendly slugs:

```asql
select slugify(name) as slug
```

Open design questions:
- dialect portability (regex replace differences)
- unicode normalization behavior

---

**See Also**:
- `docs/spec.md` - Current specification of implemented features
- GitHub issues - Work tracked as issues when prioritized
- `ai_notes/COHORT_ANALYSIS.md` - Detailed cohort analysis design
