# Auto-Alias Mapping Table

This table documents the proposed auto-aliasing behavior for all ASQL functions/aggregates. When a function is used without an explicit `as` alias, it automatically generates a column name following the pattern shown.

**Status**: Future feature - see `docs/spec_future.md` for details.

---

## The Problem: SQL's Unusable Default Aliases

SQL's default column naming is problematic. When you use functions without explicit aliases, SQL generates names that are often unusable, inconsistent, or cause conflicts:

### 1. Generic, Meaningless Names

SQL typically uses just the function name, losing all context:

```sql
-- SQL: Generic names lose context
SELECT 
  COUNT(*),                    -- → column: "count" (what does this count?)
  SUM(amount),                 -- → column: "sum" (sum of what?)
  AVG(price),                  -- → column: "avg" (average of what?)
  YEAR(created_at)             -- → column: "year" (year of what?)
FROM orders;
```

These names are meaningless when you reference them later or when reading results.

### 2. Inconsistent Naming Across Dialects

When you use multiple similar functions, SQL dialects handle naming inconsistently:

```sql
-- SQL: Different dialects create different default names
SELECT 
  COUNT(*),                    -- Row count
  COUNT(DISTINCT user_id),     -- Distinct user count
  COUNT(email),                -- Email count
  COUNT(DISTINCT email)         -- Distinct email count
FROM orders;
```

**Result varies by dialect**: 
- **PostgreSQL**: Auto-renames to `count`, `count_1`, `count_2`, `count_3` (unpredictable, hard to reference)
- **MySQL**: Uses full expression as name: `COUNT(*)`, `COUNT(DISTINCT user_id)`, `COUNT(email)`, `COUNT(DISTINCT email)` (requires quotes, hard to reference)
- **SQL Server**: Uses full expression as name: `COUNT(*)`, `COUNT(DISTINCT user_id)`, etc. (requires quotes)
- **BigQuery**: Uses generic names like `f0_`, `f1_`, `f2_`, `f3_` (completely meaningless)

