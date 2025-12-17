# Cohort Analysis in ASQL

This document explores how ASQL could dramatically simplify cohort analysis—one of the most complex and commonly needed patterns in analytics SQL.

**Last Updated**: December 2025

> **See also**: 
> - [Window Utils](WINDOW_UTILS.md) - `first()`, `prior()`, `running_sum()` and other implemented features useful for cohorts
> - [Date Handling](dates.md) - `days_since_*`, `7 days ago`, and other date patterns

---

## ✅ Already Implemented Features for Cohorts

Many building blocks for cohort analysis are **already implemented** in ASQL:

| Feature | Status | Use in Cohorts |
|---------|--------|----------------|
| `first(col order by ...)` | ✅ Implemented | Determine first activity (cohort membership) |
| `last(col order by ...)` | ✅ Implemented | Determine most recent activity |
| `arg_max(col, by_col)` | ✅ Implemented | Get value at max date (alternative to first/last) |
| `prior(col)` / `next(col)` | ✅ Implemented | Period-over-period comparisons |
| `running_sum(col)` | ✅ Implemented | Cumulative metrics, LTV calculation |
| `running_avg(col)` | ✅ Implemented | Cumulative averages |
| `rolling_avg(col, n)` | ✅ Implemented | Smoothed retention curves |
| `per ... first by ...` | ✅ Implemented | Pipeline-native deduplication |
| `distinct on (col)` | ✅ Implemented | PostgreSQL-style deduplication |
| `month(col)` / `week(col)` | ✅ Implemented | Time bucketing for cohorts |
| `days(end - start)` | ✅ Decided | Period calculation |
| `days_since_signup_date` | ✅ Decided | Time since cohort start |
| `7 days ago` | ✅ Decided | Relative date filtering |

---

## Summary

Cohort analysis is notoriously complex in SQL. It typically requires:
- 3-5 CTEs for even basic cohort queries
- Window functions with complex partitions
- Multiple self-joins
- Date arithmetic and truncation
- Aggregations across different time dimensions

