# ASQL Syntax Decisions Record

**Purpose**: Document syntax choices, alternatives considered, and rationale for ASQL language decisions.

---

## Design Principles

All syntax decisions are guided by ASQL's core values:

1. **Pipeline Order Over Projection-First** — Written order = execution order
2. **Convention Over Configuration** — Infer from naming patterns
3. **Familiarity Over Novelty** — Keep SQL vocabulary
4. **Portable Over Proprietary** — Transpile to any dialect
5. **Completeness Over Fast Queries** — Guaranteed groups, gap-filling
6. **Code Comments Over Catalogues** — Documentation in queries

---

## Vocabulary Decisions

### `where` vs `filter`

**Decision**: Use `where`

**Alternatives considered**:
- `filter` (PRQL's choice)
- `keep` (pandas-inspired)

**Rationale**:
1. **Familiarity** — Every SQL user knows `where`
2. **Clarity** — "where this is true" clearly means "keep matching rows"
3. **Ambiguity of filter** — "filter" can mean filter-in OR filter-out; `where` is unambiguous
4. **HAVING elimination** — In ASQL, `where` works anywhere in the pipeline (before or after `group by`), eliminating the need for HAVING

**Note**: PRQL argues `filter` is better because it's a fresh word without SQL's WHERE/HAVING confusion. ASQL's counter: `where` is clear, and pipeline position eliminates the confusion.

---

### `limit` vs `take`

**Decision**: Use `limit`

**Alternatives considered**:
- `take` (PRQL's choice)
- `first` (as a command)
- `top` (SQL Server style)

**Rationale**:
1. **Familiarity** — `LIMIT` is the standard SQL keyword
2. **Equal validity** — `take` is marginally more natural English, but not enough to justify the learning cost
3. **Cross-database** — Most SQL dialects use `LIMIT` (or ASQL transpiles it)

---

### `order by` vs `sort`

**Decision**: Use `order by`

**Alternatives considered**:
- `sort` (PRQL's choice)
- `sort by` (hybrid)
- Support both

**Rationale**:
1. **Familiarity** — `ORDER BY` is universal SQL
2. **Marginal benefit** — `sort` is one word shorter, but `order by -col` reads naturally
3. **Consistency** — Matches other SQL verbs we kept

**Open question**: Should ASQL support `sort by` as an alias? Probably yes, since ASQL already allows filler words. Low-cost addition.

---

### `select` for both choosing and adding columns

**Decision**: Use `select` (with `select *, ...` pattern for adding)

**Alternatives considered**:
- `derive` for adding columns (PRQL's choice)
- `extend` for adding columns (in unmerged branch)
- `add` / `with`

**Current status**: `extend` is implemented in branch `claude/with-clause-pipeline-step-jcJ89` but not merged.

**Rationale for `select`**:
1. **Familiarity** — `SELECT` is universal
2. **Fewer verbs** — One command for choosing or adding

**Rationale for `extend` (or `derive`)**:
1. **Dedicated verb** — Clearer intent: "add columns"
2. **No `*` needed** — `extend expr as col` vs `select *, expr as col`

**Recommendation**: Merge `extend`. Keep `select` for choosing columns, add `extend` for adding columns.

---

### `group by ... ()` vs separate `group` and `aggregate`

**Decision**: Combine grouping and aggregation in one clause

**Alternatives considered**:
- Separate `group` and `aggregate` (PRQL's approach)
- `summarize` (Kusto's approach)
- `rollup by` / `bucket by` / `aggregate by`

**Rationale**:
1. **Familiarity** — `GROUP BY` is universal SQL
2. **Conciseness** — 95% of use cases group AND aggregate together
3. **PRQL's orthogonality** — PRQL separates them, enabling "group without aggregate" (partition operations). ASQL handles this via `per` instead.

**Note**: The parentheses syntax for aggregates is inspired by PRQL's block structure.

---

### Join operators: `&`, `&?`, `?&`, `?&?`, `*`

**Decision**: Use symbolic operators for join types

**Alternatives considered**:
- SQL keywords: `join`, `left join`, `right join`
- PRQL style: `join table (==col)`

**Rationale**:
1. **Compactness** — Joins are common; symbols save space
2. **Visual distinction** — Easy to scan for join types
3. **Mnemonic** — `?` marks the nullable/optional side

**Tradeoff**: Less familiar to newcomers, but learnable in minutes.

---

### `#` for count

**Decision**: Use `#` as shorthand for COUNT

**Alternatives considered**:
- `count(*)` only
- `n` or `num`
- `tally`

**Rationale**:
1. **Brevity** — `#` is extremely concise
2. **Natural** — `#` universally means "number of"
3. **Extensibility** — `# users` for COUNT(DISTINCT user_id) via convention

**Note**: This is one of ASQL's more inventive choices.

---

### `??` for COALESCE

**Decision**: Use `??` operator (nullish coalescing)

**Alternatives considered**:
- `coalesce()` function only
- `||` (some languages use this)
- `or` keyword

**Rationale**:
1. **JavaScript familiarity** — `??` is the nullish coalescing operator
2. **Chainable** — `a ?? b ?? c` reads naturally
3. **Avoids confusion** — `||` is string concatenation in SQL

---

### `@` for date literals

**Decision**: Use `@` prefix for dates

**Alternatives considered**:
- SQL style: `DATE '2024-01-01'`
- String parsing: `'2024-01-01'::date`
- `#` prefix (used in some languages)

**Rationale**:
1. **Brevity** — `@2024-01-01` is much shorter than `DATE '2024-01-01'`
2. **Unambiguous** — Clearly distinguishes dates from strings
3. **Novel but intuitive** — New syntax but immediately understandable

---

### `per` for window operations

**Decision**: Use `per` command for partition-based operations

**Syntax**: `per <partition_cols> <operation> by <order_cols>`

**Operations**:
- `first` — Keep first row per partition (deduplication)
- `last` — Keep last row per partition
- `number` — Add row number column
- `rank` — Add rank column
- `dense rank` — Add dense rank column

**Alternatives considered**:
- Window function syntax only
- `partition by ... (...)` block (PRQL style)
- `deduplicate by ...`

**Rationale**:
1. **Readability** — `per customer_id first by -date` reads naturally
2. **Common pattern** — Deduplication is extremely common in analytics
3. **Reduces boilerplate** — Replaces complex window function + filter patterns

---

### `stash as` for CTEs

**Decision**: Use `stash as` to create inline CTEs

**Alternatives considered**:
- `with ... as` at top (SQL style)
- `let name = (...)` (PRQL style)
- `set name = (...)` (reserved but not implemented)

**Rationale**:
1. **Proximity** — CTE is defined where it's used
2. **Pipeline flow** — Fits naturally into the pipeline
3. **SQL familiarity** — Compiles to `WITH ... AS`

**Note**: `SET` is reserved for compiler settings only, not CTE variables.

---

### No `having` keyword

**Decision**: Use `where` for both pre- and post-aggregation filtering

**Rationale**:
1. **Simplicity** — One keyword for filtering
2. **Pipeline semantics** — Position determines when filter applies
3. **Eliminates confusion** — No WHERE vs HAVING decision

**Example**:
```asql
from orders
  where status = "active"     -- pre-aggregation (SQL WHERE)
  group by region (sum(amount) as revenue)
  where revenue > 1000        -- post-aggregation (SQL HAVING)
```

---

## Operator Decisions

### `-` prefix for descending sort

**Decision**: Use `-col` for descending order

**Alternatives considered**:
- `desc` keyword: `order by col desc`
- Suffix: `col-` or `col:desc`

**Rationale**:
1. **Brevity** — One character
2. **Precedent** — PRQL uses this, some other languages too
3. **Intuitive** — Minus = "going down"

---

### `contains`, `starts with`, `ends with` for string matching

**Decision**: Use natural language operators for LIKE patterns

**Alternatives considered**:
- `like` only
- `~` operator (regex)
- Method syntax: `col.contains("x")`

**Rationale**:
1. **Readability** — `email contains "@gmail.com"` is self-documenting
2. **No wildcards** — User doesn't need to remember `%pattern%` syntax
3. **Case variants** — `icontains`, `istarts with`, `iends with` for case-insensitive

---

### Date arithmetic: `+ 7 days`

**Decision**: Use natural language date arithmetic

**Alternatives considered**:
- Function only: `date_add(col, 7, 'day')`
- Interval syntax: `col + INTERVAL '7 days'`

**Rationale**:
1. **Readability** — `created_at + 7 days` is immediately clear
2. **Dialect portability** — ASQL handles the translation
3. **Natural** — Matches how people think about dates

---

### `ago` and `from now` for relative dates

**Decision**: Support `N unit ago` and `N unit from now`

**Examples**:
- `7 days ago`
- `1 month ago`
- `3 days from now`

**Rationale**:
1. **Common pattern** — "Last 30 days" is extremely common in analytics
2. **Readability** — `created_at >= 30 days ago` is self-documenting
3. **Reduces errors** — No manual date calculation

---

## Features Not Adopted

### `let` / `func` (PRQL's abstraction features)

**Decision**: Not implemented

**Rationale**:
1. **Different philosophy** — ASQL emphasizes convention over abstraction
2. **Complexity** — User-defined functions add language complexity
3. **Differentiation** — Let PRQL own this space

**Workaround**: Use `stash as` for reusable CTEs, or SQL functions.

---

### `derive` as separate keyword

**Status**: Implemented as `extend` in unmerged branch

**Decision pending**: Should we merge `extend`? Probably yes.

---

### PRQL's tuple syntax `{}`

**Decision**: Not adopted

**Rationale**:
1. **Unfamiliar** — SQL users don't know this syntax
2. **Parentheses work** — `group by a, b (...)` is clear enough

---

## Open Questions

### Should ASQL support both `order by` and `sort by`?

**Recommendation**: Yes, as aliases. Low cost, helps PRQL users transition.

### Should ASQL support scalar variables?

PRQL has `let threshold = 1000`. ASQL could support:
```asql
define threshold = 1000;
-- or
let threshold = 1000;
```

**Current workaround**: Cross-join a single-row CTE (ugly).

**Recommendation**: Consider adding, but carefully. Syntax TBD.

---

## Changelog

| Date | Decision | Status |
|------|----------|--------|
| 2024-XX | Use `where` over `filter` | Final |
| 2024-XX | Use `limit` over `take` | Final |
| 2024-XX | Use `order by` (consider `sort by` alias) | Final |
| 2024-XX | Use `#` for count | Final |
| 2024-XX | Use `??` for COALESCE | Final |
| 2024-XX | Use `@` for date literals | Final |
| 2024-XX | Use `per` for window operations | Final |
| 2024-XX | Use `stash as` for CTEs | Final |
| 2024-XX | No `having` keyword | Final |
| 2025-01-03 | Add `extend` for adding columns | In branch, not merged |
| 2026-01-06 | Consider `sort by` alias | Open |
| 2026-01-06 | Consider scalar variables (`let`) | Open |

