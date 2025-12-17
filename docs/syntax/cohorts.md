# Cohort Analysis

Cohort analysis groups users by a shared characteristic (usually when they "started") and tracks their behavior over time. ASQL's `cohort by` operator dramatically simplifies this complex pattern.

**Reference**: See `ai_notes/COHORT_ANALYSIS.md` for full design details.

## The Problem: Cohort Queries Are Complex

Traditional SQL requires 3-5 CTEs and 50+ lines for even basic cohort queries. A simple retention cohort requires:

1. Finding each user's cohort (when they started)
2. Finding each user's activity by period
3. Calculating periods since cohort start
4. Getting cohort sizes
5. Joining everything together
6. Calculating retention rates

**SQL Example (50+ lines):**
```sql
WITH user_cohorts AS (
    SELECT user_id, DATE_TRUNC('month', signup_date) AS cohort_month
    FROM users
),
activity_months AS (
    SELECT user_id, DATE_TRUNC('month', event_date) AS activity_month
    FROM events
    GROUP BY 1, 2
),
cohort_sizes AS (
    SELECT cohort_month, COUNT(*) AS size
    FROM user_cohorts GROUP BY 1
),
cohort_activity AS (
    SELECT 
        uc.cohort_month,
        EXTRACT(YEAR FROM AGE(am.activity_month, uc.cohort_month)) * 12 +
        EXTRACT(MONTH FROM AGE(am.activity_month, uc.cohort_month)) AS period,
        COUNT(DISTINCT uc.user_id) AS active
    FROM user_cohorts uc
    JOIN activity_months am ON uc.user_id = am.user_id
    WHERE am.activity_month >= uc.cohort_month
    GROUP BY 1, 2
)
SELECT 
    ca.cohort_month, cs.size, ca.period,
    ca.active, ROUND(ca.active::numeric / cs.size * 100, 1) AS retention
FROM cohort_activity ca
JOIN cohort_sizes cs ON ca.cohort_month = cs.cohort_month
ORDER BY ca.cohort_month, ca.period;
```

**ASQL (3 lines):**
```asql
from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)
```

**Reduction: 94%** 🎉

## Basic Syntax

The `cohort by` clause transforms any aggregation query into a cohort analysis:

```asql
from <activity_table>
group by <granularity>(<activity_date>) (<aggregations>)
cohort by <granularity>(<cohort_table>.<cohort_date>)
```

### Components

- **Activity table**: The table containing events/activities to analyze (e.g., `events`, `orders`)
- **Activity date**: The date column in the activity table (e.g., `event_date`, `order_date`)
- **Granularity**: Time bucket function - `month()`, `week()`, or `day()`
- **Cohort table**: The table containing cohort assignment (e.g., `users`, `customers`)
- **Cohort date**: The date that defines when users joined the cohort (e.g., `signup_date`, `first_order_date`)

## Examples

### User Retention by Signup Cohort

Track monthly active users by their signup month:

```asql
from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)
```

**Output columns:**
- `cohort_month`: Month users signed up
- `period`: Months since signup (0 = signup month, 1 = first month after, etc.)
- `active`: Active users in that period
- `cohort_size`: Total users in the cohort

### Revenue Cohort Analysis

Track revenue by first purchase cohort:

```asql
from orders
group by month(order_date) (sum(total) as revenue)
cohort by month(customers.first_order_date)
```

### Weekly Activity Cohorts

Track weekly active users:

```asql
from events
group by week(event_date) (count(distinct user_id) as active)
cohort by week(users.signup_date)
```

### Multiple Metrics

Track multiple metrics simultaneously:

```asql
from events
group by month(event_date) (
  count(distinct user_id) as active,
  count(*) as events,
  sum(revenue) as revenue
)
cohort by month(users.signup_date)
```

## Period Calculation

Period is automatically calculated based on the granularity:

- `cohort by month(...)` → period in **months** since cohort start
- `cohort by week(...)` → period in **weeks** since cohort start  
- `cohort by day(...)` → period in **days** since cohort start

The period calculation uses:
- The activity date column from your `group by` clause
- The cohort date from the `cohort by` clause
- Computes the difference using appropriate date arithmetic

**Period values:**
- `0`: The cohort start period (signup month/week/day)
- `1`: First period after cohort start
- `2`: Second period after cohort start
- And so on...

## Retention Calculations

With `cohort by`, retention calculations become straightforward. The `cohort_size` column is automatically available:

