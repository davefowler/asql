# ASQL: Analytic SQL — Language Specification

**Version:** 0.1  
**Status:** Draft  
**Last Updated:** 2025-01-XX

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
  filter status == "active"
  group by country ( count as count() )
  sort -count
```

**Pipeline operator (optional, explicit):**
```asql
from users
| filter status == "active"
| group by country ( count as count() )
| sort -count
```

Both styles are equivalent. Indentation-based syntax is cleaner and more natural, while the pipe operator makes the flow explicit. Choose based on preference or context.

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
| `filter` | Filter rows | `WHERE` | `filter status == "active"` |
| `derive` | Add/transform columns | `SELECT ... AS` | `derive age = years_between(now(), dob)` |
| `group by` | Group and aggregate | `GROUP BY` | `group by country ( count = count() )` |
| `join` | Join datasets | `JOIN` | `join owners on owner_id == owners.id` |
| `select` / `project` | Choose final columns | `SELECT` | `select country, users, avg_age` |
| `sort` | Sort rows | `ORDER BY` | `sort -users` (descending) |
| `take` | Limit rows | `LIMIT` | `take 10` |
| `let` | Define variable/fragment | `WITH ... AS` | `let active = from users \| filter is_active` |

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
- `&&`, `||` - alternative syntax (where `||` can also mean COALESCE)

### 4.3 Arithmetic Operators

- `+`, `-`, `*`, `/` - standard arithmetic
- `%` - modulo

### 4.4 String & Date Literals

- Strings: `"active"`, `'inactive'`
- Dates: `@2025-01-10`, `@2025-11-10`
- Numbers: `42`, `3.14`

### 4.5 Conditional Expressions (CASE)

ASQL supports SQL's `CASE` statement with natural language alternatives:

**Standard CASE syntax:**
```asql
derive status_label as case
  when status == "active" then "Active User"
  when status == "inactive" then "Inactive User"
  else "Unknown"
end
```

**Natural language alternative:**
```asql
derive status_label as 
  if status == "active" then "Active User"
  else if status == "inactive" then "Inactive User"
  else "Unknown"
```

**Simple if-then-else:**
```asql
derive is_premium as if plan == "premium" then true else false
derive discount as if amount > 100 then amount * 0.1 else 0
```

All three syntaxes compile to standard SQL `CASE` statements. Choose based on readability preference.

### 4.6 Comments

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
    revenue as sum(amount),
    customers as count(distinct customer_id),
    avg_order as avg(amount),
    max_order as max(amount),
    min_order as min(amount)
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
    revenue as total amount
    -- or: revenue as sum of amount
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
    total_users as count(),
    avg_age as avg(age)
  )
```

---

## 6. Grouping

### 6.1 Basic Grouping

```asql
from users
  group by country ( count as count() )
```

**Note**: The parentheses syntax for grouping aggregates is inspired by PRQL, which uses a similar block structure for clarity and readability.

### 6.2 Multiple Grouping Columns

```asql
from sales
  group by region, month (
    revenue as sum(amount),
    orders as count()
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
  group by owners.name ( total_pipeline as sum(amount) )
```

### 7.2 Automatic Joins (Preferred)

If a foreign key relationship exists between tables, ASQL can automatically infer the join:

**Single FK relationship:**
```asql
# If opportunities.owner_id → owners.id is the only FK
from opportunities, owners
  group by owners.name ( total_pipeline as sum(amount) )
```

**Arrow syntax (explicit relationship):**
```asql
# Explicitly specify the relationship direction
from opportunities->owners
  group by owners.name ( total_pipeline as sum(amount) )

# Or reverse direction
from owners<-opportunities
  group by owners.name ( total_pipeline as sum(amount) )
```

**Multiple FKs - specify which one:**
```asql
# If accounts has both owner_id and creator_id pointing to users
from accounts.owner->users
  group by users.name ( total as sum(amount) )

# Or using the FK name directly
from accounts
  join users on accounts.owner_id == users.id
  group by users.name ( total as sum(amount) )
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
  group by owner.name ( total_pipeline as sum(amount) )
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
  group by user.name ( total as sum(amount) )
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
  group by manager.name ( total as sum(amount) )
# Automatically uses manager_user_id
```

