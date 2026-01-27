# Syntax Decisions

This document records the syntax choices made in ASQL, what alternatives were considered, and why we made the decisions we did. It's useful for understanding the language design philosophy and for discussions about potential changes.

---

## Core Design Values

All syntax decisions are guided by ASQL's [design values](../design.md):

1. **Pipeline Order Over Projection-First** — Written order = execution order
2. **Convention Over Configuration** — Infer from naming patterns
3. **Familiarity Over Novelty** — Keep SQL vocabulary
4. **Portable Over Proprietary** — Transpile to any dialect
5. **Completeness Over Fast Queries** — Guaranteed groups, gap-filling

---

## Filtering: `where`

**Decision**: Use `where` for filtering rows.

| Alternative | Source | Why Not |
|-------------|--------|---------|
| `filter` | PRQL | Ambiguous: "filter out" vs "filter in"? `where` clearly means "keep rows where this is true" |
| `keep` | pandas | Less familiar to SQL users |

**Rationale**: `where` is universally understood by SQL users. While PRQL argues `filter` is cleaner, we found `where` is actually *clearer* — "where status = 'active'" unambiguously means "keep rows where this condition is true."

**Bonus**: In ASQL, `where` works anywhere in the pipeline. Use it before `group by` (SQL's WHERE) or after (SQL's HAVING). No need for a separate HAVING keyword.

```asql
from orders
  where status = "active"     -- pre-aggregation (WHERE)
  group by region (sum(amount) as revenue)
  where revenue > 1000        -- post-aggregation (HAVING)
```

---

## Limiting: `limit`

**Decision**: Use `limit` to restrict row count.

| Alternative | Source | Why Not |
|-------------|--------|---------|
| `take` | PRQL | Marginally more "natural English" but not enough to justify the learning cost |
| `top` | SQL Server | Non-standard SQL |
| `first` | — | Conflicts with window function `first()` |

**Rationale**: `LIMIT` is the standard SQL keyword across most dialects. While `take 10` might read slightly more naturally than `limit 10`, the difference is minimal. Familiarity wins.

---

## Sorting: `order by`

**Decision**: Use `order by` for sorting.

| Alternative | Source | Why Not |
|-------------|--------|---------|
| `sort` | PRQL | One word is nicer, but familiarity matters more |
| `sort by` | — | Considered as an alias; may be added |

**Rationale**: `ORDER BY` is universal SQL. The two-word syntax is slightly more verbose, but `order by -revenue` reads naturally.

**Descending sort**: Use `-` prefix for descending order. This is concise and intuitive:

```asql
order by -revenue          -- descending
order by created_at        -- ascending (default)
order by -year, name       -- year descending, then name ascending
```

**Future consideration**: We may add `sort by` as an alias since ASQL already supports filler words. Low-cost addition for users coming from other languages.

---

## Adding Columns: `extend`

**Decision**: Use `extend` for adding computed columns (when merged).

| Alternative | Source | Why Not |
|-------------|--------|---------|
| `derive` | PRQL | Less SQL-friendly vocabulary |
| `select *, ...` | SQL | Verbose; requires listing `*` |
| `add` | — | Too generic |
| `with` | — | Conflicts with CTE syntax |

**Rationale**: Adding a column shouldn't require `select *, expr as col`. A dedicated verb is cleaner:

```asql
-- With extend (cleaner)
from users
  extend age > 18 as is_adult

-- Without (verbose)
from users
  select *, age > 18 as is_adult
```

**Status**: `extend` is implemented but in an unmerged branch. We chose `extend` over PRQL's `derive` to maintain a more SQL-familiar vocabulary.

---

## Aggregation: `group by ... ()`

**Decision**: Combine grouping and aggregation in one clause with parentheses.

| Alternative | Source | Why Not |
|-------------|--------|---------|
| Separate `group` and `aggregate` | PRQL | More orthogonal but more verbose for the 95% case |
| `summarize` | Kusto | Less familiar than GROUP BY |
| `rollup by` | — | Considered as alias; GROUP BY is more familiar |

**Rationale**: 95% of the time you group AND aggregate together. Combining them is more concise:

```asql
from orders
  group by region (
    sum(amount) as revenue,
    # as order_count
  )
```

