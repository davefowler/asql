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

```asql
from users
  where status = "active"
  where age >= 18
```

Multiple `where` clauses are combined with AND.

### select

Choose which columns to return:

```asql
from users
  select name, email, created_at
```

If omitted, all columns are returned (equivalent to `SELECT *`).

### group by

Aggregate data by columns:

```asql
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

```asql
from users
  limit 100
```

---

## Join Keywords

| Keyword | Description |
|---------|-------------|
| `on` | Specify join condition |
| `as` | Alias for table or column |

```asql
from orders
  &? users as customer on orders.customer_id = customer.id
```

---

## CTE Keywords

| Keyword | Description |
|---------|-------------|
| `stash as` | Save intermediate result as CTE |
| `set` | Define top-level CTE |

### stash as

Save a pipeline step as a CTE:

```asql
from users
  where is_active
  stash as active_users
  group by country (# as total)
```

### set

Define a named CTE at the top level:

```asql
set active = from users where is_active

from active
  group by country (# as total)
```

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

```asql
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

```asql
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

To use a reserved word as an identifier, quote it:

```asql
from "order"        -- Table named 'order'
select "select"     -- Column named 'select'
```

---

## See Also

- **[Pipeline Basics](../syntax/pipeline.md)** — Using pipeline keywords
- **[Operators Reference](operators.md)** — All operators
- **[Functions Reference](functions.md)** — All functions
