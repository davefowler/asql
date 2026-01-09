# Pivot, Unpivot & Explode

ASQL provides operators for reshaping data between wide and long formats, and for expanding arrays into rows.

## Pivot — Rows to Columns

Transform row values into columns. Use when you have data in "long" format and want it "wide".

### Basic Syntax

```asql-play
from sales
  pivot sum(amount) by category values ('Electronics', 'Clothing', 'Food')
```

This creates columns `Electronics`, `Clothing`, and `Food` with the sum of amounts for each category.

### How It Works

1. You specify the **value expression** (what goes in the cells)
2. You specify the **pivot column** (which becomes column headers)
3. You specify the **values** (the specific values to become columns)

### With Aggregation

```asql-play
from orders
  pivot sum(amount) by status values ('pending', 'shipped', 'delivered')
  group by customer_id
```

Generates:

```sql
SELECT customer_id,
  SUM(CASE WHEN status = 'pending' THEN amount END) AS pending,
  SUM(CASE WHEN status = 'shipped' THEN amount END) AS shipped,
  SUM(CASE WHEN status = 'delivered' THEN amount END) AS delivered
FROM orders
GROUP BY customer_id
```

### Without Aggregation (MAX)

When no aggregate function is specified, MAX is used:

```asql-play
from user_settings
  pivot value by setting_name values ('theme', 'language', 'timezone')
  group by user_id
```

### Example: Custom Fields (EAV Tables)

Many SaaS platforms store custom fields in Entity-Attribute-Value format:

```
| issue_id | field_name | field_value |
|----------|------------|-------------|
| PROJ-123 | priority   | High        |
| PROJ-123 | sprint     | Sprint 5    |
```

Pivot to denormalize:

```asql-play
from issue_custom_fields
  pivot field_value by field_name values ('priority', 'sprint')
  group by issue_id
```

Result:

```
| issue_id | priority | sprint   |
|----------|----------|----------|
| PROJ-123 | High     | Sprint 5 |
```

### Dynamic Pivot

When you don't know all pivot values at compile time, use a subquery to get them dynamically:

```asql
-- Get pivot values from a subquery
from sales
  pivot sum(amount) by category values (
    from sales select distinct category
  )
```

**How It Works**

The subquery is compiled to a CTE (Common Table Expression), and pivot expressions are generated that reference the CTE. This allows the pivot values to be determined at runtime.

**Example: Dynamic Status Pivot**

```asql
from orders
  pivot sum(total) by status values (
    from orders 
    where order_date >= '2024-01-01'
    select distinct status
  )
  group by customer_id
```

This creates columns for each status value found in the filtered orders, without needing to know them in advance.

**When to Use Dynamic vs Static**

- **Static pivot**: Use when you know all possible values (e.g., fixed statuses like 'pending', 'shipped', 'delivered')
- **Dynamic pivot**: Use when values change over time or are data-driven (e.g., product categories, custom field names, user-defined tags)

**Note**: Dynamic pivot generates SQL that uses the subquery results. For true dynamic pivoting with individual columns per value at runtime, some warehouses (like Snowflake) support native `PIVOT` operators that may be more efficient.

---

## Unpivot — Columns to Rows

Transform columns into rows. Use when you have data in "wide" format and want it "long".

### Basic Syntax

```asql-play
from monthly_metrics
  unpivot jan, feb, mar, apr into month, value
```

This takes the columns `jan`, `feb`, `mar`, `apr` and creates two columns: `month` (the column name) and `value` (the column value).

### How It Works

Unpivot compiles to a UNION ALL query:

```sql
SELECT *, 'jan' AS month, jan AS value FROM monthly_metrics
UNION ALL
SELECT *, 'feb' AS month, feb AS value FROM monthly_metrics
UNION ALL
SELECT *, 'mar' AS month, mar AS value FROM monthly_metrics
UNION ALL
SELECT *, 'apr' AS month, apr AS value FROM monthly_metrics
```

### Example: Quarterly Data

```
| product | q1_sales | q2_sales | q3_sales | q4_sales |
|---------|----------|----------|----------|----------|
| Widget  | 100      | 150      | 200      | 180      |
```

Unpivot:

```asql-play
from quarterly_data
  unpivot q1_sales, q2_sales, q3_sales, q4_sales into quarter, sales
```

