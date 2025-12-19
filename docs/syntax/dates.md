# Dates & Time

Dates are fundamental to analytics. ASQL provides a clean, intuitive, and portable date syntax that compiles to the right SQL for any dialect.

## Date Literals

Use the `@` prefix for date literals:

```asql
from users
  where signup_date >= @2024-01-01

from orders
  where order_date between @2024-01-01 and @2024-12-31
```

This compiles to `DATE '2024-01-01'` in SQL.

For timestamps, include the time:

```asql
@2024-01-15T10:30:00
```

## Time Truncation Functions

Truncate dates to a specific unit:

| Function | Result | Example Output |
|----------|--------|----------------|
| `year(date)` | Truncate to year start | `2025-01-01` |
| `month(date)` | Truncate to month start | `2025-01-01` |
| `week(date)` | Truncate to week start | `2025-01-06` |
| `day(date)` | Truncate to day | `2025-01-15` |
| `hour(date)` | Truncate to hour | `2025-01-15 14:00:00` |
| `quarter(date)` | Truncate to quarter start | `2025-01-01` |

```asql-play
from orders
  group by month(created_at) (
    sum(amount) as revenue
  )
```

### Natural Language Alternatives

All of these are equivalent:

```asql
year(created_at)       -- function style
year created_at        -- space style
year_created_at        -- underscore style
year of created_at     -- "of" style
```

## Date Part Extraction

Extract specific parts (returns integers, not dates):

| Expression | Returns | Example |
|------------|---------|---------|
| `day of week date` | 1-7 | 3 (Wednesday) |
| `day of month date` | 1-31 | 15 |
| `day of year date` | 1-366 | 45 |
| `week of year date` | 1-52 | 12 |
| `month of year date` | 1-12 | 6 |
| `quarter of year date` | 1-4 | 2 |

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

### Truncation vs Extraction

- **Truncation** (`month(date)`): Returns a date, for time series
- **Extraction** (`month of year date`): Returns an integer, for "all Januaries"

```asql
month(created_at)           -- → 2025-01-01 (date)
month of year created_at    -- → 1 (integer)
```

## Date Arithmetic

Add or subtract from dates using clean inline syntax:

```asql
order_date + 7 days
order_date - 1 month
order_date + 2 weeks
created_at + 24 hours
```

Singular and plural both work:

```asql
order_date + 1 day    -- singular
order_date + 7 days   -- plural
```

This compiles to dialect-appropriate SQL:

```sql
-- PostgreSQL
order_date + INTERVAL '7 days'

-- MySQL
DATE_ADD(order_date, INTERVAL 7 DAY)

-- SQL Server
DATEADD(day, 7, order_date)
```

## Date Difference

Calculate the difference between dates:

```asql
days(end_date - start_date)      -- Integer days
months(end_date - start_date)    -- Integer months
years(end_date - start_date)     -- Integer years
hours(end_date - start_date)     -- Integer hours
weeks(end_date - start_date)     -- Integer weeks
```

Alternative function syntax:

```asql
days_between(start_date, end_date)
months_between(start_date, end_date)
```

Example:

```asql
from orders
  select 
    days(shipped_date - order_date) as fulfillment_days,
    months(now() - customer_since) as customer_tenure_months
```

## Relative Dates

### Past Dates (`ago`)

```asql
from users
  where last_login >= 7 days ago

from orders
  where created_at >= 30 days ago
  where created_at >= 1 month ago
```

### Future Dates (`from now`)

```asql
from orders
  where estimated_delivery <= 3 days from now

from reminders
  where remind_at <= 1 hour from now
```

These compile to dialect-appropriate SQL using `CURRENT_TIMESTAMP` and intervals.

## Time Since/Until Patterns

### `*_since_*` Pattern

Calculate time elapsed since a date:

```asql
days_since_created_at        -- → days(now() - created_at)
weeks_since_signup_date      -- → weeks(now() - signup_date)
months_since_last_login      -- → months(now() - last_login)
```

### `*_until_*` Pattern

Calculate time remaining until a future date:

```asql
days_until_due_date          -- → days(due_date - now())
weeks_until_deadline         -- → weeks(deadline - now())
months_until_renewal         -- → months(renewal_date - now())
```

Example:

```asql
from users
  select
    name,
    days_since_last_login,
    months_since_signup_date,
    years_since_birth_date as age

from tasks
  where days_until_due_date < 7
```

## Week Start Configuration

**Default**: ISO 8601 standard (Monday = day 1)

```asql
week(created_at)           -- Default: ISO (Monday start)
week_monday(created_at)    -- Explicit Monday start
week_sunday(created_at)    -- US-style Sunday start

day of week created_at     -- 1 = Monday, 7 = Sunday (ISO)
```

## Time Bucketing (Grouping)

Time bucketing is simply grouping by a time function:

```asql
from orders
  group by month(created_at) (
    sum(amount) as revenue
  )

from sessions
  group by week(start_time) (
    count(distinct user_id) as active_users
  )
```

## Timezone Handling

Use `::` syntax for timezone conversion:

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

## Quick Reference

| Operation | Syntax | Example |
|-----------|--------|---------|
| Date literal | `@YYYY-MM-DD` | `@2025-01-15` |
| Truncation | `unit(col)` | `month(created_at)` |
| Extraction | `unit of period col` | `day of week created_at` |
| Add/subtract | `date + N unit` | `order_date + 7 days` |
| Difference | `unit(date1 - date2)` | `days(end - start)` |
| Relative past | `N unit ago` | `7 days ago` |
| Relative future | `N unit from now` | `3 days from now` |
| Time since | `unit_since_col` | `days_since_created_at` |
| Time until | `unit_until_col` | `days_until_due_date` |
| Timezone | `col::TZ` | `created_at::PST` |

## Real-World Examples

### Daily Revenue for Last 30 Days

```asql-play
from orders
  where created_at >= 30 days ago
  group by day(created_at) (
    sum(amount) as revenue
  )
  order by day(created_at)
```

### Monthly User Signups

```asql-play
from users
  group by month(created_at) (
    # as signups
  )
  order by month
```

### Orders with Fulfillment Time

```asql
from orders
  where shipped_date is not null
  select
    id,
    order_date,
    shipped_date,
    days(shipped_date - order_date) as fulfillment_days
```

### Active Users Last Week

```asql-play
from users
  where last_login >= 7 days ago
  select name, email, days_since_last_login
```

## Next Steps

- **[Aggregations](aggregations.md)** — Grouping by date periods
- **[Guaranteed Groups](../concepts/guaranteed-groups.md)** — Gap-filling for time series
- **[Window Functions](window-functions.md)** — Prior/next for date comparisons
