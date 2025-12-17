# Convention Over Configuration

ASQL follows a "convention over configuration" philosophy. If you follow standard naming conventions, ASQL works automatically. If you don't, you can always be explicit.

## Core Philosophy

**Assume good modeling.** ASQL expects:
- Standard column naming (e.g., `created_at` for timestamps)
- Proper foreign key patterns (e.g., `user_id` for FK to `users`)
- Consistent table naming (singular or plural, but consistent)

If you follow these conventions, ASQL infers relationships, defaults, and behaviors automatically. If your schema is non-standard, you can configure explicitly.

## Foreign Key Inference

### The Convention

Foreign keys follow the pattern: `{entity}_id` or `{alias}_{entity}_id`

| FK Column | Inferred Alias | Target Table | Dot Traversal |
|-----------|----------------|--------------|---------------|
| `user_id` | `user` | `users` | `.user.` |
| `order_id` | `order` | `orders` | `.order.` |
| `owner_user_id` | `owner` | `users` | `.owner.` |
| `manager_id` | `manager` | `managers` or `users` | `.manager.` |

### How It Works

```asql
from orders
  select orders.user.name
```

ASQL:
1. Sees `.user.` traversal on `orders`
2. Looks for `user_id` column in `orders`
3. Infers target: `users` table (pluralized)
4. Creates LEFT JOIN automatically

### Multiple FKs to Same Table

When a table has multiple FKs to the same table:

```asql
-- accounts has owner_user_id, manager_user_id
from accounts
  select 
    accounts.owner.name,     -- via owner_user_id → users
    accounts.manager.name    -- via manager_user_id → users
```

Pattern: `{alias}_{table}_id` → alias is `{alias}`, target is `{table}`

## Timestamp Conventions

### Standard Names

ASQL recognizes these as timestamp columns:
- `created_at` — Record creation time
- `updated_at` — Last update time
- `deleted_at` — Soft delete timestamp

### Default Time Field

Tables with `created_at` automatically use it as the primary time field for time-based aggregations.

```asql
from users
  group by month(created_at) (# as signups)
```

### Override with Metadata

```yaml
models:
  events:
    default_time: event_timestamp
```

## Table Name Pluralization

ASQL handles plural/singular automatically:

- `from users` → `users` table
- `.user.` traversal → looks for `users` table
- `.order.` traversal → looks for `orders` table

## Inference Priority

When resolving relationships, ASQL uses this priority:

1. **Explicit `on` clause** — Always wins
2. **Schema metadata** — If relationships are defined
3. **Naming convention** — `{name}_id` enables `.{name}.` traversal
4. **Error with suggestions** — If ambiguous

```asql
-- Priority 1: Explicit always works
from orders
  & users on orders.customer_id = users.id

-- Priority 3: Convention inference
from orders
  select orders.user.name  -- Uses user_id convention
```

## dbt Compatibility

ASQL reads dbt's `schema.yml` files:

```yaml
# dbt schema.yml
models:
  - name: orders
    columns:
      - name: user_id
        tests:
          - relationships:
              to: ref('users')
              field: id
```

ASQL uses these relationships automatically.

## Case Insensitivity

ASQL is case-safe:

```asql
from Users           -- Matches 'users' table
from USERS           -- Also matches 'users'
select firstName     -- Matches 'first_name' column
```

This eliminates friction between different naming conventions:
- Database: `snake_case` (`created_at`)
- Frontend: `camelCase` (`createdAt`)
- APIs: `PascalCase` (`CreatedAt`)

## Function Shorthand

Underscores and spaces are interchangeable in function contexts:

```asql
-- All equivalent:
sum(amount)
sum_amount
sum amount
sum of amount
```

This enables natural language queries:

```asql
from sales
  group by region (
    total revenue,          -- sum(revenue)
    average price,          -- avg(price)
    # as transactions       -- count(*)
  )
```

## When Conventions Fail

If your schema doesn't follow conventions:

### Non-Standard FK Names

```asql
-- accounts.primary_contact → contacts.id (non-standard)
from accounts
  &? contacts on accounts.primary_contact = contacts.id
```

### Custom Relationships

Define in metadata:

```yaml
# asql_schema.yml
relationships:
  - from: accounts.primary_contact
    to: contacts.id
    alias: primary_contact
```

### Non-Standard Timestamps

Specify in metadata:

```yaml
models:
  events:
    default_time: event_ts  # Not 'created_at'
```

## Best Practices

### Follow Standards

1. Use `created_at`, `updated_at` for timestamps
2. Use `{table}_id` for foreign keys
3. Use plural table names (or be consistent)
4. Follow dbt modeling conventions

### Be Explicit When Needed

```asql
-- Explicit is always clearer
from orders
  & users on orders.user_id = users.id
  group by month(orders.created_at) (...)
```

### Migration Path

If your schema is non-standard, consider:
1. Adding explicit ON clauses for now
2. Renaming columns in dbt transformations
3. Creating a clean semantic layer

## Summary

| Convention | ASQL Behavior |
|------------|---------------|
| `user_id` column | Enables `.user.` traversal |
| `created_at` column | Default time field |
| Plural table names | Auto-pluralization in FK inference |
| `sum_amount` | Interpreted as `sum(amount)` |
| Case variations | Matched case-insensitively |

**Philosophy**: Good modeling makes ASQL magical. Non-standard modeling requires explicit configuration.

## Next Steps

- **[Joins](../syntax/joins.md)** — FK inference in action
- **[Dates & Time](../syntax/dates.md)** — Timestamp conventions
- **[Guaranteed Groups](guaranteed-groups.md)** — Automatic gap-filling
