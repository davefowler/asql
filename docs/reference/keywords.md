# Keywords Reference

Complete reference of ASQL keywords and their meanings.

## Pipeline Keywords

Core keywords that structure your queries.

| Keyword | Description | SQL Equivalent |
|---------|-------------|----------------|
| `from` | Start query with table | `FROM` |
| `where` | Filter rows | `WHERE` |
| `select` | Choose columns | `SELECT` |
| `group by` | Aggregate data | `GROUP BY` |
| `order by` | Sort results | `ORDER BY` |
| `limit` | Limit row count | `LIMIT` |
| `having` | Filter after grouping | `HAVING` |

### from

Every query starts with `from`:

```asql
from users
from orders
from schema.table_name
```

### where

Filter rows based on conditions:

```asql-play
from users
  where status = "active"
  where age >= 18
```

Multiple `where` clauses are combined with AND.

### select

Choose which columns to return:

```asql-play
from users
  select name, email, created_at
```

If omitted, all columns are returned (equivalent to `SELECT *`).

### group by

Aggregate data by columns:

```asql-play
from orders
  group by customer_id (
    sum(amount) as total,
    # as count
  )
```

### order by

Sort results:

```asql
from users
  order by -created_at       -- Descending
  order by name              -- Ascending
```

### limit

Limit number of rows:

```asql-play
from users
  limit 100
```

### sample

Random sampling of rows:

```asql
from users
  sample 100              -- N random rows
  sample 10%              -- N percent of rows
  sample 5 per category   -- Stratified sampling
```

---

## Data Manipulation Keywords

| Keyword | Description | SQL Equivalent |
|---------|-------------|----------------|
| `sample` | Random sampling | `ORDER BY RANDOM() LIMIT` / `TABLESAMPLE` |
| `except` | Exclude columns | `SELECT * EXCEPT(...)` |
| `rename` | Rename columns | `col AS new_name` |
| `replace` | Replace column values | `expression AS col` |
| `pivot` | Rows to columns | `CASE WHEN ... GROUP BY` |
| `unpivot` | Columns to rows | `UNION ALL` |
| `explode` | Array to rows | `CROSS JOIN UNNEST` |

### except

Exclude columns from result:

```asql-play
from users
  except password_hash, internal_notes
```

### rename

Rename columns inline:

```asql-play
from users
  rename id as user_id, name as full_name
```

### replace

Replace column values with expressions:

```asql-play
from users
  replace name with upper(name), email with lower(email)
```

### pivot

Transform row values into columns:

```asql-play
from sales
  pivot sum(amount) by category values ('Electronics', 'Clothing')
```

### unpivot

Transform columns into rows:

```asql-play
from metrics
  unpivot jan, feb, mar into month, value
```

### explode

Expand array columns into rows:

```asql-play
from posts
  explode tags as tag
```

---

## Join Keywords

| Keyword | Description |
|---------|-------------|
| `on` | Specify join condition |
| `as` | Alias for table or column |

```asql-play
from orders
  &? users as customer on orders.customer_id = customer.id
```

---

## CTE Keywords

| Keyword | Description |
|---------|-------------|
| `stash as` | Save intermediate result as CTE |
| `set` | Compiler setting statement (not a CTE) |

### stash as

Save a pipeline step as a CTE:

```asql-play
from users
  where is_active
  stash as active_users
  group by country (# as total)
```

### set

Set compiler options (not CTE variables):

```asql
SET dialect = 'postgres';
SET week_start = 'sunday';

from orders
  group by month(created_at) ( sum(amount) as revenue )
```

#### Available Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `dialect` | string | `"duckdb"` | Target SQL dialect |
| `week_start` | string | `"monday"` | Week start day: `"monday"` or `"sunday"` |
| `relative_date_type` | string | `"timestamp"` | Type for relative dates: `"timestamp"` or `"date"` |
| `include_transpilation_comments` | bool | `false` | Add explanatory comments about ASQL transformations |
| `passthrough_comments` | bool | `true` | Preserve source comments in output |

