# ASQL: Future Features & Considerations

This document contains features that are planned for future implementation, under consideration, or marked as "maybe" for v1.0.

**Note**: Features in this document are NOT implemented. See `docs/spec.md` for the current specification of implemented features.

---

---

## FK Dot Notation (Future Consideration)

ASQL may add support for automatic join traversal using FK dot notation:

**Tracking**: Not yet tracked

```asql
-- Proposed syntax
from orders
  select 
    orders.amount,
    orders.user.name,       -- Auto-joins via user_id → users.id
    orders.user.email       -- Same join, different column

-- Would compile to:
SELECT 
  orders.amount,
  user_1.name,
  user_1.email
FROM orders
LEFT JOIN users AS user_1 ON orders.user_id = user_1.id
```

### How It Would Work

1. **Pattern detection**: Preparser detects `table.fk.column` patterns where `fk` matches a `{name}_id` column
2. **Schema lookup**: Uses the relationship map to find the target table
3. **Auto-join generation**: Injects LEFT JOIN with appropriate ON clause
4. **Alias deduplication**: Multiple references to same FK reuse the same join

### Key Features

- **Convention-based**: `{name}_id` enables `.{name}.` traversal without configuration
- **Schema-aware**: Explicit relationships in schema take precedence over conventions
- **Chained traversal**: `order_items.order.user.name` traverses multiple relationships
- **LEFT JOIN default**: FK might be NULL, so outer join is safer default

### Current Workaround

Use explicit joins:

```asql
-- Instead of: from orders select orders.user.name
from orders &? users on orders.user_id = users.id
  select users.name
```

### Why Not Implemented Yet

- **Preparser complexity**: Requires detecting column patterns before SQL generation
- **Alias management**: Need to track generated aliases to avoid duplicates
- **Schema dependency**: Most useful with schema information (which is now available)

**Priority**: Medium - useful but explicit joins work well. May implement after schema support is fully tested.

---

## Database Schema Introspection (Future Consideration)

ASQL may add database introspection to auto-generate `asql_schema.yml` from a live database connection.

**Tracking**: Not yet tracked

```python
# Proposed CLI usage
asql introspect postgresql://user:pass@host/db --output asql_schema.yml

# Proposed Python API
from asql.schema import Schema
schema = Schema.from_database("postgresql://user:pass@host/db")
schema.to_yaml("asql_schema.yml")
```

### What It Would Extract

1. **Tables and columns**: Names, types, primary keys
2. **Foreign keys**: Explicit FK constraints from database metadata
3. **Inferred relationships**: Convention-based (`{name}_id` → `{names}.id`)

### Generated Output

```yaml
# asql_schema.yml (auto-generated)
tables:
  orders:
    columns: [id, user_id, amount, created_at]
  users:
    columns: [id, name, email]
    
relationships:
  # Explicit FK from database
  - from: orders.user_id
    to: users.id
    alias: user
    source: explicit
  
  # Inferred from naming convention
  - from: orders.customer_id
    to: customers.id
    alias: customer
    source: inferred
```

### Current Workaround

Manually create `asql_schema.yml` or use dbt's `schema.yml` files.

**Priority**: Low - most users have dbt or can manually define schemas. Introspection is a convenience feature.

---


## Ternary-Style Conditionals (Future Consideration)

ASQL may add support for concise ternary expressions in the future:

