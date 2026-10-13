# The Fanout Problem: 4 Ways to Fix It in SQL

When you join tables with one-to-many relationships and aggregate columns from the "one" side, those values get silently duplicated. This is called **fanout**, and it is one of the most common sources of wrong numbers in analytics.

This article describes the problem, shows four different solutions, and compares their trade-offs.

---

## The Problem

Suppose you have three tables:

| **orders** | | |
|---|---|---|
| order_id | customer_id | shipping_cost |
| 1 | 11 | $1 |
| 2 | 12 | $10 |

| **order_items** | | |
|---|---|---|
| order_id | item_id | quantity |
| 1 | apple | 1 |
| 2 | apple | 2 |
| 2 | orange | 1 |

| **customers** | | |
|---|---|---|
| customer_id | state |
| 11 | Alabama |
| 12 | Alaska |

You want: *for each state, what is the total shipping cost and the total number of items?*

The naive query:

```sql
SELECT state, SUM(shipping_cost), SUM(quantity)
FROM orders
JOIN order_items USING (order_id)
JOIN customers USING (customer_id)
GROUP BY 1
```

Produces:

| state | sum(shipping_cost) | sum(quantity) |
|---|---|---|
| Alabama | $1 | 1 |
| Alaska | **$20** | 3 |

Alaska shows $20 instead of $10. Order #2 has two items, so the join duplicated its row — and `SUM(shipping_cost)` counted it twice.

This is fanout.  It happens whenever you aggregate a column from the "one" side of a one-to-many join. The aggregate from the "many" side (`SUM(quantity) = 3`) is correct, but the "one" side aggregate is inflated by the number of matched rows.

---

## Solution 1: Symmetric Aggregates (Looker)

Looker solves this by replacing the aggregate expression with a hash-based deduplication trick:

```sql
SELECT
    state,
    SUM(DISTINCT HASH(order_id) + shipping_cost)
      - SUM(DISTINCT HASH(order_id)),
    SUM(quantity)
FROM orders
JOIN order_items USING (order_id)
JOIN customers USING (customer_id)
GROUP BY 1
```

The idea: `HASH(order_id)` produces a unique value per order. Adding `shipping_cost` and taking `SUM(DISTINCT ...)` ensures each order's cost is counted exactly once. Subtracting the hash sum recovers the original value.

