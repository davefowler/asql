# Design Principles

ASQL was created with a few core design principles that guide every language decision.

---

## 🎯 Read Like You Think

Queries should flow naturally, top to bottom, in the order you reason about data:

1. Start with your data source
2. Filter to what you care about
3. Transform and aggregate
4. Order and limit the results

**Not**: define output columns → specify source → add filters → remember to group → finally order.

This is why ASQL uses pipeline syntax. You build queries step-by-step, just like you'd explain your analysis to a colleague.

---

## 📐 Convention Over Configuration

If you follow good modeling practices (like dbt's naming conventions), ASQL makes smart inferences:

- **Foreign keys**: `user_id` automatically links to `users.id`
- **Timestamps**: `created_at` works with natural date functions
- **Naming**: Case-insensitive matching handles `snake_case`, `camelCase`, or whatever your database uses

Everything is configurable, but sensible defaults mean less boilerplate.

---

## 🔤 Familiarity Over Novelty

ASQL keeps SQL's vocabulary—`from`, `where`, `group by`, `join`. We improve the grammar, not replace the language.

- Your SQL knowledge transfers directly
- SQL snippets can be mixed with ASQL
- The compiled output is readable SQL you can inspect

We're not trying to invent a new language—we're trying to make SQL more pleasant to write.

---

## 🌐 Portable By Design

ASQL compiles to any SQL dialect via [SQLGlot](https://github.com/tobymao/sqlglot). Write once, run on:

- PostgreSQL
- MySQL / MariaDB
- SQLite
- BigQuery
- Snowflake
- Redshift
- DuckDB
- Trino / Presto
- Spark SQL
- And [many more...](https://github.com/tobymao/sqlglot#dialects)

SQLGlot handles the dialect differences so you don't have to worry about `DATE_TRUNC` vs `DATEADD` vs `DATE_ADD`.

---

## 🧩 Composable & Incremental

ASQL doesn't force you to rewrite everything. You can:

- Use ASQL for new queries while keeping existing SQL
- Gradually migrate complex queries one piece at a time
- Mix raw SQL with ASQL where needed
- Use ASQL's output (plain SQL) anywhere SQL is accepted

---

## 📖 Self-Documenting

Good code should be readable without comments. ASQL aims for queries that explain themselves:

```asql
from orders
  where created_at > 7 days ago
  group by month(created_at) ( sum(amount) as revenue )
  order by -revenue
  limit 10
```

Compare that to the equivalent SQL and you'll see why readability matters.

---

## Learn More

- [Quick Start](quick_start.md) — Learn the basics in 5 minutes
- [Language Specification](spec.md) — Complete language reference
- [Examples](examples.md) — Real-world queries with SQL comparisons