This complexity leads teams to pre-build cohort rollup tables ("data marts"), which creates:
- More tables to maintain
- Schema bloat
- Stale data if not refreshed
- Loss of flexibility (can't easily change cohort definitions)

If ASQL made cohort analysis trivial, analysts could write these queries directly in their BI tools without needing pre-built data marts.

**Vision**: A cohort analysis that takes 50+ lines of SQL should be expressible in 5-10 lines of ASQL.

---

## 1. The Problem: Cohort Queries Are Hard

### 1.1 What Is Cohort Analysis?

Cohort analysis groups users by a shared characteristic (usually when they "started") and tracks their behavior over time. Common examples:

- **User Retention**: Group users by signup month, track % active in subsequent months
- **Revenue Cohorts**: Group customers by first purchase month, track cumulative revenue
- **Feature Adoption**: Group users by when they first used a feature, track engagement
- **Subscription Cohorts**: Track upgrade/downgrade/churn rates by signup cohort

### 1.2 Why It's Complex in SQL

A basic retention cohort query requires:

```sql
-- Step 1: Find each user's cohort (when they started)
WITH user_cohorts AS (
    SELECT 
        user_id,
        DATE_TRUNC('month', signup_date) AS cohort_month
    FROM users
),

-- Step 2: Find each user's activity by month
user_activity AS (
    SELECT 
        user_id,
        DATE_TRUNC('month', activity_date) AS activity_month
    FROM events
    GROUP BY user_id, DATE_TRUNC('month', activity_date)
),

-- Step 3: Calculate months since signup for each activity
cohort_activity AS (
    SELECT 
        uc.cohort_month,
        ua.activity_month,
        EXTRACT(YEAR FROM age(ua.activity_month, uc.cohort_month)) * 12 +
        EXTRACT(MONTH FROM age(ua.activity_month, uc.cohort_month)) AS months_since_signup,
        uc.user_id
    FROM user_cohorts uc
    JOIN user_activity ua ON uc.user_id = ua.user_id
    WHERE ua.activity_month >= uc.cohort_month
),

-- Step 4: Get cohort sizes
cohort_sizes AS (
    SELECT 
        cohort_month,
        COUNT(DISTINCT user_id) AS cohort_size
    FROM user_cohorts
    GROUP BY cohort_month
)

-- Step 5: Final aggregation - retention by cohort and period
SELECT 
    ca.cohort_month,
    cs.cohort_size,
    ca.months_since_signup,
    COUNT(DISTINCT ca.user_id) AS active_users,
    ROUND(COUNT(DISTINCT ca.user_id)::numeric / cs.cohort_size * 100, 2) AS retention_rate
FROM cohort_activity ca
JOIN cohort_sizes cs ON ca.cohort_month = cs.cohort_month
GROUP BY ca.cohort_month, cs.cohort_size, ca.months_since_signup
ORDER BY ca.cohort_month, ca.months_since_signup;
```

**That's 40+ lines for a basic retention cohort!**

### 1.3 The Data Mart "Solution"

Because these queries are so complex, teams often pre-build:

- `dim_user_cohorts` - User to cohort mapping
- `fct_cohort_retention` - Pre-aggregated retention metrics
- `fct_cohort_revenue` - Pre-aggregated revenue by cohort
- `rpt_cohort_analysis` - Final presentation layer

**Problems with this approach:**
1. **Schema bloat**: 4+ tables just for cohort analysis
2. **Maintenance overhead**: Must refresh regularly
3. **Inflexibility**: Changing cohort logic requires rebuilding tables
4. **Time lag**: Analysis is only as fresh as last refresh
5. **Cost**: Extra compute for materialization

---

## 2. Current ASQL: Improvements Over SQL

The existing ASQL syntax already helps. Compare:

**SQL (27 lines):**
```sql
WITH user_cohorts AS (
    SELECT 
        user_id,
        DATE_TRUNC('month', signup_date) AS cohort_month,
        signup_date
    FROM users
),
monthly_activity AS (
    SELECT 
        user_id,
        DATE_TRUNC('month', activity_date) AS activity_month
    FROM user_activities
    GROUP BY user_id, DATE_TRUNC('month', activity_date)
)
SELECT 
    uc.cohort_month,
    COUNT(DISTINCT uc.user_id) AS cohort_size,
    COUNT(DISTINCT ma.user_id) AS active_users,
    ROUND(COUNT(DISTINCT ma.user_id)::numeric / COUNT(DISTINCT uc.user_id) * 100, 2) AS retention_rate
FROM user_cohorts uc
LEFT JOIN monthly_activity ma ON uc.user_id = ma.user_id 
    AND ma.activity_month = uc.cohort_month
GROUP BY uc.cohort_month
ORDER BY uc.cohort_month DESC;
```

**Current ASQL (21 lines):**
```asql
with user_cohorts = from users
  select 
    user_id,
    month(signup_date) as cohort_month,
    signup_date

with monthly_activity = from user_activities
  group by user_id, month(activity_date) (
    month(activity_date) as activity_month
  )

from user_cohorts
  left join monthly_activity on user_cohorts.user_id == monthly_activity.user_id 
    and monthly_activity.activity_month == user_cohorts.cohort_month
  group by user_cohorts.cohort_month (
    count(distinct user_cohorts.user_id) as cohort_size,
    count(distinct monthly_activity.user_id) as active_users,
    round(count(distinct monthly_activity.user_id)::numeric / count(distinct user_cohorts.user_id) * 100, 2) as retention_rate
  )
  order by -user_cohorts.cohort_month
```

**~22% reduction** - better, but still complex. The structure mirrors SQL. Let's do better.

---

## 2.1 Better ASQL with Implemented Features

Using features that are **already implemented or decided**, we can write cleaner cohort queries today:

### Using `first()` for Cohort Membership

```asql
-- Determine cohort by first purchase, not signup
from orders
  group by customer_id (
    first(order_date order by order_date) as cohort_date,
    first(order_id order by order_date) as first_order_id
  )
```

### Using `days_since_*` / `months_since_*` Pattern

The `*_since_*` pattern (from dates.md) is **perfect** for cohort period calculation:

```asql
from users
  join events on user_id
  select
    user_id,
    month(signup_date) as cohort_month,
    event_date,
    months_since_signup_date as period,    -- Auto-expands to months(now() - signup_date)
    days_since_signup_date as days_active  -- Auto-expands to days(now() - signup_date)
```

For cohorts where you need `months(event_date - signup_date)` (not from now), use the explicit form:

```asql
from users
  join events on user_id
  select
    user_id,
    month(signup_date) as cohort_month,
    months(event_date - signup_date) as period  -- Periods since cohort start
```

### Using `prior()` for Period-over-Period

```asql
-- Month-over-month retention change
from cohort_metrics
  order by cohort_month, period
  select
    cohort_month,
    period,
    retention,
    prior(retention) as prev_period_retention,
    retention - prior(retention) as retention_change
```

### Using `running_sum()` for LTV

```asql
-- Cumulative revenue per cohort (LTV curve)
from cohort_revenue
  order by cohort_month, period
  select
    cohort_month,
    period,
    revenue,
    running_sum(revenue) as cumulative_revenue,
    running_sum(revenue) / cohort_size as ltv
```

### Using `first by` for Deduplication

```asql
-- Get first activity per user (for cohort assignment)
from events
  per user_id first by event_date
```

### Using `distinct on` for First Row Per Group

```asql
-- PostgreSQL-style: first event per user
from events
  distinct on (user_id)
  order by user_id, event_date
```

### Improved Cohort Query with Current Features

Combining implemented features, a cohort query becomes cleaner:

```asql
-- Step 1: Get cohort assignment using first()
with user_cohorts = from events
  group by user_id (
    month(first(event_date order by event_date)) as cohort_month
  )

-- Step 2: Activity with period calculation
with activity = from events
  join user_cohorts on user_id
  select
    user_id,
    cohort_month,
    month(event_date) as activity_month,
    months(event_date - first_event_date) as period  -- Need to track first_event_date

-- Step 3: Aggregate with running calculations
from activity
  group by cohort_month, period (
    count(distinct user_id) as active_users
  )
  order by cohort_month, period
  select
    cohort_month,
    period,
    active_users,
    prior(active_users) as prev_period_active,
    running_sum(active_users) as cumulative_active
```

Still complex, but **much cleaner** than raw SQL. The dream syntax below would eliminate even more boilerplate.

---

## 3. Proposed ASQL Cohort Syntax

### 3.1 The Core Idea: `cohort by` Parallels `group by`

**Philosophy**: Write a normal query, then add `cohort by` to split it by cohort. The syntax mirrors `group by` exactly.

```asql
-- Write the query you want...
from events
  group by month(event_date) (
    count(distinct user_id) as active
  )
  -- ...then add cohort by to split it
  cohort by month(users.signup_date)
```

**Output:**
| cohort_month | period | active |
|--------------|--------|--------|
| 2024-01 | 0 | 1000 |
| 2024-01 | 1 | 450 |
| 2024-01 | 2 | 320 |
| 2024-02 | 0 | 1200 |
| ... | ... | ... |

**How it works:**
1. System infers join: `events.user_id → users.id` (convention-based)
2. Computes each user's cohort from the function: `month(users.signup_date)`
3. Computes period from the same function: `months(event_date - users.signup_date)`
4. Groups by `cohort_month, period` instead of just `month(event_date)`
5. **Auto-sorts** by `cohort_month, period` (needed for window functions)

### 3.2 Why This is Elegant

**Parallels `group by`**: Same pattern, easy to learn:

```asql
group by month(event_date) ( <aggregates> )
cohort by month(users.signup_date) ( <derivations> )
```

**Composable**: Any query can become a cohort query by adding one line:

```asql
-- Revenue by month → Revenue cohort
from orders
  group by month(order_date) (sum(total) as revenue)
  cohort by month(customers.first_order_date)

-- Sessions by week → Session cohort  
from sessions
  group by week(started_at) (count(*) as sessions)
  cohort by week(users.signup_date)

-- Multiple metrics
from events
  group by month(event_date) (
    count(distinct user_id) as active,
    count(*) as events,
    sum(revenue) as revenue
  )
  cohort by month(users.signup_date)
```

### 3.3 Syntax Details

```
cohort by <time_function>(<cohort_column>) [on <join_key>]
```

- The **function** (`month`, `week`, `day`) determines both truncation AND period calculation
- The **column** (`users.signup_date`) identifies the cohort table and cohort date
- Optional `on <key>` for explicit joins when inference fails

**Granularity matching:**
```asql
-- ✅ Group by month, cohort by month
group by month(event_date) (...) 
cohort by month(users.signup_date)

-- ✅ Group by week, cohort by month (finer activity, coarser cohort)  
group by week(event_date) (...) 
cohort by month(users.signup_date)

-- ❌ Group by month, cohort by day (doesn't make sense - error)
group by month(event_date) (...) 
cohort by day(users.signup_date)
```

### 3.4 Derived Columns with Parens

**The power feature**: Add parens to `cohort by` for derived columns. Inside the parens, `cohort_size` is automatically available:

```asql
from events
  group by month(event_date) (
    count(distinct user_id) as active
  )
  cohort by month(users.signup_date) (
    prior(active) as prev,
    delta(active) as change,
    pct_change(active) as growth,
    pct(active, cohort_size) as retention
  )
```

**What happens inside `cohort by (...)`:**
- `cohort_size` is automatically available (no `with cohort_size` needed!)
- Window functions (`prior`, `running_sum`) are auto-partitioned by cohort, ordered by period
- Auto-sort is implicit

### 3.5 Join Inference

The system figures out how to join the activity table to the cohort table:

```asql
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date)
  -- Infers: events.user_id → users.id (convention-based FK)
```

**How inference works:**
1. Parse `users.signup_date` → cohort table is `users`
2. Look at `events` → activity table
3. Find FK: `events.user_id → users.id` (naming convention)
4. If ambiguous, require explicit `on` clause

**Explicit join** (when inference fails):
```asql
from orders
  group by month(order_date) (sum(total) as revenue)
  cohort by month(customers.first_purchase_date) on customer_id
```

### 3.6 Period Calculation

Period is automatically calculated based on the function used:

```asql
cohort by month(users.signup_date)
-- Period = months(activity_date - users.signup_date)

cohort by week(users.signup_date)
-- Period = weeks(activity_date - users.signup_date)

cohort by day(users.signup_date)
-- Period = days(activity_date - users.signup_date)
```

### 3.7 Segmented Cohorts

Add segment dimensions before the time function:

```asql
-- By acquisition channel
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by users.channel, month(users.signup_date)

-- By plan type
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by users.plan_type, month(users.signup_date)

-- With derivations
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by users.channel, month(users.signup_date) (
    pct(active, cohort_size) as retention
  )
```

**Output:** `channel, cohort_month, period, active, retention`

### 3.8 Pivot Output

```asql
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date) (
    pct(active, cohort_size) as retention
  )
  pivot period as columns

-- Output (wide format):
-- cohort_month | cohort_size | retention_0 | retention_1 | retention_2
-- 2024-01      | 1000        | 100%        | 45%         | 32%
-- 2024-02      | 1200        | 100%        | 48%         | 35%
```

---

## 4. Common Cohort Metrics

With `cohort by`, you calculate metrics directly—`cohort_size` is implicit inside parens:

### 4.1 Retention

```asql
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date) (
    pct(active, cohort_size) as retention
  )
```

### 4.2 Churn

```asql
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date) (
    pct(cohort_size - active, cohort_size) as churn
  )
```

### 4.3 LTV (Lifetime Value)

Use `running_sum()` for cumulative metrics—auto-partitioned by cohort:

```asql
from orders
  group by month(order_date) (sum(total) as revenue)
  cohort by month(customers.first_order_date) (
    running_sum(revenue) as cumulative_revenue,
    running_sum(revenue) / cohort_size as ltv
  )
```

### 4.4 Period-over-Period Change

Use `prior()` and `delta()`—auto-partitioned by cohort:

```asql
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date) (
    prior(active) as prev,
    delta(active) as change,
    pct_change(active) as growth
  )
```

### 4.5 Smoothed Metrics

Use `rolling_avg()`—auto-partitioned by cohort:

```asql
from events
  group by week(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date) (
    rolling_avg(active, 4) as four_week_avg
  )
```

### 4.6 Survival (Subscriptions)

```asql
from subscription_events
  where status == "active"
  group by month(event_date) (count(distinct subscription_id) as active_subs)
  cohort by month(subscriptions.start_date) (
    pct(active_subs, cohort_size) as survival
  )
```

---

## 5. Example Transformations

### 5.1 Basic Retention Cohort

**Current SQL (50 lines):**
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

**Proposed ASQL (3 lines):**
```asql
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date)
```

**Reduction: 90%** 🎉

### 5.2 Revenue Cohort with LTV

**Current SQL (65+ lines):** *(same pattern as above)*

**Proposed ASQL (5 lines):**
```asql
from orders
  group by month(order_date) (sum(total) as revenue)
  cohort by month(customers.first_order_date) (
    running_sum(revenue) as cumulative,
    running_sum(revenue) / cohort_size as ltv
  )
```

### 5.3 Segmented Cohorts

```asql
from events
  where created_at >= 6 months ago
  group by month(event_date) (count(distinct user_id) as active)
  cohort by users.channel, month(users.signup_date) (
    pct(active, cohort_size) as retention
  )
  pivot period as columns
```

### 5.4 Using Implemented Features

```asql
-- Period-over-period with prior() and delta()
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date) (
    prior(active) as prev,
    delta(active) as change,
    pct_change(active) as growth
  )

-- Smoothed with rolling_avg()
from events
  group by week(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date) (
    rolling_avg(active, 4) as smoothed
  )

-- Cohort membership with first()
from events
  group by user_id (
    month(first(event_date order by event_date)) as cohort_month
  )
```

**Output (for segmented pivot):**
| channel | cohort_month | cohort_size | retention_0 | retention_1 | retention_2 |
|---------|--------------|-------------|-------------|-------------|-------------|
| organic | 2024-01 | 500 | 100% | 52% | 45% |
| paid | 2024-01 | 800 | 100% | 38% | 32% |

---

## 6. Implementation Approach

### 6.1 Parser Changes

Add `cohort by` as a pipeline modifier:
- `cohort by <time_function>(<table.column>)` - Adds cohort dimension
- `cohort by ... ( <derivations> )` - Optional parens for derived columns
- `cohort by <segment>, <time_function>(<column>)` - Segment support
- ✅ `pivot` - Already implemented (different branch)

**Key simplification**: `cohort_size` is implicit inside parens—no separate `with cohort_size` needed!

### 6.2 Semantic Analysis

When encountering `cohort by month(users.signup_date)`:
1. Parse function call: extract granularity (`month`) and column (`users.signup_date`)
2. Parse cohort column reference (`users.signup_date`) → cohort table is `users`
3. Infer join from activity table to cohort table (`events.user_id → users.id`)
4. Calculate period: `months(activity_date - cohort_date)`
5. If parens present, inject `cohort_size` into derivation scope

### 6.3 SQL Generation

Transform `cohort by` modifier:
1. Add JOIN to cohort table (inferred or explicit)
2. Add cohort column: `DATE_TRUNC('month', users.signup_date) as cohort_month`
3. Add period column: `months(activity_date - users.signup_date) as period`
4. Add `cohort_size`: window function `COUNT(*) OVER (PARTITION BY cohort_month)`
5. Modify GROUP BY to include `cohort_month, period`
6. Add ORDER BY `cohort_month, period` (auto-sort)
7. Process derivations inside parens with `cohort_size` in scope

**Example:**
```asql
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date)
```
**Compiles to:**
```sql
WITH cohort_base AS (
  SELECT user_id, DATE_TRUNC('month', signup_date) AS cohort_month
  FROM users
)
SELECT 
  cb.cohort_month,
  -- period calculation
  COUNT(DISTINCT e.user_id) AS active
FROM events e
JOIN cohort_base cb ON e.user_id = cb.user_id
GROUP BY cb.cohort_month, period
```

### 6.4 Dialect Handling

Date arithmetic varies by dialect (SQLGlot handles translation):
- PostgreSQL: `AGE()`, `EXTRACT()`
- MySQL: `TIMESTAMPDIFF()`
- BigQuery: `DATE_DIFF()`
- Snowflake: `DATEDIFF()`

---

## 7. Why This Matters for BI Tools

### 7.1 Current State

BI tools like Metabase, Looker, Mode require:
1. Pre-built cohort tables (dbt models)
2. Complex saved SQL snippets
3. Custom LookML/measures
4. Scheduled refreshes

### 7.2 With ASQL

Analysts could write:
```asql
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date) (
    pct(active, cohort_size) as retention
  )
```

Directly in the BI tool's SQL editor, with:
- No data engineering required
- Real-time cohort analysis
- Easy parameter changes (month → week, add filters)
- No stale data

### 7.3 The "Skip the Data Mart" Vision

Instead of:
```
raw_data → dbt → staging → cohort_models → BI tool
```

With ASQL:
```
raw_data → BI tool (with ASQL)
```

Not always possible (performance), but for exploration and ad-hoc analysis, this is transformative.

---

## 8. Related Features

### 8.1 Already Implemented ✅

These features that enhance cohort analysis are **already available**:

| Feature | Source | Cohort Use Case |
|---------|--------|-----------------|
| `first(col order by ...)` | WINDOW_UTILS.md | Determine cohort membership (first purchase, first login) |
| `last(col order by ...)` | WINDOW_UTILS.md | Most recent activity |
| `arg_max(col, by_col)` | WINDOW_UTILS.md | Alternative cohort membership |
| `prior(col)` | WINDOW_UTILS.md | Period-over-period comparisons |
| `next(col)` | WINDOW_UTILS.md | Forward-looking comparisons |
| `running_sum(col)` | WINDOW_UTILS.md | Cumulative LTV, cumulative retention |
| `running_avg(col)` | WINDOW_UTILS.md | Smoothed cumulative metrics |
| `rolling_avg(col, n)` | WINDOW_UTILS.md | Moving average retention |
| `per ... first by ...` | WINDOW_UTILS.md | Pipeline-native deduplication |
| `distinct on (col)` | WINDOW_UTILS.md | PostgreSQL-style dedup |
| `row_number() over (...)` | WINDOW_UTILS.md | Standard window functions |

### 8.2 Decided Syntax (Ready to Implement) ✅

| Feature | Source | Cohort Use Case |
|---------|--------|-----------------|
| `days(end - start)` | dates.md | Period calculation |
| `months(end - start)` | dates.md | Period calculation |
| `days_since_col` pattern | dates.md | Time since cohort start |
| `7 days ago` | dates.md | Filtering recent cohorts |
| `date + 7 days` | dates.md | Date arithmetic for period boundaries |

### 8.3 Still Needed for Full Cohort Support

| Feature | Priority | Description |
|---------|----------|-------------|
| `cohort by <func>(<col>)` modifier | HIGH | Add cohort dimension to any aggregation |
| Join inference | HIGH | Auto-join activity table to cohort table |
| Period calculation | HIGH | Auto-calculate `granularity(activity - cohort)` |
| Implicit `cohort_size` in parens | HIGH | Available inside `cohort by (...)` |
| Auto-sort | MEDIUM | Implicit `ORDER BY cohort_month, period` |
| `pivot` | ✅ Implemented | Already done (different branch) |
| `pct(part, whole)` | MEDIUM | Percentage utility (uses implicit `cohort_size`) |
| `delta(col)` | MEDIUM | `col - prior(col)` shorthand |
| `pct_change(col, decimals?)` | MEDIUM | Percentage change utility |

### 8.4 Synergies

The implemented features from WINDOW_UTILS.md and dates.md provide **most of the building blocks** for cohort analysis.

**Today (manual):**
```asql
with user_cohorts = from orders
  group by customer_id (
    month(first(order_date order by order_date)) as cohort_month
  )

from orders
  join user_cohorts on customer_id
  group by cohort_month, months(order_date - cohort_date) as period (
    count(distinct customer_id) as active,
    sum(total) as revenue
  )
  order by cohort_month, period
  select *, prior(active) as prev, running_sum(revenue) as cum_rev
```

**With `cohort by`:**
```asql
from orders
  group by month(order_date) (
    count(distinct customer_id) as active,
    sum(total) as revenue
  )
  cohort by month(customers.first_order_date) (
    prior(active) as prev,
    running_sum(revenue) as cum_rev
  )
```

The `cohort by` modifier handles join, period calculation, cohort_size, and auto-sort—everything else uses existing ASQL features.

---

## 9. Priority & Implementation Order

### Phase 1: Foundation ✅ COMPLETE

These features are **already implemented or decided**:

1. ✅ `first(column order by ...)` aggregate (WINDOW_UTILS.md)
2. ✅ `last(column order by ...)` aggregate (WINDOW_UTILS.md)
3. ✅ `prior()` / `next()` functions (WINDOW_UTILS.md)
4. ✅ `running_sum()` / `running_avg()` (WINDOW_UTILS.md)
5. ✅ `rolling_avg()` / `rolling_sum()` (WINDOW_UTILS.md)
6. ✅ `per ... first by ...` deduplication (WINDOW_UTILS.md)
7. ✅ `distinct on` (WINDOW_UTILS.md)
8. ✅ `days(end - start)` / `months(end - start)` syntax (dates.md)
9. ✅ `days_since_*` pattern (dates.md)
10. ✅ `7 days ago` syntax (dates.md)
11. ⏳ Document best practices for current ASQL cohort patterns

### Phase 2: Core Cohort Syntax (Next Priority)

12. `cohort by <func>(<table.column>)` modifier parsing
13. Join inference (activity table → cohort table via FK convention)
14. Period column calculation (`granularity(activity_date - cohort_date)`)
15. Auto-sort by `cohort_month, period`
16. Implicit `cohort_size` inside `cohort by (...)`

### Phase 3: Helper Functions

17. `pct(part, whole)` - percentage calculation
18. `delta(col)` - `col - prior(col)` shorthand
19. `pct_change(col, decimals?)` - percentage change utility

### Phase 4: Advanced Features

20. Explicit join key syntax: `cohort by ... on <key>`
21. Segmented cohorts: `cohort by channel, month(users.signup_date)`
22. Cohort filtering: `where cohort_month >= ...`
23. ✅ `pivot` already implemented (different branch)

### Phase 5: Polish

24. Cohort-aware query optimization
25. BI tool integrations
26. Documentation & examples
27. Cohort visualization recommendations

---

## 10. Comprehensive Examples

These 20 examples validate that the `cohort by` syntax handles all common cohort use cases. Each example uses **only existing ASQL syntax** (group by, prior, running_sum, etc.) plus the **one new `cohort by` modifier**.

> **Note**: When implementing, add the key examples below to `examples/pairs/` as ASQL/SQL pairs to verify correct SQL generation.

### 10.1 Basic Retention (User Signup Cohorts)

```asql
-- Monthly active users by signup cohort
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date)
```

**Output:** `cohort_month, period, active`

### 10.2 Retention with Percentage

```asql
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date) (
    pct(active, cohort_size) as retention
  )
```

**Output:** `cohort_month, period, active, cohort_size, retention`

### 10.3 Revenue Cohort (First Purchase)

```asql
from orders
  group by month(order_date) (
    sum(total) as revenue,
    count(distinct customer_id) as buyers
  )
  cohort by month(customers.first_order_date)
```

**Output:** `cohort_month, period, revenue, buyers`

### 10.4 LTV with Cumulative Revenue

```asql
from orders
  group by month(order_date) (sum(total) as revenue)
  cohort by month(customers.first_order_date) (
    running_sum(revenue) as cumulative,
    running_sum(revenue) / cohort_size as ltv
  )
```

### 10.5 Weekly Granularity

```asql
from sessions
  group by week(started_at) (
    count(*) as sessions,
    sum(duration_minutes) as total_minutes
  )
  cohort by week(users.signup_date)
```

### 10.6 Daily Granularity (First 30 Days)

```asql
from events
  where event_date <= signup_date + 30 days
  group by day(event_date) (count(distinct user_id) as active)
  cohort by day(users.signup_date)
```

### 10.7 Segmented Cohorts (By Channel)

```asql
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by users.channel, month(users.signup_date)
```

**Output:** `channel, cohort_month, period, active`

### 10.8 Segmented Cohorts (By Plan)

```asql
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by users.plan_type, month(users.signup_date)
```

### 10.9 Feature Adoption Cohort

```asql
-- Cohort by when users first used a feature
from feature_events
  where feature_name == "dashboard"
  group by week(event_date) (count(distinct user_id) as feature_users)
  cohort by week(users.first_dashboard_use_date)
```

### 10.10 Subscription Cohorts (Active Subscriptions)

```asql
from subscription_events
  where event_type == "active"
  group by month(event_date) (count(distinct subscription_id) as active_subs)
  cohort by month(subscriptions.start_date)
```

### 10.11 Filtered Activity

```asql
-- Only count purchase events
from events
  where event_type == "purchase"
  group by month(event_date) (
    count(distinct user_id) as purchasers,
    sum(amount) as revenue
  )
  cohort by month(users.signup_date)
```

### 10.12 Filtered Cohorts

```asql
-- Only US users in cohort
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date)
  where users.country == "US"  -- Filter cohort table
```

### 10.13 Period-over-Period Change

```asql
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date) (
    prior(active) as prev,
    delta(active) as change,
    pct_change(active) as growth
  )
```

### 10.14 Smoothed Retention (Rolling Average)

```asql
from events
  group by week(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date) (
    rolling_avg(active, 4) as four_week_avg
  )
```

### 10.15 Pivoted Output (Matrix View)

```asql
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date) (
    pct(active, cohort_size) as retention
  )
  pivot period as columns

-- Output (wide format):
-- cohort_month | cohort_size | retention_0 | retention_1 | retention_2 | ...
-- 2024-01      | 1000        | 100%        | 45%         | 32%         | ...
-- 2024-02      | 1200        | 100%        | 48%         | 35%         | ...
```

### 10.16 Multiple Metrics

```asql
from events
  group by month(event_date) (
    count(distinct user_id) as active,
    count(*) as events,
    avg(session_duration) as avg_session,
    sum(revenue) as revenue
  )
  cohort by month(users.signup_date)
```

### 10.17 Explicit Join Key

```asql
-- When inference doesn't work (non-standard FK name)
from orders
  group by month(order_date) (sum(total) as revenue)
  cohort by month(customers.first_purchase_date) on customer_id
```

### 10.18 Comparing Cohort Segments

```asql
-- Compare paid vs organic
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by users.channel, month(users.signup_date) (
    pct(active, cohort_size) as retention
  )
  pivot period as columns
```

### 10.19 Recent Cohorts Only

```asql
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date)
  where cohort_month >= 6 months ago  -- Filter to recent cohorts
```

### 10.20 Churn Analysis

```asql
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date) (
    cohort_size - active as churned,
    pct(cohort_size - active, cohort_size) as churn_rate
  )
```

---

## 11. Open Questions

1. **Join inference ambiguity?**
   - What if multiple FKs could work? (e.g., `events.user_id` vs `events.created_by_id`)
   - Solution: Require explicit `on` clause when ambiguous
   ```asql
   cohort by month(users.signup_date) on created_by_id
   ```

2. **Period column naming?**
   - Just `period` (simple) vs `months_since_cohort` (explicit)?

3. **Incomplete periods?**
   - Should period 3 show if we only have partial data?
   - Option: Add a `where period_complete` filter

4. **Performance for large datasets?**
   - At what scale does this need materialization?
   - Could ASQL suggest/generate dbt models?

5. **NULL handling in cohort column?**
   - Users without signup_date → exclude or create "unknown" cohort?
   - Default: exclude (filter out NULLs)

6. **Multiple activity tables?**
   - Union them first, then apply cohort:
   ```asql
   from (events union purchases union logins)
     group by month(created_at) (count(distinct user_id) as active)
     cohort by month(users.signup_date)
   ```

---

## 11.5 References & Inspiration

- **Amplitude's Retention Analysis**: Best-in-class cohort UI
- **Mixpanel's Cohort Charts**: Popular visualization patterns
- **Mode Analytics Cohort Templates**: Common SQL patterns
- **dbt's metrics package**: Semantic layer approach
- **Looker's LookML cohort patterns**: Declarative cohort definitions
- **Excel Pivot Tables**: For the pivot output idea

---

## 12. Parsing & Implementation Notes

### 12.1 Syntax Compatibility

The `cohort by` modifier syntax is designed to be **fully compatible** with existing ASQL and SQLGlot:

**Already-working parts:**
- `from events` - standard
- `group by month(event_date) (...)` - existing ASQL group by
- `count(distinct user_id)` - standard aggregation
- `prior()`, `running_sum()`, `rolling_avg()` - already implemented

**New parts to implement:**
- `cohort by <func>(<table.col>)` - new pipeline modifier (parallels `group by`)
- `cohort by ... ( <derivations> )` - parens for derived columns
- Implicit `cohort_size` inside parens
- Auto-sort by `cohort_month, period`
- `on <key>` - optional explicit join key

### 12.2 Parsing Considerations

The `cohort by` clause is unambiguous:
```
cohort by [<segment>,] <func>(<table.column>) [on <join_key>] [( <derivations> )]
          └─ optional    └─ month/week/day    └─ dotted      └─ optional    └─ optional
```

**No conflicts with existing syntax:**
- `cohort by` is a new keyword pair (not used elsewhere)
- Parallels `group by` structure exactly
- `<func>()` reuses existing time functions (month, week, day)
- `<table.column>` is standard dotted identifier syntax
- Parens for derivations mirrors `group by ... (...)` syntax

### 12.3 SQL Generation

Each `cohort by` modifier transforms to:
1. A CTE for cohort assignment (with cohort size calculation)
2. A JOIN to the cohort CTE
3. Period calculation column
4. Modified GROUP BY
5. ORDER BY `cohort_month, period`
6. Derived column calculations from parens (if present)

This is straightforward SQL generation via SQLGlot.

---

## 13. Documentation & Examples TODO

### 13.1 Playground Examples

When implementing, add these examples to the playground:

```yaml
# examples/pairs/XX_cohort_basic.asql
# examples/pairs/XX_cohort_retention.asql  
# examples/pairs/XX_cohort_ltv.asql
# examples/pairs/XX_cohort_segmented.asql
# examples/pairs/XX_cohort_pivoted.asql
```

**Priority examples for playground:**
1. Basic retention cohort (the "hello world" of cohorts)
2. Retention with percentage calculation
3. LTV with running_sum()
4. Segmented cohorts by channel
5. Pivoted matrix output

### 13.2 Documentation Requirements

**docs/spec.md** - Add section on cohort analysis:
- Syntax reference
- How join inference works
- Period calculation explanation
- Examples for each use case

**docs/examples.md** - Add cohort examples:
- Before/after SQL comparison
- Common patterns (retention, LTV, churn)
- Advanced patterns (segmented, filtered)

**README.md** - Feature highlight:
- Add cohort analysis to feature list
- Simple example showing the power

### 13.3 Test Coverage

When implementing, ensure tests for:
- [ ] Basic `cohort by` parsing
- [ ] Granularity variations (month, week, day)
- [ ] Join inference (convention-based FK detection)
- [ ] Explicit `on` clause when inference fails
- [ ] Implicit `cohort_size` inside parens
- [ ] Auto-sort by `cohort_month, period`
- [ ] Derived columns inside `cohort by (...)`
- [ ] Period calculation for each granularity
- [ ] Integration with `pivot`
- [ ] Segmented cohorts (multiple cohort dimensions)
- [ ] Helper functions: `pct()`, `delta()`, `pct_change()`
- [ ] SQL generation for each dialect (Postgres, MySQL, BigQuery, Snowflake)

### 13.4 Error Messages

Implement clear errors for:
- "Cannot infer join between `events` and `users`. Use `cohort by ... on user_id`"
- "Cohort granularity `day` is finer than group by granularity `month`"
- "Cohort column `users.signup_date` not found"
- "Unknown column in cohort derivation: `cohort_size` only available inside `cohort by (...)`"

---

## 14. Conclusion

Cohort analysis represents one of the highest-value opportunities for ASQL. The gap between current SQL complexity (50+ lines) and ideal expressiveness (3 lines) is massive.

### Progress So Far

**Good news**: Many building blocks are already implemented:
- ✅ `first()` / `last()` with ORDER BY for cohort membership
- ✅ `prior()` / `next()` for period-over-period analysis
- ✅ `running_sum()` for cumulative LTV
- ✅ `per ... first by ...` for deduplication
- ✅ `days(end - start)` / `months(end - start)` for period calculation
- ✅ `7 days ago` syntax for filtering
- ✅ `pivot` for wide format output

**Today's ASQL** already provides ~30-40% reduction in cohort query complexity compared to SQL.

### The Dream

With `cohort by`:

```asql
from events
  group by month(event_date) (count(distinct user_id) as active)
  cohort by month(users.signup_date) (
    pct(active, cohort_size) as retention
  )
```

Write any query, add `cohort by` at the end. This provides **90%+ reduction** in complexity and enables:

1. **Analysts** to write cohort queries directly without data engineering help
2. **Data teams** to reduce the number of rollup tables they maintain
3. **BI tools** to support real-time cohort analysis out of the box
4. **Organizations** to get faster, more flexible analytics

### Key Design Decisions

1. **`cohort by` parallels `group by`** - Same pattern, easy to learn
2. **Function syntax `month(col)`** - Granularity is part of the function, not a separate keyword
3. **Implicit `cohort_size`** - Available inside `cohort by (...)`, no separate `with cohort_size`
4. **Auto-sort** - Results ordered by `cohort_month, period` automatically
5. **Parens for derivations** - Window functions auto-partitioned by cohort

### Syntax Validated

The 20 examples in Section 10 demonstrate that the `cohort by` syntax handles all common cohort use cases:
- Basic retention, LTV, churn
- Multiple granularities (month, week, day)
- Segmented cohorts
- Filtered activity and cohorts
- Integration with existing features (prior, running_sum, rolling_avg, pivot)

The syntax is **minimal** (just one new modifier), **composable** (works with any group by query), and **unambiguous** (no parsing conflicts).

The building blocks are in place. The `cohort by` modifier is the elegant, composable next step.

---

**End of Document**