This is clever enough that Looker [patented it](https://patents.google.com/patent/CA2965831A1).

**Pros:**

- No query restructuring needed — it's a single flat query with the same structure as the naive version.
- Works without knowing which side of the join is "many" — the hash dedup is applied per-aggregate.

**Cons:**

- **Unreadable SQL.** If you've ever looked at Looker-generated SQL and wondered "what on earth is that?", this is why. You cannot debug or verify this by hand.
- **Slow.** `DISTINCT` aggregates are more expensive than simple ones on every database engine.
- **Combinatorial explosion.** With multiple one-to-many joins, the intermediate result can blow up in size because the full cross-product is still computed — the dedup happens *after* the explosion.
- **Fragile.** The hash trick assumes no collisions and requires careful type handling (`HASH(pk)` must produce values large enough that `hash + measure_value` doesn't lose precision).
- **Patented.** Looker holds patent CA2965831A1 on this technique.
- **Dialect-dependent.** Requires a `HASH` or `MD5` function, which varies across databases.

---

## Solution 2: Pre-Aggregate the Many Side

Instead of joining and then trying to fix the result, prevent the fanout from ever happening. Pre-aggregate the many-side table into a subquery that produces one row per join key:

```sql
SELECT state, SUM(shipping_cost), SUM(quantity)
FROM orders
JOIN (
    SELECT order_id, SUM(quantity) AS quantity
    FROM order_items
    GROUP BY 1
) USING (order_id)
JOIN customers USING (customer_id)
GROUP BY 1
```

The subquery collapses `order_items` down to one row per `order_id`. Now the join with `orders` is one-to-one, and `SUM(shipping_cost)` is never inflated.

This technique was [described by George Fraser](https://www.fivetran.com/blog/how-to-use-measures-with-one-to-many-joins) as a non-patented alternative to Looker's approach. At the time of writing, no BI tool used this method, despite it being the most natural solution.

**Pros:**

- **Cleanest SQL.** This is what a skilled analyst would write by hand. Anyone reviewing the output can immediately understand what it does and verify it's correct.
- **Most efficient.** The fanned-out intermediate result is never created. The subquery runs on just the many-side table, bounded by its size — no cross-product, no DISTINCT pass.
- **Scales to multiple 1:M joins.** Each many-side table gets its own independent subquery. Two many-side tables = two subqueries, not a combinatorial explosion.
- **Standard SQL-92.** Works identically on every database — Postgres, Snowflake, BigQuery, DuckDB, MySQL, Redshift.
- **No patent issues.**

**Cons:**

- **Requires a declared join direction.** You need to know which table to pre-aggregate — i.e., which side of the join can have many rows per key. A declared foreign key is exactly that statement: an FK must reference a unique key, so the FK side is the "many" side by definition. No row counts or profiled statistics are needed — see [What metadata you actually need](#what-metadata-you-actually-need) below.
- **Cross-table expressions are harder.** An expression like `SUM(orders.tax_rate * order_items.price)` references columns from both tables. Since the many-side is pre-aggregated, individual row values aren't available. These expressions must either be computed *inside* the subquery (if possible) or left unprotected. In ASQL, the clean workaround is usually to compute the row-level expression in an earlier pipe stage and then aggregate the derived column later.

---

## Solution 3: Group By the Primary Key

A third approach: do the join, but then wrap it in a subquery that groups by the one-side primary key. This collapses the fanned-out rows back to one per order:

```sql
SELECT state, SUM(shipping_cost), SUM(sum_quantity)
FROM (
    SELECT order_id, customer_id, MIN(shipping_cost) AS shipping_cost,
           SUM(quantity) AS sum_quantity
    FROM orders
    JOIN order_items USING (order_id)
    GROUP BY 1, 2
) agg
JOIN customers USING (customer_id)
GROUP BY 1
```

The inner `GROUP BY order_id, customer_id` collapses the fanned-out rows back to one per order. `SUM(quantity)` aggregates the many-side at the correct grain. For one-side columns like `shipping_cost`, we use `MIN()` — since all duplicated rows have the same value, `MIN` just picks it. (You could also use `MAX` or `ANY_VALUE` where supported — the point is any of them return the one true value.)

A common variation puts `shipping_cost` directly in the GROUP BY clause instead of wrapping it in `MIN()`. That also works — since `shipping_cost` is functionally dependent on `order_id`, grouping by it doesn't change the result. But using an aggregate like `MIN()` is slightly more robust: it makes the intent explicit ("this value is the same for every row in the group, just give it to me") and won't silently split rows if the assumption is ever wrong due to a data quality issue.

This is essentially the same technique as Solution 2 — both use multiple levels of aggregation. The difference is structural:

- **Solution 2** isolates each many-side table into its own subquery *before* joining.
- **Solution 3** joins first, then collapses the result with a GROUP BY on the one-side PK.

Both produce correct results. Solution 2 tends to be cleaner when there are multiple many-side tables. Solution 3 can be simpler when you're working with a single join and want to keep everything in one subquery.

For ASQL specifically, pipe stages change this tradeoff slightly. If a row-level derived
value needs columns from both sides of a join, you can often compute it in one stage and
then aggregate it in a later stage. That avoids some cases that would otherwise require
the "group by the primary key" fallback. But if the grouped step itself still groups,
filters, or orders by raw many-side columns, then the step still depends on many-side
row shape and cannot be safely rewritten as a pre-aggregated join.

**Pros:**

- **Less metadata needed.** You only need to know the primary key of the one-side table — not the FK column, the join direction, or which table is "many". This makes it a good fallback when full schema metadata isn't available.
- **Single subquery.** Both tables are handled in one pass, which can be simpler for straightforward cases.
- **Handles cross-table expressions.** Since both tables are still joined row-by-row inside the subquery, expressions like `SUM(orders.tax_rate * order_items.price)` work naturally.
- **Standard SQL-92.** No dialect-specific functions needed.

**Cons:**

- **The double-SUM pattern.** The outer query aggregates `SUM(sum_quantity)` — a SUM of a SUM. This is correct but can confuse readers who aren't expecting two levels of aggregation.
- **Gets complex with multiple many-side tables.** If `orders` joins to both `order_items` and `returns`, you need all the many-side aggregates in a single inner subquery, which becomes unwieldy.
- **Still creates the fanned-out intermediate.** The join produces the full cross-product before the GROUP BY collapses it. Less efficient than Solution 2, which never creates the fanout.

---

## Solution 4: CTE + DISTINCT Per Table

A fourth approach uses Common Table Expressions (CTEs) to separately deduplicate each source table after the join:

```sql
WITH order_aggs AS (
    SELECT DISTINCT o.order_id, o.shipping_cost, o.customer_id
    FROM orders o
    JOIN order_items oi USING (order_id)
    -- DISTINCT on order_id removes the duplicated order rows
),
item_aggs AS (
    SELECT order_id, SUM(quantity) AS quantity
    FROM order_items
    GROUP BY 1
)
SELECT c.state, SUM(oa.shipping_cost), SUM(ia.quantity)
FROM order_aggs oa
JOIN item_aggs ia USING (order_id)
JOIN customers c ON oa.customer_id = c.customer_id
GROUP BY 1
```

For each table that has aggregates, a dedicated CTE either uses `DISTINCT` on the primary key to undo the fanout (for the "one" side) or pre-aggregates by the foreign key (for the "many" side). The final query joins these clean CTEs together.

This is closest in spirit to Solution 3 — both join first and then deduplicate. The difference is that Solution 4 creates separate CTEs per source table instead of collapsing everything in a single subquery.

**Pros:**

- **Systematic.** Each source table gets its own CTE with a uniform pattern. Easy to implement as an automated transform — just loop over the tables.
- **Scales to many tables.** Unlike Solution 3's single-subquery approach, adding more tables just means adding more CTEs rather than making one subquery more complex.
- **Standard SQL-92.** Only uses `WITH`, `SELECT DISTINCT`, `GROUP BY`, and `JOIN`.

**Cons:**

- **"Join then undo" is wasteful.** The `order_aggs` CTE joins orders to order_items, then uses DISTINCT to throw away the item rows — doing work just to reverse it. Solution 2 avoids this entirely.
- **Verbose output.** A query touching three tables generates three CTEs before the final SELECT. The generated SQL is harder to read than Solutions 2 or 3.
- **DISTINCT overhead.** `SELECT DISTINCT` on the one-side CTE adds a dedup pass that Solutions 2 and 3 avoid.
- **Cross-table expressions are awkward.** They can't be deduplicated by either table's PK, so they need a separate unprotected CTE — which means some aggregates are fanout-protected and others aren't, which is confusing.

---

## Comparison

|  | Symmetric Aggregates | Pre-Aggregate | Group By PK | CTE + DISTINCT |
|---|---|---|---|---|
| **Readability** | Poor | Excellent | Good | OK |
| **Efficiency** | Slow (DISTINCT agg) | Best (no fanout created) | Medium | Medium |
| **Creates fanout?** | Yes (dedup after) | No (prevented) | Yes (collapsed after) | Yes (dedup after) |
| **Schema needed** | PK only | FK only (declared direction) | PK only | PK + table lineage |
| **Cross-table aggs** | Works | Hard | Works | Partial |
| **Multiple 1:M joins** | Combinatorial explosion | Clean (subquery per table) | Complex GROUP BY | CTE per table |
| **SQL standard** | Needs HASH function | SQL-92 | SQL-92 | SQL-92 |
| **Patent issues** | Yes | No | No | No |

All four produce correct results. The meaningful differences are in readability, performance, and how gracefully they handle complex schemas.

### Our recommendation: Solutions 2 and 3

**Solution 2 (pre-aggregate) is the gold standard** when you have schema metadata. It produces the cleanest SQL — the kind a skilled analyst would write by hand. It's the most efficient because the fanned-out intermediate result is never created. And it scales cleanly to multiple one-to-many joins. If you're building a tool that generates SQL automatically and you have access to schema information (PKs and FKs), this is the approach to use.

**Solution 3 (group by PK) is the best fallback** when you don't have full schema metadata, or when you're writing SQL by hand and want a quick fix. You only need to know the primary key — not the FK or the join direction. It also handles cross-table expressions naturally, since both tables are still joined row-by-row inside the subquery.

**In practice, Solutions 2 and 3 are the same underlying idea** — multiple levels of aggregation — just structured differently. George Fraser put it well: "same thing, you're doing multiple levels of aggregation." Both are clean, reliable, standard SQL that any database can optimize well.

**Solution 1 (symmetric aggregates)** is ingenious but produces SQL that no human can read or debug. It exists for automated SQL generation in BI tools where output readability doesn't matter. It's also patented.

**Solution 4 (CTE + DISTINCT)** is a reasonable automated approach but is strictly worse than Solution 2 — it does the join then undoes it with DISTINCT, producing more verbose SQL with more overhead. Its one advantage is ease of implementation as a mechanical transform.

---

## What Metadata You Actually Need

It's easy to assume fanout protection needs data statistics — row counts, measured
multiplicities, "is this join really 1:M in practice?". It doesn't. Two different
things hide under the word "cardinality", and only one of them matters:

- **Direction** (structural): which side of the join *can* have many rows per key.
  A declared foreign key is precisely this statement — an FK must reference a
  unique key, so `order_items.order_id → orders.order_id` means "order_items is
  the at-most-many side, orders is the exactly-one side". Direction is what the
  pre-aggregation rewrite needs, and a declared FK carries all of it.
- **Statistics** (measured): whether the many side actually has >1 row per key in
  today's data. This never affects correctness — only whether protection was
  worth the work.

The reason statistics can't affect correctness is an asymmetry: **protecting a
join that didn't need it is a no-op, not an error.** Pre-aggregating a table that
is already unique on the join key returns the identical relation — the rewrite
produces the same result, just with an extra pass. Wrong numbers only ever come
from *not* protecting a join that fans out. (Looker documents the same asymmetry:
their guidance is to declare `many_to_many` when unsure, because with correct
primary keys that "will always produce accurate results" at a performance cost.
The dangerous direction is exclusively under-declaring.)

So the division of labor is:

1. **Declared FKs** decide *what must be protected* — correctness.
2. **Uniqueness knowledge** (a PK or unique constraint on the join column) decides
   *what can be skipped* — performance. A truly 1:1 join needs no rewrite, and
   the only fact required to skip it is that the join column is unique.
3. If neither is declared, a one-time `COUNT(*) = COUNT(DISTINCT key)` probe on
   the join column proves the same uniqueness fact from data. That is the entire
   useful role of profiling here.

### How ASQL applies this

Fanout protection is on by default: with a schema that declares relationships,
ASQL protects every shape it can prove from the declared FK matched against the
`ON` clause — no row counts, no profiling:

- **Joined many side with aggregates** → pre-aggregated by the foreign key
  before joining (Solution 2).
- **Joined many side no aggregate references** (join used as a filter) →
  collapsed to `SELECT DISTINCT <fk>` so it keeps filtering without
  multiplying rows.
- **FROM-side many table with one-side aggregates** (`FROM order_items JOIN
  orders … SUM(orders.shipping_cost)`) → re-aggregated through an inner
  `GROUP BY <join key>` stage that captures each one-side value once per key
  (Solution 3, with the join key standing in for the primary key).

Query shapes that depend on raw many-side rows (grouping, filtering, or
ordering by many-side columns) and aggregates that cannot cross the boundary
are left unchanged with a diagnostic comment — provable-but-unrewritten risk
emits an `ASQL fanout warning` rather than staying silent. Protection can be
disabled per query with `SET fanout_protection = false`.

---

## When Fanout Is Intentional

Not all fanout is a bug. A few cases where the duplicated result is actually what you want:

- **Weighted metrics.** If you're computing `SUM(order.weight * item.quantity)`, the cross-product is the correct calculation — each item contributes its quantity times the order's weight.
- **Debugging.** Sometimes you want to see the raw joined result to understand a relationship. "How many rows come back when I join these two tables?" is a valid question.
- **One-to-one joins.** When the relationship is actually 1:1, there's no fanout. The "fix" adds overhead for zero benefit.

Knowing when fanout is a problem — and when it isn't — is part of the craft of analytics.

---

## Further Reading

- [How to Use Measures With One-to-Many Joins](https://www.fivetran.com/blog/how-to-use-measures-with-one-to-many-joins) — George Fraser's original blog post describing Solution 2
- [Looker's Symmetric Aggregates Explained](https://help.looker.com/hc/en-us/articles/360023722974) — Looker's documentation of their approach
- [Looker Patent (CA2965831A1)](https://patents.google.com/patent/CA2965831A1) — The actual patent filing