PRQL separates `group` and `aggregate` for orthogonality, enabling "group without aggregate" (partition operations). ASQL handles that use case with the `per` command instead.

**Note**: The parentheses syntax is inspired by PRQL's block structure, which we found readable and elegant.

---

## Counting: `#`, `##`, `uniq`

**Decision**: Use `#` as shorthand for COUNT, `##` for COUNT DISTINCT.

| Alternative | Source | Why Not |
|-------------|--------|---------|
| `count(*)` only | SQL | More verbose |
| `n` or `num` | — | Less intuitive |

**Rationale**: `#` universally means "number of." `##` (double hash) visually conveys "distinct":

```asql
from users
  group by country (
    # as total,                -- COUNT(*)
    #email as with_email,      -- COUNT(email)
    ##user_id as unique_users  -- COUNT(DISTINCT user_id)
  )
```

The `uniq(col)` function is an alternative for those who prefer function-style syntax for distinct counts.

---

## Joins: `&`, `&?`, `?&`, `*`

**Decision**: Use symbolic operators for join types.

| Operator | Join Type | Mnemonic |
|----------|-----------|----------|
| `&` | INNER JOIN | Both sides required |
| `&?` | LEFT JOIN | Right side optional (nullable) |
| `?&` | RIGHT JOIN | Left side optional (nullable) |
| `?&?` | FULL OUTER | Both sides optional |
| `*` | CROSS JOIN | Cartesian product |

| Alternative | Source | Why Not |
|-------------|--------|---------|
| SQL keywords | SQL | More verbose; `LEFT JOIN` is 9 characters vs 2 |
| `join ... (==col)` | PRQL | Less visually distinct |

**Rationale**: Joins are common in analytics. Compact symbols save space while being visually distinctive. The mnemonic "? marks the nullable side" makes them learnable quickly.

```asql
from orders
  &? customers on orders.customer_id = customers.id
  -- LEFT JOIN: orders always present, customers may be NULL
```

**Tradeoff**: Less familiar to newcomers. But learnable in minutes, and the visual distinction helps when scanning code.

---

## Null Handling: `??`

**Decision**: Use `??` for COALESCE (nullish coalescing).

| Alternative | Source | Why Not |
|-------------|--------|---------|
| `coalesce()` only | SQL | More verbose |
| `\|\|` | Some languages | `\|\|` is string concatenation in SQL |
| `or` | — | Confusing with logical OR |

**Rationale**: `??` is the nullish coalescing operator in JavaScript, TypeScript, C#, Swift, and PHP. It's concise and chains naturally:

```asql
revenue ?? 0                    -- default to 0
name ?? nickname ?? "Unknown"   -- multiple fallbacks
```

Both `??` and `coalesce()` work in ASQL.

---

## Date Literals: `@`

**Decision**: Use `@` prefix for date literals.

| Alternative | Source | Why Not |
|-------------|--------|---------|
| `DATE '2024-01-01'` | SQL | Verbose |
| String casting | — | Ambiguous; requires explicit cast |

**Rationale**: `@2024-01-01` is much shorter than `DATE '2024-01-01'` and immediately distinguishes dates from strings:

```asql
where created_at >= @2024-01-01
where created_at between @2024-01-01 and @2024-12-31
```

---

## Date Arithmetic: `+ 7 days`

**Decision**: Use natural language date arithmetic.

| Alternative | Source | Why Not |
|-------------|--------|---------|
| `date_add(col, 7, 'day')` | SQL | Verbose and varies by dialect |
| `col + INTERVAL '7 days'` | PostgreSQL | Dialect-specific |

**Rationale**: Date arithmetic is common in analytics. Natural language syntax is readable and dialect-portable:

```asql
created_at + 7 days
created_at - 1 month
due_date + 2 weeks
```

ASQL handles the dialect translation automatically.

---

## Relative Dates: `ago` and `from now`

**Decision**: Support `N unit ago` and `N unit from now`.

**Rationale**: "Last 30 days" is the most common filter in analytics. Make it readable:

```asql
where created_at >= 30 days ago
where created_at >= 1 month ago
where due_date <= 7 days from now
```

---

## String Matching: `contains`, `starts with`, `ends with`

**Decision**: Use natural language string matching operators.

