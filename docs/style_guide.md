# ASQL Style Guide

This guide defines the preferred style for ASQL code examples and documentation. It covers both configurable "pretty" settings and preferred syntax patterns.

## Purpose

This style guide ensures consistency across ASQL documentation and examples. While ASQL accepts multiple valid syntaxes, this guide defines what we consider the **default/preferred style** for:
- Documentation examples
- Tutorials and quick starts
- Code samples

**Note**: Users can configure their own style preferences via `asql.config.yaml`. This guide reflects the default configuration.

---

## Part 1: Configurable Style Settings

These settings are controlled by `StyleConfig` in `asql/config.py` and affect output formatting (via `normalize()` and `reverse_compile()`).

### Equality Operator

**Preferred**: `=` (single equals)  
**Alternative**: `==` (double equals, also accepted)

```asql
-- Preferred
where status = "active"

-- Also works, but not preferred
where status == "active"
```

**Rationale**: `=` is standard SQL and more familiar to SQL users. `==` is accepted for those coming from programming languages.

---

### Count Notation

**Preferred**: `#` (hash shorthand)  
**Alternative**: `count(*)` (function form)

```asql
-- Preferred
group by country ( # as total )

-- Also works, but not preferred
group by country ( count(*) as total )
```

**Note**: `count(distinct col)` and `running_count(*)` must use function form (no shorthand exists).

---

### Null Coalescing

**Preferred**: `??` (operator)  
**Alternative**: `coalesce()` (function form)

```asql
-- Preferred
select name ?? "Unknown" as display_name
select price ?? sale_price ?? 0 as final_price

-- Also works, but not preferred
select coalesce(name, "Unknown") as display_name
```

**Rationale**: `??` is more concise and chains naturally. It's the default operator form.

---

### Descending Order

**Preferred**: `-col` (prefix minus)  
**Alternative**: `col DESC` (suffix, SQL style)

```asql
-- Preferred
order by -created_at
order by -revenue, name

-- Also works, but not preferred (SQL style)
order by created_at DESC
```

**In window functions**: Use `per` syntax with `-` prefix:
```asql
-- Preferred (per syntax)
per customer_id first by -order_date
per department rank by -salary

-- Avoid (SQL window function syntax)
row_number() over (partition by customer_id order by order_date DESC)
```

**Note**: The `per` syntax is ASQL's preferred way to express window operations and fully supports the `-` prefix for descending order.

---


### Type Casting

**Preferred**: `::` (double colon, PostgreSQL style)  
**Alternative**: `CAST(... AS ...)` (SQL standard)

```asql
-- Preferred
select created_at::DATE as date_day
select value::INTEGER as int_value

-- Also works, but not preferred
select CAST(created_at AS DATE) as date_day
```

---

### String Quotes

**Preferred**: `"` (double quotes)  
**Alternative**: `'` (single quotes)

```asql
-- Preferred
where status = "active"
where name = "John"

-- Also works, but not preferred
where status = 'active'
```