#### Comment Settings

Control how comments appear in the generated SQL:

```asql
-- Add explanatory comments about ASQL transformations (like spine)
SET include_transpilation_comments = true;

-- Strip all source comments from output
SET passthrough_comments = false;

from orders
  spine by month(order_date) ( sum(amount) as revenue )
```

When `include_transpilation_comments` is enabled, the generated SQL includes helpful comments explaining complex transformations:

```sql
/* ASQL spine: Gap-filling CTEs were generated to ensure all 
   expected time periods appear (even with zero/null aggregates). */
WITH month_order_date_spine AS (...)
...
```

### spine

Gap-filling transform. Use `spine by` as a transform or `spine()` within `group by`:

```asql
-- spine by: full spine transform
from orders
  spine by month(order_date) ( sum(amount) as revenue )

-- spine() in group by: selective spine
from orders
  group by spine(month(order_date)), region ( sum(amount) as revenue )
```

See [Spine (Gap-Filling)](../group_by.md#spine-gap-filling) for details.

---

## Window Keywords

| Keyword | Description |
|---------|-------------|
| `per` | Define partition for window operation |
| `by` | Specify ordering in window context |
| `first` | Keep first row per partition |
| `last` | Keep last row per partition |
| `number` | Add row number |
| `rank` | Add rank |
| `dense rank` | Add dense rank |
| `qualify` | Filter on window function result |

### per

Define partition for window operations:

```asql-play
from orders
  per customer_id first by -order_date
```

### qualify

Filter on window function results:

```asql
from orders
  select *, row_number() over (...) as rn
  qualify rn = 1
```

---

## Logical Keywords

| Keyword | Description |
|---------|-------------|
| `and` | Logical AND |
| `or` | Logical OR |
| `not` | Logical NOT |
| `in` | Membership test |
| `is` | Null check / equality |
| `between` | Range check |

```asql
where status = "active" and not is_deleted
where status in ("a", "b", "c")
where email is not null
where amount between 100 and 1000
```

---

## Conditional Keywords

| Keyword | Description |
|---------|-------------|
| `when` | Start conditional expression |
| `then` | Result for condition |
| `otherwise` | Default result |
| `else` | Alias for otherwise |

```asql
select
  when status
    is "active" then "Active"
    is "pending" then "Pending"
    otherwise "Unknown"
  as label
```

---

## Aggregate Keywords

| Keyword | Description |
|---------|-------------|
| `distinct` | Unique values only |
| `as` | Alias for result |
| `of` | Natural language connector |

```asql
count(distinct user_id)
sum(amount) as revenue
average of price
```

---

## Special Keywords

| Keyword | Description |
|---------|-------------|
| `distinct on` | PostgreSQL-style deduplication |
| `over` | Window frame specification |
| `partition by` | Window partition |
| `rows` | Window frame rows |

```asql-play
from orders
  distinct on (customer_id)
  order by customer_id, -order_date
```

```asql
select sum(amount) over (partition by region order by date)
```

---

## Reserved Words

These words have special meaning and cannot be used as unquoted identifiers:

- `from`, `where`, `select`, `group`, `by`, `order`, `limit`
- `and`, `or`, `not`, `in`, `is`, `between`
- `as`, `on`, `join`
- `when`, `then`, `else`, `otherwise`
- `stash`, `set`
- `per`, `first`, `last`, `number`, `rank`
- `qualify`, `over`, `partition`, `rows`
- `sample`, `except`, `rename`, `replace`, `with`
- `pivot`, `unpivot`, `explode`, `into`, `values`

To use a reserved word as an identifier, quote it:

```asql-play
from "order"        -- Table named 'order'
select "select"     -- Column named 'select'
```

---

## See Also

- **[Pipeline Basics](../syntax/pipeline.md)** — Using pipeline keywords
- **[Operators Reference](operators.md)** — All operators
- **[Functions Reference](functions.md)** — All functions
