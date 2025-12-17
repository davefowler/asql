# Reference

Quick reference documentation for ASQL syntax, functions, and operators.

## Reference Pages

- **[Functions](functions.md)** — Complete list of built-in functions
- **[Operators](operators.md)** — All operators with examples
- **[Keywords](keywords.md)** — Reserved keywords and their meanings

## Quick Lookup

### Aggregate Functions

| Function | Description | Example |
|----------|-------------|---------|
| `count(*)` or `#` | Count rows | `# as total` |
| `sum(col)` | Sum values | `sum(amount)` |
| `avg(col)` | Average | `avg(price)` |
| `min(col)` | Minimum | `min(date)` |
| `max(col)` | Maximum | `max(amount)` |
| `count(distinct col)` | Distinct count | `count(distinct user_id)` |

### Date Functions

| Function | Description | Example |
|----------|-------------|---------|
| `year(date)` | Truncate to year | `year(created_at)` |
| `month(date)` | Truncate to month | `month(created_at)` |
| `week(date)` | Truncate to week | `week(created_at)` |
| `day(date)` | Truncate to day | `day(created_at)` |
| `hour(date)` | Truncate to hour | `hour(created_at)` |

### Window Functions

| Function | Description | Example |
|----------|-------------|---------|
| `prior(col)` | Previous row | `prior(revenue)` |
| `next(col)` | Next row | `next(revenue)` |
| `running_sum(col)` | Cumulative sum | `running_sum(amount)` |
| `rolling_avg(col, n)` | Moving average | `rolling_avg(price, 7)` |

### Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `&` | Inner join | `& users on id = user_id` |
| `&?` | Left join | `&? users on id = user_id` |
| `??` | Null coalesce | `value ?? 0` |
| `::` | Type cast | `value::INTEGER` |
| `-col` | Descending order | `order by -created_at` |

### Pipeline Keywords

| Keyword | SQL Equivalent | Example |
|---------|----------------|---------|
| `from` | `FROM` | `from users` |
| `where` | `WHERE` | `where is_active` |
| `select` | `SELECT` | `select name, email` |
| `group by` | `GROUP BY` | `group by country (...)` |
| `order by` | `ORDER BY` | `order by -created_at` |
| `limit` | `LIMIT` | `limit 100` |
| `stash as` | `WITH ... AS` | `stash as filtered` |

## See Also

- **[Syntax Guide](../syntax/index.md)** — Detailed syntax documentation
- **[Language Specification](../spec.md)** — Complete language reference
- **[Examples](../examples.md)** — Real-world query examples
