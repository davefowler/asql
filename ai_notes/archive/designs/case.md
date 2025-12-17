# Conditional Expressions with `when`

This document explores the `when` keyword for conditional expressions in ASQL, replacing SQL's verbose CASE statement with a cleaner, more natural syntax.

## Decision Summary

**Chosen syntax:** Use `when` as the primary keyword with `is`/`is not` for equality, `in` for multiple values, and `otherwise`/`else` for defaults.

```asql
# Equality - using 'is' (most readable)
when status
  is "active" then 1
  is "pending" then 0
  otherwise -1

# Inequality - using 'is not'
when status
  is not "deleted" then 1
  otherwise 0

# Multiple values - using 'in'
when status
  in ("active", "pending") then "open"
  in ("completed", "shipped") then "done"
  otherwise "unknown"

# Implied equality (most concise)
when status
  "active" then 1
  "pending" then 0
  else -1

# Comparisons - operator per line
when age
  < 4 then "infant"
  < 12 then "child"
  < 18 then "teen"
  otherwise "adult"
```

---

## Why `when` instead of `case`?

| Aspect | `case` | `when` |
|--------|--------|--------|
| **Readability** | "In the case of status..." | "When status is active..." |
| **SQL baggage** | Carries `CASE`/`WHEN` redundancy | Fresh start, single keyword |
| **Natural language** | Awkward | Reads like English |

**`when` reads beautifully:**
```asql
when status is "active" then 1     # "When status is active, then 1"
when age < 18 then "minor"         # "When age is less than 18, then minor"
```

---

## The `is` Operator for Equality

### Proposal: `is` as an alias for `=`

```asql
# These are equivalent:
when status is "active" then 1
when status = "active" then 1
when status "active" then 1        # Implied equality
```

### Why `is` works well

1. **Natural English:** "When status is active" reads perfectly
2. **Distinct from assignment:** Unlike `=`, no confusion with setting values
3. **SQL precedent:** SQL uses `IS` for `IS NULL`, `IS TRUE`, etc.
4. **Complements comparisons:** `is` for equality, `<`/`>` for comparisons

### Potential concerns

**SQL's `IS` is special-purpose:**
```sql
WHERE status IS NULL
WHERE flag IS TRUE
WHERE value IS DISTINCT FROM other
```

**Resolution:** In ASQL, `is` is simply equality. For null checking, use:
```asql
where status = null       # or
where status is null      # both work
where status is missing   # potential future keyword
```

### Recommendation

**Support all three forms:**

| Form | When to use | Example |
|------|-------------|---------|
| `is` | Maximum readability | `when status is "active" then 1` |
| `=` | Familiar to SQL users | `when status = "active" then 1` |
| (implied) | Maximum brevity | `when status "active" then 1` |

---

## Complete Syntax

### Simple conditional (with subject)

```asql
when <expr>
  [is | = | <op>] <value> then <result>
  [is | = | <op>] <value> then <result>
  ...
  else <default>
```

### Searched conditional (no subject)

```asql
when
  <condition> then <result>
  <condition> then <result>
  ...
  else <default>
```

---

## Real-World Examples

### Status mapping

```asql
from orders
  select
    order_id,
    when status
      is "pending" then "⏳ Waiting"
      is "shipped" then "📦 On the way"
      is "delivered" then "✅ Complete"
      otherwise "❓ Unknown"
    as status_display
```

### Age brackets

```asql
from users
  select
    name,
    when age
      < 4 then "infant"
      < 12 then "child"
      < 18 then "teen"
      < 65 then "adult"
      otherwise "senior"
    as age_group
```

### Grade calculation

```asql
from students
  select
    name,
    when score
      >= 90 then "A"
      >= 80 then "B"
      >= 70 then "C"
      >= 60 then "D"
      else "F"
    as grade
```

### Conditional aggregation

```asql
from orders
  group by customer_id
  select
    customer_id,
    count(*) as total_orders,
    sum(when status is "completed" then 1 otherwise 0) as completed_count,
    sum(when status in ("returned", "refunded") then amount otherwise 0) as returned_value,
    sum(when status is not "cancelled" then amount otherwise 0) as valid_revenue
```

### In WHERE clauses

```asql
from products
  where when category
    is "electronics" then price > 100
    is "clothing" then price > 50
    else price > 25
```

### Complex conditions (searched when)

```asql
from employees
  select
    name,
    when
      department = "engineering" and years > 5 then "senior_eng"
      department = "engineering" then "eng"
      department = "sales" and quota_met then "top_sales"
      otherwise "other"
    as role_category
```

### Nested conditionals

