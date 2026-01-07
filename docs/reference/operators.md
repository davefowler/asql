# Operators Reference

Complete reference of ASQL operators.

## Comparison Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `=` | Equals | `where status = "active"` |
| `==` | Equals (alternative) | `where status == "active"` |
| `!=` | Not equals | `where status != "cancelled"` |
| `<` | Less than | `where age < 18` |
| `>` | Greater than | `where amount > 100` |
| `<=` | Less than or equal | `where age <= 65` |
| `>=` | Greater than or equal | `where amount >= 1000` |

Both `=` and `==` work for equality. Use whichever feels natural.

---

## Null Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `is null` | Check if null | `where email is null` |
| `is not null` | Check if not null | `where phone is not null` |

---

## Membership Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `in` | Value in list | `where status in ("a", "b")` |
| `not in` | Value not in list | `where country not in ("XX")` |

```asql
where status in ("pending", "active", "shipped")
where category not in ("archived", "deleted")
```

---

## Logical Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `and` | Logical AND | `where a = 1 and b = 2` |
| `or` | Logical OR | `where a = 1 or a = 2` |
| `not` | Logical NOT | `where not is_deleted` |
| `&&` | Alternative AND | `where a = 1 && b = 2` |

Use parentheses for complex conditions:

```asql
where (status = "active" or status = "pending")
  and not is_deleted
```

---

## Arithmetic Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `+` | Addition | `price + tax` |
| `-` | Subtraction | `total - discount` |
| `*` | Multiplication | `quantity * price` |
| `/` | Division | `total / count` |
| `%` | Modulo | `id % 100` |

---

## Nullish Coalescing Operator

| Operator | Description | Example |
|----------|-------------|---------|
| `??` | Null coalesce | `value ?? 0` |

Returns the left operand if not null, otherwise the right operand.

```asql
name ?? "Unknown"                           -- Single fallback
primary_phone ?? mobile_phone ?? "N/A"      -- Chained
(amount ?? 0) > 100                         -- In conditions
```

Compiles to `COALESCE()` in SQL.

---

## Type Cast Operator

| Operator | Description | Example |
|----------|-------------|---------|
| `::` | Type cast | `value::INTEGER` |
| `::type?` | Safe cast | `value::INTEGER?` |

Standard cast (errors on failure):

```asql
value::INTEGER
timestamp::DATE
amount::DECIMAL(10,2)
```

Safe cast (returns NULL on failure):

```asql
value::INTEGER?                 -- NULL if cast fails
value::INTEGER? ?? 0            -- With default
```

Supported types:
- Numeric: `INT`, `INTEGER`, `BIGINT`, `FLOAT`, `DOUBLE`, `DECIMAL`, `NUMERIC`
- String: `VARCHAR`, `CHAR`, `TEXT`, `STRING`
- Date/Time: `DATE`, `TIMESTAMP`, `TIMESTAMP_NTZ`, `TIME`
- Boolean: `BOOLEAN`, `BOOL`

---

## Join Operators

| Operator | Join Type | SQL Equivalent |
|----------|-----------|----------------|
| `&` | Inner join | `INNER JOIN` |
| `&?` | Left join | `LEFT JOIN` |
| `?&` | Right join | `RIGHT JOIN` |
| `?&?` | Full outer join | `FULL OUTER JOIN` |
| `*` | Cross join | `CROSS JOIN` |

**Mnemonic**: `?` marks the side that might be NULL.

```asql
from orders & customers on orders.customer_id = customers.id     -- Inner
from orders &? customers on orders.customer_id = customers.id    -- Left
from orders ?& customers on orders.customer_id = customers.id    -- Right
from orders ?&? customers on orders.customer_id = customers.id   -- Full
from products * colors                                            -- Cross
```

---

## Order Operator

| Operator | Description | Example |
|----------|-------------|---------|
| `-column` | Descending order | `order by -created_at` |

The `-` prefix indicates descending order:

```asql
order by name               -- Ascending (A-Z)
order by -name              -- Descending (Z-A)
order by -amount, name      -- Amount DESC, then name ASC
```

---

## Count Shorthand

| Operator | Description | SQL Equivalent |
|----------|-------------|----------------|
| `#` | Count all rows | `COUNT(*)` |
| `# *` | Explicit row count | `COUNT(*)` |
| `#(col)` | Count column | `COUNT(col)` |
| `#(distinct col)` | Distinct count | `COUNT(DISTINCT col)` |
| `# users` | Distinct entity count | `COUNT(DISTINCT user_id)` |
| `# of users` | Natural language variant | `COUNT(DISTINCT user_id)` |

