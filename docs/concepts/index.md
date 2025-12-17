# Concepts

This section explains the core ideas and design philosophy behind ASQL.

## Core Concepts

- **[Pipeline Semantics](pipelines.md)** — Why FROM-first and what it means for your queries
- **[Guaranteed Groups](guaranteed-groups.md)** — Automatic gap-filling for complete analytics
- **[Convention Over Configuration](conventions.md)** — How ASQL infers relationships and defaults
- **[Function Shorthand](shorthand.md)** — Underscore/space flexibility explained

## Design Philosophy

ASQL is built on several key principles:

### 1. Queries Should Read Like Questions

```asql
from users
  where status = "active"
  group by country (# as total)
  order by -total
```

Reads naturally: "From users, where status is active, group by country counting total, order by total descending."

### 2. Convention Over Configuration

If you follow standard naming conventions (like dbt's), ASQL works automatically:

- `user_id` enables `.user.` dot traversal
- `created_at` is recognized as a timestamp
- Table names are pluralized automatically

### 3. Familiarity Over Novelty

ASQL keeps SQL's familiar nouns and functions:
- `select`, `where`, `order by`, `limit`
- `sum()`, `avg()`, `count()`
- `join`, `on`, `as`

It improves the ordering and syntax without inventing an entirely new language.

### 4. Pipeline Semantics

Every query is a sequence of tabular transformations. Data flows top-to-bottom, making complex queries easier to understand and debug.

### 5. Portable and Inspectable

ASQL transpiles to SQL for any dialect. You can always see the generated SQL to understand exactly what will run.

## Why Not Just SQL?

SQL's syntax was designed in the 1970s for interactive terminals. The execution order doesn't match the written order:

```sql
SELECT region, SUM(amount)     -- 5th
FROM sales                      -- 1st
WHERE year = 2024               -- 2nd
GROUP BY region                 -- 3rd
HAVING SUM(amount) > 1000       -- 4th
ORDER BY 2 DESC                 -- 6th
LIMIT 10;                       -- 7th
```

This inside-out structure makes complex queries harder to read, write, and review. You end up using CTEs primarily to linearize logic.

ASQL fixes this by putting operations in execution order.

## Next Steps

- **[Pipeline Semantics](pipelines.md)** — Deep dive into FROM-first design
- **[Guaranteed Groups](guaranteed-groups.md)** — Understanding automatic gap-filling
- **[Syntax Guide](../syntax/index.md)** — Complete syntax reference