**Note**: SQL output examples may use single quotes (that's correct for SQL).

---


## Part 2: Preferred Syntax Patterns

These are syntax choices that aren't configurable settings, but represent preferred ASQL patterns over SQL alternatives.

### Conditional Expressions: `when` over `CASE WHEN`

**Preferred**: `when` expressions  
**Avoid**: `CASE WHEN ... THEN ... ELSE ... END`

```asql
-- Preferred
select
  when status
    is "active" then "Active User"
    is "pending" then "Pending"
    otherwise "Unknown"
  as status_label

-- Avoid (SQL style)
select
  CASE 
    WHEN status = 'active' THEN 'Active User'
    WHEN status = 'pending' THEN 'Pending'
    ELSE 'Unknown'
  END as status_label
```

**Rationale**: `when` is more concise, reads naturally, and is ASQL's primary conditional syntax.

---

### Equality in `when`: `is` over `=`

**Preferred**: `is` for equality in `when` expressions  
**Alternative**: `=` (also works)

```asql
-- Preferred (most readable)
when status
  is "active" then 1
  is "pending" then 0
  otherwise -1

-- Also works
when status
  = "active" then 1
  = "pending" then 0
  otherwise -1
```

**Rationale**: `is` reads more naturally: "when status is active" vs "when status equals active".

---

### Default Clause: `otherwise` over `else`

**Preferred**: `otherwise`  
**Alternative**: `else` (also accepted)

```asql
-- Preferred
when status
  is "active" then 1
  otherwise 0

-- Also works
when status
  is "active" then 1
  else 0
```

**Rationale**: `otherwise` is more explicit and reads better in natural language.

---

### Ternary Expressions: Not Available - Use `when`

**Note**: Ternary-style conditionals (like `condition ? value1 : value2` or `value1 if condition else value2`) are **not implemented** in ASQL.

**Use `when` instead:**
```asql
-- Preferred (ASQL way)
when amount = 0 then null otherwise amount

-- Not available (ternary syntax)
amount = 0 ? null : amount              -- ❌ Not supported
null if amount = 0 else amount          -- ❌ Not supported
```

**Rationale**: `when` expressions are ASQL's standard conditional syntax. They're more readable for complex conditions and support multiple branches. For simple two-branch cases, `when ... then ... otherwise ...` is still preferred.

---

### CTEs: `stash as` over `WITH ... AS`

**Preferred**: `stash as` (inline CTEs)  
**Alternative**: `WITH ... AS` (SQL style, also accepted)

```asql
-- Preferred (ASQL style)
from users
  where status = "active"
  stash as active_users

from active_users
  group by country ( # as total )

-- Also works (SQL style)
WITH active_users AS (
  SELECT * FROM users WHERE status = 'active'
)
SELECT country, COUNT(*) as total
FROM active_users
GROUP BY country
```

**Rationale**: `stash as` is more concise, keeps CTE definition close to usage, and fits ASQL's pipeline model.

---

### Pipeline Style: Indentation over Pipe Operator

**Preferred**: Indentation-based pipelines  
**Alternative**: Pipe operator `|` (also supported)

```asql
-- Preferred (indentation)
from users
  where status = "active"
  group by country ( # as total )
  order by -total

-- Also works (explicit pipes)
from users
| where status = "active"
| group by country ( # as total )
| order by -total
```

**Rationale**: Indentation is cleaner, more natural, and easier to write. Pipe operators are available for those who prefer explicit flow markers.

---

### String Matching: Natural operators over `LIKE`

**Preferred**: `contains`, `starts with`, `ends with`  
**Alternative**: `LIKE` with wildcards (SQL style, also accepted)

```asql
-- Preferred
where email contains "@gmail.com"
where name starts with "John"
where domain ends with ".com"

-- Also works (SQL style)
where email LIKE '%@gmail.com%'
where name LIKE 'John%'
where domain LIKE '%.com'
```

**Rationale**: Natural language operators are more readable and don't require wildcard syntax.

---

### Window Functions: `per` syntax over SQL `OVER()`

**Preferred**: `per` command syntax  
**Alternative**: SQL `OVER()` window functions (also accepted)

```asql
-- Preferred (per syntax)
from orders
  per customer_id first by -order_date

from employees
  per department rank by -salary

-- Avoid (SQL window function syntax)
from orders
  select *, row_number() over (partition by customer_id order by order_date DESC) as rn
  qualify rn = 1
```

**Rationale**: `per` syntax is more concise, readable, and fits ASQL's pipeline model. It fully supports the `-` prefix for descending order.

**Note**: For advanced window frame specifications (e.g., `ROWS BETWEEN ... PRECEDING`), SQL `OVER()` syntax may be necessary and is acceptable.

---

### Aggregations: Natural language over function calls (when appropriate)

**Preferred**: Natural language aggregates  
**Alternative**: Function calls (also work)

```asql
-- Preferred (natural language)
group by region ( sum of revenue as total_revenue )

-- Also works (function calls)
group by region ( sum(revenue) as total_revenue )
```

**Rationale**: Natural language reads better, though function calls are also clear and sometimes more explicit.

---

### Joins: Symbolic operators over SQL `JOIN`

**Preferred**: `&`, `&?`, `?&`, `*` operators  
**Alternative**: SQL `JOIN` syntax (also accepted)

```asql
-- Preferred (ASQL operators)
from opportunities &? owners
from orders & customers on orders.customer_id = customers.id

-- Also works (SQL style)
from opportunities LEFT JOIN owners ON ...
from orders INNER JOIN customers ON orders.customer_id = customers.id
```

**Rationale**: Symbolic operators (`&` for inner, `&?` for left, etc.) are more concise and visually clear. The `?` marks the nullable side.

---

### Foreign Key Traversal: Dot notation over explicit joins

**Preferred**: Dot notation (`.owner.name`)  
**Alternative**: Explicit joins (also work)

```asql
-- Preferred (dot notation)
from opportunities
  select amount, owner.name, owner.email

-- Also works (explicit join)
from opportunities &? owners on opportunities.owner_id = owners.id
  select amount, owners.name, owners.email
```

**Rationale**: Dot notation is more concise and leverages FK naming conventions automatically. It reads naturally: "opportunities.owner.name" means "the name of the owner of this opportunity".

---

### Date Literals: `@` prefix over string dates

**Preferred**: `@2025-01-10`  
**Alternative**: String dates `"2025-01-10"` (also work)

```asql
-- Preferred
where created_at >= @2025-01-10
where order_date between @2025-01-01 and @2025-01-31

-- Also works
where created_at >= "2025-01-10"
```

**Rationale**: The `@` prefix makes it clear this is a date literal, not a string, and avoids ambiguity.

---

### Window Functions: Simplified functions over SQL equivalents

**Preferred**: `prior()`, `next()`, `running_sum()`, `running_avg()`, `arg_max()`, `arg_min()`  
**Alternative**: SQL `LAG()`, `LEAD()`, `SUM() OVER()`, etc. (also accepted)

```asql
-- Preferred (ASQL functions)
select prior(revenue) as prev_revenue
select running_sum(amount) as cumulative
select arg_max(order_id, order_date) as latest_order_id

-- Also works (SQL window functions)
select lag(revenue, 1) over (order by date) as prev_revenue
select sum(amount) over (order by date rows unbounded preceding) as cumulative
```

**Rationale**: ASQL functions are more concise and readable. They handle common patterns without verbose `OVER()` clauses.

---

### Max/Min: `max()`/`min()` over `greatest()`/`least()`

**Preferred**: `max()`, `min()` for multiple values  
**Alternative**: `greatest()`, `least()` (SQL style, also accepted)

```asql
-- Preferred
select max(price1, price2, price3) as highest_price
select min(start_date, end_date) as earliest_date

-- Also works (SQL style)
select greatest(price1, price2, price3) as highest_price
select least(start_date, end_date) as earliest_date
```

**Rationale**: `max()` and `min()` are more intuitive and consistent with aggregation functions.

---

### Column Operators: `except`, `rename`, `replace` over explicit SELECT

**Preferred**: Column operators  
**Alternative**: Explicit SELECT lists (also work)

```asql
-- Preferred (column operators)
from users
  except password, ssn
  rename id as user_id
  replace name with upper(name)

-- Also works (explicit SELECT)
from users
  select id as user_id, upper(name) as name, email, ...
```

**Rationale**: Column operators are more concise and work well with `select *`. They're especially useful when you want most columns with a few modifications.

**Note**: `except` requires dialect support (BigQuery, Snowflake, DuckDB). For unsupported dialects, explicit SELECT is necessary.

---

### Date Arithmetic: Natural syntax over functions

**Preferred**: `date + 7 days`, `date - 1 month`  
**Alternative**: `DATEADD()`, `INTERVAL` (SQL style, also accepted)

```asql
-- Preferred
where created_at >= 7 days ago
where delivery_date = order_date + 3 days
select order_date + 1 month as next_month

-- Also works (SQL style)
where created_at >= CURRENT_DATE - INTERVAL '7 days'
where delivery_date = DATEADD(day, 3, order_date)
```

**Rationale**: Natural date arithmetic reads better: "7 days ago" vs "CURRENT_DATE - INTERVAL '7 days'". It's also dialect-portable.

---

## Part 3: Style Summary Table

| Category | Preferred | Alternative | Notes |
|----------|-----------|------------|-------|
| **Equality** | `=` | `==` | Standard SQL |
| **Count** | `#` | `count(*)` | Shorthand preferred |
| **Coalesce** | `??` | `coalesce()` | Operator form |
| **Descending** | `-col` | `col DESC` | Prefix minus |
| **Cast** | `::` | `CAST(...)` | PostgreSQL style |
| **Quotes** | `"` | `'` | Double quotes |
| **Conditionals** | `when` | `CASE WHEN` | ASQL syntax |
| **Equality in when** | `is` | `=` | More readable |
| **Default clause** | `otherwise` | `else` | More explicit |
| **CTEs** | `stash as` | `WITH ... AS` | Inline style |
| **Filtering** | `where` | `if` | Standard keyword |
| **Pipelines** | Indentation | `\|` | Cleaner |
| **String matching** | `contains` | `LIKE` | Natural language |
| **Window functions** | `per` syntax | `OVER()` | More concise |
| **Joins** | `&`, `&?` operators | `JOIN` | More concise |
| **FK traversal** | `.owner.name` | Explicit joins | Leverages conventions |
| **Date literals** | `@2025-01-10` | `"2025-01-10"` | Clearer type |
| **Window helpers** | `prior()`, `running_sum()` | `LAG()`, `SUM() OVER()` | More concise |
| **Max/Min** | `max()`, `min()` | `greatest()`, `least()` | More intuitive |
| **Column ops** | `except`, `rename` | Explicit SELECT | More concise |
| **Date arithmetic** | `+ 7 days` | `DATEADD()`, `INTERVAL` | More readable |

---

## When to Deviate

This style guide applies to **documentation and examples**. In practice:

1. **User preferences**: Users can configure their own style via `asql.config.yaml`
2. **Context matters**: Some examples intentionally show alternatives for educational purposes
3. **SQL interop**: When showing SQL equivalents or interop, SQL syntax is appropriate
4. **Coming-from guides**: Guides showing migrations from SQL/R/pandas may show both styles

---

## Implementation Notes

- Style settings are enforced via `normalize()` function
- Documentation examples should follow this guide
- Users can override via configuration
- All syntaxes are accepted on input (this guide is about output/preference)

---

## Related Documentation

- [Configuration System](../asql/config.py) - StyleConfig implementation
- [Language Specification](spec.md) - Full ASQL syntax reference
- [Quick Start](quick_start.md) - Getting started with ASQL