When followed by a table name, `#` infers the primary key using convention (table name → `{singular}_id`):

```asql
-- as total_rows                    -- COUNT(*)
-- users as unique_users            -- COUNT(DISTINCT user_id)
-- of orders as order_count         -- COUNT(DISTINCT order_id)
#(email) as emails_present         -- COUNT(email)
#(distinct customer_id) as unique  -- COUNT(DISTINCT customer_id)
```

---

## String Matching Operators

ASQL provides intuitive string matching operators that are more readable than SQL's `LIKE` syntax.

| Operator | Description | SQL Equivalent | Example |
|----------|-------------|----------------|---------|
| `contains "pattern"` | Case-sensitive substring match | `LIKE '%pattern%'` | `where email contains "@gmail.com"` |
| `icontains "pattern"` | Case-insensitive substring match | `ILIKE '%pattern%'` (PostgreSQL) or `LOWER(column) LIKE LOWER('%pattern%')` | `where email icontains "gmail"` |
| `starts with "pattern"` | Case-sensitive prefix match | `LIKE 'pattern%'` | `where name starts with "John"` |
| `istarts with "pattern"` | Case-insensitive prefix match | `ILIKE 'pattern%'` or `LOWER(column) LIKE LOWER('pattern%')` | `where domain istarts with "https://"` |
| `ends with "pattern"` | Case-sensitive suffix match | `LIKE '%pattern'` | `where filename ends with ".pdf"` |
| `iends with "pattern"` | Case-insensitive suffix match | `ILIKE '%pattern'` or `LOWER(column) LIKE LOWER('%pattern')` | `where email iends with ".com"` |
| `matches "pattern"` | LIKE pattern matching (with `%` and `_` wildcards) | `LIKE 'pattern'` | `where email matches "%@gmail.com"` |

### Examples

**Case-sensitive operators:**
```asql
where email contains "@gmail.com"
where name starts with "John"
where filename ends with ".pdf"
```

**Case-insensitive operators:**
```asql
where email icontains "gmail"
where name istarts with "john"
where filename iends with ".pdf"
```

**Pattern matching with wildcards:**
```asql
where email matches "%@gmail.com"
where phone matches "555-___-____"
```

**With logical operators:**
```asql
where email contains "@gmail.com" and status == "active"
where name starts with "John" or name starts with "Jane"
```

**With function calls:**
```asql
where upper(name) contains "JOHN"
where (email ?? "") contains "@"
```

**Note**: The `matches` operator uses LIKE syntax (with `%` and `_` wildcards), not regex. Case-insensitive operators use `ILIKE` for PostgreSQL and dialects that support it; otherwise they compile to `LOWER(column) LIKE LOWER(pattern)`.

---

## Date Operators

### Date Literal

| Syntax | Description | Example |
|--------|-------------|---------|
| `@YYYY-MM-DD` | Date literal | `@2024-01-15` |
| `@YYYY-MM-DDTHH:MM:SS` | Timestamp | `@2024-01-15T10:30:00` |

```asql
where order_date >= @2024-01-01
where created_at < @2024-12-31T23:59:59
```

### Date Arithmetic

| Syntax | Description | Example |
|--------|-------------|---------|
| `date + N unit` | Add interval | `order_date + 7 days` |
| `date - N unit` | Subtract interval | `created_at - 1 month` |

```asql
order_date + 7 days
created_at - 2 weeks
due_date + 1 month
```

### Relative Dates

| Syntax | Description | Example |
|--------|-------------|---------|
| `N unit ago` | Past relative | `7 days ago` |
| `N unit from now` | Future relative | `3 days from now` |

```asql
where created_at >= 30 days ago
where due_date <= 7 days from now
```

---

## Operator Precedence

From highest to lowest:

1. `::` (type cast)
2. `*`, `/`, `%` (multiplication, division, modulo)
3. `+`, `-` (addition, subtraction)
4. `=`, `!=`, `<`, `>`, `<=`, `>=` (comparison)
5. `??` (nullish coalescing)
6. `not` (logical NOT)
7. `and`, `&&` (logical AND)
8. `or` (logical OR)

Use parentheses when precedence is unclear:

```asql
where (amount ?? 0) > 100
where (a = 1 or b = 2) and not c = 3
```

---

## See Also

- **[Functions Reference](functions.md)** — All functions
- **[Expressions](../syntax/expressions.md)** — Using operators in expressions
- **[Joins](../syntax/joins.md)** — Join operator details
