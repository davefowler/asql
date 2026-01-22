# Cohort Analysis

Cohort analysis groups users by a shared characteristic (usually when they "started") and tracks their behavior over time. ASQL's features make cohort queries simple and readable.

## What is Cohort Analysis?

Cohort analysis tracks **the same entities over time periods** relative to when they started. Key components:

- **Cohort**: When each entity "started" (signup month, first purchase month, etc.)
- **Period**: Time elapsed since their cohort start (0 = start, 1 = first period after, etc.)
- **Cohort size**: How many entities in each cohort (for retention %)

## The Simple Pattern

In ASQL, cohort analysis is just computed columns + GROUP BY:

```asql
from orders
join users
group by 
  month(users.signup_date) as cohort,
  months_between(orders.created_at, users.signup_date) as period
(
  count(distinct customer_id) as active
)
```

That's it. ASQL's **alias reuse** lets you reference `cohort` and `period` immediately after defining them.

## Why This Works

Traditional SQL requires CTEs because you can't reference a computed column in the same SELECT:

```sql
-- This DOESN'T work in SQL:
SELECT 
  DATE_TRUNC('month', signup_date) AS cohort,
  DATEDIFF(month, cohort, order_date) AS period  -- ERROR!
FROM ...
```

ASQL's alias reuse handles this automatically - each alias becomes available to subsequent expressions.

## Examples

### User Retention by Signup Cohort

Track monthly active users by their signup month:

```asql
from events
join users
group by 
  month(users.signup_date) as cohort,
  months_between(events.event_date, users.signup_date) as period
(
  count(distinct user_id) as active
)
order by cohort, period
```

**Output columns:**
- `cohort`: Month users signed up
- `period`: Months since signup (0 = signup month, 1 = first month after, etc.)
- `active`: Active users in that period

### Revenue Cohort Analysis

Track revenue by first purchase cohort:

```asql
from orders
join customers
group by 
  month(customers.first_order_date) as cohort,
  months_between(orders.order_date, customers.first_order_date) as period
(
  sum(total) as revenue,
  count(distinct customer_id) as customers
)
order by cohort, period
```

### Weekly Cohorts

Track weekly active users with weekly periods:

```asql
from events
join users
group by 
  week(users.signup_date) as cohort,
  weeks_between(events.event_date, users.signup_date) as period
(
  count(distinct user_id) as active
)
order by cohort, period
```

### Retention with Cohort Size

To calculate retention percentage, you need cohort size. Use a window function:

```asql
from events
join users
group by 
  month(users.signup_date) as cohort,
  months_between(events.event_date, users.signup_date) as period
(
  count(distinct user_id) as active
)
select *,
  first(active) over cohort as cohort_size,
  round(active::numeric / cohort_size * 100, 1) as retention_pct
order by cohort, period
```

The `first(active) over cohort` gets the period 0 value (all users in cohort), which is the cohort size.

### Cumulative Metrics (LTV)

Use `running_sum()` for lifetime value:

```asql
from orders
join customers
group by 
  month(customers.first_order_date) as cohort,
  months_between(orders.order_date, customers.first_order_date) as period
(
  sum(total) as revenue,
  count(distinct customer_id) as customers
)
select *,
  running_sum(revenue) over cohort as cumulative_revenue,
  first(customers) over cohort as cohort_size,
  running_sum(revenue) over cohort / cohort_size as ltv
order by cohort, period
```

### Self-Cohort (First Activity as Cohort)

When the cohort date isn't in a separate table, use a subquery or window function to find each entity's first activity:

```asql
from (
  from orders
  select *,
    month(first(created_at) over customer_id) as cohort
)
group by 
  cohort,
  months_between(created_at, cohort) as period
(
  count(distinct customer_id) as active
)
order by cohort, period
```

### Segmented Cohorts

Add segment dimensions to compare cohorts across segments:

```asql
from events
join users
group by 
  users.channel,
  month(users.signup_date) as cohort,
  months_between(events.event_date, users.signup_date) as period
(
  count(distinct user_id) as active
)
order by channel, cohort, period
```

## Period Calculation Functions

ASQL provides date difference functions for period calculation:

| Function | Returns |
|----------|---------|
| `months_between(date1, date2)` | Months between dates |
| `weeks_between(date1, date2)` | Weeks between dates |
| `days_between(date1, date2)` | Days between dates |

Or use explicit arithmetic:
```asql
datediff('month', signup_date, event_date) as period
```

## Gap Filling with Spine

For complete cohort matrices (showing 0 for periods with no activity), use `spine by`:

```asql
from events
join users
spine by 
  month(users.signup_date) as cohort,
  months_between(events.event_date, users.signup_date) as period
(
  count(distinct user_id) as active
)
order by cohort, period
```

The `spine by` ensures you get a row for every (cohort, period) combination.

## Common Patterns

### Retention Table

```asql
from events
join users
group by 
  month(users.signup_date) as cohort,
  months_between(events.event_date, users.signup_date) as period
(
  count(distinct user_id) as active
)
select cohort, period, active,
  first(active) over cohort as cohort_size,
  round(active::numeric / cohort_size * 100, 1) as retention_pct
where period between 0 and 12
order by cohort, period
```

### Churn Analysis

```asql
from events
join users
group by 
  month(users.signup_date) as cohort,
  months_between(events.event_date, users.signup_date) as period
(
  count(distinct user_id) as active
)
select cohort, period, active,
  first(active) over cohort as cohort_size,
  cohort_size - active as churned,
  round((cohort_size - active)::numeric / cohort_size * 100, 1) as churn_pct
order by cohort, period
```

## See Also

- [Window Functions](window-functions.md) - `first()`, `running_sum()`, and other functions useful for cohorts
- [Date Functions](dates.md) - `month()`, `week()`, date arithmetic
- [Spine (Gap Filling)](../spec.md#spine-by-gap-filling) - Ensuring complete time series