**When conventions don't match:**
```asql
# Schema: Accounts table has ownerId (non-standard name, doesn't end in _user_id)
# ASQL requires explicit join or model configuration

from accounts
  join users on accounts.ownerId == users.id
  group by users.name ( total as sum(amount) )
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
  group by month(created_at) ( signups as # )
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
  group by month ( signups as # )
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

**Philosophy**: We assume you're doing good modeling. If you follow standards, ASQL is magical. If you don't, you can still use ASQL, but you'll need to be more explicit. This encourages good practices while remaining flexible.

---

## 9. Filtering

### 9.1 Basic Filters

```asql
from users
  filter status == "active"
  filter age >= 18
```

### 9.2 Multiple Conditions

```asql
from opportunities
  filter status == "open"
  filter owner.is_active
  filter org_type != "Non Profit"
```

### 9.3 Alternative Syntax: `if`

```asql
from opportunities
  group by owner.name ( total as sum(amount) )
  if status == "open"
  if owner.is_active
```

**Note**: `if` is syntactic sugar for `filter` and can be used interchangeably. It makes queries read more naturally: "total pipeline by owner name if status is open".

---

## 10. Variables & CTEs

### 10.1 Simple Variables

```asql
let active_users = from users
  filter is_active

from active_users
  group by country ( total as count() )
```

### 10.2 Column Variables

```asql
from users
  derive all_ages as age
  derive avg_all_ages as avg(all_ages)
```

### 10.3 Nested Variables

```asql
let base = from users
  filter plan == "premium"

let by_country = from base
  group by country ( count as count() )

from by_country
  sort -count
```

---

## 11. Functions

### 11.1 User-Defined Scalar Functions

```asql
func lifespan(age) = age / 73.0

from users
  derive expectancy as lifespan(age)
```

### 11.2 User-Defined Table Functions

```asql
func top_n(table, n, key) =
  table
    sort -{key}
    take n

from sales
  top_n(10, amount)
```

### 11.3 Built-in Functions

Standard SQL functions are available:

- `count()`, `sum()`, `avg()`, `min()`, `max()`
- `distinct()`
- `coalesce()` or `||` operator
- `date_format()`, `year()`, `month()`, etc.
- `years_between()`, `days_between()`, etc.

### 11.4 Function Examples

```asql
func year(table) = DATE_FORMAT('%Y', table._mainDate)

from users
| year(created_at)
```

---

## 12. Models (Optional Metadata)

Models define schema metadata, relationships, measures, and dimensions:

```yaml
model users:
  dimensions:
    country: string
    age: number
  measures:
    count: count()
    avg_age: avg(age)
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
| group by country ( count, avg_age )
```

---

## 13. Nested Results (Optional)

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

## 14. Indentation & Multi-line Queries

### 14.1 Indentation Rules

Every line must return a new table. For multi-line operations, indent:

```asql
from users
  filter status == "active"
  filter age >= 18
  group by country ( count as count() )
```

### 14.2 Nested Selects

```asql
from users
  select {
    name,
    orders = from orders
      filter orders.user_id == users.id
      select total as sum(amount)
  }
```

---

## 15. Capitalization & Naming

### 15.1 Case-Safe Design

**ASQL is case-safe by design.** This means you can use any naming convention without worrying about case sensitivity issues:

```asql
# All of these work the same way
from Users
from users
from USERS

# Column names too
select firstName
select first_name
select FirstName
select FIRST_NAME
```

**Why this matters**: 
- **Database best practices** often recommend snake_case (`created_at`, `user_id`)
- **Frontend development** typically uses camelCase (`createdAt`, `userId`)
- **APIs** might return PascalCase (`CreatedAt`, `UserId`)
- **Legacy databases** might have inconsistent casing

ASQL eliminates this friction by treating all these as equivalent, allowing you to write queries using whatever naming style feels natural.

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

When column names conflict, the compiler automatically qualifies:

```asql
from users
  join orders
