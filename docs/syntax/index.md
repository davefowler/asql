# Syntax Guide

This section provides detailed documentation on ASQL syntax. Each page covers a specific aspect of the language.

## Core Syntax

- **[Pipe Syntax](pipe.md)** — FROM-first queries, pipe operators, chaining transformations
- **[Expressions & Operators](expressions.md)** — Comparisons, arithmetic, logical operators, conditionals
- **[Aggregations](aggregations.md)** — GROUP BY, aggregate functions, natural language aggregates
- **[Joins](joins.md)** — Join operators, FK inference, dot notation traversal
- **[Dates & Time](dates.md)** — Date literals, truncation, arithmetic, relative dates
- **[Window Functions](window-functions.md)** — Ranking, running totals, prior/next, deduplication
- **[CTEs & Settings](ctes.md)** — `stash as` (CTEs) and `SET` (compiler settings)
- **[Cohort Analysis](cohorts.md)** — Cohort assignment, retention calculations, period-over-period comparisons

## Data Manipulation

- **[Sampling](sampling.md)** — Random sampling, percentage sampling, stratified sampling
- **[Pivot, Unpivot & Explode](pivot-unpivot.md)** — Reshaping data, column operators, array expansion

## Quick Reference

| Operation | ASQL Syntax | SQL Equivalent |
|-----------|-------------|----------------|
| Start query | `from users` | `SELECT * FROM users` |
| Filter rows | `where status = "active"` | `WHERE status = 'active'` |
| Select columns | `select name, email` | `SELECT name, email` |
| Group and aggregate | `group by country (# as total)` | `SELECT country, COUNT(*) AS total GROUP BY country` |
| Sort descending | `order by -created_at` | `ORDER BY created_at DESC` |
| Limit results | `limit 10` | `LIMIT 10` |
| Random sample | `sample 100` | `ORDER BY RANDOM() LIMIT 100` |
| Inner join | `& users on id = user_id` | `INNER JOIN users ON id = user_id` |
| Left join | `&? users on id = user_id` | `LEFT JOIN users ON id = user_id` |
| Count rows | `#` | `COUNT(*)` |
| Date literal | `@2024-01-15` | `DATE '2024-01-15'` |
| Null coalesce | `value ?? 0` | `COALESCE(value, 0)` |
| Exclude column | `except password_hash` | `SELECT * EXCEPT(password_hash)` |
| Pivot | `pivot sum(x) by cat values (...)` | `CASE WHEN ... GROUP BY` |
| Explode array | `explode tags as tag` | `CROSS JOIN UNNEST(tags)` |
| Cohort analysis | `group by month(signup) as cohort, months_between(date, signup) as period` | Multiple CTEs |

## Syntax Flexibility

ASQL embraces flexibility in how you write queries:

### Underscores and Spaces

In function contexts, underscores and spaces are interchangeable:

```asql
-- All equivalent:
sum(amount)           -- explicit function call
sum_amount            -- underscore shorthand
sum amount            -- space shorthand
sum of amount         -- "of" style
```

### Equality Operators

Both `=` and `==` work for equality:

```asql
where status = "active"   -- SQL style
where status == "active"  -- programmer style
```

### Pipe Operators

Pipe operators are optional—indentation works too:

```asql
-- Indentation-based (preferred):
from users
  where is_active
  group by country (# as total)

-- Explicit pipe operators:
from users
| where is_active
| group by country (# as total)
```

## Next Steps

- Start with **[Pipe Syntax](pipe.md)** to understand the core structure
- See **[Examples](../examples.md)** for real-world query patterns
- Read the **[Language Specification](../spec.md)** for complete reference
