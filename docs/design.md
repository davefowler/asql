# Design Principles

ASQL is built on a set of core principles that guide every language decision. These principles sometimes conflict, and when they do, this ordering generally reflects our priorities.

---


## Built for Analysis

SQL has always tried to be everything to everyone—transactional systems, analytics, ETL, application backends. These have fundamentally different needs, yet SQL has never branched into specialized dialects the way programming languages have.

ASQL makes a choice: we are a dialect for analysis and transformation, full stop. We are not trying to please DBAs optimizing write throughput or application developers minimizing latency. This focus gives us freedom.

Auto-generating date spines? Transactional SQL would never. But for analytics, it's obviously correct. Helper functions for common analysis patterns? An OLTP purist would object to the overhead. We don't care—we're not building for them.

This vertical focus means every design decision can ask a simpler question: *does this make analysis easier?* If yes, we do it. The needs of other SQL workloads are not our concern.

---

## Respect the Past, Move Forward

Some SQL keywords have confused generations of analysts. `CASE WHEN THEN ELSE END` is verbose and awkward. `PARTITION BY` and `ROWS BETWEEN` are incantations even experienced developers look up every time. These aren't sacred—they're historical accidents that calcified into standards.

ASQL makes the call: where syntax has been a persistent source of confusion, we improve it. Not for novelty, but because clarity matters more than tradition. `if/then/else` reads like English. `over last 7 rows` says what it means.

Some behaviors are simply wrong for analysis. When you group by month in SQL, months with no data disappear from your result.  Its a quirk of SQL's row-oriented processing, not a deliberate design choice. This breaks charts, time series analysis, and stakeholder expectations. ASQL generates complete date ranges by default, because that is what correct analysis requires.

We can make these decisions confidently because we don't force the change. The original SQL syntax remains fully supported. Analysts who think in `CASE WHEN` can keep writing it. Default behaviors can be configured. This backward compatibility gives us the freedom to move forward—we can fix long-standing pain points without breaking muscle memory or existing queries.

```asql
from orders
  where created_at > 7 days ago
  group by month(created_at) ( 
    sum(amount) as revenue 
  )
  order by -revenue
  limit 10
```

When syntax is clear:

1. **More people can write it.** Lower barriers mean broader adoption.
2. **Writing becomes a pleasure.** Natural syntax reduces cognitive load.
3. **Maintenance becomes tractable.** Code that reads like prose is code that can be understood months later.
4. **Less mistakes are made.** Errors stand out when the surrounding code is self-explanatory.

Especially as AI generates more of our queries, we need them to be fast to scan and easy to verify.

---

## Convention Over Configuration

If you follow good modeling practices (like dbt's naming conventions), ASQL makes smart inferences:

- **Foreign keys**: `user_id` automatically links to `users.id`
- **Timestamps**: `created_at` works with natural date functions
- **Naming**: Case-insensitive matching handles `snake_case`, `camelCase`, or whatever your database uses

Everything is configurable, but sensible defaults mean less boilerplate.

---

## Standing on the Shoulders of Giants

We studied the tools that data practitioners love (dbt, Pandas, PRQL, Kusto, R etc) collecting their best ideas, understanding the problems they solve, and asking: *how might these concepts be expressed directly in SQL?*

ASQL does not exist in a vacuum. It is a synthesis of decades of collective wisdom about how humans want to work with data.

---

## Documentation Lives in Code

Comments should live alongside the code they describe. Documentation that exists separately from the source inevitably drifts out of sync.

ASQL treats comments as first-class citizens. Thanks to SQLGlot's AST-level support, comments propagate through compilation—from ASQL source to generated SQL to downstream consumers. Whether your comments end up in BI tools, data catalogs, dbt docs, or AI context, they travel with the query.

Documentation happens when it is easy. ASQL makes it easy.

---

## Composable and Incremental

ASQL does not demand a rewrite. Adoption is incremental:

- Use ASQL for new queries while keeping existing SQL
- Migrate complex queries one piece at a time
- Mix raw SQL with ASQL where needed
- Use ASQL's output (plain SQL) anywhere SQL is accepted

The output is always standard SQL. There is no lock-in.

---

## Learn More

- [Quick Start](quick_start.md) — Learn the basics in 5 minutes
- [Language Specification](spec.md) — Complete language reference
- [Examples](examples.md) — Real-world queries with SQL comparisons
