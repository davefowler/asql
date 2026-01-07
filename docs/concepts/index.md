# Concepts

This section explains the core ideas and design values behind ASQL.

## Core Concepts

- **[Pipeline Semantics](pipelines.md)** — Why FROM-first and what it means for your queries
- **[Guaranteed Groups](guaranteed-groups.md)** — Automatic gap-filling for complete analytics
- **[Convention Over Configuration](conventions.md)** — How ASQL infers relationships and defaults
- **[Function Shorthand](shorthand.md)** — Underscore/space flexibility explained

## Design Values

ASQL is built on deliberate tradeoffs—we value:

### 1. Pipeline Order Over Projection-First

SQL's syntax was designed in the 1970s. The written order doesn't match execution:

```sql
SELECT region, SUM(amount)     -- 5th
FROM sales                      -- 1st
WHERE year = 2024               -- 2nd
GROUP BY region                 -- 3rd
HAVING SUM(amount) > 1000       -- 4th
ORDER BY 2 DESC                 -- 6th
```

ASQL writes queries in the order they execute. Data flows top-to-bottom. This not only reads more naturally, but eliminates the messy subquery and CTE scaffolding that traditional SQL requires due to its choice to be projection-first.  

#### Related Features

- [Pipeline Semantics](pipelines.md) — deep dive on execution order
- [Pipeline Syntax](../syntax/pipeline.md) — FROM-first query structure
- [Aggregations](../syntax/aggregations.md) — no HAVING keyword needed

### 2. Convention Over Configuration

The best configuration is no configuration. When columns like `user_id` and `created_at` follow predictable patterns, ASQL can infer relationships and types automatically:

- `user_id` enables `.user.` dot traversal
- `created_at` is recognized as a timestamp
- Table names are pluralized automatically

You write less, and the query stays focused on *what* you want, not *how* to get it.

#### Related Features

- [Conventions](conventions.md) — naming patterns ASQL recognizes
- [Auto-aliasing](../reference/auto-aliasing.md) — automatic column naming
- [Joins](../syntax/joins.md) — implicit join syntax

### 3. Familiarity Over Novelty

New syntax has a cost: every teammate must learn it, every code review must translate it. ASQL keeps SQL's vocabulary so your existing knowledge transfers:

- `select`, `where`, `order by`, `limit`
- `sum()`, `avg()`, `count()`
- `join`, `on`, `as`

The learning curve is hours, not weeks.

#### Related Features

- [Functions](../reference/functions.md) — SQL-compatible function reference
- [Operators](../reference/operators.md) — standard operators
- [Keywords](../reference/keywords.md) — familiar SQL keywords

### 4. Portable Over Proprietary

Proprietary query languages lock you to a vendor. When you need to switch databases or debug performance, you're stuck. ASQL transpiles to all major SQL dialects—Postgres, BigQuery, Snowflake, DuckDB, and more. You can always inspect the generated SQL and take your queries anywhere.

#### Related Features

- [Dialect Limitations](../dialect-limitations.md) — what works where
- [Integrating ASQL](../integrating.md) — using ASQL with your stack

### 5. Completeness Over Fast Queries

Analytics and data modeling require complete data. When groups and ranges are guaranteed—unlike traditional SQL—complexity and uncertainty are greatly reduced. The tradeoff? Typically less than 5% extra query time. Date spines are generated in-memory (milliseconds). Categorical spines add one lightweight DISTINCT query. For analytics, correctness over raw speed is an obvious choice.

#### Related Features

- [Guaranteed Groups](guaranteed-groups.md) — how gap-filling works
- [Spines and Performance](guaranteed-groups.md#spines-and-performance) — detailed performance analysis
- [Aggregations](../syntax/aggregations.md) — OVER EVERY syntax

### 6. Code Comments Over Catalogues

Software engineering learned this decades ago: external documentation rots. The wiki says one thing, the code does another, and nobody knows which is right. Data teams are still catching up. When comments live in the query, they travel with it—versioned, reviewed, and maintained together.

ASQL preserves your `--` comments through transpilation. It also adds helpful comments to explain generated SQL (like spine CTEs), so the output is self-documenting.

#### Related Features

- [Comments Syntax](../syntax/expressions.md#comments) — inline comments in queries
- [Transpilation Comments](guaranteed-groups.md#transpilation-comments) — ASQL-generated explanations

## Next Steps

- **[Pipeline Semantics](pipelines.md)** — Deep dive into FROM-first design
- **[Guaranteed Groups](guaranteed-groups.md)** — Understanding automatic gap-filling
- **[Syntax Guide](../syntax/index.md)** — Complete syntax reference