| Alternative | Source | Why Not |
|-------------|--------|---------|
| `LIKE` only | SQL | Requires remembering `%pattern%` syntax |
| `~` regex | — | Most SQL dialects don't support regex well |

**Rationale**: String matching is common, and LIKE syntax is error-prone:

```asql
-- ASQL (clear)
where email contains "@gmail.com"
where name starts with "John"
where filename ends with ".pdf"

-- SQL LIKE (cryptic)
WHERE email LIKE '%@gmail.com%'
WHERE name LIKE 'John%'
WHERE filename LIKE '%.pdf'
```

Case-insensitive variants: `icontains`, `istarts with`, `iends with`.

---

## Window Operations: `per`

**Decision**: Use `per` command for partition-based operations.

| Alternative | Source | Why Not |
|-------------|--------|---------|
| Window function syntax only | SQL | Verbose for common patterns |
| `partition by ... ()` block | PRQL-like | More complex syntax |
| `deduplicate by` | dbt-style | Only covers one use case |

**Rationale**: Deduplication and row numbering are extremely common patterns. `per` makes them concise:

```asql
-- Keep most recent order per customer (deduplication)
from orders
  per customer_id first by -order_date

-- Add row numbers per customer
from orders
  per customer_id number by -order_date

-- Rank employees by salary within department
from employees
  per department rank by -salary
```

The syntax reads naturally: "per customer_id, first by order_date descending."

---

## Cohort Analysis: Alias Reuse Pattern

**Decision**: Use ASQL's alias reuse for cohort analysis instead of special syntax.

| Alternative | Source | Why Not |
|-------------|--------|---------|
| Manual CTEs | SQL | 50+ lines of boilerplate |
| `cohort by` operator | Earlier ASQL | Added unnecessary complexity; alias reuse already solves this |

**Rationale**: Cohort retention analysis is one of the most common analytics patterns. We originally had a `cohort by` operator, but realized ASQL's alias reuse already makes this simple:

```asql
from events
join users
group by 
  month(users.signup_date) as cohort,
  months_between(events.event_date, users.signup_date) as period
(count(distinct user_id) as active)
```

ASQL's alias reuse lets you reference `cohort` immediately after defining it - no CTEs needed. This is cleaner than a special operator because it composes naturally with other ASQL features.

---

## Guaranteed Groups: Automatic Gap-Filling

**Decision**: GROUP BY automatically fills gaps with NULLs.

| Alternative | Source | Why Not |
|-------------|--------|---------|
| SQL behavior (no filling) | SQL | Causes dashboard bugs, incorrect calculations |
| Require explicit `guarantee()` | — | Too much boilerplate for the common case |

**Rationale**: Missing data in grouped results is a constant source of analytics bugs. When you group by month, you expect all months to appear:

```asql
from orders
  where order_date >= @2024-01-01 and order_date < @2024-07-01
  group by month(order_date) (
    sum(amount) ?? 0 as revenue
  )
```

All 6 months appear, even if some have no orders.

**Consideration**: This changes semantics from standard SQL. Users coming from SQL might be surprised. We mitigate this with:
1. Clear documentation
2. Explicit `spine by` syntax (use `group by` for no gap-filling)
3. Planned `guarantee()` function for explicit control of categorical values

**Tradeoff**: Small performance overhead (<5%) for the spine generation.

---

## CTEs: `stash as`

**Decision**: Use `stash as` for inline CTEs.

| Alternative | Source | Why Not |
|-------------|--------|---------|
| `WITH ... AS` at top | SQL | CTE defined far from usage |
| `let name = (...)` | PRQL | Different syntax; variable-like |
| `set name = (...)` | — | Reserved for compiler settings |

**Rationale**: CTEs should be defined close to where they're used:

```asql
from users
  where is_active
  stash as active_users
  group by country (# as total)
  order by -total
```

The name appears right before you reference it, making the flow clear.

---

## No `having` Keyword

**Decision**: Eliminate HAVING; use `where` everywhere.

| Alternative | Source | Why Not |
|-------------|--------|---------|
| Keep `having` | SQL | Adds complexity; WHERE/HAVING distinction is confusing |

**Rationale**: Pipeline semantics eliminate the need for HAVING. The position of `where` in the pipeline determines when filtering occurs:

