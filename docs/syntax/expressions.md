# Expressions & Operators

ASQL provides familiar operators for filtering, calculating, and transforming data.

## Comparison Operators

| Operator | Meaning | Example |
|----------|---------|---------|
| `=` or `==` | Equals | `where status = "active"` |
| `!=` | Not equals | `where status != "cancelled"` |
| `<` | Less than | `where age < 18` |
| `>` | Greater than | `where amount > 100` |
| `<=` | Less than or equal | `where age <= 65` |
| `>=` | Greater than or equal | `where amount >= 1000` |

Both `=` and `==` work for equality. Use whichever feels natural:

```asql
where status = "active"   -- SQL style
where status == "active"  -- programmer style
```

## Null Checks

Use `is` and `is not` for null checks:

```asql
where email is null
where phone is not null
```

## Membership (IN)

Check if a value is in a list:

```asql
where status in ("pending", "active", "shipped")
where country not in ("XX", "YY")
```

## String Matching Operators

ASQL provides intuitive string matching operators that are more readable than SQL's `LIKE` syntax.

### Case-Sensitive Operators

**Contains (substring match):**
```asql
where email contains "@gmail.com"
where name contains "John"
```

**Starts with (prefix match):**
```asql
where email starts with "admin"
where domain starts with "https://"
```

**Ends with (suffix match):**
```asql
where email ends with ".com"
where filename ends with ".pdf"
```

### Case-Insensitive Operators

For case-insensitive matching, use the `i` prefix:

```asql
where email icontains "gmail"        -- Case-insensitive contains
where name istarts with "john"        -- Case-insensitive starts with
where filename iends with ".pdf"     -- Case-insensitive ends with
```

### Pattern Matching

The `matches` operator supports SQL `LIKE` syntax with `%` and `_` wildcards:

```asql
where email matches "%@gmail.com"
where phone matches "555-___-____"
```

**Note**: `matches` uses LIKE syntax (with `%` and `_` wildcards), not regex.

### SQL Equivalents

| ASQL | SQL Equivalent |
|------|---------------|
| `contains "pattern"` | `LIKE '%pattern%'` |
| `icontains "pattern"` | `ILIKE '%pattern%'` (PostgreSQL) or `LOWER(column) LIKE LOWER('%pattern%')` |
| `starts with "pattern"` | `LIKE 'pattern%'` |
| `istarts with "pattern"` | `ILIKE 'pattern%'` or `LOWER(column) LIKE LOWER('pattern%')` |
| `ends with "pattern"` | `LIKE '%pattern'` |
| `iends with "pattern"` | `ILIKE '%pattern'` or `LOWER(column) LIKE LOWER('%pattern')` |
| `matches "%pattern%"` | `LIKE '%pattern%'` |

### Examples

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

## Logical Operators

| Operator | Meaning | Example |
|----------|---------|---------|
| `and` | Logical AND | `where a = 1 and b = 2` |
| `or` | Logical OR | `where a = 1 or a = 2` |
| `not` | Logical NOT | `where not is_deleted` |
| `&&` | Alternative AND | `where a = 1 && b = 2` |

Use parentheses for complex conditions:

```asql
where (status = "active" or status = "pending")
  and not is_deleted
```

## Arithmetic Operators

| Operator | Meaning | Example |
|----------|---------|---------|
| `+` | Addition | `price + tax` |
| `-` | Subtraction | `total - discount` |
| `*` | Multiplication | `quantity * price` |
| `/` | Division | `total / count` |
| `%` | Modulo | `id % 100` |

## Nullish Coalescing (`??`)

The `??` operator provides a default value for nulls:

```asql
-- If name is null, use "Unknown"
select name ?? "Unknown" as display_name

-- Chain multiple fallbacks
select primary_phone ?? mobile_phone ?? "N/A" as phone

-- Use in WHERE clauses
where (is_deleted ?? false) = false
```

This compiles to `COALESCE()` in SQL:

```sql
SELECT COALESCE(name, 'Unknown') AS display_name
```

## Type Casting (`::`)

Cast values to different types using PostgreSQL-style syntax:

```asql
select value::INTEGER as int_value
select timestamp::DATE as date_only
select amount::DECIMAL as decimal_amount
```

For safe casting that returns NULL on failure (instead of erroring):

```asql
select value::INTEGER? as safe_int    -- Returns NULL if cast fails
select value::INTEGER? ?? 0 as int_or_zero
```

## Conditional Expressions (`when`)

ASQL uses `when` for conditional logic, replacing SQL's verbose CASE statements:

### Simple Equality

```asql
select
  when status
    is "active" then "Active User"
    is "pending" then "Pending Approval"
    otherwise "Unknown"
  as status_label
```

### Comparison Operators

```asql
select
  when age
    < 13 then "child"
    < 20 then "teen"
    < 65 then "adult"
    otherwise "senior"
  as age_group
```

### Multiple Values

```asql
select
  when status
    in ("active", "pending") then "open"
    in ("completed", "shipped") then "done"
    otherwise "other"
  as category
```

### Complex Conditions (Searched When)

```asql
select
  when
    is_vip and amount > 1000 then "priority"
    amount > 500 then "standard"
    otherwise "basic"
  as service_tier
```

### In Aggregations

```asql
from orders
  group by customer_id (
    sum(when status is "completed" then 1 otherwise 0) as completed_count,
    sum(when status is "returned" then amount otherwise 0) as returned_total
  )
```

All `when` expressions compile to SQL `CASE WHEN ... THEN ... ELSE ... END`.

## String Literals

Strings can use single or double quotes:

```asql
where status = "active"
where status = 'active'
```

## Numeric Literals

Numbers work as expected:

```asql
where amount > 100
where price = 19.99
where discount = 0.15
```

## Comments

ASQL uses SQL-style comments:

```asql
-- This is a single-line comment
from users
  where is_active  -- inline comment
  
/* This is a
   multi-line comment */
```

Note: `#` is reserved for count syntax, not comments.

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
where (status = "active" or status = "pending") and not is_deleted
```

## Next Steps

- **[Aggregations](aggregations.md)** — GROUP BY and aggregate functions
- **[Dates & Time](dates.md)** — Date expressions and arithmetic
- **[Window Functions](window-functions.md)** — Advanced analytical functions