```asql
from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)
```

You can calculate retention rates in your BI tool or with window functions:

```asql
from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)
select
  cohort_month,
  period,
  active,
  cohort_size,
  round(active::numeric / cohort_size * 100, 1) as retention_pct
```

## Period-over-Period Comparisons

Use window functions like `prior()` for period-over-period analysis:

```asql
from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)
select
  cohort_month,
  period,
  active,
  prior(active) as prev_period_active,
  active - prior(active) as change,
  round((active - prior(active))::numeric / prior(active) * 100, 1) as pct_change
```

The `cohort by` clause automatically partitions window functions by cohort and orders by period, so `prior()` works correctly.

## Cumulative Metrics (LTV)

Use `running_sum()` for cumulative metrics like Lifetime Value (LTV):

```asql
from orders
group by month(order_date) (sum(total) as revenue)
cohort by month(customers.first_order_date)
select
  cohort_month,
  period,
  revenue,
  running_sum(revenue) as cumulative_revenue,
  running_sum(revenue) / cohort_size as ltv
```

## Segmented Cohorts

Add segment dimensions before the time function to create segmented cohorts:

```asql
from events
group by month(event_date) (count(distinct user_id) as active)
cohort by users.channel, month(users.signup_date)
```

This creates cohorts segmented by acquisition channel, allowing you to compare retention across different channels.

**Output columns:**
- `channel`: Acquisition channel
- `cohort_month`: Month users signed up
- `period`: Months since signup
- `active`: Active users
- `cohort_size`: Total users in that channel cohort

## Explicit Join Keys

When join inference fails (non-standard foreign key names), use the `on` clause:

```asql
from orders
group by month(order_date) (sum(total) as revenue)
cohort by month(customers.first_order_date) on customer_id
```

## Common Use Cases

### 1. User Retention Analysis

```asql
from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)
```

### 2. Revenue Cohort with LTV

```asql
from orders
group by month(order_date) (sum(total) as revenue)
cohort by month(customers.first_order_date)
select
  cohort_month,
  period,
  revenue,
  running_sum(revenue) as cumulative_revenue,
  running_sum(revenue) / cohort_size as ltv
```

### 3. Feature Adoption Cohorts

```asql
from feature_events
where feature_name == "dashboard"
group by week(event_date) (count(distinct user_id) as feature_users)
cohort by week(users.first_dashboard_use_date)
```

### 4. Subscription Survival Analysis

```asql
from subscription_events
where status == "active"
group by month(event_date) (count(distinct subscription_id) as active_subs)
cohort by month(subscriptions.start_date)
```

### 5. Churn Analysis

```asql
from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)
select
  cohort_month,
  period,
  active,
  cohort_size,
  cohort_size - active as churned,
  round((cohort_size - active)::numeric / cohort_size * 100, 1) as churn_rate
```

## How It Works

When you use `cohort by`, ASQL automatically:

1. **Creates cohort CTEs**: Generates `cohort_base` (cohort assignment) and `cohort_sizes` (cohort size calculation)
2. **Infers joins**: Automatically joins the activity table to the cohort table using foreign key conventions
3. **Calculates period**: Computes periods since cohort start based on the granularity function
4. **Modifies GROUP BY**: Adds `cohort_month` and `period` to the grouping
5. **Adds columns**: Includes `cohort_month`, `period`, and `cohort_size` in the SELECT
6. **Orders results**: Automatically orders by `cohort_month, period`

## Best Practices

1. **Match granularities**: Use the same granularity in `group by` and `cohort by` (e.g., both `month()`)
2. **Use explicit join keys**: When foreign key inference fails, use `on` clause
3. **Filter activity**: Apply filters before `cohort by` to analyze specific event types
4. **Combine with window functions**: Use `prior()`, `running_sum()`, etc. for advanced analysis

## Limitations

- **Join inference**: Requires standard foreign key naming (e.g., `user_id` → `users.id`)
- **Granularity matching**: Activity and cohort granularities should match or be compatible
- **Single cohort dimension**: Currently supports one cohort definition per query (segmented cohorts are supported)

## See Also

- [Window Functions](window-functions.md) - `prior()`, `running_sum()`, and other functions useful for cohorts
- [Date Functions](dates.md) - `month()`, `week()`, `day()` functions
- [Spec: Cohort Analysis](../spec.md#14-cohort-analysis) - Full specification
