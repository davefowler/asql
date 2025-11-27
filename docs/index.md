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
  where status == "active"
  group by country ( # as total_users )
  sort -total_users
```

**Pipeline operator (optional, explicit):**
```asql
from users
| where status == "active"
| group by country ( # as total_users )
| sort -total_users
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
| `where` | Filter rows | `WHERE` | `where status == "active"` |
| `group by` | Group and aggregate | `GROUP BY` | `group by country ( # as total_users )` |
| `join` | Join datasets | `JOIN` | `join owners on owner_id == owners.id` |
| `select` / `project` | Choose final columns | `SELECT` | `select country, users, avg_age` |
| `sort` | Sort rows | `ORDER BY` | `sort -users` (descending), `sort -updated_at` (descending column) |
| `take` | Limit rows | `LIMIT` | `take 10` |
| `set` | Define variable/fragment (CTE) | `WITH ... AS` | `set active = from users \| where is_active` |

---

## 4. Expressions & Operators

### 4.1 Comparison Operators

- `==` - equals
- `!=` - not equals
- `<`, `>`, `<=`, `>=` - comparison
- `is`, `is not` - null checks
- `in`, `not in` - membership

### 4.2 Logical Operators

- `and`, `or`, `not` - logical operations
- `&&` - alternative syntax for `and`

**Note**: `||` is **not** used for logical OR in ASQL. Use the `or` keyword instead. The `||` operator is reserved for COALESCE (see Section 4.6).

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

### 4.6 COALESCE Operator (`||`)

ASQL uses the `||` operator for COALESCE, providing a cleaner syntax than the function call. This is similar to JavaScript's nullish coalescing, but works with any falsy values (NULL, FALSE, empty strings, etc.).

**Syntax:**
```asql
# Function form
coalesce(column, default_value)

# Operator form (preferred)
column || default_value

# Chained (multiple fallbacks)
column || fallback1 || fallback2 || "default"
```

**Examples:**
```asql
# Handle NULL values
from users select name || "Unknown" as display_name

# Multiple fallbacks
from products select price || sale_price || 0 as final_price

# In WHERE clauses
from users where not is_deleted || FALSE

# With boolean logic
from orders where status || "pending" == "completed"
```

**Why `||` for COALESCE?**
- More concise than `coalesce()` function calls
- Familiar to developers who use `||` for nullish coalescing in JavaScript/TypeScript
- Chains naturally: `a || b || c` reads as "a, or b, or c"
- Note: In ASQL, `||` is **not** used for logical OR (use `or` keyword instead) or string concatenation (use `concat()` function)

**Precedence:**
The `||` operator has higher precedence than logical operators (`and`, `or`, `not`) but lower than comparison operators (`==`, `!=`, etc.). This means:
- `not is_deleted || FALSE` parses as `NOT COALESCE(is_deleted, FALSE)` ✅
- `status == "active" || "pending"` parses as `COALESCE(status == "active", "pending")` ✅

### 4.7 Conditional Expressions (CASE)

ASQL uses DuckDB/Spark-style `CASE` syntax, which is cleaner and more concise than SQL-standard syntax:

**Simple CASE (DuckDB/Spark-style)**:
```asql
from users
  select 
    case status
      when "active" then 1
      when "pending" then 0
      else -1
    end as status_code
```

**Searched CASE (when conditions are complex)**:
```asql
from users
  select 
    case
      when status == "active" and created_at > "2024-01-01" then 1
      when status == "pending" then 0
      else -1
    end as status_code
```

**Benefits of DuckDB/Spark-style**:
- More concise - expression appears once at the top (for simple CASE)
- More readable - avoids repeating the expression in each WHEN clause
- Familiar to users of DuckDB and Spark SQL
- Consistent indentation makes nested conditions easier to read

**Reverse Compilation**: SQL `CASE` statements are automatically converted to this syntax when converting SQL to ASQL.

**Examples from real queries**:
```asql
# Complex business logic
from opportunity
  select 
    case
      when is_won then "Won"
      when NOT is_won and is_closed then "Lost"
      when NOT is_closed and lower(forecast_category) in ("pipeline", "forecast", "bestcase") then "Pipeline"
      else "Other"
    end as status
```

**Natural language alternatives** (future consideration):

**Standard CASE syntax:**
```asql
select status_label as case
  when status == "active" then "Active User"
  when status == "inactive" then "Inactive User"
  else "Unknown"
end
```

**Natural language alternative:**
```asql
select status_label as 
  if status == "active" then "Active User"
  else if status == "inactive" then "Inactive User"
  else "Unknown"
```

**Simple if-then-else:**
```asql
select is_premium as if plan == "premium" then true else false
select discount as if amount > 100 then amount * 0.1 else 0
```

All three syntaxes compile to standard SQL `CASE` statements. Choose based on readability preference.

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

# Natural language syntax
Sum of amount as revenue
Total of amount as revenue
Sum amount as revenue
Total amount as revenue

# In group by
from sales
  group by region (
    total amount as revenue
    -- or: sum of amount as revenue
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

### 7.1 Explicit Joins

Traditional explicit join syntax:

```asql
from opportunities
  join owners on owner_id == owners.id
  group by owners.name ( sum(amount) as total_pipeline )
```

### 7.2 Automatic Joins (Preferred)

If a foreign key relationship exists between tables, ASQL can automatically infer the join:

**Single FK relationship:**
```asql
# If opportunities.owner_id → owners.id is the only FK
from opportunities, owners
  group by owners.name ( sum(amount) as total_pipeline )
```

**Arrow syntax (explicit relationship):**
```asql
# Explicitly specify the relationship direction
from opportunities->owners
  group by owners.name ( sum(amount) as total_pipeline )

# Or reverse direction
from owners<-opportunities
  group by owners.name ( sum(amount) as total_pipeline )
```

**Multiple FKs - specify which one:**
```asql
# If accounts has both owner_id and creator_id pointing to users
from accounts.owner->users
  group by users.name ( sum(amount) as total )

# Or using the FK name directly
from accounts
  join users on accounts.owner_id == users.id
  group by users.name ( sum(amount) as total )
```

### 7.3 Smart Joins via Dot Notation (Model Metadata)

If relationships are defined in a model file (compatible with dbt's relationship syntax):

```yaml
models:
  opportunities:
    links:
      owner: owners.id
    # dbt-style relationships also supported:
    relationships:
      - to: owners
        field: owner_id
```

Then you can use dot notation without explicit joins:

```asql
from opportunities
  group by owner.name ( sum(amount) as total_pipeline )
```

**dbt Compatibility**: ASQL model files are compatible with dbt's `relationships` syntax. If you're using dbt, ASQL can read your existing `schema.yml` files to infer relationships automatically.

### 7.4 Join Strategy & Convention-Based Inference

ASQL uses a convention-based approach to infer joins:

**Inference priority:**
1. **Model metadata** - If relationships are explicitly defined in model files, use them
2. **Naming convention inference** - If `Accounts.user_id` exists and there's a `Users` table, infer `Accounts.user_id → Users.id`
3. **Single FK check** - If only one FK exists between tables, auto-join
4. **Require explicit specification** - If multiple FKs exist or conventions don't match, require explicit syntax
5. **Fall back to explicit join** - Always allow traditional `join ... on ...` syntax

**Convention assumptions:**
- Foreign keys follow the pattern `{referenced_table}_id` (e.g., `user_id`, `owner_id`, `account_id`)
- **Multiple FKs**: When a table has multiple foreign keys to the same table, they should end with `{table}_id` format:
  - ✅ `owner_user_id`, `manager_user_id`, `support_rep_user_id` (all point to Users)
  - ✅ `billing_account_id`, `shipping_account_id` (both point to Accounts)
  - ❌ `ownerId`, `managerRef` (non-standard, requires explicit configuration)
  This convention makes it clear what each FK points to and enables automatic inference.
- Primary keys are typically `id`, but also support `{table}_id` (e.g., `Users.user_id`) and `pk` patterns
- Primary key patterns are configurable in compiler/linter settings
- Table names are pluralized or follow your team's standard

**Example of convention-based inference:**
```asql
# Schema: Accounts table has user_id column, Users table exists
# ASQL infers: Accounts.user_id → Users.id

from accounts
  group by user.name ( sum(amount) as total )
# Automatically joins: accounts JOIN users ON accounts.user_id = users.id
```

**Multiple FKs to same table:**
```asql
# Schema: Accounts has owner_user_id, manager_user_id, support_rep_user_id
# All end in _user_id, so ASQL can infer which one based on context

from accounts
  group by owner.name ( total as sum(amount) )
# Automatically uses owner_user_id

from accounts
  group by manager.name ( sum(amount) as total )
# Automatically uses manager_user_id
```

**When conventions don't match:**
```asql
# Schema: Accounts table has ownerId (non-standard name, doesn't end in _user_id)
# ASQL requires explicit join or model configuration

from accounts
  join users on accounts.ownerId == users.id
  group by users.name ( sum(amount) as total )
```

**Philosophy**: Follow standard naming conventions (especially ending multiple FKs with `{table}_id`), and joins happen automatically. Use non-standard names, and you'll need to be explicit (which encourages standardization).

---

## 8. Dates & Time

### 8.1 Simple Time Functions (No More EXTRACT!)

ASQL provides simple, intuitive date functions instead of verbose SQL date extraction:

**ASQL syntax:**
```asql
year(created_at)      -- Returns: 2025 (full year)
month(created_at)     -- Returns: 2025-01 (year-month for time series)
week(created_at)      -- Returns: 2025-W01 (year-week for time series)
day(created_at)       -- Returns: 2025-01-15 (full date for time series)
hour(created_at)      -- Returns: 2025-01-15 14:00 (date-hour)
```

**Clarification on time functions:**
- `day(created_at)` returns the full date (e.g., `2025-01-15`) for time series analysis, not the day of week
- For day of week, use `weekday(created_at)` which returns `Monday`, `Tuesday`, etc.
- Alternative: `created_at.weekday` could return day of week, while `created_at.day` returns the date
- All time functions return values suitable for time series (include year/month context to avoid sorting issues)

**As opposed to SQL:**
```sql
-- PostgreSQL - need to extract and format
EXTRACT(YEAR FROM created_at)
DATE_TRUNC('month', created_at)
DATE_TRUNC('day', created_at)

-- MySQL - inconsistent function names
YEAR(created_at)
DATE_FORMAT(created_at, '%Y-%m')
DATE_FORMAT(created_at, '%Y-%m-%d')

-- SQL Server - different syntax again
YEAR(created_at)
DATEPART(year, created_at)
FORMAT(created_at, 'yyyy-MM')
```

**Natural language alternatives:**
```asql
year of created_at
month of created_at
day of created_at
```

**Method-style syntax (alternative, for day-of-week distinction):**
```asql
created_at.year       -- Full year
created_at.month      -- Year-month
created_at.day        -- Full date (for time series)
created_at.weekday    -- Day of week (Monday, Tuesday, etc.)
created_at.hour       -- Date-hour
```

All syntaxes are equivalent for the main time functions. Method-style syntax may be useful for distinguishing `day` (date) from `weekday` (day of week).

### 8.2 Time Bucketing

Time bucketing is simply grouping by a time function:

```asql
from users
  group by month(created_at) ( # as signups )
```

**As opposed to SQL:**
```sql
-- PostgreSQL
SELECT DATE_TRUNC('month', created_at) AS month, COUNT(*) AS signups
FROM users
GROUP BY DATE_TRUNC('month', created_at)

-- MySQL
SELECT DATE_FORMAT(created_at, '%Y-%m') AS month, COUNT(*) AS signups
FROM users
GROUP BY DATE_FORMAT(created_at, '%Y-%m')
```

This is standard SQL grouping - ASQL just makes the time functions simpler and more consistent.

### 8.3 Natural Language Time Grouping

```asql
# of Users by month
# of Sales by week
Revenue by year
```

**⚠️ Warning**: These shortcuts assume a default time column has been set (see Section 8.4). Without explicit defaults, these can be ambiguous and potentially dangerous.

### 8.4 Default Time Fields

**dbt compatibility**: dbt does not have a standard `default_time` field in its schema files. ASQL can extend dbt's schema format with this metadata, or infer defaults from conventions.

Model metadata can specify default time fields:

```yaml
models:
  users:
    default_time: created_at
```

Then `group by month` implicitly uses `created_at`:

```asql
from users
  group by month ( # as signups )
```

**Note**: Ideally, ASQL doesn't create its own model format. It should use dbt's existing `schema.yml` files when available, or infer from database schema metadata and conventions.

**Convention-based inference**: ASQL follows a "convention over configuration" philosophy:

1. **Standard naming assumptions**: ASQL assumes you follow good modeling standards:
   - Timestamp columns are named `created_at`, `updated_at` (not `dateCreated`, `lastModified`, etc.)
   - Foreign keys follow patterns like `user_id`, `owner_id`, `account_id`
   - Tables are properly pluralized or follow your team's convention

2. **Smart defaults**: Based on these conventions, ASQL can infer:
   - **Time fields**: If a table has `created_at`, it's assumed to be the primary time field for time-based aggregations. `updated_at` is secondary.
   - **Foreign keys**: If `Accounts.user_id` exists and there's a `Users` table, ASQL infers the relationship `Accounts.user_id → Users.id`
   - **Relationships**: Standard FK naming (`{table}_id`) enables automatic join inference

3. **Configurable but opinionated**: All defaults can be overridden:
   ```yaml
   models:
     users:
       default_time: signup_date  # Override convention
     accounts:
       links:
         owner: users.id  # Explicit relationship if naming doesn't match
   ```

4. **dbt compatibility**: ASQL works seamlessly with dbt projects that follow dbt's modeling standards. If you're using dbt, ASQL can read your `schema.yml` files and infer relationships automatically.

**⚠️ Important Considerations**:

1. **Standards matter**: ASQL works best when you follow modeling standards. If your schema is non-standard, you may need to configure relationships explicitly.
2. **Explicit overrides**: While conventions are helpful, explicit configuration is always clearer. Use `group by month(created_at)` when clarity is important.
3. **Migration path**: If you're migrating to ASQL, consider standardizing your schema first (e.g., renaming `dateCreated` → `created_at`) to unlock automatic inference.
4. **Best practice**: Follow dbt-style modeling standards, and ASQL will "just work." Deviate from standards, and you'll need explicit configuration (which is fine, but more verbose).
5. **dbt integration**: Ideally, ASQL will be built into dbt out of the gate. You'll be able to use ASQL even in raw cleaning stages. In those stages, you may need to be more explicit (or start with a `select` to rename columns to standards), but ASQL's pipelining and cleaner syntax will still be quite useful. A common pattern: start cleanup with a `select` command renaming things to standards, then continue with pipeline operations.

**Philosophy**: We assume you're doing good modeling. If you follow standards, ASQL is magical. If you don't, you can still use ASQL, but you'll need to be more explicit. This encourages good practices while remaining flexible.

---

## 9. Filtering

### 9.1 Basic Filters

ASQL uses `where` instead of `filter` because it's more intuitive - "where" clearly means "filter in" (keep rows that match), whereas "filter" is ambiguous (filter in or filter out?).

```asql
from users
  where status == "active"
  where age >= 18
```

### 9.2 Multiple Conditions

Multiple conditions can be written in several ways:

**Separate where clauses:**
```asql
from opportunities
  where status == "open"
  where owner.is_active
  where org_type != "Non Profit"
```

**Using `and` on same line:**
```asql
from opportunities
  where status == "open" and owner.is_active and org_type != "Non Profit"
```

**Using `&` operator:**
```asql
from opportunities
  where status == "open" & owner.is_active & org_type != "Non Profit"
```

**Tabbed indentation (multi-line):**
```asql
from opportunities
  where status == "open"
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

## 10. Sorting

### 10.1 Basic Sorting

The `sort` clause orders rows by one or more columns:

```asql
from users sort name
from users sort -total_users
```

**Descending order**: Use the `-` prefix to sort in descending order:
- `sort name` → ascending (A-Z)
- `sort -name` → descending (Z-A)

### 10.2 Sorting by Function Calls

You can sort by function calls using the `-` prefix for descending order:

```asql
from users sort month(created_at)
from users sort -updated_at
from events sort -year(created_at), name
```

**Examples:**
- `sort updated_at` → Sort by updated_at ascending
- `sort -updated_at` → Sort by updated_at descending (newest first)
- `sort -year(created_at), name` → Sort by year descending, then name ascending

This syntax makes it easy to sort by computed values like date functions.

### 10.3 Multiple Sort Columns

Multiple sort columns are separated by commas:

```asql
from users sort -total_users, name
from sales sort -revenue, region, -date
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
  sort -total_users
```

The comment marks where you might have created a CTE in SQL, but the pipeline continues naturally. CTEs are still available when you need to reuse a subquery multiple times.

### 11.2 Stashing CTEs in Pipelines (`stash as`)

Instead of defining CTEs at the top level with `set`, you can stash intermediate pipeline results directly within a pipeline using `stash as`. This keeps CTEs close to where they're used and makes chaining clearer. The key benefit is that you end with the name and use it right after, so your eyes don't have to jump around.

**Basic usage (at the end):**
```asql
from users
  where status == "active"
  group by country ( # as total_users )
  select country, total_users
  stash as revenue

from revenue
  sort -total_users
```

**Using `stash as` in the middle of a pipeline:**
```asql
from users
  where status == "active"
  stash as active_users
  group by country ( # as total_users )
  sort -total_users
```

When `stash as` appears in the middle, it stashes everything before it as a CTE, then continues with the pipeline.

**Multiple queries reusing a stashed CTE:**
```asql
from sales
  where year(date) == 2025
  group by region ( sum(amount) as revenue )
  stash as use_this_later
  sort -revenue
  take 10;

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
  sort -total_users
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
    sort -{key}
    take n

from sales
  top_n(10, amount)
```

**Implementation**: Table functions are expanded inline during compilation - they don't create actual database functions. The function body is substituted where the function is called, then the whole query is compiled to SQL.

### 12.3 Built-in Functions

Standard SQL functions are available:

- `count()`, `sum()`, `avg()`, `min()`, `max()`
- `distinct()`
- `coalesce()` or `||` operator (JavaScript-style, also used in some SQL dialects like PostgreSQL for string concatenation, but ASQL uses it for COALESCE to match common usage)
- `date_format()`, `year()`, `month()`, etc.
- `years_between()`, `days_between()`, etc.

### 12.4 Function Examples

```asql
func year(table) = DATE_FORMAT('%Y', table._mainDate)

from users
| year(created_at)
```

---

## 13. Models (Optional Metadata)

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

## 14. Nested Results (Optional)

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

## 15. Indentation & Multi-line Queries

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

## 16. Capitalization & Naming

### 15.1 Case-Safe Design

**ASQL is case-safe by design.** This means you can use capital letters in column and table names without wrapping them in quotes obsessively. However, table/column names must still match the actual database names (case-insensitively).

```asql
# You can write queries using any case style
from Users
  select firstName, createdAt, user_id
  where status == "active"

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
  join orders
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

## 17. Examples

### Example 1: Simple Analytic Query

```asql
from sales
  where year(date) == 2025
  group by region ( sum(amount) as revenue )
  sort -revenue
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
  join owners
  where owners.is_active
  group by owners.name ( sum(amount) as total_pipeline )
  sort -total_pipeline
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
  where status == "open"
  join owners
  where owners.is_active
  where org_type != "Non Profit"
  group by owner.name ( sum(amount) as total_pipeline )
  sort -total_pipeline
  take 10
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
  where status == "active"
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

## 18. Compilation & Transpilation

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

## 19. Implementation Roadmap

| Stage | Milestone | Description |
|-------|-----------|-------------|
| v0.1 | Parser + SQLGlot transpiler + CLI | Basic syntax parsing and SQL generation |
| v0.2 | VSCode extension | Autocomplete, syntax highlighting, SQL preview |
| v0.3 | Model layer + relationships | YAML model files, FK inference |
| v0.4 | Functions, fragments, REPL | User-defined functions, query fragments, interactive REPL |
| v1.0 | Optimizer, dialects, adapters | Query optimization, full dialect support, DuckDB adapter |

---

## 20. Design Decisions & Rationale

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

## 21. Future Considerations

- **Visual SQL Editor**: ASQL's structure could enable a great visual query builder whose base could also be a text editor/IDE. Get the best of visual and text-based exploration.
- **dbt Integration**: Building ASQL into dbt out of the gate would make it immediately useful for the dbt community
- **Common Schema Format**: A shared schema/statistics library for cross-database compatibility
- **Query Optimization**: ASQL-specific optimizations before SQL generation
- **IDE Integration**: Full-featured editor with autocomplete, error checking, SQL preview
- **Testing Framework**: Query testing and validation tools

---

## 22. Major Benefits of ASQL

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
  sort -total_users
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
          | sort_op
          | take_op
          | set_op

filter_op := 'where' expression
           | 'if' expression

group_by_op := 'group' 'by' expression_list '(' aggregate_list ')'

join_op := 'join' table_name ('on' expression)?

select_op := 'select' column_list

sort_op := 'sort' ('-'? (column_name | function_call))+

take_op := 'take' number

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