**The Problem**: Even though dialects don't error, the names are:
- **Unpredictable** (PostgreSQL's `count_1`, `count_2` pattern)
- **Require quotes** (MySQL/SQL Server's `COUNT(*)` format)
- **Meaningless** (BigQuery's `f0_`, `f1_` pattern)
- **Hard to reference** in subsequent queries or code

### 3. Verbose Code from Constant Renaming

Because SQL's defaults are unusable, you're forced to add aliases everywhere:

```sql
-- SQL: Verbose, repetitive aliasing
SELECT 
  COUNT(*) AS total_orders,
  COUNT(DISTINCT user_id) AS unique_customers,
  COUNT(email) AS emails_counted,
  SUM(amount) AS total_revenue,
  AVG(amount) AS avg_order_value,
  YEAR(created_at) AS order_year,
  MONTH(created_at) AS order_month
FROM orders
GROUP BY YEAR(created_at), MONTH(created_at);
```

Every single function needs an explicit alias. This is verbose and error-prone.

### 4. Inconsistent Naming Leads to Broken Continuity

Aliases can be very useful but also create a break in continuity.  When you're forced to come up with names for each thing, continuity breaks.  Convention and consistent style gets harder to follow and enforce.

```sql
-- Developer A's query
SELECT COUNT(*) AS total FROM orders;

-- Developer B's query (different name!)
SELECT COUNT(*) AS count FROM orders;

-- Developer C's query (yet another name!)
SELECT COUNT(*) AS num_orders FROM orders;
```

Different names mean you can't reliably reference columns across queries, breaking declarative continuity.

### 5. Paren Notation Requires Quoted Identifiers

Some SQL dialects use the full expression as the column name, which includes parentheses:

```sql
-- SQL: Paren notation creates names that need quotes
SELECT 
  year(created_at),           -- → column: "year(created_at)" (needs quotes!)
  count(distinct user_id),     -- → column: "count(distinct user_id)" (needs quotes!)
  sum(amount * quantity)       -- → column: "sum(amount * quantity)" (needs quotes!)
FROM orders;
```

These names require quoted identifiers everywhere you reference them, making code harder to read and write.

---

## The Solution: Transparent, Standardized Auto-Naming

ASQL's auto-aliasing solves these problems by generating **transparent, standardized column names** that:

1. **Include context** - Names reflect what the function operates on
2. **Prevent conflicts** - Each function gets a unique name automatically
3. **Use underscores** - Clean, readable names that don't require quotes
4. **Enable declarative continuity** - Consistent naming across queries

### Example: How ASQL Handles the Same Query

```asql
-- ASQL: Auto-aliases are transparent and unique
from orders
  group by year(created_at), month(created_at) (
    #,                          -- → column: "num" (clear: row count)
    # users,                    -- → column: "num_users" (clear: distinct users)
    count(email),               -- → column: "num_email" (clear: email count)
    count(distinct email),      -- → column: "num_distinct_email" or "uniq_email" (if configured)
    sum(amount),                -- → column: "sum_amount" (clear: sum of amount)
    avg(amount),                -- → column: "avg_amount" (clear: average of amount)
    year(created_at),           -- → column: "year_created_at" (clear: year of created_at)
    month(created_at)           -- → column: "month_created_at" (clear: month of created_at)
  )
order by -sum_amount            -- Can reference auto-aliased column!
```

**Benefits**:
- ✅ **No conflicts** - Each column has a unique, meaningful name
- ✅ **Less verbosity** - No need for explicit `as` aliases
- ✅ **Clear context** - Names tell you exactly what they represent
- ✅ **No quotes needed** - Underscore notation is clean and readable
- ✅ **Declarative continuity** - Write `sum_amount` and reference `sum_amount` later

### The Bonus: Declarative Consistency

Because ASQL's auto-aliases follow predictable patterns, you can often **use the auto-alias as the function call itself**:

```asql
-- You can write the auto-alias directly!
from orders
  group by region (
    sum_amount,        -- → sum(amount) → column: "sum_amount" ✅
    avg_price,         -- → avg(price) → column: "avg_price" ✅
    num_orders,        -- → # orders → column: "num_orders" ✅
    year_created_at    -- → year(created_at) → column: "year_created_at" ✅
  )
order by -sum_amount   -- References the same column name!
```

This creates **declarative consistency**: the name you write is the name you get, with no mismatch.

### Why Underscores Instead of Parens?

ASQL uses underscores (`sum_amount`) instead of SQL's paren notation (`sum(amount)`) because:

1. **No quotes needed**: `sum_amount` is a valid identifier, while `sum(amount)` requires quotes
2. **Cleaner syntax**: Easier to read and write
3. **Consistent with analytics conventions**: Underscores are standard in analytics tooling
4. **Works everywhere**: Can be used in `order by`, `where`, `having`, etc. without quotes

```asql
-- ASQL: Clean, no quotes needed
from orders
  group by region (
    sum_amount
  )
order by -sum_amount        -- ✅ Works without quotes
where sum_amount > 1000     -- ✅ Works without quotes
```

vs.

```sql
-- SQL: Requires quotes if using paren notation
SELECT sum(amount) AS "sum(amount)"
FROM orders
ORDER BY "sum(amount)"      -- ❌ Needs quotes
WHERE "sum(amount)" > 1000  -- ❌ Needs quotes
```

---

## Mapping Table

The table below shows the proposed auto-aliasing patterns for all ASQL functions:

| Function | Auto Alias Pattern | Can Call With Auto Alias? | SQL's Default Name | Example |
|----------|-------------------|---------------------------|-------------------|---------|
| **Aggregates** |
| `sum(col)` | `sum_{col}` | ✅ | `sum` (PostgreSQL) or `SUM(col)` (MySQL/SQL Server) or `f0_` (BigQuery) | `sum(amount)` → `sum_amount` |
| `avg(col)` | `avg_{col}` | ✅ | `avg` (PostgreSQL) or `AVG(col)` (MySQL/SQL Server) or `f0_` (BigQuery) | `avg(price)` → `avg_price` |
| `min(col)` | `min_{col}` | ✅ | `min` (PostgreSQL) or `MIN(col)` (MySQL/SQL Server) or `f0_` (BigQuery) | `min(date)` → `min_date` |
| `max(col)` | `max_{col}` | ✅ | `max` (PostgreSQL) or `MAX(col)` (MySQL/SQL Server) or `f0_` (BigQuery) | `max(amount)` → `max_amount` |
| `count(*)` / `#` | `num` (or `count` if configured, or `#` if configured) | ✅ | `count` (PostgreSQL) or `COUNT(*)` (MySQL/SQL Server) or `f0_` (BigQuery) | `#` → `num` |
| `count(col)` | `num_{col}` (or `count_{col}` if configured) | ✅ | `count` (PostgreSQL) or `COUNT(col)` (MySQL/SQL Server) or `f0_` (BigQuery) | `count(email)` → `num_email` |
| `count(distinct col)` | `num_distinct_{col}` or `uniq_{col}` (configurable) | ✅ | `count` (PostgreSQL) or `COUNT(DISTINCT col)` (MySQL/SQL Server) or `f0_` (BigQuery) | `count(distinct user_id)` → `num_distinct_user_id` or `uniq_user_id` |
| `# orders` | `num_orders` | ✅ | `count` (or blank) | `# orders` → `num_orders` |
| `first(col order by ...)` | `first_{col}` | ✅ | `first` or `first(col order by ...)` | `first(order_id order by -date)` → `first_order_id` |
| `last(col order by ...)` | `last_{col}` | ✅ | `last` or `last(col order by ...)` | `last(order_id order by date)` → `last_order_id` |
| `arg_max(col1, col2)` | `arg_max_{col1}_{col2}` | ✅ | `arg_max` or `arg_max(col1, col2)` | `arg_max(order_id, date)` → `arg_max_order_id_date` |
| `arg_min(col1, col2)` | `arg_min_{col1}_{col2}` | ✅ | `arg_min` or `arg_min(col1, col2)` | `arg_min(order_id, date)` → `arg_min_order_id_date` |
| **Date Functions** |
| `year(col)` | `year_{col}` | ✅ | `year` (or `year(col)`) | `year(created_at)` → `year_created_at` |
| `month(col)` | `month_{col}` | ✅ | `month` (or `month(col)`) | `month(created_at)` → `month_created_at` |
| `week(col)` | `week_{col}` | ✅ | `week` (or `week(col)`) | `week(created_at)` → `week_created_at` |
| `day(col)` | `day_{col}` | ✅ | `day` (or `day(col)`) | `day(created_at)` → `day_created_at` |
| `quarter(col)` | `quarter_{col}` | ✅ | `quarter` (or `quarter(col)`) | `quarter(created_at)` → `quarter_created_at` |
| `hour(col)` | `hour_{col}` | ✅ | `hour` (or `hour(col)`) | `hour(created_at)` → `hour_created_at` |
| `day_of_week(col)` | `day_of_week_{col}` | ✅ | `day_of_week` (or expression) | `day_of_week(created_at)` → `day_of_week_created_at` |
| `day_of_month(col)` | `day_of_month_{col}` | ✅ | `day_of_month` (or expression) | `day_of_month(created_at)` → `day_of_month_created_at` |
| `day_of_year(col)` | `day_of_year_{col}` | ✅ | `day_of_year` (or expression) | `day_of_year(created_at)` → `day_of_year_created_at` |
| `week_of_year(col)` | `week_of_year_{col}` | ✅ | `week_of_year` (or expression) | `week_of_year(created_at)` → `week_of_year_created_at` |
| `month_of_year(col)` | `month_of_year_{col}` | ✅ | `month_of_year` (or expression) | `month_of_year(created_at)` → `month_of_year_created_at` |
| `quarter_of_year(col)` | `quarter_of_year_{col}` | ✅ | `quarter_of_year` (or expression) | `quarter_of_year(created_at)` → `quarter_of_year_created_at` |
| `date_trunc(unit, col)` | `{unit}_{col}` | ✅ | `date_trunc` (or expression) | `date_trunc("month", created_at)` → `month_created_at` |
| `days(col1 - col2)` | `days_{col1}_{col2}` | ✅ | `datediff` or `days(col1 - col2)` | `days(end_date - start_date)` → `days_end_date_start_date` |
| `weeks(col1 - col2)` | `weeks_{col1}_{col2}` | ✅ | `datediff` or `weeks(col1 - col2)` | `weeks(end_date - start_date)` → `weeks_end_date_start_date` |
| `months(col1 - col2)` | `months_{col1}_{col2}` | ✅ | `datediff` or `months(col1 - col2)` | `months(end_date - start_date)` → `months_end_date_start_date` |
| `years(col1 - col2)` | `years_{col1}_{col2}` | ✅ | `datediff` or `years(col1 - col2)` | `years(end_date - start_date)` → `years_end_date_start_date` |
| `hours(col1 - col2)` | `hours_{col1}_{col2}` | ✅ | `datediff` or `hours(col1 - col2)` | `hours(end_date - start_date)` → `hours_end_date_start_date` |
| **Window Functions** |
| `prior(col)` | `prior_{col}` | ✅ | `lag` (or expression) | `prior(revenue)` → `prior_revenue` |
| `next(col)` | `next_{col}` | ✅ | `lead` (or expression) | `next(revenue)` → `next_revenue` |
| `running_sum(col)` | `running_sum_{col}` | ✅ | `sum` (or expression) | `running_sum(amount)` → `running_sum_amount` |
| `running_avg(col)` | `running_avg_{col}` | ✅ | `avg` (or expression) | `running_avg(amount)` → `running_avg_amount` |
| `running_count(*)` | `running_num` | ✅ | `count` (or expression) | `running_count(*)` → `running_num` |
| `rolling_avg(col, n)` | `rolling_avg_{col}_{n}` | ✅ | `avg` (or expression) | `rolling_avg(revenue, 7)` → `rolling_avg_revenue_7` |
| `rolling_sum(col, n)` | `rolling_sum_{col}_{n}` | ✅ | `sum` (or expression) | `rolling_sum(amount, 30)` → `rolling_sum_amount_30` |
| `row_number()` | `row_num` | ✅ | `row_number` | `row_number()` → `row_num` |
| `rank()` | `rank` | ✅ | `rank` | `rank()` → `rank` |
| `dense_rank()` | `dense_rank` | ✅ | `dense_rank` | `dense_rank()` → `dense_rank` |
| **String Functions** |
| `upper(col)` | `upper_{col}` | ✅ | `upper` (or `upper(col)`) | `upper(name)` → `upper_name` |
| `lower(col)` | `lower_{col}` | ✅ | `lower` (or `lower(col)`) | `lower(email)` → `lower_email` |
| `length(col)` | `length_{col}` | ✅ | `length` (or `length(col)`) | `length(name)` → `length_name` |
| `trim(col)` | `trim_{col}` | ✅ | `trim` (or `trim(col)`) | `trim(input)` → `trim_input` |
| `ltrim(col)` | `ltrim_{col}` | ✅ | `ltrim` (or `ltrim(col)`) | `ltrim(input)` → `ltrim_input` |
| `rtrim(col)` | `rtrim_{col}` | ✅ | `rtrim` (or `rtrim(col)`) | `rtrim(input)` → `rtrim_input` |
| `substring(col, start, len)` | `substring_{col}` | ✅ | `substring` or `substring(col, start, len)` | `substring(email, 1, 5)` → `substring_email` |
| `replace(col, old, new)` | `replace_{col}` | ✅ | `replace` or `replace(col, old, new)` | `replace(text, "old", "new")` → `replace_text` |
| `concat(col1, col2)` | `concat_{col1}_{col2}` | ✅ | `concat` or `concat(col1, col2)` | `concat(first, last)` → `concat_first_last` |
| `string_agg(col, sep)` | `string_agg_{col}` | ✅ | `string_agg` or `string_agg(col, sep)` | `string_agg(name, ", ")` → `string_agg_name` |
| **Type Functions** |
| `cast(col AS type)` / `col::type` | `{col}_{type}` | ✅ | `cast` or `cast(col AS type)` | `amount::INTEGER` → `amount_integer` |
| **Special Functions** |
| `coalesce(col1, col2)` / `col1 ?? col2` | `coalesce_{col1}_{col2}` | ✅ | `coalesce` or `coalesce(col1, col2)` | `primary ?? secondary` → `coalesce_primary_secondary` |
| `guarantee(col, values)` | `guarantee_{col}` | ✅ | `guarantee` or `guarantee(col, values)` | `guarantee(status, [...])` → `guarantee_status` |

## Notes

- **✅ Can Call With Auto Alias**: These functions support the shorthand syntax where you can write the auto-alias directly (e.g., `sum_amount` instead of `sum(amount) as sum_amount`)
- **SQL's Default Name**: What SQL generates when no alias is provided. This varies significantly by dialect:
  - **PostgreSQL**: Uses function name, auto-renames duplicates (`count`, `count_1`, `count_2`) - unpredictable
  - **MySQL**: Uses full expression as name (`COUNT(*)`, `COUNT(DISTINCT user_id)`) - requires quotes
  - **SQL Server**: Uses full expression as name (`COUNT(*)`, `SUM(amount)`) - requires quotes
  - **BigQuery**: Uses generic names (`f0_`, `f1_`, `f2_`) - completely meaningless
  - **"or expression"** means: SQL might use either the function name OR the full expression, depending on the dialect
- **SQL's Inconsistent Naming**: When multiple functions with the same name are used without aliases:
  - **PostgreSQL**: Auto-renames to `count`, `count_1`, `count_2` (unpredictable, hard to reference)
  - **MySQL/SQL Server**: Uses full expression (`COUNT(*)`, `COUNT(DISTINCT user_id)`) - requires quoted identifiers
  - **BigQuery**: Uses generic names (`f0_`, `f1_`) - meaningless
  - **ASQL Solution**: Auto-aliasing creates predictable, meaningful names (e.g., `num`, `num_user_id`, `num_email`, `num_distinct_email`) that don't require quotes
- **Count vs Num**: ASQL uses `num` (analytics-friendly) instead of `count` (SQL word) for auto-aliases. The `#` symbol and `num` are analytics terms, while `count` is the SQL function name.

## Pattern Rules

1. **Single-arg functions**: `func(col)` → `func_col`
2. **Multi-arg functions**: `func(col1, col2)` → `func_col1_col2`
3. **Functions with parameters**: `func(col, n)` → `func_col_n`
4. **Special cases**:
   - `count(*)` / `#` → `num` (not `count` - analytics-friendly)
   - `# orders` → `num_orders` (supports `num of orders` natural language)
   - `running_count(*)` → `running_num` (see [Future Consideration: `running_num()` vs `running_count()`](../docs/spec_future.md#function-naming-consistency-running_num-vs-running_count-future-consideration))
   - `row_number()` → `row_num` (Note: `row_number()` function stays as-is; `num` here is just the auto-alias, not a rename of the function. `num` means "number of" for counts, while `row_number()` is about numbering/ranking rows.)
   - `rank()` → `rank`
   - `dense_rank()` → `dense_rank`

## Rationale

Auto-aliasing makes queries more concise and enables declarative continuity - you can write `sum_amount` and reference `sum_amount` later without needing explicit aliases. This works best for single-argument functions that follow the `func_col` pattern.

### Handling Conflicts

**SQL's Problem**: When you use multiple similar functions without aliases, SQL creates inconsistent, hard-to-reference names:
```sql
-- SQL without aliases (PROBLEMATIC)
SELECT 
  COUNT(*),                    -- PostgreSQL: "count", MySQL: "COUNT(*)", BigQuery: "f0_"
  COUNT(DISTINCT user_id),     -- PostgreSQL: "count_1", MySQL: "COUNT(DISTINCT user_id)", BigQuery: "f1_"
  COUNT(email),                -- PostgreSQL: "count_2", MySQL: "COUNT(email)", BigQuery: "f2_"
  COUNT(DISTINCT email)         -- PostgreSQL: "count_3", MySQL: "COUNT(DISTINCT email)", BigQuery: "f3_"
FROM orders;
```
- **PostgreSQL**: Auto-renames to `count`, `count_1`, `count_2`, `count_3` (unpredictable pattern)
- **MySQL/SQL Server**: Uses full expression (`COUNT(*)`) - requires quoted identifiers
- **BigQuery**: Uses generic names (`f0_`, `f1_`) - completely meaningless

**ASQL's Solution**: Auto-aliasing prevents conflicts by including column context:
```asql
-- ASQL with auto-aliasing (NO CONFLICTS)
from orders
  group by region (
    #,                          -- → column: "num"
    # users,                    -- → column: "num_users"
    count(email),               -- → column: "num_email"
    count(distinct email)       -- → column: "num_distinct_email" or "uniq_email" (if configured)
  )
```
Each gets a unique, meaningful name automatically. With `SET distinct_count_alias = "uniq"`, distinct counts use the shorter `uniq_{col}` pattern.

### Count vs Num Naming

ASQL uses `num` instead of `count` for auto-aliases because:
- **`#` and `num` are analytics-friendly terms** - more intuitive for analysts
- **`count` is a SQL word** - technical, less readable
- **Natural language support**: `num of orders` reads better than `count of orders`
- **Consistency**: `num_orders` aligns with analytics vocabulary
- **Conflict prevention**: `num`, `num_email`, `num_distinct_email` are all unique

Examples:
- `#` → `num` (not `count`, unless configured)
- `# orders` → `num_orders` (supports `num of orders` shorthand)
- `count(email)` → `num_email`
- `count(distinct email)` → `num_distinct_email` (or `uniq_email` if configured)
- `running_count(*)` → `running_num` (see [Future Consideration: `running_num()` vs `running_count()`](../docs/spec_future.md#function-naming-consistency-running_num-vs-running_count-future-consideration))

---

## Configurable Alias Rules

While ASQL provides sensible defaults for auto-aliasing, some users may want to customize the naming patterns to match their preferences or existing conventions.

### Configuration Options

Auto-aliasing behavior can be configured in two ways:

#### 1. Config File (Recommended for Project-Wide Settings)

Create `asql.config.yaml` (or `asql.config.yml`, `.asqlrc.yaml`) in your project root:

```yaml
# asql.config.yaml

# Compile settings (affect SQL generation)
compile:
  # Count alias: "num" (default), "count", or "#" (experimental)
  count_alias: "num"
  
  # Distinct count alias: "num_distinct" (default), "uniq", or "unique"
  distinct_count_alias: "num_distinct"
```

Or in JSON format (`asql.config.json`):

```json
{
  "compile": {
    "count_alias": "num",
    "distinct_count_alias": "num_distinct"
  }
}
```

#### 2. Inline SET Statements (Override for Specific Queries)

```asql
-- Override config file settings for this query
SET count_alias = "count";     -- Use "count" instead of "num"
SET count_alias = "#";         -- Use "#" as alias (experimental, may require quotes)

SET distinct_count_alias = "uniq";  -- Use "uniq" instead of "num_distinct"
SET distinct_count_alias = "unique"; -- Alternative: "unique"

-- Example with custom settings
SET count_alias = "count";
SET distinct_count_alias = "uniq";

from orders
  group by region (
    #,                          -- → column: "count" (instead of "num")
    count(distinct user_id)     -- → column: "uniq_user_id" (instead of "num_distinct_user_id")
  )
```

**Precedence**: Inline `SET` statements override config file settings for that query.

### Default vs. Custom Behavior

| Setting | Default | Alternative Options | Config File Key | Example Output |
|---------|---------|-------------------|-----------------|----------------|
| `count_alias` | `"num"` | `"count"`, `"#"` | `compile.count_alias` | `#` → `num` (default) or `count` or `#` |
| `distinct_count_alias` | `"num_distinct"` | `"uniq"`, `"unique"` | `compile.distinct_count_alias` | `count(distinct email)` → `num_distinct_email` (default) or `uniq_email` |

### Config File Location

ASQL searches for config files in the following order:
1. `asql.config.yaml` (preferred)
2. `asql.config.yml` (alternative YAML extension)
3. `.asqlrc.yaml` (hidden file alternative)

The search starts in the current directory and walks up parent directories until a config file is found. This allows project-level, directory-level, or user-level configuration.

**Example project structure**:
```
my-project/
  asql.config.yaml          # Project-wide settings
  queries/
    analysis/
      asql.config.yaml      # Override for this subdirectory
      monthly_report.asql
```

### Rationale for Configurability

1. **Team conventions**: Some teams prefer `count` over `num` for consistency with SQL
2. **Legacy compatibility**: Existing codebases may use different naming patterns
3. **Personal preference**: Some users find `uniq` more readable than `num_distinct`
4. **Experimental features**: `#` as alias allows testing edge cases (though may require quoted identifiers)

**Note**: While configurability is useful, the defaults (`num`, `num_distinct`) are recommended for:
- Better analytics readability
- Consistency with `#` symbol
- Avoiding SQL keyword conflicts

---

## Implementation Notes: `uniq()` Function and Syntax

### Proposed: `uniq()` Function as Shorthand for `count(distinct ...)`

To complement the `uniq_{col}` alias pattern, we could add a `uniq()` function as syntactic sugar for `count(distinct ...)`:

```asql
-- Proposed syntax
from orders
  group by region (
    uniq(user_id),        -- → COUNT(DISTINCT user_id) → column: "uniq_user_id"
    uniq(email),          -- → COUNT(DISTINCT email) → column: "uniq_email"
    uniq_orders           -- → COUNT(DISTINCT order_id) → column: "uniq_orders" (shorthand)
  )
```

**Benefits**:
- More concise than `count(distinct ...)`
- Aligns with the `uniq_{col}` alias pattern
- Natural language feel: "unique users" → `uniq_users`

### Proposed: `# of uniq emails` Natural Language Syntax

Extend the `#` shorthand to support natural language distinct counts:

```asql
-- Proposed syntax
from orders
  group by region (
    # of uniq users,      -- → COUNT(DISTINCT user_id) → column: "uniq_users"
    # of uniq emails,     -- → COUNT(DISTINCT email) → column: "uniq_emails"
    # uniq customers      -- → COUNT(DISTINCT customer_id) → column: "uniq_customers"
  )
```

**Benefits**:
- Natural language readability
- Consistent with `# orders` pattern
- Supports both `# of uniq X` and `# uniq X` forms

### Implementation Considerations

#### Option 1: `uniq()` Function Only

```asql
-- Add uniq() as function
uniq(col)                 -- → COUNT(DISTINCT col) → column: "uniq_col"
uniq_user_id              -- → uniq(user_id) → column: "uniq_user_id" (shorthand)
```

**Pros**: Simple, clear function name
**Cons**: Doesn't support `# of uniq` natural language

#### Option 2: `uniq()` Function + `# of uniq` Syntax

```asql
-- Both forms supported
uniq(user_id)             -- → COUNT(DISTINCT user_id) → column: "uniq_user_id"
# of uniq users           -- → COUNT(DISTINCT user_id) → column: "uniq_users"
# uniq users              -- → COUNT(DISTINCT user_id) → column: "uniq_users"
```

**Pros**: Maximum flexibility and readability
**Cons**: More parsing complexity

#### Option 3: Alias Pattern Only (No Function)

```asql
-- Only support alias pattern
count(distinct user_id)   -- → column: "uniq_user_id" (if distinct_count_alias = "uniq")
uniq_user_id              -- → count(distinct user_id) → column: "uniq_user_id" (shorthand)
```

**Pros**: No new function, just alias configuration
**Cons**: Still requires `count(distinct ...)` syntax

### Recommended Approach

**Phase 1**: Support `uniq_{col}` alias pattern via configuration
- `SET distinct_count_alias = "uniq"`
- `count(distinct email)` → `uniq_email`
- `uniq_email` shorthand → `count(distinct email)`

**Phase 2**: Add `uniq()` function (if user demand)
- `uniq(email)` → `COUNT(DISTINCT email)` → `uniq_email`
- Natural extension of alias pattern

**Phase 3**: Add `# of uniq` syntax (if user demand)
- `# of uniq users` → `COUNT(DISTINCT user_id)` → `uniq_users`
- Maximum natural language support

### Parsing Challenges

1. **`# of uniq X`**: Need to parse `uniq` as keyword in `#` context
2. **Ambiguity**: `uniq` could be column name vs. function/pattern
3. **Table inference**: `# of uniq users` needs to infer `user_id` from `users` table

### Testing Scenarios

```asql
-- Test uniq() function
from orders
  group by region (
    uniq(user_id),
    uniq(email),
    uniq_orders
  )

-- Test # of uniq syntax
from orders
  group by region (
    # of uniq users,
    # uniq customers
  )

-- Test configuration
SET distinct_count_alias = "uniq";
from orders
  group by region (
    count(distinct user_id)  -- Should produce "uniq_user_id"
  )

-- Test column precedence
-- If table has column "uniq_email", should use column, not function
from orders
  select uniq_email  -- Column takes precedence
```
