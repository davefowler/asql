# Joins

ASQL uses symbolic operators for joins, making the join type visually clear at a glance.

## Join Operators

| Operator | Join Type | SQL Equivalent | Meaning |
|----------|-----------|----------------|---------|
| `&` | INNER JOIN | `INNER JOIN` | Both sides must match |
| `&?` | LEFT JOIN | `LEFT JOIN` | Right side is optional (can be NULL) |
| `?&` | RIGHT JOIN | `RIGHT JOIN` | Left side is optional (can be NULL) |
| `?&?` | FULL OUTER JOIN | `FULL OUTER JOIN` | Both sides are optional |
| `*` | CROSS JOIN | `CROSS JOIN` | Cartesian product |

**Mnemonic**: The `?` marks the side that might be NULL.

## Basic Join Syntax

### INNER JOIN

Only rows where both tables match:

```asql-play
from orders & customers on orders.customer_id = customers.id
  select orders.id, customers.name, orders.amount
```

### LEFT JOIN

All rows from the left table, with matching rows from the right (or NULL):

```asql-play
from customers &? orders on customers.id = orders.customer_id
  select customers.name, orders.amount
```

### RIGHT JOIN

All rows from the right table, with matching rows from the left (or NULL):

```asql-play
from orders ?& customers on orders.customer_id = customers.id
```

### FULL OUTER JOIN

All rows from both tables:

```asql-play
from orders ?&? customers on orders.customer_id = customers.id
```

### CROSS JOIN

Every combination of rows (cartesian product):

```asql-play
from products * colors
  select products.name, colors.name as color
```

## Table Aliasing

Use `as` to alias joined tables:

```asql-play
from orders &? users as customer on orders.customer_id = customer.id
  select orders.amount, customer.name, customer.email
```

Aliases are especially useful when joining the same table multiple times:

```asql
from orders
  &? users as customer on orders.customer_id = customer.id
  &? users as sales_rep on orders.sales_rep_id = sales_rep.id
  select
    orders.id,
    customer.name as customer_name,
    sales_rep.name as sales_rep_name
```

## Multiple Joins

Chain multiple joins in sequence:

```asql
from order_items
  & orders on order_items.order_id = orders.id
  & customers on orders.customer_id = customers.id
  & products on order_items.product_id = products.id
  select
    customers.name,
    products.name as product,
    order_items.quantity,
    order_items.price
```

## FK Dot Notation (Auto-Joins)

If your columns follow the `{name}_id` pattern, ASQL can automatically infer joins using dot notation.

### Basic Traversal

```asql
-- orders has user_id column → auto-joins to users
from orders
  select 
    orders.amount,
    orders.user.name,      -- Auto LEFT JOIN via user_id
    orders.user.email
```

Compiles to:

```sql
SELECT orders.amount, user_1.name, user_1.email
FROM orders
LEFT JOIN users AS user_1 ON orders.user_id = user_1.id
```

### How It Works

1. ASQL sees `orders.user.name`
2. Looks for `user_id` column in `orders`
3. Infers target table: tries `user` → `users` (pluralization)
4. Creates a LEFT JOIN automatically
5. Multiple references to same FK reuse the same join

### Chained Traversal

Navigate through multiple relationships:

```asql
from order_items
  select 
    order_items.quantity,
    order_items.order.total,           -- → orders
    order_items.order.customer.name    -- → orders → customers
```

### Multiple FKs to Same Table

When a table has multiple FKs to the same table, use the naming convention `<alias>_<table>_id`:

```asql
-- accounts has owner_user_id and manager_user_id
from accounts
  select 
    accounts.name,
    accounts.owner.name as owner_name,      -- via owner_user_id → users
    accounts.manager.name as manager_name   -- via manager_user_id → users
```

## Self-Joins (Hierarchies)

For hierarchical data like org charts:

```asql
-- Explicit self-join
from employees &? employees as manager on employees.manager_id = manager.id
  select employees.name, manager.name as manager_name

-- Or with dot notation (if manager_id exists)
from employees
  select 
    employees.name, 
    employees.manager.name as manager_name,
    employees.manager.manager.name as skip_level_manager
```

## Join Conditions

### Equality Conditions

Most joins use equality:

```asql
& customers on orders.customer_id = customers.id
```

### Multiple Conditions

Use `and` for multiple join conditions:

```asql
& products on 
    order_items.product_id = products.id 
    and order_items.variant_id = products.variant_id
```

### Non-Equality Conditions

Less common, but supported:

```asql
& price_history on 
    orders.product_id = price_history.product_id
    and orders.created_at >= price_history.valid_from
    and orders.created_at < price_history.valid_until
```

## FK Naming Conventions

ASQL uses naming conventions to auto-detect relationships:

| FK Column | Inferred Alias | Target Table | Dot Traversal |
|-----------|----------------|--------------|---------------|
| `user_id` | `user` | `users` | `.user.` |
| `account_id` | `account` | `accounts` | `.account.` |
| `owner_user_id` | `owner` | `users` | `.owner.` |
| `manager_user_id` | `manager` | `users` | `.manager.` |
| `parent_account_id` | `parent_account` | `accounts` | `.parent_account.` |

**Pattern**: `<alias>_<table>_id` → alias is `<alias>`, traverses to `<table>` (pluralized)

## Inference Priority

When resolving joins, ASQL uses this priority:

1. **Explicit `on` clause** — Always wins
2. **Model metadata** — If relationships are defined in schema files
3. **Naming convention** — `{name}_id` enables `.{name}.` traversal
4. **Error with suggestions** — If ambiguous or no match found

## Joins with Aggregations

Combine joins with GROUP BY:

```asql-play
from orders
  & customers on orders.customer_id = customers.id
  group by customers.country (
    sum(orders.amount) as revenue,
    count(distinct customers.id) as customer_count
  )
  order by -revenue
```

## Quick Reference

| SQL | ASQL Operator | Example |
|-----|---------------|---------|
| `INNER JOIN` | `&` | `& users on id = user_id` |
| `LEFT JOIN` | `&?` | `&? users on id = user_id` |
| `RIGHT JOIN` | `?&` | `?& users on id = user_id` |
| `FULL OUTER JOIN` | `?&?` | `?&? users on id = user_id` |
| `CROSS JOIN` | `*` | `* colors` |

| Feature | Syntax | Example |
|---------|--------|---------|
| Aliasing | `as` | `&? users as owner` |
| Explicit condition | `on` | `& users on orders.user_id = users.id` |
| FK traversal | `.fk.` | `orders.user.name` |

## Next Steps

- **[Aggregations](aggregations.md)** — GROUP BY with joins
- **[Window Functions](window-functions.md)** — Advanced analytical queries
- **[Examples](../examples.md)** — Real-world join patterns