Result:

```
| product | quarter  | sales |
|---------|----------|-------|
| Widget  | q1_sales | 100   |
| Widget  | q2_sales | 150   |
| Widget  | q3_sales | 200   |
| Widget  | q4_sales | 180   |
```

### Use Cases

- **Normalizing spreadsheet-style data** — Wide imports with columns per period
- **Chart preparation** — Many visualization tools expect long format
- **Time series analysis** — Convert period columns to rows

---

## Explode — Arrays to Rows

Expand array-typed columns into multiple rows. One row per array element.

### Basic Syntax

```asql-play
from posts
  explode tags as tag
```

This takes an array column `tags` and creates one row per tag.

### How It Works

**Input:**

```
| post_id | title         | tags                    |
|---------|---------------|-------------------------|
| 1       | Intro to SQL  | ['sql', 'database']     |
| 2       | Python Tips   | ['python', 'coding']    |
```

**Query:**

```asql-play
from posts
  explode tags as tag
  select post_id, title, tag
```

**Output:**

```
| post_id | title         | tag      |
|---------|---------------|----------|
| 1       | Intro to SQL  | sql      |
| 1       | Intro to SQL  | database |
| 2       | Python Tips   | python   |
| 2       | Python Tips   | coding   |
```

### Dialect-Specific Compilation

| Dialect | SQL Output |
|---------|------------|
| BigQuery | `CROSS JOIN UNNEST(tags) AS tag` |
| Snowflake | `CROSS JOIN LATERAL FLATTEN(INPUT => tags) AS tag` |
| PostgreSQL | `CROSS JOIN LATERAL unnest(tags) AS tag` |
| DuckDB | `CROSS JOIN UNNEST(tags) AS t(tag)` |

### Use Cases

- **Tag analysis** — Count posts per tag
- **Multi-value attributes** — Analyze array-typed columns
- **JSON arrays** — After extracting arrays from JSON

### Example: Tag Frequency

```asql-play
from posts
  explode tags as tag
  group by tag (# as post_count)
  order by -post_count
  limit 10
```

---

## Column Operators

ASQL provides operators for manipulating columns without listing them all.

### `except` — Exclude Columns

Exclude specific columns from the result:

```asql-play
from users
  except password_hash, internal_notes
```

**Compiles to:**

```sql
SELECT * EXCEPT(password_hash, internal_notes) FROM users
```

### `rename` — Rename Columns

Rename columns inline:

```asql-play
from users
  rename id as user_id, name as user_name
```

**Compiles to:**

```sql
SELECT * EXCEPT(id, name), id AS user_id, name AS user_name FROM users
```

### `replace` — Replace Column Values

Replace column values with new expressions:

```asql
from users
  replace name with upper(name)

-- Multiple replacements
from users
  replace name with upper(name), email with lower(email)
```

**Compiles to:**

```sql
SELECT * EXCEPT(name, email), upper(name) AS name, lower(email) AS email FROM users
```

### Combining Operators

```asql-play
from users
  except password_hash
  rename id as user_id
  replace name with upper(name)
```

### Dialect Support

The `EXCEPT` syntax is supported by:
- BigQuery: `* EXCEPT(col)`
- Snowflake: `* EXCLUDE(col)`
- DuckDB: `* EXCLUDE(col)`

For PostgreSQL, MySQL, and SQLite, you need to list columns explicitly.

---

## Quick Reference

| Operation | Syntax | Example |
|-----------|--------|---------|
| Pivot (rows → columns) | `pivot expr by col values (...)` | `pivot sum(amount) by status values ('a', 'b')` |
| Unpivot (columns → rows) | `unpivot cols into name, value` | `unpivot jan, feb, mar into month, value` |
| Explode (array → rows) | `explode array_col as alias` | `explode tags as tag` |
| Exclude columns | `except col1, col2` | `except password_hash` |
| Rename columns | `rename old as new` | `rename id as user_id` |
| Replace values | `replace col with expr` | `replace name with upper(name)` |

## Next Steps

- **[Aggregations](aggregations.md)** — Using pivot with GROUP BY
- **[Pipeline Basics](pipeline.md)** — Combining operations
- **[Examples](../examples.md)** — Real-world patterns