**Tracking**: [#28](https://github.com/davefowler/asql/issues/28)

```asql
-- Potential future syntax (not yet decided)
amount == 0 ? null : amount           -- JS-style
null if amount == 0 else amount       -- Python-style
```

**Current**: Use ASQL `when` (or SQL `CASE WHEN ... THEN ... ELSE ... END`):
```asql
CASE WHEN amount == 0 THEN NULL ELSE amount END
```

**Priority**: Low - `when` syntax is already clear and readable. Ternary expressions are syntactic sugar.

---


## Shorthand Natural Language (50/50 on implementation)

For very simple exploratory queries, you can omit the `from` clause and infer it from the aggregation:

**Tracking**: [#40](https://github.com/davefowler/asql/issues/40)

```asql
# of Users by country
Sum of revenue by region
Avg Users.age by country
```

**Note**: This shorthand is nice for a big percentage of exploratory queries, but it's different from other queries that start with `from`. In these examples, the `from` table is inferred from its use in `# of Users`. It's really nice shorthand, but also potentially confusing.

**Status**: Marked as 50/50 on implementation - may or may not make it into v1.0.

**Pros**:
- Very concise for exploratory queries
- Natural language feel

**Cons**:
- Different syntax from other queries
- Potentially confusing
- Requires inference logic

---


## Future Considerations

These are broader ideas that may or may not be implemented:

- **Visual SQL Editor**: ASQL's structure could enable a great visual query builder whose base could also be a text editor/IDE. Get the best of visual and text-based exploration.
- **dbt Integration**: Building ASQL into dbt out of the gate would make it immediately useful for the dbt community
- **Common Schema Format**: A shared schema/statistics library for cross-database compatibility
- **Query Optimization**: ASQL-specific optimizations before SQL generation
- **IDE Integration**: Full-featured editor with autocomplete, error checking, SQL preview
- **Testing Framework**: Query testing and validation tools

---

## Safe casting (`::type?`) (Future Consideration)

ASQL may add “safe cast” syntax that returns `NULL` on cast failure.

### Why it exists
- Dialects differ (`TRY_CAST`, `SAFE_CAST`, etc.)
- Real data often contains non-castable values (`\"N/A\"`, empty strings, mixed types)

### Proposed syntax

```asql
select value::integer? as value_int
select value::integer? ?? 0 as value_int
```

### Current
Use strict casts (`value::integer`) and/or dialect-specific SQL (`TRY_CAST`, `SAFE_CAST`) directly.

---

## Safe divide (`/?`) (Future Consideration)

ASQL may add a safe divide operator where divide-by-zero yields `NULL` (i.e., the result is “not required”).

### Proposed syntax

```asql
4 /? 3     -- normal division
4 /? 0     -- NULL (safe-divide)
```

### Current
Use SQL `CASE` / `NULLIF` patterns directly, e.g. `a / NULLIF(b, 0)` (dialect dependent).

---

## Table sources: `series(...)` / `date_spine(...)` (Future Consideration)

ASQL may add table-producing functions that can be used directly in `from`:

```asql
from series(1, 100)
from date_spine(start = @2024-01-01, end = @2024-12-31, grain = day)
```

**Why it exists**: Sometimes you want to generate rows without an existing source table (numbers/date dimension).

**Current**: Prefer compiler `auto_spine` (gap-filling for grouped date dimensions) where applicable, or use warehouse-native generators in raw SQL.

---

## Union relations: `from union(t1, t2, ...)` (Future Consideration)

ASQL may add a convenience table source for unioning a list of relations:

```asql-play
from union(users_2022, users_2023, users_2024)
```

Open design questions:
- schema alignment vs “union all as-is”
- `fill_missing = null` behavior
- dialect differences

---

## `slugify(expr)` (Future Consideration)

ASQL may add a helper to convert strings to URL-friendly slugs:

**Tracking**: [#64](https://github.com/davefowler/asql/issues/64)

```asql
select slugify(name) as slug
```

Open design questions:
- dialect portability (regex replace differences)
- unicode normalization behavior

---

## Universal Auto-Aliasing for All Aggregates (Future Consideration)

ASQL may implement automatic column aliasing for all aggregate and transformation functions, enabling declarative continuity where the function call syntax matches the output column name.

**Tracking**: [#65](https://github.com/davefowler/asql/issues/65)

### Proposed Behavior

When any aggregate or transformation function is used without an explicit `as` alias, ASQL would automatically generate a column name following predictable patterns:

```asql
-- Current (requires explicit aliases)
from orders
  group by customer_id (
    sum(amount) as total_spent,
    first(order_id order by -order_date) as latest_order,
    # as order_count
  )

-- Future (auto-aliases)
from orders
  group by customer_id (
    sum(amount),                    -- → column: sum_amount
    first(order_id order by -order_date),  -- → column: first_order_id
    #                                -- → column: num (analytics-friendly)
    # orders                         -- → column: num_orders
  )
order by -sum_amount                -- Can reference auto-aliased column
```

### Benefits

- **Declarative continuity**: Write `sum_amount` and reference `sum_amount` - no mismatch
- **Less verbosity**: Fewer `as` clauses needed
- **Consistency**: All functions follow the same pattern
- **Shorthand integration**: Auto-aliases work seamlessly with underscore shorthand syntax

### Design Considerations

1. **Pattern**: `func(col)` → `func_col` for single-arg functions
2. **Multi-arg functions**: May require explicit aliases (e.g., `concat(col1, col2)`)
3. **Complex expressions**: Functions with expressions (e.g., `sum(amount * quantity)`) may require explicit aliases
4. **Backward compatibility**: Explicit `as` aliases would still work and override auto-aliases
5. **Shorthand support**: Functions that support shorthand (like `sum_amount`) already work - this extends the pattern

### Current

Most aggregates require explicit `as` aliases. Shorthand forms like `sum_amount` already work and create columns with matching names.

---

## Date Aggregate Convention: Dropping `_at` Suffix (Future Consideration)

ASQL may add a convention where date aggregates on columns ending in `_at` can optionally drop the `_at` suffix for brevity.

### Proposed syntax

```asql
-- Current (always works)
month_created_at  -- → month(created_at)
year_updated_at   -- → year(updated_at)

-- Future (optional shorthand)
month_created     -- → month(created_at) (infers _at suffix)
year_updated      -- → year(updated_at) (infers _at suffix)
```

### Rationale

- **Convention-based**: Columns ending in `_at` are almost always timestamps
- **Brevity**: Shorter syntax for common patterns
- **Readability**: `month_created` reads naturally

### Open design questions

- Should this only work for columns ending in `_at`, or also `_date`, `_time`?
- What if both `created_at` and `created` exist? (prefer explicit)
- Should this be opt-in via config, or always available?
- Does this apply to all date functions (`year`, `month`, `day`, `date`, `date_trunc`, etc.)?

### Current

Use explicit column names: `month_created_at`, `year_updated_at`, etc.

---

## Function Naming Consistency: `running_num` vs `running_count` (Future Consideration)

ASQL may rename `running_count()` to `running_num()` for consistency with the `num` naming convention used for count auto-aliases.

**Current**: `running_count(*)` → column: `running_count` (or `running_num` if auto-aliased)

**Proposed**: `running_num(*)` → column: `running_num`

### Rationale

- **Consistency**: If `#` → `num` and `count(*)` → `num`, then `running_count(*)` should be `running_num(*)`
- **Analytics-friendly**: `num` is more analytics-friendly than `count`
- **Declarative continuity**: `running_num` matches the auto-alias pattern `running_num`

### Current Behavior

```asql
-- Current syntax
from orders
  select running_count(*) as row_num
```

### Proposed Behavior

```asql
-- Future syntax
from orders
  select running_num(*) as row_num
  -- Or with auto-aliasing:
  select running_num(*)  -- → column: running_num
```

### Migration Considerations

- **Backward compatibility**: `running_count()` could remain as an alias for `running_num()`
- **Deprecation path**: Support both, document `running_count` as deprecated
- **Auto-aliasing**: If auto-aliasing is implemented, `running_count(*)` would auto-alias to `running_num` anyway

### Related Functions

This could also apply to:
- `running_count(*)` → `running_num(*)`
- Consider if `count()` function itself should have a `num()` alias (probably not, as `count()` is standard SQL)

**Status**: Under consideration - would improve consistency but requires breaking change or careful migration path.

---

## Preset Alias Templates (Future Consideration)

ASQL may provide preset alias templates as shortcuts for common naming conventions, allowing users to quickly apply standard styles without writing custom templates.

**Proposed syntax**:

```yaml
# asql.config.yaml
compile:
  alias_preset: "snake_case"  # or "camelCase", "UPPER_SNAKE", "PascalCase"
```

**Available presets** (proposed):

| Preset | Template | Example Output |
|--------|----------|----------------|
| `snake_case` | `{prefix}_{col}` | `sum_amount`, `num_orders` |
| `camelCase` | `{prefix|title}{col|title}` | `SumAmount`, `NumOrders` |
| `UPPER_SNAKE` | `{prefix|upper}_{col|upper}` | `SUM_AMOUNT`, `NUM_ORDERS` |
| `PascalCase` | `{prefix|title}{col|title}` | `SumAmount`, `NumOrders` |
| `lower_snake` | `{prefix|lower}_{col|lower}` | `sum_amount`, `num_orders` |

**Benefits**:
- Quick setup for common conventions
- Shareable styles across projects
- Less configuration needed for standard cases
- Can still override individual functions if needed

**Implementation**:
- Preset sets `alias_template` automatically
- Can be overridden by explicit `alias_template` setting
- Function-specific templates still take precedence

**Status**: Future consideration - nice-to-have convenience feature, not critical for initial implementation.

---

## Reusable Column Aliases (Future Consideration)

ASQL may add support for referencing column aliases within the same SELECT clause and subsequent clauses, eliminating one of SQL's most frustrating limitations.

**Tracking**: [Issue #83](https://github.com/davefowler/asql/issues/83)

### Motivation

Standard SQL doesn't allow referencing an alias defined in the same SELECT clause. This forces verbose patterns:

```sql
-- Standard SQL: Must repeat the expression or use subquery/CTE
SELECT 
    unit_price * (1 - discount) AS discount_price,
    unit_price * (1 - discount) * quantity AS total_price,  -- repeated!
    unit_price * (1 - discount) * quantity * (1 + tax_rate) AS taxed_price  -- repeated again!
FROM order_items
```

DuckDB solved this elegantly by allowing alias reuse.

### DuckDB Reference

```sql
SELECT
    unit_price * (1 - discount) AS discount_price,
    discount_price * quantity AS total_price,  -- reuses discount_price!
    total_price * (1 + tax_rate) AS taxed_price  -- reuses total_price!
FROM order_items
WHERE taxed_price > 100;  -- can filter on derived column!
```

### Proposed ASQL Syntax

```asql
from order_items
  select
    unit_price * (1 - discount) as discount_price,
    discount_price * quantity as total_price,
    total_price * (1 + tax_rate) as taxed_price
  where taxed_price > 100
```

### Benefits

- **DRY principle**: Define expression once, reference by name
- **Readability**: Shows logical dependency between columns
- **Maintainability**: Change expression in one place
- **Fewer errors**: No risk of updating one copy but not another

### Implementation Approach

1. **DuckDB target**: Emit directly (native support)
2. **Other dialects**: Auto-generate CTE chain or subquery wrapping:

```sql
-- Generated for non-DuckDB dialects
WITH _step1 AS (
  SELECT *, unit_price * (1 - discount) AS discount_price FROM order_items
),
_step2 AS (
  SELECT *, discount_price * quantity AS total_price FROM _step1
),
_step3 AS (
  SELECT *, total_price * (1 + tax_rate) AS taxed_price FROM _step2
)
SELECT * FROM _step3 WHERE taxed_price > 100
```

### Open Design Questions

1. **Detection**: How to detect alias references vs column names? Need to track defined aliases
2. **Order dependency**: Aliases can only reference earlier aliases (same row, left-to-right)
3. **Circular references**: Must detect and error on `a as b, b as a`
4. **WHERE/HAVING**: Should alias references work in WHERE? (DuckDB allows this)
5. **Performance**: CTE chain for non-DuckDB may have performance implications

### Current Workaround

Use explicit CTEs or ASQL's `with` clause:

```asql
from order_items
  select *, unit_price * (1 - discount) as discount_price
with discount_price * quantity as total_price
with total_price * (1 + tax_rate) as taxed_price
  where taxed_price > 100
```

Or repeat expressions (error-prone).

**Priority**: High - Addresses a major SQL pain point. Very high value for analytics workflows with chained calculations.

---

## ASOF JOIN (Future Consideration)

ASQL may add support for ASOF joins, which join on the nearest preceding key value. This is essential for time-series analytics.

**Tracking**: Not yet tracked

### Motivation

Time-series data often requires joining records based on "as of" semantics - finding the most recent value before a given timestamp. Common use cases:
- Financial trades matched with the latest quote
- IoT sensor readings matched with configuration changes
- Event streams matched with state snapshots

Standard SQL requires complex window functions or correlated subqueries to achieve this.

### DuckDB Reference

```sql
SELECT *
FROM trades
ASOF JOIN quotes
ON trades.symbol = quotes.symbol
AND trades.timestamp >= quotes.timestamp;
```

Gets the most recent quote as of each trade time.

### Proposed ASQL Syntax

**Option 1: Explicit ASOF keyword**

```asql
from trades
  asof join quotes on symbol 
    and trades.timestamp >= quotes.timestamp
```

**Option 2: ASOF modifier on regular join**

```asql
from trades
  & quotes on symbol asof timestamp  -- implicit >= semantics
```

**Option 3: ASOF as join operator**

```asql
from trades
  &~ quotes on symbol, timestamp  -- &~ as "asof join" operator
```

### Benefits

- **Time-series analytics**: Essential for finance, IoT, event streams
- **Cleaner syntax**: Replaces complex window function patterns
- **Performance**: Database can optimize ASOF joins better than equivalent SQL

### Open Design Questions

1. **Operator syntax**: Should we use a new join operator (`&~`) or keyword (`asof join`)?
2. **Implicit semantics**: Should `asof timestamp` imply `>=` or require explicit comparison?
3. **Multiple columns**: How to handle ASOF on multiple time columns?
4. **Dialect support**: DuckDB has native support; other dialects need window function fallback
5. **Direction**: Support both "as of before" (`>=`) and "as of after" (`<=`)?

### Current Workaround

Use window functions with explicit logic:

```asql
from trades
  &? quotes on trades.symbol = quotes.symbol
    and quotes.timestamp <= trades.timestamp
  per trades.id first by -quotes.timestamp
```

Or use raw SQL with correlated subquery.

**Priority**: Medium-High - Very valuable for time-series use cases (finance, IoT, event analytics).

---

## List Comprehensions / Array Transformations (Future Consideration)

ASQL may add Python-style list comprehensions for transforming array columns.

**Tracking**: [Issue #82](https://github.com/davefowler/asql/issues/82)  
**Research**: See [ai_notes/archive/research/list-comprehensions-research.md](../ai_notes/archive/research/list-comprehensions-research.md) for detailed analysis.

### Proposed Syntax

```asql
from events
  select [lower(tag) for tag in tags] as normalized_tags

from data
  select [x * 2 for x in numbers if x > 0] as doubled
```

### Dialect Support

| Dialect | Strategy | SQLGlot Help? |
|---------|----------|---------------|
| DuckDB | Pass through (native) | ✅ |
| BigQuery | `ARRAY(SELECT ... FROM UNNEST(...))` | ✅ |
| Postgres | `ARRAY(SELECT ... FROM UNNEST(...))` | ✅ |
| Snowflake | `ARRAY_AGG(...) + FLATTEN` | ❌ Custom needed |
| MySQL | Not supported (no arrays) | N/A |

### Implementation Notes

- **Postgres-style is portable** for most dialects: `ARRAY(SELECT expr FROM UNNEST(arr) AS var)`
- **SQLGlot transpiles correctly** for DuckDB/BigQuery/Postgres
- **Snowflake requires custom handling** - SQLGlot generates invalid syntax
- **Preparser needs dialect awareness** (like pivot) for Snowflake support

### Benefits

- Clean syntax for array transformations
- Useful for JSON/nested data structures
- Familiar to Python users

**Priority**: Medium - valuable for semi-structured data but not critical for most analytics.

---

## Dynamic Column Selection: `columns matching` (Future Consideration)

ASQL may add pattern-based column selection for working with wide tables that follow naming conventions.

**Tracking**: Not yet tracked

### Motivation

Wide tables often have columns following naming patterns (e.g., `sales_q1`, `sales_q2`, `amount_usd`, `amount_eur`). Selecting or transforming these requires tedious enumeration. DuckDB's `COLUMNS()` expression solves this elegantly.

### DuckDB Reference

```sql
-- Select columns matching regex
SELECT COLUMNS('.*_id') FROM orders;

-- Apply function to matching columns
SELECT COLUMNS('sales_.*')::DECIMAL(10,2) FROM quarterly_data;

-- With lambda for transformation
SELECT COLUMNS(c -> c LIKE '%_amount')::INT FROM payments;
```

### Proposed ASQL Syntax

```asql
# Select columns matching a pattern
from quarterly_data
  select columns matching 'sales_*'

# With alias grouping
from events
  select columns matching '*_at' as timestamps

# Apply transformations to matching columns
from dirty_data
  select columns matching 'amount_*' :: decimal(10,2)

# Exclude pattern (inverse matching)
from users
  select * except columns matching '*_internal'
```

### Benefits

- **ETL workflows**: Easily select/transform groups of related columns
- **Wide tables**: Work with tables that have 50+ columns following conventions
- **Schema evolution**: Queries automatically include new columns matching the pattern
- **Less repetition**: No need to enumerate `sales_q1, sales_q2, sales_q3, sales_q4`

### Open Design Questions

1. **Pattern syntax**: Use glob patterns (`sales_*`) or regex (`sales_.*`)? Glob is simpler but regex is more powerful
2. **Transformation syntax**: How to apply functions to matched columns? `:: type` for casts, but what about `upper()` or other functions?
3. **Alias handling**: What happens when you alias a pattern match? Create array? Struct? Just document column names?
4. **Dialect support**: DuckDB has native `COLUMNS()`, but other dialects would need column enumeration at compile time (requires schema)
5. **Interaction with `except`**: Should `except columns matching 'pattern'` be supported?

### Current Workaround

Explicitly list all columns:

```asql
from quarterly_data
  select sales_q1, sales_q2, sales_q3, sales_q4
```

Or use `select *` and filter in downstream processing.

**Priority**: Medium-High - Very useful for ETL and analytics on wide tables, but requires schema awareness for non-DuckDB dialects.

---

## Pipe Syntax Standard Alignment (Future Consideration)

ASQL may adopt compatibility with the emerging SQL pipe syntax standard used by BigQuery, Spark/Databricks, and (with variation) Snowflake. This would position ASQL as a **multi-dialect transpiler for pipe syntax**, allowing users to write the emerging standard and deploy anywhere.

**Tracking**: Not yet tracked  
**Research**: See [ai_notes/archive/research/pipe-syntax-adoption-analysis.md](../ai_notes/archive/research/pipe-syntax-adoption-analysis.md)

### Background

In 2024-2025, major platforms independently converged on nearly identical pipe syntax:

| Platform | Operator | Status | Reference |
|----------|----------|--------|-----------|
| BigQuery | `\|>` | GA (Feb 2025) | [VLDB 2024 paper](https://www.vldb.org/pvldb/vol17/p4051-shute.pdf) |
| Spark/Databricks | `\|>` | Available (v4.0) | [Databricks docs](https://docs.databricks.com/sql/language-manual/sql-ref-syntax-qry-pipeline) |
| Snowflake | `->>` | Available (May 2025) | Different operator, similar concept |
| ASQL | newline / `\|` | Current | Implicit piping |

This convergence validates ASQL's FROM-first, pipeline-based design. Rather than competing, ASQL can embrace this standard while adding value through multi-dialect transpilation.

### Strategy: Accept Pipe Syntax as Input Aliases

ASQL would accept pipe syntax operators as **aliases** for existing ASQL features, enabling users familiar with BigQuery/Spark to use ASQL immediately.

### Proposed Additions

#### 1. Accept `|>` Operator (Alias)

The `|>` operator would be accepted and effectively ignored (ASQL already uses newlines or `|` for pipelining).

```asql
# These would be equivalent:
from orders |> where status = 'active' |> select id, total

from orders
  where status = 'active'
  select id, total
```

**Implementation**: Lexer treats `|>` as whitespace/newline equivalent.

#### 2. `drop` as Alias for `except`

Pipe syntax uses `DROP` to remove columns. ASQL would accept `drop` as an alias for `except`.

```asql
# Pipe syntax style
from users
  drop ssn, internal_notes

# Current ASQL style (remains valid)
from users
  except ssn, internal_notes
```

**Implementation**: Parser treats `drop` as synonym for `except` when followed by column list.

**Note**: Context distinguishes from SQL `DROP TABLE`. In ASQL pipeline context, `drop` operates on columns.

#### 3. `aggregate` as Alternative Aggregation Syntax

Pipe syntax uses `AGGREGATE ... GROUP BY`. ASQL would accept this as alternative to inline `group by (agg)` syntax.

```asql
# Pipe syntax style
from orders
  aggregate 
    sum(total) as revenue,
    count(*) as order_count
  group by region

# Current ASQL style (remains valid)
from orders
  group by region (
    sum(total) as revenue,
    count(*) as order_count
  )
```

**Implementation**: Parser accepts `aggregate ... group by` pattern and transforms to ASQL's internal representation.

**Note**: Both syntaxes would be valid. The inline `group by col (agg)` style remains recommended for ASQL as it's more compact.

#### 4. `extend` Keyword for Adding Columns

Pipe syntax uses `EXTEND` to add columns while keeping all existing ones. This is cleaner than `select *, expr as col`.

```asql
from sales
  extend revenue - cost as profit
  extend profit / revenue as margin

# Equivalent to (but cleaner than):
from sales
  select *, revenue - cost as profit
  select *, profit / revenue as margin
```

**Key behavior**: 
- `extend` implicitly includes all existing columns (like `select *`)
- Multiple `extend` statements can chain, each seeing columns from previous extends
- This naturally enables column reuse (see "Reusable Column Aliases" section)

**Implementation**: 
- `extend expr as col` → `select *, expr as col`
- With column reuse feature, later extends can reference earlier ones

**Value**: High - significantly cleaner for incremental column creation.

### Operators NOT Being Added

#### `SET` - Intentionally Omitted

Pipe syntax uses `SET col = expr` to modify existing columns. ASQL intentionally does **not** adopt this keyword because:

1. **Term overloading**: `SET` has strong associations with SQL `UPDATE` statements and variable assignment
2. **ASQL already has `replace`**: The `replace col with expr` syntax serves this purpose
3. **Semantic clarity**: `replace` makes it clear you're replacing a column's definition

```asql
# ASQL's existing syntax (preferred)
from products
  replace price with price * 1.10

# NOT adding:
# from products
#   set price = price * 1.10  -- Rejected: too similar to UPDATE semantics
```

### Compatibility Matrix

| Pipe Syntax | ASQL Alias | ASQL Native | Status |
|-------------|------------|-------------|--------|
| `\|>` | Accept & ignore | newline / `\|` | 📋 Planned |
| `WHERE` | N/A | `where` | ✅ Already compatible |
| `SELECT` | N/A | `select` | ✅ Already compatible |
| `DROP` | `drop` | `except` | 📋 Planned alias |
| `RENAME` | N/A | `rename` | ✅ Already identical |
| `EXTEND` | `extend` | `select *, expr` | 📋 Planned |
| `SET` | ❌ Not adding | `replace col with expr` | ❌ Intentionally omitted |
| `AGGREGATE ... GROUP BY` | `aggregate ... group by` | `group by col (agg)` | 📋 Planned alias |
| `ORDER BY` | N/A | `order by` | ✅ Already compatible |
| `LIMIT` | N/A | `limit` | ✅ Already compatible |
| `DISTINCT` | N/A | `distinct` | ✅ Already compatible |
| `JOIN` | N/A | `join` / `&` | ✅ Already compatible |
| `TABLESAMPLE` | N/A | `sample` | ✅ Already compatible |
| `PIVOT` / `UNPIVOT` | N/A | `pivot` / `unpivot` | ✅ Already compatible |

### Output Mode: Emit Pipe Syntax

When targeting BigQuery or Spark, ASQL could optionally emit native pipe syntax for better readability of generated SQL.

```asql
# Input
from orders
  where status = 'completed'
  except internal_notes
  group by region (sum(total) as revenue)
  order by -revenue
```

```sql
-- Output for BigQuery (with pipe syntax mode)
FROM orders
|> WHERE status = 'completed'
|> DROP internal_notes
|> AGGREGATE SUM(total) AS revenue GROUP BY region
|> ORDER BY revenue DESC
```

**Implementation**: Add `--emit-pipe-syntax` flag or config option for BigQuery/Spark targets.

### Benefits

1. **Industry alignment**: Users familiar with BigQuery/Spark pipe syntax can use ASQL immediately
2. **Knowledge transfer**: Skills learned in ASQL transfer to native platforms and vice versa
3. **Polyfill capability**: ASQL brings pipe syntax to databases that don't support it natively (Postgres, MySQL, SQLite)
4. **dbt integration**: ASQL could preprocess pipe syntax in dbt models, compiling to any warehouse
5. **Future-proofing**: If pipe syntax becomes ISO standard, ASQL is already compatible

### Migration Path

1. **Phase 1**: Accept `|>`, `drop`, `extend` as aliases (input compatibility)
2. **Phase 2**: Add `aggregate ... group by` alternative syntax
3. **Phase 3**: Optional pipe syntax output for BigQuery/Spark targets
4. **Phase 4**: Documentation positioning ASQL as "Pipe Syntax for Every Database"

### Related Features

- **Reusable Column Aliases**: Enables `extend` chaining to reference earlier columns
- **Replace Syntax**: ASQL's `replace col with expr` covers pipe syntax's `SET` use case

**Priority**: High - Industry alignment with major platforms. Low implementation complexity (mostly parser aliases).

---

**See Also**:
- `docs/spec.md` - Current specification of implemented features
- GitHub issues - Work tracked as issues when prioritized