```asql
from employees
  select
    name,
    when department
      is "engineering" then when level
        is "junior" then 70000
        is "senior" then 120000
        otherwise 90000
      is "sales" then when level
        is "junior" then 50000
        is "senior" then 100000
        otherwise 70000
      otherwise 60000
    as base_salary
```

---

## Comparison to SQL

### Before (SQL)
```sql
SELECT
  name,
  CASE 
    WHEN age < 4 THEN 'infant'
    WHEN age < 12 THEN 'child'
    WHEN age < 18 THEN 'teen'
    ELSE 'adult'
  END AS age_group,
  CASE status
    WHEN 'active' THEN 1
    WHEN 'pending' THEN 0
    ELSE -1
  END AS status_code
FROM users
```

### After (ASQL)
```asql
from users
  select
    name,
    when age
      < 4 then "infant"
      < 12 then "child"
      < 18 then "teen"
      otherwise "adult"
    as age_group,
    when status
      is "active" then 1
      is "pending" then 0
      otherwise -1
    as status_code
```

**Improvements:**
- No repeated `WHEN` keyword
- `is` reads naturally for equality
- Cleaner indentation structure
- `when` is the single entry keyword

---

## Comparison to Other Languages

| Language | Syntax | ASQL equivalent |
|----------|--------|-----------------|
| **SQL** | `CASE WHEN x < 4 THEN 'a' END` | `when x < 4 then "a"` |
| **Kotlin** | `when (x) { in 0..4 -> "a" }` | `when x < 4 then "a"` |
| **Ruby** | `case x when 0..4 then "a"` | `when x < 4 then "a"` |
| **Python** | `match x: case _: ...` | `when x ... else ...` |

**ASQL's `when` is:**
- Cleaner than SQL (single keyword, no repetition)
- More SQL-familiar than arrows (`->`)
- Supports natural `is` equality

---

## Grammar

```
when_expr := 'when' [subject_expr] when_branch+ else_branch?

subject_expr := identifier | expression

when_branch := condition 'then' result

condition := 
  | 'is' value                    # Equality with 'is'
  | 'is' 'not' value              # Inequality with 'is not'
  | '=' value                     # Equality with '='
  | '!=' value                    # Inequality with '!='
  | value                         # Implied equality (string/number literal)
  | comparison_op value           # Comparison (<, >, <=, >=)
  | 'in' '(' value_list ')'       # Multiple value match
  | full_expression               # For searched when (no subject)

else_branch := ('else' | 'otherwise') result
```

---

## Implementation Notes

### Parser changes

1. Add `when` as a new expression starter
2. After `when`, look for optional subject expression
3. For each branch:
   - If `is` or `=`: equality comparison
   - If comparison operator: use that operator
   - If literal value: implied equality
   - If complex expression (searched when): full condition
4. `else` is optional default
5. No `end` keyword needed (use indentation/context)

### Compiler output

All forms compile to SQL CASE:

```asql
when status is "active" then 1 else 0
```
↓
```sql
CASE WHEN status = 'active' THEN 1 ELSE 0 END
```

```asql
when age < 18 then "minor" else "adult"
```
↓
```sql
CASE WHEN age < 18 THEN 'minor' ELSE 'adult' END
```

---

## Additional Features

### `is not` for inequality ✅

```asql
when status
  is not "deleted" then 1
  otherwise 0
```

Reads naturally: "when status is not deleted, then 1"

### `in` for multiple values ✅

```asql
when status
  in ("active", "pending") then "open"
  in ("completed", "shipped") then "done"
  otherwise "unknown"
```

Reads naturally: "when status is in active or pending, then open"

### `otherwise` as alias for `else` ✅

```asql
when status
  is "active" then 1
  otherwise 0
```

More natural English flow. Both `else` and `otherwise` are supported.

### Range support ❌ (not now)

```asql
# Future consideration - not implementing yet
when age
  in 0..4 then "infant"
  in 5..12 then "child"
```

Elegant but adds parsing complexity. May consider in the future.

---

## Summary

| Feature | Decision |
|---------|----------|
| Primary keyword | `when` (not `case`) |
| Equality | `is`, `=`, or implied |
| Inequality | `is not`, `!=` |
| Multiple values | `in ("a", "b", "c")` |
| Comparison operators | `<`, `>`, `<=`, `>=` per line |
| Default clause | `else` or `otherwise` |
| End keyword | Not required |
| Searched form | `when` with no subject, full conditions |
| Range support | Not yet (future consideration) |

The `when` + `is` combination gives ASQL a clean, readable conditional syntax that improves significantly on SQL's verbose CASE statements while remaining intuitive for SQL users.