```asql
from orders
  where status = "active"     -- before aggregation (SQL's WHERE)
  group by region (sum(amount) as revenue)
  where revenue > 1000        -- after aggregation (SQL's HAVING)
```

One keyword, clear semantics.

---

## Scalar Variables: Not Implemented

**Decision**: No `let` or scalar variable syntax (yet).

| Alternative | Source | Status |
|-------------|--------|--------|
| `let threshold = 1000` | PRQL | Considered for future |
| `define threshold = 1000` | — | Considered for future |

**Current workaround**: Use a single-row CTE:

```asql
from (select 1000 as threshold) stash as config
from orders
  * config
  where amount > config.threshold
```

**Consideration**: Scalar variables are useful for thresholds, date ranges, and configuration. However, they add language complexity. ASQL's philosophy is "convention over configuration," not "abstraction." We may add this feature if demand is high, but it's not a priority.

---

## User-Defined Functions: Not Implemented

**Decision**: No `func` definitions (like PRQL).

**Rationale**: ASQL emphasizes convention-based convenience over abstraction. User-defined functions add significant language complexity. We let PRQL own this space.

**Workaround**: Use `stash as` for reusable CTEs, or define SQL functions in your database.

---

## Case-Insensitive Identifiers

**Decision**: ASQL is case-safe.

**Rationale**: Database conventions (snake_case) conflict with frontend conventions (camelCase). ASQL eliminates this friction:

```asql
from Users                    -- matches 'users' table
select firstName, createdAt   -- matches 'first_name', 'created_at'
```

This reduces errors when moving between different naming conventions.

---

## Auto-Aliasing

**Decision**: Automatically generate column names for expressions without aliases.

**Rationale**: SQL produces unusable default names like `SUM(amount)` or `f0_`. ASQL generates meaningful names:

```asql
from orders
  group by region (
    sum(amount),    -- → column: sum_amount
    avg(price),     -- → column: avg_price
    count(*)        -- → column: num
  )
  order by -sum_amount  -- reference the auto-alias!
```

Pattern: `{function}_{column}` (configurable).

---

## Summary Table

| Feature | ASQL Choice | Main Alternative | Winner Criteria |
|---------|-------------|------------------|-----------------|
| Filtering | `where` | `filter` | Clarity |
| Limiting | `limit` | `take` | Familiarity |
| Sorting | `order by` | `sort` | Familiarity |
| Adding columns | `extend` | `derive` | SQL-friendly |
| Aggregation | `group by ()` | `group` + `aggregate` | Conciseness |
| Counting | `#` | `count(*)` | Brevity |
| Joins | `&`, `&?` | SQL keywords | Compactness |
| Nulls | `??` | `coalesce()` | Brevity |
| Dates | `@2024-01-01` | `DATE '...'` | Brevity |
| Date math | `+ 7 days` | `date_add()` | Readability |
| Relative dates | `ago`, `from now` | Manual | Readability |
| String matching | `contains` | `LIKE` | Readability |
| Window ops | `per` | Window functions | Conciseness |
| Cohorts | Alias reuse pattern | Manual CTEs | Productivity |
| Gap-filling | Automatic | Manual spines | Correctness |
| CTEs | `stash as` | `WITH ... AS` | Proximity |
| Post-aggregation filter | `where` | `having` | Simplicity |

---

## Open Questions

These are syntax decisions still under consideration:

1. **`sort by` alias**: Should we add `sort by` as an alias for `order by`? Probably yes.

2. **Scalar variables**: Should we add `let threshold = 1000`? Under consideration.

3. **`sort` without `by`**: Should bare `sort -col` work? Probably, for consistency with ASQL's filler-word approach.

---

## Changelog

| Date | Decision | Notes |
|------|----------|-------|
| 2024 | Core syntax established | `where`, `limit`, `order by`, `group by ()` |
| 2024 | `#` count shorthand | Novel but intuitive |
| 2024 | `per` for window operations | Simplifies deduplication |
| 2024 | Guaranteed groups | Automatic gap-filling |
| 2024 | Cohort pattern | Alias reuse enables simple cohort queries |
| 2025-01 | `extend` implemented | In branch, pending merge |
| 2026-01 | Documentation | This page created |