-- If both have 'id', automatically becomes users.id and orders.id
```

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

## 16. Examples

### Example 1: Simple Analytic Query

```asql
from sales
  filter year(date) == 2025
  group by region ( revenue as sum(amount) )
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
  filter owners.is_active
  group by owners.name ( total_pipeline as sum(amount) )
  sort -total_pipeline
```

### Example 3: Time Series

```asql
from sessions
  group by week(start_time) (
    active_users as count(distinct user_id)
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
let base = from users
  filter plan == "premium"

from base
  group by country ( count as count() )
```

### Example 6: Complex Pipeline

```asql
from opportunities
  filter status == "open"
  join owners
  filter owners.is_active
  filter org_type != "Non Profit"
  group by owner.name ( total_pipeline as sum(amount) )
  sort -total_pipeline
  take 10
```

### Example 7: Date Grouping

```asql
from users
  group by month(created_at) ( signups as count() )
  select month, signups
```

### Example 8: User-Defined Function

```asql
func lifespan(age) = age / 73.0

from users
  derive expectancy as lifespan(age)
  group by country ( avg_expectancy as avg(expectancy) )
```

### Example 9: Case-Safe Naming

```asql
-- Works regardless of database naming convention
from Users
  select firstName, createdAt, user_id
  filter status == "active"
```

### Example 10: Natural Language with "of"

```asql
from sales
  group by region (
    revenue as total of amount
    customers as # of distinct customer_id
    avg_order as average of amount
  )
```

---

## 17. Compilation & Transpilation

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
  group by country ( count as count() )
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

## 18. Implementation Roadmap

| Stage | Milestone | Description |
|-------|-----------|-------------|
| v0.1 | Parser + SQLGlot transpiler + CLI | Basic syntax parsing and SQL generation |
| v0.2 | VSCode extension | Autocomplete, syntax highlighting, SQL preview |
| v0.3 | Model layer + relationships | YAML model files, FK inference |
| v0.4 | Functions, fragments, REPL | User-defined functions, query fragments, interactive REPL |
| v1.0 | Optimizer, dialects, adapters | Query optimization, full dialect support, DuckDB adapter |

---

## 19. Design Decisions & Rationale

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

ASQL transpiles to SQL, ensuring compatibility with existing tools, databases, and knowledge. It's an evolution, not a revolution.

---

## 20. Future Considerations

- **Visual SQL Editor**: ASQL's structure could enable a great visual query builder who's base could also be a text editor/IDE.  Get the best of visual and text based exploration.
- **Common Schema Format**: A shared schema/statistics library for cross-database compatibility
- **Query Optimization**: ASQL-specific optimizations before SQL generation
- **IDE Integration**: Full-featured editor with autocomplete, error checking, SQL preview
- **Testing Framework**: Query testing and validation tools

---

## Appendix A: Grammar Sketch (Informal)

```
query := from_clause pipeline*

from_clause := 'from' table_name

pipeline := operator  -- indentation-based, or '|' operator (optional)

operator := filter_op
          | derive_op
          | group_by_op
          | join_op
          | select_op
          | sort_op
          | take_op
          | let_op

filter_op := 'filter' expression
           | 'if' expression

derive_op := 'derive' assignment+

group_by_op := 'group' 'by' expression_list '(' aggregate_list ')'

join_op := 'join' table_name ('on' expression)?

select_op := 'select' column_list

sort_op := 'sort' ('-'? column_name)+

take_op := 'take' number

let_op := 'let' var_name '=' query

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

- **PRQL**: Pipeline structure, derive, group by blocks, let & func
- **KQL**: Verb syntax (filter, project, summarize), pipeline operators
- **Malloy**: Model layer, measures/dimensions, time bucketing concept (ASQL uses simpler `month()`, `year()` functions rather than Malloy's `time_bucket()` function), default_time concept
- **EdgeQL**: Dot traversal for relationships, nested result shapes
- **FunSQL**: Composable variables and reusable fragments
- **Google Pipe-SQL**: Compatibility mindset, additive approach
- **SQLGlot**: Transpilation engine and SQL parsing

---

**End of Specification**

