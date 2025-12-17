# ASQL: Analytic SQL — Language Specification

**Version:** 0.1  
**Status:** Draft  
**Last Updated:** November 16, 2025

---

<div style="background: #fff3cd; border: 2px solid #ffc107; border-radius: 8px; padding: 20px; margin: 20px 0; font-size: 16px; line-height: 1.6;">


⚠️ <b>This language specification and implementation are a heavy work-in-progress (WIP).</b>

This project is in active development and contains many known issues, bugs, and incomplete features.  Much of the specification is just brainstorming and prototyping.  Do not rely on this for anything yet. 


</div>

---

## 1. Overview

ASQL (Analytic SQL, pronounced "Ask-el") is a modern, pipeline-based query language designed specifically for analytical workloads. It transpiles cleanly to standard SQL (via SQLGlot) and aims to be more human-readable, less verbose, and better suited for analytics than traditional SQL.

**Key Philosophy**: ASQL should feel like asking a natural question, not writing cryptic code. It reads like natural language while maintaining the power and precision of SQL.

**⚠️ Note**: This specification is an extensive list of brainstormed improvements to SQL. Not all features should necessarily be implemented. It's meant to be open-minded and aggressive to start, with features refined based on real-world usage and feedback.

### Design Philosophy

- **Natural language feel**: Queries read like questions you'd ask a colleague
- **Convention over configuration**: ASQL assumes good modeling standards and makes smart inferences based on conventions. If you follow standards (like dbt's naming conventions), ASQL works seamlessly. Everything is configurable, but we have strong opinions.
- **Pipeline semantics**: Every query is a sequence of tabular transformations
- **Familiarity over novelty**: Keeps SQL's nouns and functions, simplifies verbs and ordering
- **Standards-based inference**: Smart behaviors are convention-driven, not magical. We assume standardized naming (e.g., `created_at` for timestamps), proper foreign keys, and good modeling practices.
- **Readable and composable**: Short, expressive, indentation-based pipelines
- **Case-safe**: Works seamlessly with camelCase, snake_case, PascalCase, and any naming convention
- **Portable**: Transpiles to ANSI SQL or specific dialects via SQLGlot
- **Inspectable**: Every ASQL query can show its generated SQL, plan, and metrics

---

## 2. Core Syntax

### 2.1 Basic Query Structure

Every ASQL query starts with a data source. Transformations can be chained using indentation (preferred) or optional pipeline operators (`|`):

**Indentation-based (preferred, cleaner):**
```asql
from users
  where status = "active"
  group by country ( # as total_users )
  order by -total_users
```

**Pipeline operator (optional, explicit):**
```asql
from users
| where status = "active"
| group by country ( # as total_users )
| order by -total_users
```

Both styles are equivalent. Choose based on preference or context.

**Pros of indentation-based:**
- ✅ Cleaner, more natural reading flow
- ✅ Less visual clutter
- ✅ Feels more like natural language
- ✅ Easier to write (no need to type `|`)

**Pros of pipeline operator (`|`):**
- ✅ Makes data flow explicit and visible
- ✅ Familiar to users of PRQL, PowerShell, Unix pipes
- ✅ Easier to parse visually in complex queries
- ✅ Can help with debugging (see exactly where each transformation happens)

**Recommendation**: Support both. Indentation-based is the default and recommended style, but the pipe operator is available for those who prefer explicit flow markers or are coming from other pipeline-based languages.

### 2.2 Entry Point: `from`

The `from` clause specifies the starting table:

```asql
from users
from sales
from opportunities
```

**Smart inference**: When referencing columns, the table can be inferred:
- `Users.name` → explicit table reference
- `User.name` → smart plural handling (inferred as `Users.name`)

---

## 3. Pipeline Operators

Operators are applied in logical order using the pipe (`|`) symbol:

| Operator | Meaning | SQL Equivalent | Example |
|----------|---------|----------------|---------|
| `where` | Filter rows | `WHERE` | `where status = "active"` |
| `group by` | Group and aggregate | `GROUP BY` | `group by country ( # as total_users )` |
| `&`, `&?`, `?&`, `*` | Join datasets | `JOIN` | `& owners on owner_id = owners.id` |
| `select` / `project` | Choose final columns | `SELECT` | `select country, users, avg_age` |
| `order by` | Sort rows | `ORDER BY` | `order by -users` (descending) |
| `limit` | Limit rows | `LIMIT` | `limit 10` |
| `set` | Define variable/fragment (CTE) | `WITH ... AS` | `set active = from users \| where is_active` |

---

## 4. Expressions & Operators

### 4.1 Comparison Operators

- `=` - equals (also accepts `==`)
- `!=` - not equals
- `<`, `>`, `<=`, `>=` - comparison
- `is`, `is not` - null checks
- `in`, `not in` - membership

**Note**: Both `=` and `==` work for equality. `=` is preferred as it's standard SQL, but `==` is accepted for those coming from programming languages.

### 4.2 Logical Operators

- `and`, `or`, `not` - logical operations
- `&&` - alternative syntax for `and`

**Note**: Use the `or` keyword for logical OR (not `||`). The `??` operator is used for COALESCE (see Section 4.6).

### 4.3 Arithmetic Operators

- `+`, `-`, `*`, `/` - standard arithmetic
- `%` - modulo

### 4.4 String & Date Literals

- Strings: `"active"`, `'inactive'`
- Dates: `@2025-01-10`, `@2025-11-10`
- Numbers: `42`, `3.14`

### 4.5 String Matching (Planned)

ASQL will provide intuitive string matching operators that are more readable than SQL's `LIKE` syntax. The design is inspired by the best practices from modern query languages and libraries:

**Research & Inspiration:**
- **KQL (Kusto)**: `contains`, `startswith`, `endswith`, `matches regex` - very intuitive
- **Python pandas**: `.str.contains()`, `.str.startswith()`, `.str.endswith()` - clear and explicit
- **JavaScript**: `.includes()`, `.startsWith()`, `.endsWith()` - simple and readable
- **dplyr (R)**: `str_detect()`, `str_starts()`, `str_ends()` - functional but verbose
- **SQL**: `LIKE '%pattern%'` - cryptic, requires wildcards, not intuitive

**Proposed ASQL Syntax:**

```asql
# Contains (substring match)
from users where email contains "@gmail.com"
from users where name contains "John"

# Starts with
from users where email starts with "admin"
from users where domain starts with "https://"

# Ends with
from users where email ends with ".com"
from users where filename ends with ".pdf"

# Case-insensitive variants (optional)
from users where email contains "GMAIL" ignore case
from users where name starts with "john" ignore case

# Regex matching (advanced)
from users where email matches "^[a-z]+@[a-z]+\\.com$"
from users where phone matches "^\d{3}-\d{3}-\d{4}$"
```

**Design Principles:**
1. **Natural language**: Reads like English - "email contains gmail" is clearer than "email LIKE '%gmail%'"
2. **No wildcards required**: `contains` is more intuitive than `LIKE '%pattern%'`
3. **Explicit operations**: `starts with` and `ends with` are clearer than `LIKE 'pattern%'` and `LIKE '%pattern'`
4. **Case handling**: Default behavior TBD (case-sensitive or case-insensitive), with explicit `ignore case` option
5. **Regex support**: Available but secondary - most users don't need regex for common string matching

**Comparison with SQL:**

| ASQL | SQL Equivalent | Notes |
|------|----------------|-------|
| `contains "pattern"` | `LIKE '%pattern%'` | More intuitive, no wildcards |
| `starts with "pattern"` | `LIKE 'pattern%'` | Clearer intent |
| `ends with "pattern"` | `LIKE '%pattern'` | Clearer intent |
| `matches "regex"` | `~ 'regex'` or `REGEXP` | Explicit regex matching |
| `contains "PATTERN" ignore case` | `ILIKE '%pattern%'` (PostgreSQL) | Explicit case handling |

**Alternative Syntax Considerations:**

1. **Method-style** (like Python/JS):
   ```asql
   from users where email.contains("@gmail.com")
   from users where name.starts_with("John")
   ```
   - Pros: Familiar to programmers, explicit
   - Cons: Less natural language feel, requires dots

2. **Function-style**:
   ```asql
   from users where contains(email, "@gmail.com")
   from users where starts_with(name, "John")
   ```
   - Pros: Functional, clear
   - Cons: Less readable, more verbose

3. **Natural language** (recommended):
   ```asql
   from users where email contains "@gmail.com"
   from users where name starts with "John"
   ```
   - Pros: Most readable, natural language feel
   - Cons: Requires keyword parsing

**Recommendation**: Use natural language syntax (`contains`, `starts with`, `ends with`) as it aligns with ASQL's philosophy of reading like natural language. This makes queries accessible to non-technical users while remaining precise.

**Implementation Priority**: Medium - String matching is common but can be worked around with `LIKE` in the interim. Should be implemented after arithmetic operators and before advanced features.

### 4.6 COALESCE Operator (`??`)

ASQL uses the `??` operator for COALESCE (nullish coalescing), providing a cleaner syntax than the function call.

**Syntax:**
```asql
# Function form
coalesce(column, default_value)

# Operator form (preferred)
column ?? default_value

# Chained (multiple fallbacks)
column ?? fallback1 ?? fallback2 ?? "default"
```

**Examples:**
```asql
# Handle NULL values
from users select name ?? "Unknown" as display_name

# Multiple fallbacks
from products select price ?? sale_price ?? 0 as final_price

# In WHERE clauses
from users where not (is_deleted ?? false)

# With boolean logic
from orders where (status ?? "pending") = "completed"
```

**Why `??` for COALESCE?**
- JavaScript uses `??` for nullish coalescing (not `||`)
- `||` in SQL is string concatenation in most dialects - avoids confusion
- More concise than `coalesce()` function calls
- Chains naturally: `a ?? b ?? c` reads as "a, or if null b, or if null c"

**Precedence:**
The `??` operator has higher precedence than logical operators (`and`, `or`, `not`) but lower than comparison operators (`=`, `!=`, etc.). Use parentheses for clarity in complex expressions.

### 4.7 Conditional Expressions (`when`)

ASQL uses `when` for conditional expressions, replacing SQL's verbose `CASE` statement with cleaner, more natural syntax.

**Basic syntax with `is` for equality:**
```asql
from users
  select
    name,
    when status
      is "active" then "Active User"
      is "pending" then "Pending"
      otherwise "Unknown"
    as status_label
```

**Implied equality (most concise):**
```asql
when status
  "active" then 1
  "pending" then 0
  otherwise -1
```

**Comparison operators:**
```asql
when age
  < 4 then "infant"
  < 12 then "child"
  < 18 then "teen"
  otherwise "adult"
```

**Inequality with `is not`:**
```asql
when status
  is not "deleted" then 1
  otherwise 0
```

**Multiple values with `in`:**
```asql
when status
  in ("active", "pending") then "open"
  in ("completed", "shipped") then "done"
  otherwise "unknown"
```

**Searched when (complex conditions):**
```asql
when
  age < 18 and country = "US" then "US Minor"
  age < 18 then "Minor"
  otherwise "Adult"
```

**Complex business logic:**
```asql
from opportunity
  select
    when
      is_won then "Won"
      not is_won and is_closed then "Lost"
      not is_closed and lower(forecast_category) in ("pipeline", "forecast", "bestcase") then "Pipeline"
      otherwise "Other"
    as status
```

**In aggregations:**
```asql
from orders
  group by customer_id
  select
    customer_id,
    sum(when status is "completed" then 1 otherwise 0) as completed_count,
    sum(when status is "returned" then amount otherwise 0) as returned_value
```

**Operators supported:**
- `is` / `=` - equality
- `is not` / `!=` - inequality
- `<`, `>`, `<=`, `>=` - comparisons
- `in (values)` - multiple value match

**Default clause:** Both `else` and `otherwise` are supported (they are aliases).

All forms compile to standard SQL `CASE WHEN ... THEN ... ELSE ... END`.

### 4.8 Type Casting (`::`)

ASQL uses PostgreSQL-style double colon (`::`) syntax for type casting, which is more concise and readable than SQL's `CAST(... AS ...)` syntax.

**Syntax:**
```asql
expression::type_name
```

**Examples:**
```asql
# Cast to timestamp
from fields
  select _fivetran_synced::TIMESTAMP as _fivetran_synced

# Cast to date
from events
  select created_at::DATE as date_day

# Cast to integer
from products
  select price::INT as price_int

# Cast to string
from users
  select id::VARCHAR as user_id_str

# Cast in WHERE clauses
from orders
  where created_at::DATE == "2024-01-01"
```

**Precedence:**
The `::` operator has high precedence (same as function calls), so it binds tightly:
- `amount::INT * 2` → `(amount::INT) * 2` ✅
- `sum(amount)::FLOAT` → `(sum(amount))::FLOAT` ✅

**Reverse Translation:**
When converting SQL to ASQL, `CAST(... AS ...)` expressions are automatically converted to `::` syntax:
- SQL: `CAST(_fivetran_synced AS TIMESTAMP)` → ASQL: `_fivetran_synced::TIMESTAMP`
- SQL: `CAST(created_at AS DATE)` → ASQL: `created_at::DATE`

**Supported Types:**
All standard SQL types are supported, including:
- Numeric: `INT`, `INTEGER`, `BIGINT`, `FLOAT`, `DOUBLE`, `DECIMAL`, `NUMERIC`
- String: `VARCHAR`, `CHAR`, `TEXT`, `STRING`
- Date/Time: `DATE`, `TIMESTAMP`, `TIMESTAMP_NTZ`, `TIME`
- Boolean: `BOOLEAN`, `BOOL`
- And dialect-specific types (e.g., Snowflake's `NUMBER`, BigQuery's `INT64`)

### 4.9 Comments

ASQL uses SQL-standard comment syntax:

- Single-line: `-- this is a comment`
- Multi-line: `/* this is a multi-line comment */`

**Note**: We use `--` instead of `#` because:
- It's the SQL standard (familiar to SQL users)
- `#` is reserved for count aggregation syntax (see Section 5.2)
- Better compatibility with SQL tooling and editors

### 4.10 String Functions

ASQL provides clean string manipulation functions.

#### String Concatenation

Use `concat()` for joining strings:

```asql
from users
  select concat(first_name, " ", last_name) as full_name
```

For concatenating values across rows in a GROUP BY, use `string_agg()`:

```asql
from orders
  group by customer_id (
    string_agg(product_name, ", ") as products
  )
```

**Note**: `string_agg()` is the standard name used in PostgreSQL, SQL Server, and DuckDB. ASQL compiles to the appropriate dialect (e.g., `GROUP_CONCAT` for MySQL, `LISTAGG` for Snowflake).

#### Substring with Slice Syntax

ASQL supports Python-style slice syntax for extracting substrings:

```asql
from users
  select 
    email[1:5] as email_prefix,        -- characters 1-5
    email[1:] as from_start,           -- from position 1 to end
    email[-5:] as last_five,           -- last 5 characters
    email[3:8] as middle_part          -- characters 3-8
```

**Slice syntax:**
- `string[start:end]` - characters from start to end (1-indexed)
- `string[start:]` - from start to end of string
- `string[:end]` - from beginning to end position
- `string[-n:]` - last n characters

The traditional `substring()` function is also supported:
```asql
substring(email, 1, 5) as email_prefix
```

#### String Replacement

Use `replace()` for string substitution:

```asql
from products
  select replace(description, "old", "new") as updated_desc
```

#### String Functions Reference

| Function | Description | Example |
|----------|-------------|---------|
| `concat(a, b, ...)` | Concatenate strings | `concat(first, " ", last)` |
| `string_agg(col, sep)` | Aggregate strings with separator | `string_agg(name, ", ")` |
| `string[start:end]` | Slice substring | `email[1:5]` |
| `substring(str, pos, len)` | Extract substring | `substring(email, 1, 5)` |
| `replace(str, old, new)` | Replace occurrences | `replace(text, "a", "b")` |
| `lower(str)` | Convert to lowercase | `lower(name)` |
| `upper(str)` | Convert to uppercase | `upper(code)` |
| `trim(str)` | Remove whitespace | `trim(input)` |
| `length(str)` | String length | `length(name)` |

### 4.11 Comparison Functions

#### Multi-Value Min/Max

Use `min()` and `max()` with multiple arguments to find the smallest or largest value:

```asql
from products
  select 
    max(price1, price2, price3) as highest_price,
    min(start_date, end_date) as earliest_date
```

**SQL alternatives**: `greatest()` and `least()` are also supported for familiarity with SQL:

```asql
from products
  select greatest(price1, price2, price3) as highest_price
```

**Recommendation**: Use `max()` and `min()` as they're more intuitive and consistent with aggregation functions.

**Note**: This is configurable - if you prefer SQL-style `greatest()`/`least()` as the default, this can be adjusted in ASQL settings.

### 4.12 NULL Handling

#### NULLIF Alternative

Instead of SQL's `NULLIF()` function, use the `when` conditional expression:

```asql
from transactions
  select 
    when amount == 0 then null else amount as safe_amount
```

This is clearer than `nullif(amount, 0)` and consistent with ASQL's conditional syntax.

#### Ternary-Style Conditionals (Future Consideration)

ASQL may add support for concise ternary expressions in the future:

```asql
-- Potential future syntax (not yet decided)
amount == 0 ? null : amount           -- JS-style
null if amount == 0 else amount       -- Python-style
```

For now, use the `when` syntax which is clear and readable:
```asql
when amount == 0 then null else amount
```

### 4.13 Function Shorthand (Underscore/Space Principle)

ASQL provides flexible syntax for function calls where **underscores and spaces are interchangeable**. This makes queries more natural to write and read.

#### The Core Principle

All of these are equivalent and produce the same result:

```asql
-- Function call styles (all equivalent):
sum(amount)           -- explicit function call
sum_amount            -- underscore shorthand
sum amount            -- space shorthand
sum of amount         -- "of" style (natural language)
```

All produce a column named `sum_amount`.

#### Applies to All Functions

This principle applies universally to:

**Aggregations:**
```asql
sum_revenue           -- → sum(revenue)
avg_price             -- → avg(price)
count_orders          -- → count(orders)
max_amount            -- → max(amount)
```

**Date functions:**
```asql
year_created_at       -- → year(created_at)
month_signup_date     -- → month(signup_date)
day_of_week_order_date -- → day_of_week(order_date)
```

**Multi-word functions:**
```asql
day_of_week(created_at)     -- explicit
day_of_week_created_at      -- underscore shorthand
day of week created_at      -- space shorthand (most natural)
```

#### Auto-Generated Column Names

When using function shorthand, column names are auto-generated:

```asql
from sales
  select sum_amount, avg_price, month_created_at
  
-- Equivalent to:
from sales
  select 
    sum(amount) as sum_amount,
    avg(price) as avg_price,
    month(created_at) as month_created_at
```

#### Where This Applies

| Context | Applies? | Example |
|---------|----------|---------|
| SELECT expressions | ✅ Yes | `select sum_amount` |
| GROUP BY | ✅ Yes | `group by month_created_at` |
| ORDER BY | ✅ Yes | `order by -sum_amount` |
| WHERE conditions | ✅ Yes | `where days_since_created_at > 30` |
| Column names (literals) | ❌ No | `created_at` stays as-is |
| Table names | ❌ No | `user_accounts` stays as-is |
| String literals | ❌ No | `"hello_world"` stays as-is |

#### Ambiguity Resolution

If an actual column name matches a potential function pattern, the **column takes precedence**:

```asql
-- If table has actual column "sum_revenue":
select sum_revenue    -- Uses the column, not sum(revenue)

-- To force function interpretation, use explicit syntax:
select sum(revenue) as sum_revenue
```

#### Extended Patterns

Some patterns expand to more complex expressions:

```asql
-- Time since patterns
days_since_created_at     -- → days(now() - created_at)
months_since_signup_date  -- → months(now() - signup_date)

-- Time until patterns  
days_until_due_date       -- → days(due_date - now())
```

---

## 5. Aggregations

### 5.1 Standard Aggregates

Aggregates are used within `group by` blocks. ASQL uses `as` syntax (like SQL) for aliasing:

```asql
from sales
  group by region (
    sum(amount) as revenue,
    count(distinct customer_id) as customers,
    avg(amount) as avg_order,
    max(amount) as max_order,
    min(amount) as min_order
  )
```

**Default return behavior**: If no `select` clause is specified, the query returns all grouping columns followed by all aggregations in the order they're listed. `select *` has the same behavior.

### 5.2 Count Aggregation (`#`)

The `#` symbol is a shortcut for `count(*)`. Multiple syntaxes are supported:

```asql
# Basic count syntaxes
#                    -- count(*)
#(Users)             -- count(*) from Users
# of Users           -- count(*) from Users (natural language)
Users.#              -- count(*) from Users
Total # of Users     -- count(*) from Users (with label)

# In select statements
from Users
  select #, birthday
  -- Returns: count(*) as #, birthday

# Count with conditions
#(Users.birthday)    -- count(Users.birthday)
# of Users.birthday  -- count(Users.birthday)
```

**Syntax flexibility**: The `of` keyword is treated as filler and ignored. These are all equivalent:
- `# id` → `count(id)`
- `#(id)` → `count(id)`
- `# of id` → `count(id)`

**Table name substitution**: When a table name is used instead of a column name, it's replaced with `*`:
- `# Users` → `count(*)`
- `#(Users)` → `count(*)`
- `# of Users` → `count(*)`

### 5.3 Sum & Total Aggregation

`sum` and `total` are interchangeable (both compile to `SUM()`):

```asql
# Standard syntax
sum(amount) as revenue
total(amount) as revenue

# Shorthand syntax (see Section 4.13)
sum_amount              -- → sum(amount) as sum_amount
total_revenue           -- → sum(revenue) as total_revenue

# Natural language syntax
Sum of amount as revenue
Total of amount as revenue
Sum amount as revenue
Total amount as revenue

# In group by
from sales
  group by region (
    sum_amount,         -- shorthand
    total amount as revenue
  )
```

### 5.4 Average Aggregation

Multiple natural language forms for averages:

```asql
# Standard syntax
avg(Users.age) as avg_age
average(Users.age) as avg_age

# Natural language syntax
Avg Users.age as avg_age
Average of Users.age as avg_age
Average Users.age as avg_age
Avg of Users.age as avg_age

# With expressions
Avg(Users.age + 3) as adjusted_age
Average of Users.age + 3 as adjusted_age
```

### 5.5 Natural Language Philosophy

ASQL encourages natural language expressions. The `of` keyword can replace parentheses, making queries read like questions:

```asql
# Instead of: count(*) from Users where country = 'US'
# of Users where country == "US"

# Instead of: sum(amount) from sales
# Sum of amount from sales

# Instead of: avg(age) from users group by country
# Average of Users.age by country
```

This makes ASQL queries feel like asking questions rather than writing code.

### 5.6 Contextual Aggregates

When grouping, aggregates are computed per group:

```asql
from users
  group by country (
    count() as total_users,
    avg(age) as avg_age
  )
```

### 5.7 Window Functions

ASQL provides intuitive syntax for common window function patterns, making operations like deduplication, ranking, and running totals much cleaner than SQL.

#### The `per` Command (Pipeline Window Operations)

The `per` command creates a window context for operations on partitions:

**Syntax:**
```
per <partition_cols> <operation> by <order_cols> [as <alias>]
```

Or without partition (whole table):
```
<operation> by <order_cols> [as <alias>]
```

**Available Operations:**

| Operation | What it does | Default alias | Row count |
|-----------|--------------|---------------|-----------|
| `first` | Keep first row per partition | (no column) | ↓ Reduces |
| `last` | Keep last row per partition | (no column) | ↓ Reduces |
| `number` | Add row number column | `row_num` | Same |
| `rank` | Add rank column | `rank` | Same |
| `dense rank` | Add dense rank column | `dense_rank` | Same |

**Examples:**
```asql
# DEDUPLICATION: Keep most recent order per customer
from orders
  per customer_id first by -order_date

# ADD ROW NUMBER: Number orders per customer (most recent = 1)
from orders
  per customer_id number by -order_date
# Result: adds `row_num` column

# ADD RANK: Rank employees by salary within department
from employees
  per department rank by -salary
# Result: adds `rank` column

# NO PARTITION: Number all rows
from events
  number by -timestamp
# Result: adds `row_num` to all rows, ordered by timestamp desc
```

**Reading the syntax naturally:**
- `per customer_id first by -order_date` → "Per customer, get the first by order date descending"
- `per department rank by -salary` → "Per department, rank by salary descending"

#### first() / last() in GROUP BY

Use `first()` and `last()` as aggregates within GROUP BY to extract values:

```asql
from orders
  group by customer_id (
    first(order_id order by -order_date) as latest_order,
    last(order_id order by order_date) as first_order,
    count(*) as total_orders
  )
```

**Comparison: `per ... first` vs `first()` in GROUP BY:**
- Use `per ... first` when you want the **whole row** (deduplication)
- Use `first()` in GROUP BY when you want **specific aggregated values**

#### arg_max() / arg_min() (ClickHouse-inspired)

Get the value of one column where another column is max/min:

```asql
from orders
  group by customer_id (
    arg_max(order_id, order_date) as latest_order_id,
    arg_min(order_id, order_date) as earliest_order_id
  )
```

#### prior() / next() (Simplified LAG/LEAD)

```asql
from monthly_sales
  order by month
  select
    month,
    revenue,
    prior(revenue) as prior_revenue,       # LAG(revenue, 1)
    prior(revenue, 3) as three_months_ago,
    next(revenue) as next_revenue          # LEAD(revenue, 1)
```

#### Running Aggregates (Cumulative)

```asql
from transactions
  order by date
  select
    date,
    amount,
    running_sum(amount) as cumulative_amount,
    running_avg(amount) as avg_to_date,
    running_count(*) as transaction_number
```

**Shorthand:** `running amount` is equivalent to `running_sum(amount)`.

#### Rolling Window Aggregates

Moving window with specified size:

```asql
from daily_sales
  order by date
  select
    date,
    revenue,
    rolling_avg(revenue, 7) as seven_day_avg,
    rolling_sum(revenue, 30) as monthly_total
```

#### Window Functions Quick Reference

| Intent | ASQL Syntax |
|--------|-------------|
| Most recent row per group | `per group_col first by -date` |
| Oldest row per group | `per group_col first by date` |
| Add row numbers per group | `per group_col number by -date` |
| Add rank per group | `per group_col rank by -value` |
| Add dense rank per group | `per group_col dense rank by -value` |
| Get column value at max | `arg_max(col, sort_col)` |
| Previous row value | `prior(col)` |
| Next row value | `next(col)` |
| Cumulative sum | `running_sum(col)` |
| Cumulative average | `running_avg(col)` |
| 7-day moving average | `rolling_avg(col, 7)` |
| First value in group | `first(col order by ...)` |

---

## 6. Grouping

### 6.1 Basic Grouping

```asql
from users
  group by country ( # as total_users )
```

**Note**: The parentheses syntax for grouping aggregates is inspired by PRQL, which uses a similar block structure for clarity and readability.

**Alternative names**: While `group by` is standard SQL and recommended, alternatives that may be more intuitive to newcomers include:
- `rollup by` - emphasizes aggregation
- `bucket by` - emphasizes grouping into buckets
- `aggregate by` - explicit about aggregation

These are syntactic alternatives - all compile to SQL `GROUP BY`. `group by` remains the primary syntax for familiarity and SQL compatibility.

### 6.2 Multiple Grouping Columns

```asql
from sales
  group by region, month (
    sum(amount) as revenue,
    count() as orders
  )
```

### 6.3 Natural Language Grouping

For very simple queries, natural language syntax can be used:

```asql
# of Users by country
Sum of revenue by region, month
Avg Users.age by country
```

**Note**: These are syntactic shortcuts. For complex queries, the explicit `group by` syntax with parentheses (Section 6.1) is recommended for clarity and consistency.

---

## 7. Joins & Relationships

ASQL uses symbolic operators for joins, making the join type visually clear. The `&` represents the join point, and `?` marks optional (nullable) sides.

### 7.1 Join Operators

| Operator | Join Type | SQL Equivalent | Meaning |
|----------|-----------|----------------|---------|
| `&` | INNER JOIN | `INNER JOIN` | Both sides must match |
| `&?` | LEFT JOIN | `LEFT JOIN` | Right side is optional (can be NULL) |
| `?&` | RIGHT JOIN | `RIGHT JOIN` | Left side is optional (can be NULL) |
| `?&?` | FULL OUTER JOIN | `FULL OUTER JOIN` | Both sides are optional |
| `*` | CROSS JOIN | `CROSS JOIN` | Cartesian product |

**Mnemonic**: "The `?` marks the side that might be NULL"

### 7.2 Basic Join Syntax

```asql
-- INNER JOIN: only matching rows
from opportunities & owners
  select opportunities.amount, owners.name

-- LEFT JOIN: all opportunities, owners may be NULL
from opportunities &? owners
  select opportunities.amount, owners.name

-- RIGHT JOIN: all owners, opportunities may be NULL  
from opportunities ?& owners
  select opportunities.amount, owners.name

-- FULL OUTER JOIN: all rows from both sides
from opportunities ?&? owners
  select opportunities.amount, owners.name

-- CROSS JOIN: every combination
from opportunities * owners
  select opportunities.amount, owners.name
```

### 7.3 Table Aliasing

Use `as` to alias joined tables:

```asql
from opportunities &? users as owner
  select opportunities.amount, owner.name, owner.email
```

### 7.4 Explicit Join Conditions

When automatic FK inference isn't desired or possible, specify the join condition with `on`:

```asql
from opportunities &? owners on opportunities.owner_id == owners.id
  select opportunities.amount, owners.name

-- With alias
from opportunities &? users as owner on opportunities.owner_id == owner.id
  select opportunities.amount, owner.name
```

### 7.5 Dot Notation for FK Traversal

**This works WITHOUT a model file** - ASQL recognizes FK naming conventions.

If a column follows the pattern `{name}_id`, you can traverse it using `.{name}.`:

```asql
-- opportunities has owner_id column (FK to users table)
from opportunities
  select 
    opportunities.amount,
    opportunities.owner.name,      -- Auto-joins via owner_id
    opportunities.owner.email      -- Same join, different column
```

Compiles to:
```sql
SELECT 
  opportunities.amount,
  owner_1.name,
  owner_1.email
FROM opportunities
LEFT JOIN users AS owner_1 ON opportunities.owner_id = owner_1.id
```

**Key points:**
- The FK column `owner_id` enables `.owner.` traversal
- ASQL finds the target table by checking: `owners` table, then `users` table (singularization)
- Dot traversal defaults to LEFT JOIN (the FK might be NULL)
- Multiple references to same FK reuse the same join (no duplicate joins)

### 7.6 Chained FK Traversal

Navigate through multiple relationships:

```asql
-- order_items.order_id → orders.user_id → users
from order_items
  select 
    order_items.quantity,
    order_items.order.total,           -- → orders
    order_items.order.user.name        -- → orders → users
```

### 7.7 Multiple FKs to Same Table

When a table has multiple FKs to the same table, use the `<alias>_<table>_id` convention:

```asql
-- accounts has owner_user_id, manager_user_id, support_rep_user_id all → users
from accounts
  select 
    accounts.owner.name as owner_name,           -- via owner_user_id
    accounts.manager.name as manager_name,       -- via manager_user_id  
    accounts.support_rep.name as support_name    -- via support_rep_user_id
```

The FK naming pattern `<alias>_user_id` enables `.alias.` dot traversal to the `users` table.

Or with explicit joins:
```asql
from accounts 
  &? users as owner on accounts.owner_user_id == owner.id
  &? users as manager on accounts.manager_user_id == manager.id
  select owner.name, manager.name
```

### 7.8 Convention-Based Inference

ASQL uses naming conventions to auto-detect joins:

**FK Naming Patterns:**

| FK Column | Alias | Target Table | Dot Traversal |
|-----------|-------|--------------|---------------|
| `user_id` | `user` | `users` | `.user.` |
| `account_id` | `account` | `accounts` | `.account.` |
| `owner_user_id` | `owner` | `users` | `.owner.` |
| `manager_user_id` | `manager` | `users` | `.manager.` |
| `parent_account_id` | `parent_account` | `accounts` | `.parent_account.` |

**Pattern**: `<alias>_<table_name>_id` → alias is `<alias>`, traverses to `<table_name>` table

**Inference priority:**
1. **Explicit `on` clause** - Always wins
2. **Model metadata** - If relationships are explicitly defined in model files
3. **Naming convention inference** - `{name}_id` enables `.{name}.` traversal
4. **Single FK check** - If only one FK exists between tables, auto-join
5. **Error with suggestions** - If ambiguous or no match found

### 7.9 Self-Joins (Hierarchies)

```asql
-- Employees and their managers (explicit)
from employees &? employees as manager on employees.manager_id == manager.id
  select employees.name, manager.name as manager_name

-- Or with dot notation (uses manager_id FK automatically)
from employees
  select 
    employees.name, 
    employees.manager.name as manager_name,
    employees.manager.manager.name as skip_level_manager
```

### 7.10 Optional Model Metadata

While not required, you can define relationships explicitly for non-standard FK names:

```yaml
# asql_schema.yml
relationships:
  - from: opportunities.owner_id
    to: users.id
    alias: owner
    
  - from: accounts.primary_contact
    to: contacts.id  # Non-standard name, needs explicit mapping
```

**dbt Compatibility**: ASQL can read dbt's `schema.yml` files to infer relationships from `relationships` tests.

### 7.11 Join Quick Reference

| SQL | ASQL Operator | ASQL with ON clause |
|-----|---------------|---------------------|
| `INNER JOIN` | `&` | `& users on ...` |
| `LEFT JOIN` | `&?` | `&? users on ...` |
| `RIGHT JOIN` | `?&` | `?& users on ...` |
| `FULL OUTER JOIN` | `?&?` | `?&? users on ...` |
| `CROSS JOIN` | `*` | `* users` |

| Feature | Syntax | Example |
|---------|--------|---------|
| Aliasing | `as` | `&? users as owner` |
| Explicit condition | `on` | `&? users on orders.user_id == users.id` |
| FK traversal | `.fk.` | `orders.user.name` (via `user_id`) |

**Key principles:**
1. **`?` marks the optional/nullable side**: Easy to remember
2. **FK inference via naming convention**: `{name}_id` enables `.{name}.` traversal
3. **No model file required**: Convention-based inference works out of the box
4. **Explicit always works**: Full `on` clause syntax never fails
5. **Smart deduplication**: Dot traversal reuses explicit joins when FK matches

---

## 8. Dates & Time

Dates are one of the most important features in analytics. ASQL provides a clean, intuitive, and portable date syntax that compiles to the right dialect-specific SQL.

### 8.1 Date Literals

ASQL uses the `@` prefix for date literals:

```asql
from users
  where signup_date >= @2024-01-01

from orders
  where order_date between @2024-01-01 and @2024-12-31
```

The `@` prefix distinguishes dates from strings and is clean and unambiguous.

### 8.2 Time Truncation Functions

ASQL provides simple time truncation functions for grouping and time series:

```asql
year(created_at)      -- Truncate to year start: 2025-01-01
month(created_at)     -- Truncate to month start: 2025-01-01
week(created_at)      -- Truncate to week start: 2025-01-06
day(created_at)       -- Truncate to day: 2025-01-15
hour(created_at)      -- Truncate to hour: 2025-01-15 14:00:00
quarter(created_at)   -- Truncate to quarter start
```

**Natural language alternatives** (all equivalent):
```asql
year(created_at)      -- function style
year created_at       -- space style
year_created_at       -- underscore style (ASQL interprets as year(created_at))
year of created_at    -- "of" style
```

These compile to `DATE_TRUNC()` and are ideal for time series grouping.

### 8.3 Date Part Extraction

Extracting date parts (day of week, week of year, etc.) uses natural language phrases:

```asql
day of week created_at        -- 1-7 (which day of the week)
day of month created_at       -- 1-31 (which day of the month)
day of year created_at        -- 1-366 (which day of the year)
week of year created_at       -- 1-52 (which week of the year)
month of year created_at      -- 1-12 (which month)
quarter of year created_at    -- 1-4 (which quarter)
```

**Function equivalents** (same behavior):
```asql
day_of_week(created_at)
week_of_year(created_at)
month_of_year(created_at)
```

**Example usage:**
```asql
-- Weekend orders
from orders
  where day of week order_date in (6, 7)

-- Sales by day of week
from sales
  group by day of week sale_date (
    sum(amount) as revenue
  )
```

**Distinction from truncation:**
- `month(created_at)` → `2025-01-01` (truncated date, for time series)
- `month of year created_at` → `1` (integer, for "all Januaries")

### 8.4 Date Arithmetic

Adding or subtracting from dates uses clean inline syntax:

```asql
order_date + 7 days
order_date - 1 month
order_date + 2 weeks
created_at + 24 hours
updated_at - 90 minutes
```

**Singular/plural both work:**
```asql
order_date + 1 day           -- singular
order_date + 7 days          -- plural
```

**Compiles to** (dialect-specific):
```sql
-- PostgreSQL
order_date + INTERVAL '7 days'

-- SQL Server  
DATEADD(day, 7, order_date)

-- MySQL
DATE_ADD(order_date, INTERVAL 7 DAY)
```

### 8.5 Date Difference

Getting days/months/years between dates:

```asql
days(end_date - start_date)      -- Returns integer days
months(end_date - start_date)    -- Returns integer months
years(end_date - start_date)     -- Returns integer years
hours(end_date - start_date)     -- Returns integer hours
weeks(end_date - start_date)     -- Returns integer weeks
```

**Alternative syntax:**
```asql
days_between(start_date, end_date)
months_between(start_date, end_date)
```

**Example:**
```asql
from orders
  select 
    days(shipped_date - order_date) as fulfillment_days,
    months(now() - customer_since) as customer_tenure_months
```

### 8.6 Relative Dates (`ago` and `from now`)

**Past dates with `ago`:**
```asql
from users
  where last_login >= 7 days ago

from orders
  where created_at >= 30 days ago
  where created_at >= 1 month ago
  where created_at >= 3 hours ago
```

**Future dates with `from now`:**
```asql
from orders
  where estimated_delivery <= 3 days from now

from reminders
  where remind_at <= 1 hour from now
```

**Compiles to:**
```sql
-- PostgreSQL
WHERE last_login >= CURRENT_DATE - INTERVAL '7 days'
WHERE estimated_delivery <= CURRENT_TIMESTAMP + INTERVAL '3 days'
```

### 8.7 Time Since/Until Patterns

**`*_since_*` pattern** - time elapsed since a date:
```asql
days_since_created_at        -- → days(now() - created_at)
weeks_since_signup_date      -- → weeks(now() - signup_date)
months_since_last_login      -- → months(now() - last_login)
years_since_birth_date       -- → years(now() - birth_date)
```

**`*_until_*` pattern** - time remaining until a future date:
```asql
days_until_due_date          -- → days(due_date - now())
weeks_until_deadline         -- → weeks(deadline - now())
months_until_renewal         -- → months(renewal_date - now())
```

**Example usage:**
```asql
from users
  select
    name,
    days_since_last_login,
    months_since_signup_date,
    years_since_birth_date as age

from tasks
  where days_until_due_date < 7
  -- Tasks due within a week
```

### 8.8 Week Start Configuration

**Default**: ISO 8601 standard (Monday = day 1)

```asql
week(created_at)              -- Default: ISO (Monday start)
week_monday(created_at)       -- Explicit Monday start
week_sunday(created_at)       -- US-style Sunday start

day of week created_at        -- Default: 1 = Monday, 7 = Sunday
```

**Rationale**: ISO 8601 is the international standard. Most analytics/business contexts expect Monday start.

### 8.9 Timezone Handling

Use cast-like syntax with `::` for timezone conversion:

```asql
-- Short timezone codes
created_at::PST
created_at::UTC
created_at::EST

-- Full IANA timezone names (quoted)
created_at::"America/Los_Angeles"
created_at::"Europe/London"

-- Chained with other operations
month(created_at::PST)
created_at::UTC + 7 days
```

**Compiles to** (PostgreSQL):
```sql
created_at AT TIME ZONE 'PST'
created_at AT TIME ZONE 'America/Los_Angeles'
```

### 8.10 Time Bucketing (Grouping)

Time bucketing is simply grouping by a time function:

```asql
from users
  group by month(created_at) ( # as signups )

from sales
  group by week(sale_date) ( sum(amount) as revenue )
```

### 8.11 Date Functions Quick Reference

| Operation | ASQL Syntax | Example |
|-----------|-------------|---------|
| Date literal | `@YYYY-MM-DD` | `@2025-01-15` |
| Truncation | `unit(col)` | `month(created_at)` |
| Extraction | `unit of period col` | `day of week created_at` |
| Arithmetic | `date + N unit` | `order_date + 7 days` |
| Difference | `unit(date1 - date2)` | `days(end - start)` |
| Relative past | `N unit ago` | `7 days ago` |
| Relative future | `N unit from now` | `3 days from now` |
| Time since | `unit_since_col` | `days_since_created_at` |
| Time until | `unit_until_col` | `days_until_due_date` |
| Timezone | `col::TZ` | `created_at::PST` |
| Week (Sunday) | `week_sunday(col)` | `week_sunday(created_at)` |

### 8.12 Default Time Fields & Conventions

ASQL follows a "convention over configuration" philosophy:

1. **Standard naming**: Timestamp columns named `created_at`, `updated_at` enable automatic inference
2. **Smart defaults**: If a table has `created_at`, it's assumed to be the primary time field
3. **Configurable**: Override defaults in model metadata when needed

```yaml
models:
  users:
    default_time: signup_date  # Override convention
```

**Best practice**: Follow dbt-style modeling standards, and ASQL's date features "just work."

---

## 9. Filtering

### 9.1 Basic Filters

ASQL uses `where` instead of `filter` because it's more intuitive - "where" clearly means "filter in" (keep rows that match), whereas "filter" is ambiguous (filter in or filter out?).

```asql
from users
  where status = "active"
  where age >= 18
```

### 9.2 Multiple Conditions

Multiple conditions can be written in several ways:

**Separate where clauses:**
```asql
from opportunities
  where status = "open"
  where owner.is_active
  where org_type != "Non Profit"
```

**Using `and` on same line:**
```asql
from opportunities
  where status = "open" and owner.is_active and org_type != "Non Profit"
```

**Using `&` operator:**
```asql
from opportunities
  where status = "open" & owner.is_active & org_type != "Non Profit"
```

**Tabbed indentation (multi-line):**
```asql
from opportunities
  where status = "open"
    and owner.is_active
    and org_type != "Non Profit"
```

**Using `or` (with parentheses for grouping):**
```asql
from opportunities
  where (status == "open" or status == "pending")
    and owner.is_active
```

All of these compile to SQL `WHERE` clauses. The pipeline approach makes complex conditions easier to read than nested SQL.

### 9.3 Alternative Syntax: `if`

```asql
from opportunities
  group by owner.name ( total as sum(amount) )
  if status == "open"
  if owner.is_active
```

**Note**: `if` is syntactic sugar for `where` and can be used interchangeably. It makes queries read more naturally: "total pipeline by owner name if status is open".

---

## 10. Ordering

### 10.1 Basic Ordering

The `order by` clause sorts rows by one or more columns:

```asql
from users order by name
from users order by -total_users
```

**Descending order**: Use the `-` prefix for descending order:
- `order by name` → ascending (A-Z)
- `order by -name` → descending (Z-A)

### 10.2 Ordering by Function Calls

You can order by function calls using the `-` prefix for descending order:

```asql
from users order by month(created_at)
from users order by -updated_at
from events order by -year(created_at), name
```

**Examples:**
- `order by updated_at` → Sort by updated_at ascending
- `order by -updated_at` → Sort by updated_at descending (newest first)
- `order by -year(created_at), name` → Sort by year descending, then name ascending

This syntax makes it easy to order by computed values like date functions.

### 10.3 Multiple Order Columns

Multiple order columns are separated by commas:

```asql
from users order by -total_users, name
from sales order by -revenue, region, -date
```

The `-` prefix applies only to the column immediately following it.

---

## 11. Variables & CTEs

### 11.1 Simple Variables & CTEs

Variables in ASQL create CTEs (Common Table Expressions). The syntax is designed to make CTEs easier and less necessary:

**Using `set` (creates CTE):**
```asql
set active_users = from users
  where is_active

from active_users
  group by country ( # as total_users )
```

**Why `set`?**
- **SQL familiarity**: SQL uses `SET` in various contexts (SET variables, SET operations)
- **Clear intent**: "Set this variable to this query" is intuitive
- **CTE mapping**: Maps naturally to SQL's `WITH ... AS` (Common Table Expression)
- **Not `let`**: `let` comes from functional programming (Lisp, ML, Haskell) and doesn't fit SQL's imperative style

**Alternatives considered**: `let`, `const`, `var`, `define`, `with`
- `let` - Too functional programming style, not SQL-like
- `const`/`var` - JavaScript-specific, not SQL
- `define` - Too generic
- `with` - Conflicts with SQL's `WITH` keyword usage
- `set` ✅ - Most SQL-like and clear

**Major benefit: Less need for CTEs**: Because ASQL uses pipelines, you often don't need CTEs at all. Instead of breaking into a CTE, you can just add a comment marking a logical stopping point:

```asql
from users
  where is_active
  -- cleaned users by country
  group by country ( # as total_users )
  order by -total_users
```

The comment marks where you might have created a CTE in SQL, but the pipeline continues naturally. CTEs are still available when you need to reuse a subquery multiple times.

### 11.2 Stashing CTEs in Pipelines (`stash as`)

Instead of defining CTEs at the top level with `set`, you can stash intermediate pipeline results directly within a pipeline using `stash as`. This keeps CTEs close to where they're used and makes chaining clearer. The key benefit is that you end with the name and use it right after, so your eyes don't have to jump around.

**Basic usage (at the end):**
```asql
from users
  where status = "active"
  group by country ( # as total_users )
  select country, total_users
  stash as revenue

from revenue
  order by -total_users
```

**Using `stash as` in the middle of a pipeline:**
```asql
from users
  where status = "active"
  stash as active_users
  group by country ( # as total_users )
  order by -total_users
```

When `stash as` appears in the middle, it stashes everything before it as a CTE, then continues with the pipeline.

**Multiple queries reusing a stashed CTE:**
```asql
from sales
  where year(date) == 2025
  group by region ( sum(amount) as revenue )
  stash as use_this_later
  order by -revenue
  limit 10;

from use_this_later
  where revenue > 1000
  select region, revenue
```

**Benefits of `stash as`:**
- ✅ **Proximity**: CTEs are defined where they're used, often right before they're referenced
- ✅ **Clear chaining**: You can see the data flow clearly at the end of pipelines
- ✅ **Reusability**: Multiple queries can reference the same stashed CTE
- ✅ **Natural flow**: Fits naturally into the pipeline syntax
- ✅ **Better readability**: You end with the name and use it right after, so your eyes don't have to jump around

**When to use `stash as` vs `set`:**
- Use `stash as` when you want to stash an intermediate result within a pipeline (can be in the middle or at the end)
- Use `set` when you want to define a CTE at the top level before any queries
- Both compile to SQL `WITH ... AS` CTEs

### 11.3 Nested Variables

```asql
set base = from users
  where plan == "premium"

set by_country = from base
  group by country ( # as total_users )

from by_country
  order by -total_users
```

---

## 12. Functions

### 12.1 User-Defined Scalar Functions

Functions in ASQL are similar to dbt macros or PostgreSQL functions, but simpler and more integrated:

**Basic function:**
```asql
func age(user) = years(now() - user.birthday)

from users
  select age(user) as user_age
  group by country ( avg_age as average of user_age )
```

**Function taking table name (works on any table with matching column):**
```asql
func age(table) = years(now() - table.birthday)

# Works on any table with a 'birthday' column
from users
  select age(users) as user_age

from employees
  select age(employees) as employee_age
```

**Another example - days since created:**
```asql
func days_since_created(table) = days(now() - table.created_at)

# Works on any table with created_at
from users
  select days_since_created(users) as days_active
```

**Typing**: Functions are not typed - ASQL infers types from usage. This keeps the syntax simple and natural.

**dbt comparison**:
- **dbt macros**: More powerful but require Jinja templating, harder to read
- **dbt semantic models**: More structured but require YAML configuration
- **ASQL functions**: Simple, readable, drop-in replacements that feel like built-in functions

**PostgreSQL comparison**:
- PostgreSQL functions require `CREATE FUNCTION` statements, separate from queries
- ASQL functions are defined inline and feel like part of the query language

**Example with natural language:**
```asql
func age(user) = years(now() - user.birthday)

# Natural language usage
avg age of user by country
# Reads like: "average age of user, grouped by country"
```

**Note**: Functions can be used in SELECT expressions to compute values:
```asql
from users
  select age(user) as user_age
  group by country ( avg(user_age) as avg_age )
```

### 12.2 User-Defined Table Functions

Table functions transform entire tables. These are implemented as drop-in replacements (macros) that expand inline:

```asql
func top_n(table, n, key) =
  table
    order by -{key}
    limit n

from sales
  top_n(10, amount)
```

**Implementation**: Table functions are expanded inline during compilation - they don't create actual database functions. The function body is substituted where the function is called, then the whole query is compiled to SQL.

### 12.3 Built-in Functions

Standard SQL functions are available:

- `count()`, `sum()`, `avg()`, `min()`, `max()`
- `distinct()`
- `coalesce()` or `??` operator (JavaScript-style nullish coalescing)
- `date_format()`, `year()`, `month()`, etc.
- `years_between()`, `days_between()`, etc.

### 12.4 Function Examples

```asql
func year(table) = DATE_FORMAT('%Y', table._mainDate)

from users
| year(created_at)
```

---

## 13. Data Transformation Operators

ASQL provides built-in operators that replace common dbt macro patterns, making queries cleaner and more portable.

### 13.1 Column Set Operators

These operators manipulate column sets without needing to list every column.

#### `except` - Exclude Columns

Exclude specific columns from the result:

```asql
# Exclude sensitive columns
from users
  except email, phone, ssn

# After a join, exclude from specific tables
from users
  & orders on users.id = orders.user_id
  except users.password_hash, orders.internal_notes
```

**Compiles to**: Explicit `SELECT` with all columns except those listed (uses schema metadata).

#### `rename` - Rename Columns

Rename columns inline:

```asql
from users
  rename id as user_id, name as user_name

# Rename with table prefix after join
from users
  & orders on users.id = orders.user_id
  rename users.id as user_id
```

**Compiles to**: `SELECT id AS user_id, name AS user_name, ...`

#### `prefix` - Prefix Column Names

Add a prefix to column names (especially useful after joins):

```asql
from users
  prefix user_

# Prefix specific table's columns
from users
  & orders on users.id = orders.user_id
  prefix orders.* with order_
```

**Compiles to**: `SELECT id AS user_id, name AS user_name, ...`

#### Combining Column Operators

```asql
from users
  & orders on users.id = orders.user_id
  except users.password_hash, orders.internal_notes
  rename users.id as user_id
  prefix orders.* with order_
```

### 13.2 Deduplicate

Remove duplicate rows based on specified columns, keeping one row per group:

```asql
# Keep most recent per user/event combination
from events
  deduplicate by user_id, event_type
  order by -created_at

# Keep first occurrence
from events
  deduplicate by user_id, event_type
  order by created_at
```

The `order by` determines which row to keep when duplicates exist.

**Compiles to**:
```sql
-- On warehouses with QUALIFY:
SELECT * FROM events
QUALIFY ROW_NUMBER() OVER (PARTITION BY user_id, event_type ORDER BY created_at DESC) = 1

-- Fallback:
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id, event_type ORDER BY created_at DESC) AS rn
  FROM events
)
SELECT * FROM ranked WHERE rn = 1
```

### 13.3 Pivot / Unpivot

#### `pivot` - Rows to Columns

Transform row values into columns:

```asql
# Basic pivot
from sales
  pivot amount by category

# Pivot with aggregation
from sales
  pivot sum(amount) by category

# Dynamic pivot (values from subquery)
from sales
  pivot amount by category from (select distinct category from products)
```

**Example use case - denormalizing custom fields:**

Many SaaS platforms store custom fields in EAV (Entity-Attribute-Value) tables:

```asql
# Jira custom fields table:
# | issue_id | field_name   | field_value |
# | PROJ-123 | priority     | High        |
# | PROJ-123 | sprint       | Sprint 5    |

from issue_custom_fields
  pivot field_value by field_name

# Result:
# | issue_id | priority | sprint   |
# | PROJ-123 | High     | Sprint 5 |
```

#### `unpivot` - Columns to Rows

Transform columns into rows:

```asql
from monthly_metrics
  unpivot jan, feb, mar, apr into month, value
```

**Compiles to**: Native `PIVOT`/`UNPIVOT` where supported (Snowflake, BigQuery), `CASE`/`WHEN` + `GROUP BY` fallback elsewhere.

### 13.4 Fill (Gap Filling)

Fill gaps in time series data after grouping:

```asql
# Auto-detect range from data, NULL for missing values
from orders
  group by month(created_at) as month (
    sum(amount) as revenue
  )
  fill month

# Specify default values for filled rows
from orders
  group by month(created_at) as month (
    sum(amount) as revenue
  )
  fill month with {revenue: 0}

# Explicit range bounds (both inclusive)
from orders
  group by month(created_at) as month (
    sum(amount) as revenue
  )
  fill month start '2024-01-01' stop '2024-12-01'

# Combined: explicit range with defaults
from orders
  group by month(created_at) as month (
    sum(amount) as revenue
  )
  fill month with {revenue: 0} start '2024-01-01' stop today()
```

**Range detection**: By default, `fill` auto-detects the range using `MIN()`/`MAX()` of the grouped column. Use `start`/`stop` for explicit bounds (e.g., always show full year).

**Why `start`/`stop`?** We use these instead of `from`/`to` to avoid confusion with the `from` clause.

### 13.5 Date Spine / Series

Generate sequences as table sources:

```asql
# Date spine - one row per day/week/month
from date_spine(start = '2020-01-01', end = today(), grain = day)

# Numeric series
from series(1, 100)

# Join with actual data to fill gaps
from date_spine(start = '2024-01-01', end = '2024-12-31', grain = month) as dates
  left join (
    from orders
      group by month(created_at) as month (
        sum(amount) as revenue
      )
  ) as sales on dates.date = sales.month
```

**Compilation**: Uses native `generate_series()` where available, numbers table or recursive CTE fallback elsewhere.

### 13.6 Union with Schema Alignment

Union tables with automatic column alignment:

```asql
# Union multiple tables, aligning columns
from union(users_2022, users_2023, users_2024)

# With options
from union(users_2022, users_2023, fill_missing = null)
```

**Compilation**: Reads schemas, produces aligned `SELECT` lists with missing columns filled as `NULL`, then `UNION ALL`.

### 13.7 Surrogate Keys

Generate consistent surrogate keys:

```asql
select key(user_id, order_id) as order_key
```

**Semantics**:
- Stable hashing algorithm across runs
- Consistent NULL handling (NULLs hash consistently)
- Type normalization before hashing

**Compiles to**: Warehouse-appropriate hash function with delimiter injection and null handling.

### 13.8 Safe Casting

ASQL supports safe type casting that returns `NULL` on failure instead of erroring:

```asql
# Strict cast - errors on failure (default, SQL-compatible)
select value::integer

# Safe cast - returns NULL on failure (? suffix)
select value::integer?

# Safe cast with default (using ?? coalescing)
select value::integer? ?? 0
```

**Why this matters**: Real-world data is messy. Columns may contain `"N/A"`, empty strings, or invalid formats. Safe casting handles this gracefully:

```asql
# Form submission with user input
from form_submissions
  select 
    response_id,
    age_input::integer? ?? 0 as age,     -- "N/A" becomes 0
    amount_input::decimal? as amount     -- Invalid becomes NULL
```

**Compilation**:
- `value::integer` → `CAST(value AS INTEGER)`
- `value::integer?` → `TRY_CAST(value AS INTEGER)` (or `SAFE_CAST` on BigQuery)
- `value::integer? ?? 0` → `COALESCE(TRY_CAST(value AS INTEGER), 0)`

### 13.9 Safe Divide

Avoid divide-by-zero errors:

```asql
select safe_divide(revenue, users) as revenue_per_user
```

**Compiles to**: `CASE WHEN users = 0 THEN NULL ELSE revenue / users END` (or native `SAFE_DIVIDE` on BigQuery).

### 13.10 Operator Quick Reference

| Operator | Purpose | Example |
|----------|---------|---------|
| `except` | Exclude columns | `except email, phone` |
| `rename` | Rename columns | `rename id as user_id` |
| `prefix` | Prefix column names | `prefix user_` |
| `deduplicate by` | Remove duplicates | `deduplicate by user_id order by -date` |
| `pivot ... by` | Rows to columns | `pivot amount by category` |
| `unpivot ... into` | Columns to rows | `unpivot jan, feb into month, value` |
| `fill` | Gap fill time series | `fill month with {revenue: 0}` |
| `date_spine()` | Generate date sequence | `from date_spine(start='2024-01-01', end=today(), grain=day)` |
| `series()` | Generate number sequence | `from series(1, 100)` |
| `union()` | Union with alignment | `from union(t1, t2, t3)` |
| `key()` | Surrogate key | `key(user_id, order_id)` |
| `::type?` | Safe cast | `value::integer?` |
| `safe_divide()` | Null on divide-by-zero | `safe_divide(a, b)` |

---

## 14. Models (Optional Metadata)

**Philosophy**: Ideally, ASQL doesn't create its own model format. It should:
1. Use dbt's existing `schema.yml` files when available
2. Infer from database schema metadata and conventions
3. Only create custom models when neither of the above are available

If relationships are defined in dbt's `schema.yml`:

```yaml
models:
  - name: opportunities
    columns:
      - name: owner_id
        tests:
          - relationships:
              to: ref('owners')
              field: id
```

Then ASQL can use those relationships automatically:

```asql
from opportunities
  group by owner.name ( sum(amount) as total_pipeline )
```

**Custom model format** (only if dbt/schema metadata unavailable):
```yaml
model users:
  default_time: created_at
  links:
    orders: orders.user_id

model opportunities:
  links:
    owner: owners.id
  default_time: created_at
```

Usage:

```asql
from users
  group by country ( # as total_users, average of age as avg_age )
```

---

## 15. Nested Results (Optional)

Inspired by EdgeQL, support nested result shapes:

```asql
from countries
| select {
    name,
    users = from users 
      | filter users.country == countries.code 
      | select name, age
  }
```

---

## 16. Indentation & Multi-line Queries

### 14.1 Indentation Rules

Every line must return a new table. For multi-line operations, indent:

```asql
from users
  filter status == "active"
  filter age >= 18
  group by country ( count() as count )
```

### 14.2 Nested Selects

```asql
from users
  select {
    name,
    orders = from orders
      filter orders.user_id == users.id
      select sum(amount) as total
  }
```

---

## 17. Capitalization & Naming

### 15.1 Case-Safe Design

**ASQL is case-safe by design.** This means you can use capital letters in column and table names without wrapping them in quotes obsessively. However, table/column names must still match the actual database names (case-insensitively).

```asql
# You can write queries using any case style
from Users
  select firstName, createdAt, user_id
  where status = "active"

# ASQL resolves case-insensitively to actual database names
# If database has: users table, first_name column, created_at column
# ASQL matches them correctly without requiring exact case
```

**Important clarification**: 
- `from Users` will query the `users` table (case-insensitive match)
- `from USERS` will NOT query a different table - it matches `users` case-insensitively
- You can use `firstName` in your query even if the database column is `first_name`
- Aliases can be in any case: `select firstName as UserName` works fine

**Why this matters**: 
- **Database best practices** often recommend snake_case (`created_at`, `user_id`)
- **Frontend development** typically uses camelCase (`createdAt`, `userId`)
- **APIs** might return PascalCase (`CreatedAt`, `UserId`)
- **Legacy databases** might have inconsistent casing

ASQL eliminates the friction of matching exact case, allowing you to write queries using whatever naming style feels natural while still matching the correct database objects.

### 15.2 Case Handling Strategy

ASQL normalizes identifiers internally while preserving the original case for SQL generation:

1. **Parse**: Accept any case variation
2. **Normalize**: Convert to a canonical form for matching
3. **Resolve**: Match against schema (case-insensitive)
4. **Generate**: Use the database's preferred case (from schema metadata) or preserve original

**Example:**
```asql
# You write:
from Users
  select firstName, createdAt

# ASQL resolves (case-insensitive):
# - Users → users (if that's the actual table name)
# - firstName → first_name (if that's the actual column)
# - createdAt → created_at (if that's the actual column)

# Generated SQL uses actual database names:
SELECT first_name, created_at FROM users
```

### 15.3 Automatic Conflict Resolution

**⚠️ Warning**: When column names conflict, automatically qualifying them (e.g., `users.id` and `orders.id`) might not be implemented in the initial version. This could be confusing and error-prone. Better to require explicit qualification:

```asql
from users
  & orders
-- If both have 'id', you should explicitly qualify:
select users.id as user_id, orders.id as order_id
```

**Recommendation**: In v1.0, require explicit qualification for ambiguous columns. Auto-qualification could be added later if there's clear demand, but explicit is safer and clearer.

### 15.4 Why Case-Safe is Good

**Pros:**
- ✅ Eliminates a common source of errors
- ✅ Works seamlessly across different naming conventions
- ✅ Reduces cognitive load (don't worry about case)
- ✅ Better developer experience

**Potential Concerns:**
- ⚠️ Might hide typos (but schema validation catches these)
- ⚠️ Could be confusing if database has both `UserId` and `user_id` (but this is rare and would be caught during resolution)

**Verdict**: Case-safety is a significant quality-of-life improvement that outweighs the minor risks. The compiler can warn about ambiguous cases during schema resolution.

---

## 18. Examples

### Example 1: Simple Analytic Query

```asql
from sales
  where year(date) == 2025
  group by region ( sum(amount) as revenue )
  order by -revenue
```

**Generated SQL:**
```sql
WITH step1 AS (
  SELECT * FROM sales WHERE EXTRACT(YEAR FROM date) = 2025
)
SELECT region, SUM(amount) AS revenue
FROM step1
GROUP BY region
ORDER BY revenue DESC;
```

### Example 2: Joins & Conditions

```asql
from opportunities
  & owners
  where owners.is_active
  group by owners.name ( sum(amount) as total_pipeline )
  order by -total_pipeline
```

### Example 3: Time Series

```asql
from sessions
  group by week(start_time) (
    # of distinct user_id as active_users
  )
  select week, active_users
```

### Example 4: Natural Language Aggregates

```asql
# of Users by country
Sum of revenue by region
Avg Users.age by country
```

### Example 5: Variables and Reuse

```asql
set base = from users
  where plan == "premium"

from base
  group by country ( # as total_users )
```

### Example 6: Complex Pipeline

```asql
from opportunities
  where status = "open"
  & owners
  where owners.is_active
  where org_type != "Non Profit"
  group by owner.name ( sum(amount) as total_pipeline )
  order by -total_pipeline
  limit 10
```

### Example 7: Date Grouping

```asql
from users
  group by month(created_at) ( # as signups )
  select month, signups
```

### Example 8: User-Defined Function

```asql
func age(user) = years(now() - user.birthday)

from users
  select age(user) as user_age
  group by country ( avg_age as average of user_age )
```

### Example 9: Case-Safe Naming

```asql
-- Works regardless of database naming convention
from Users
  select firstName, createdAt, user_id
  where status = "active"
```

### Example 10: Natural Language with "of"

```asql
from sales
  group by region (
    total amount as revenue
    # of distinct customer_id as customers
    average amount as avg_order
  )
```

**Note on "as" order**: Keep SQL's order - `expression as alias`. So `total amount as revenue` reads correctly: "total amount, aliased as revenue". The natural language function names like `total amount` make it sound like they're already aliases, but they're expressions that need aliasing. In group by blocks, always use `expression as alias` format: `sum(amount) as revenue`, `# as total_users`, etc.

**Example with function:**
```asql
func age(user) = years(now() - user.birthday)

# Natural language usage
avg age of user by country
# Reads beautifully: "average age of user, grouped by country"
```

### Example 11: Shorthand Natural Language (50/50 on implementation)

For very simple exploratory queries, you can omit the `from` clause and infer it from the aggregation:

```asql
# of Users by country
Sum of revenue by region
Avg Users.age by country
```

**Note**: This shorthand is nice for a big percentage of exploratory queries, but it's different from other queries that start with `from`. In these examples, the `from` table is inferred from its use in `# of Users`. It's really nice shorthand, but also potentially confusing. This feature is marked as 50/50 on implementation - may or may not make it into v1.0.

---

## 19. Compilation & Transpilation

### 17.1 Compilation Process

1. **Parse**: ASQL → AST (Abstract Syntax Tree)
2. **Resolve**: AST → Resolved AST (with type info, relationships)
3. **Transform**: Resolved AST → SQL AST (via SQLGlot)
4. **Generate**: SQL AST → Target SQL dialect

### 17.2 Intermediate Representation

Each pipeline step becomes a CTE:

```asql
from users
  filter status == "active"
  group by country ( count() as count )
```

Becomes:

```sql
WITH step1 AS (
  SELECT * FROM users WHERE status = 'active'
)
SELECT country, COUNT(*) AS count
FROM step1
GROUP BY country;
```

### 17.3 Target Dialects

Via SQLGlot, ASQL can transpile to:
- ANSI SQL
- PostgreSQL
- MySQL
- SQLite
- BigQuery
- Snowflake
- Redshift
- And more...

---

## 20. Implementation Roadmap

| Stage | Milestone | Description |
|-------|-----------|-------------|
| v0.1 | Parser + SQLGlot transpiler + CLI | Basic syntax parsing and SQL generation |
| v0.2 | VSCode extension | Autocomplete, syntax highlighting, SQL preview |
| v0.3 | Model layer + relationships | YAML model files, FK inference |
| v0.4 | Functions, fragments, REPL | User-defined functions, query fragments, interactive REPL |
| v1.0 | Optimizer, dialects, adapters | Query optimization, full dialect support, DuckDB adapter |

---

## 21. Design Decisions & Rationale

### 19.1 Why Remove SELECT?

Traditional SQL requires `SELECT` at the start, but the columns you need often aren't known until the end of the query. ASQL's pipeline approach lets you build up the query naturally, with `select`/`project` appearing only when needed.

### 19.2 Why Indentation-Based Syntax?

Indentation-based syntax (with optional pipe operators) is cleaner and more natural than requiring explicit operators. It reads like a conversation: "from users, filter active ones, group by country, count them." The pipe operator (`|`) is available for those who prefer explicit flow markers.

### 19.3 Why Natural Language?

ASQL is pronounced "Ask-el" - it should feel like asking a question. Natural language syntax (`# of Users`, `Sum of amount`, `Average of age`) makes queries readable to non-technical stakeholders while maintaining precision.

### 19.4 Why Case-Safe?

Database conventions (snake_case) conflict with frontend conventions (camelCase). ASQL eliminates this friction by being case-insensitive, allowing developers to write queries using whatever naming style feels natural.

### 19.5 Why Convention Over Configuration?

ASQL follows a "convention over configuration" philosophy (inspired by frameworks like Rails and dbt):

- **Assumes good modeling**: If you follow standards (standardized column names like `created_at`, proper FK naming like `user_id`), ASQL infers relationships and defaults automatically
- **Encourages best practices**: By making standard patterns easy and non-standard patterns explicit, ASQL encourages good modeling
- **Reduces boilerplate**: Most queries don't need explicit joins or time field specifications when conventions are followed
- **Configurable when needed**: Everything can be overridden, but defaults work for 80% of cases
- **dbt-friendly**: Works seamlessly with dbt projects that follow dbt's modeling standards

**Example**: If you have `Accounts.user_id` and a `Users` table, ASQL automatically infers the FK relationship. If you have `Accounts.ownerUserRef`, you'll need to configure it explicitly (encouraging you to rename it to `owner_id`).

### 19.6 Why Not Replace SQL?

ASQL transpiles to SQL, ensuring compatibility with existing tools, databases, and knowledge. It's an evolution, not a revolution. Maybe one day different databases will adopt ASQL or move toward it, just as JavaScript moved toward CoffeeScript's ideas (async/await, arrow functions, etc.).

---

## 22. Future Considerations

- **Visual SQL Editor**: ASQL's structure could enable a great visual query builder whose base could also be a text editor/IDE. Get the best of visual and text-based exploration.
- **dbt Integration**: Building ASQL into dbt out of the gate would make it immediately useful for the dbt community
- **Common Schema Format**: A shared schema/statistics library for cross-database compatibility
- **Query Optimization**: ASQL-specific optimizations before SQL generation
- **IDE Integration**: Full-featured editor with autocomplete, error checking, SQL preview
- **Testing Framework**: Query testing and validation tools

---

## 23. Major Benefits of ASQL

### 21.1 Reduced Need for CTEs and Nested Queries

Traditional SQL often requires CTEs or nested subqueries to break down complex logic. ASQL's pipeline approach eliminates most of this need:

**SQL (requires CTE):**
```sql
WITH filtered_users AS (
  SELECT * FROM users WHERE is_active
),
grouped AS (
  SELECT country, COUNT(*) as total
  FROM filtered_users
  GROUP BY country
)
SELECT * FROM grouped ORDER BY total DESC;
```

**ASQL (no CTE needed):**
```asql
from users
  where is_active
  -- cleaned users by country
  group by country ( # as total_users )
  order by -total_users
```

The comment marks where you might have created a CTE in SQL, but the pipeline continues naturally.

### 21.2 More Readable Column Names

Natural language syntax makes column names more readable without needing explicit aliases:

**SQL:**
```sql
SELECT country, COUNT(*) as total_users, AVG(age) as avg_age
```

**ASQL:**
```asql
select country, # of Users as total_users, average of age
```

The natural language makes columns self-documenting - `# of Users` is clearer than `count` or even `total_users`.

### 21.3 Less Boilerplate

- No need to write `SELECT` at the start when you don't know what columns you need yet
- No need for explicit joins when FKs follow conventions
- No need for verbose date extraction functions
- No need to quote identifiers obsessively

### 21.4 Better for Analytics

- Time functions that work consistently across databases
- Natural language aggregations that read like questions
- Pipeline flow that matches analytical thinking
- Convention-based defaults that reduce configuration

---

## Appendix A: Grammar Sketch (Informal)

```
query := from_clause pipeline*

from_clause := 'from' table_name

pipeline := operator  -- indentation-based, or '|' operator (optional)

operator := filter_op
          | group_by_op
          | join_op
          | select_op
          | order_op
          | limit_op
          | set_op

filter_op := 'where' expression
           | 'if' expression

group_by_op := 'group' 'by' expression_list '(' aggregate_list ')'

join_op := 'join' table_name ('on' expression)?

select_op := 'select' column_list

order_op := 'order' 'by' ('-'? (column_name | function_call))+

limit_op := 'limit' number

set_op := 'set' var_name '=' query

aggregate := var_name 'as' aggregate_func '(' expression ')'
           | natural_language_aggregate
           | '#' | '#(' expression ')' | '# of' expression

aggregate_func := 'count' | 'sum' | 'avg' | 'min' | 'max'
```

---

## Appendix B: Comparison with Other Languages

| Feature | SQL | PRQL | Malloy | ASQL |
|---------|-----|------|--------|------|
| Pipeline syntax | ❌ | ✅ | ✅ | ✅ |
| Model layer | ❌ | ❌ | ✅ | ✅ (optional) |
| Natural language | ❌ | ❌ | ✅ | ✅ |
| Smart joins | ❌ | ❌ | ✅ | ✅ |
| Time bucketing | Manual | Manual | ✅ | ✅ |
| Transpiles to SQL | N/A | ✅ | ✅ | ✅ |

---

## References & Inspiration

- **PRQL**: Pipeline structure, group by blocks, func (note: PRQL uses `let` but ASQL uses `set` for SQL familiarity)
- **KQL**: Verb syntax (filter, project, summarize), pipeline operators
- **Malloy**: Model layer, measures/dimensions, time bucketing concept (ASQL uses simpler `month()`, `year()` functions rather than Malloy's `time_bucket()` function), default_time concept
- **EdgeQL**: Dot traversal for relationships, nested result shapes
- **FunSQL**: Composable variables and reusable fragments
- **Google Pipe-SQL**: Compatibility mindset, additive approach
- **SQLGlot**: Transpilation engine and SQL parsing

---

**End of Specification**



