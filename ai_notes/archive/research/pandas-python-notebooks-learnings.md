# ASQL + Pandas/Notebooks: Capturing Common Analytic Patterns

## Summary

This document analyzes common pandas operations and Python notebook patterns to identify features that could be elevated into ASQL. For each pattern we show:

1. **Pandas** - How it's done in pandas
2. **Current ASQL** - How you'd do it today in ASQL (may be verbose)
3. **Proposed Enhancement** - Potential new syntax (if any improvement needed)

**Key insight:** Notebooks are often used because SQL is too verbose for exploratory analysis. If ASQL can match pandas' expressiveness while compiling to SQL, analysts can work at scale without leaving their familiar mental model.

---

## Pattern Analysis

### 1. Null Filling (Simple)

#### Pandas
```python
df['amount'].fillna(0)
df['name'].fillna('Unknown')
df.fillna({'amount': 0, 'name': 'Unknown'})
```

#### Current ASQL ✅ Already Good
```asql
-- Already have the ?? operator (coalesce)
from orders
select 
  amount ?? 0 as amount,
  name ?? 'Unknown' as name
```

#### Proposed Enhancement
**None needed.** The `??` operator is concise and intuitive. No new syntax required.

---

### 2. Forward Fill / Backward Fill (Time Series)

#### Pandas
```python
# Carry forward last known value
df['value'].fillna(method='ffill')

# Within groups
df.groupby('user_id')['value'].fillna(method='ffill')
```

**Use case:** Sensor data with gaps, stock prices on non-trading days, slowly-changing dimensions where NULLs should inherit the previous value.

#### Why `prior()` doesn't solve this

ASQL has `prior(col)` which maps to LAG, but that's different from forward fill:

| timestamp | value | prior(value) | fill_forward |
|-----------|-------|--------------|--------------|
| 1         | 100   | NULL         | 100          |
| 2         | NULL  | 100          | 100 ← from row 1 |
| 3         | NULL  | **NULL** ← problem! | 100 ← still from row 1 |
| 4         | 200   | NULL         | 200          |

- `prior()` = value from **immediately previous row** (row 3 gets NULL because row 2 is NULL)
- Forward fill = **last non-null value** from any preceding row (row 3 still gets 100)

Forward fill requires `IGNORE NULLS` which isn't exposed in current ASQL.

#### Current ASQL (Verbose)
```asql
from events
select 
  user_id,
  timestamp,
  coalesce(value, 
    last_value(value ignore nulls) over (
      partition by user_id 
      order by timestamp 
      rows between unbounded preceding and 1 preceding
    )
  ) as value
```

This is **very verbose** for a common time series pattern.

#### Proposed Enhancement

#### Clarification: Two Different "Fill" Operations

There are two distinct "fill" operations in data analysis - ASQL handles them differently:

| Operation | What it does | Example | ASQL Solution |
|-----------|--------------|---------|---------------|
| **Gap Fill** | Adds missing ROWS to time series | Jan, Mar, Apr → Jan, **Feb**, Mar, Apr | **auto_spine** (automatic) |
| **Forward Fill** | Fills NULL VALUES with previous value | [100, NULL, NULL] → [100, 100, 100] | Not yet implemented |

These are fundamentally different operations.

📄 **For detailed analysis of gap filling, spines, the `guarantee()` proposal, continuous vs. discrete columns, and when to spine vs. not, see [spines.md](../designs/spines.md).**

**Summary of recommendations:**

**ASQL auto_spine (gap filling) - IMPLEMENTED:**

Gap filling is now handled **automatically** by auto_spine. Date truncations in GROUP BY are automatically gap-filled:

```asql
from orders
where created_at >= @2024-01-01 and created_at < @2025-01-01
group by month(created_at) as month (
  sum(amount) ?? 0 as revenue  # ?? 0 sets default for filled rows
)
-- All 12 months appear, even those with $0 revenue
```

The `fill` command was originally proposed but never implemented - auto_spine made it unnecessary.

**Forward Fill (not yet implemented):**

| Name | Pros | Cons |
|------|------|------|
| `fill_forward` | Pandas-familiar | Clear intent |
| `ffill` | Short, pandas-style | Cryptic |
| `carry_forward` | Very descriptive | Longer |
| `propagate` | Describes action | Unfamiliar |
| `prior_nonnull()` | Function, composable | Less discoverable |

#### Reframe: SQL's Missing Data Problem

SQL has a fundamental "shortcoming" for analytics: **dates with no data simply don't appear in results.**

```sql
SELECT month, SUM(sales) FROM orders GROUP BY month
-- If no sales in Feb, Feb is MISSING from results!
```

This is technically correct (there were no rows to aggregate) but **wrong for analytics**:
- Dashboards show gaps instead of zeros
- Charts have missing data points  
- Trend analysis breaks

**For analytics, you almost always want complete date ranges.**

#### Should ASQL Auto-Spine Dates? → ✅ DECIDED: Yes, auto_spine is ON by default

> **IMPLEMENTED**: Auto-spine is now on by default (`auto_spine = true`). Date truncations in GROUP BY are automatically gap-filled. Range is inferred from WHERE clause bounds, falling back to MIN/MAX from data. Use `SET auto_spine = false` to disable, or filter with `WHERE revenue > 0` to remove filled rows.
>
> See `ai_notes/spines.md` for full implementation details.

| Approach | Pros | Cons |
|----------|------|------|
| **Auto-spine all date GROUP BYs** ✅ | Zero effort, matches analyst intent | Implicit magic, row count changes unexpectedly |
| Opt-in via function | Explicit intent | Extra syntax |
| Opt-out (auto by default) | Matches 90% use case | Surprising for SQL users |

**The case for auto-spine (why we chose this):**
- Analytics queries almost always want complete date ranges
- It's what every BI tool does (Looker, Tableau, etc.)
- The current SQL behavior is a constant source of bugs

**The case against auto-spine by default (addressed):**
- Implicit behavior that differs from SQL could confuse veterans → Can disable with `SET auto_spine = false`
- Need to infer date range (min/max from data? what if data is sparse?) → Inferred from WHERE clause, fallback to MIN/MAX
- Not all queries need complete ranges (see below) → Filter with `WHERE col > 0` to remove filled rows

#### When Spining is Good vs. Not

| Context | Want Spine? | Why |
|---------|-------------|-----|
| **Dashboard/chart queries** | ✅ Yes | Charts need complete date ranges, no gaps |
| **Time series analysis** | ✅ Yes | Rolling averages, YoY comparisons break with gaps |
| **Reports for stakeholders** | ✅ Yes | Executives expect all periods to appear |
| **Mart models (dbt)** | ✅ Usually | End-user tables should be complete |
| **Staging models (dbt)** | ❌ No | Just cleaning data, preserve original sparsity |
| **"Show months with sales > $1M"** | ❌ No | You explicitly want to exclude zero months |
| **Event data ("days with errors")** | ❌ No | You want ONLY days when errors occurred |
| **Intermediate transforms** | ⚠️ Maybe | Spine rows might cause issues in downstream joins |
| **Data validation/QA** | ❌ No | You WANT to see gaps to identify issues |
| **Sparse categorical data** | ❌ No | Not all product/region combos should exist |

**Key insight: Analytics queries usually want spining, transformation/modeling steps often don't.**

> **IMPLEMENTED SOLUTION**: Auto-spine is ON by default for date truncations. For non-date columns, use `guarantee()` with explicit values. To opt out: `SET auto_spine = false` or filter results.

```asql
-- Default: auto-spine fills all months (dates gap-filled automatically)
from orders
where created_at >= @2024-01-01 and created_at < @2025-01-01
group by month(created_at) as month (sum(amount) ?? 0 as revenue)

-- Non-dates: use guarantee() for explicit spine values
from sales
group by guarantee(region, ['North', 'South', 'East', 'West']) (
  sum(amount) ?? 0 as total
)

-- Opt-out: disable auto-spine for this query
SET auto_spine = false;
from raw_orders
group by month(created_at) as month (sum(amount) as revenue)
```

#### Smart Range Detection: Use the WHERE Clause!

Most analytics queries already specify a date range in WHERE:

```asql
from orders
where created_at >= '2024-01-01' and created_at < '2025-01-01'
group by guarantee(month(created_at)) as month (...)
```

**Why not infer the spine range from the WHERE clause?**

Different BI tools handle gap-filling differently:

| Approach | Examples | Trade-offs |
|----------|----------|------------|
| **Frontend zero-fill** | Chartio, many others | SQL stays pure; frontend fills gaps for charts. Works well but puts burden on visualization layer. |
| **Query modification** | Some semantic layers | Modify SQL to add spines. More complex, can surprise users. |
| **Explicit in query** | Raw SQL users | User must know the pattern. Easy to forget. |

Chartio's approach (frontend zero-fill) is clean - keeps SQL pure and simple. But it requires the frontend to know about dates and filling. When users write their own SQL, you can't trust they'll handle it.

**For ASQL specifically:**
- ASQL is already "not pure SQL" - it's a higher-level language that compiles to SQL
- The "purity" concern doesn't apply the same way
- We can make this a language feature that "just works"

ASQL could infer the spine range from the WHERE clause:

```asql
from orders
where created_at between '2024-01-01' and '2024-12-31'
group by guarantee(month(created_at)) as month (
  sum(amount) ?? 0 as revenue
)
-- Spine automatically uses Jan 2024 - Dec 2024 from the WHERE clause!
```

**Range detection priority:**
1. Explicit range in `guarantee()`: `guarantee(month(...), '2024-01-01' to '2024-12-01')`
2. Infer from WHERE clause bounds on the same column
3. Fall back to MIN/MAX from actual data

**Edge cases:**
- No date filter? → Use MIN/MAX from data
- Complex WHERE (OR conditions, subqueries)? → Fall back to MIN/MAX or require explicit
- Multiple date columns? → Only infer for the column being grouped

**This is powerful because:**
- Zero extra syntax for the common case
- Matches user intent (they filtered to a range, they want that range)
- How every BI tool works
- Explicit override available when needed

```asql
-- Common case: WHERE clause defines range (zero extra work)
from orders
where created_at >= '2024-01-01'
group by guarantee(month(created_at)) as month (...)
-- Uses 2024-01-01 to MAX(created_at) from data

-- Explicit override when needed
from orders
where created_at >= '2024-01-01'  
group by guarantee(month(created_at), stop = '2024-12-01') as month (...)
-- Uses 2024-01-01 from WHERE, explicit stop
```

#### Proposed: `guarantee()` or `spine()` Function

Instead of magic, make it explicit but easy:

**Option 1: `guarantee()` - ensure all values in range exist**
```asql
from orders
group by guarantee(month(created_at)) as month (
  sum(amount) as revenue
)
-- Guarantees all months from min to max appear, missing = NULL

-- With explicit range:
group by guarantee(month(created_at), start='2024-01-01', stop='2024-12-01') as month

-- With default values:
group by guarantee(month(created_at)) as month (
  sum(amount) as revenue ?? 0
)
```

**Option 2: `spine()` - generate the spine inline**
```asql
from orders
group by spine(month(created_at)) as month (
  sum(amount) as revenue
)
```

**Option 3: `range()` - specify you want the full range**
```asql
from orders
group by range(month(created_at)) as month (
  sum(amount) as revenue
)
```

**Option 4: `complete()` - R/tidyr-inspired**
```asql
from orders
group by complete(month(created_at)) as month (
  sum(amount) as revenue
)
```

#### My Recommendation

I like **`guarantee()`** because:
- It reads as a contract: "I guarantee this column will have all values"
- Clear intent: you're guaranteeing completeness
- Works for non-dates too: `guarantee(category)` could ensure all categories appear

```asql
-- Basic usage (auto-detect range from data)
from orders
group by guarantee(month(created_at)) as month (
  sum(amount) as revenue
)

-- With explicit range
from orders  
group by guarantee(month(created_at), '2024-01-01' to '2024-12-01') as month (
  sum(amount) as revenue
)

-- With default for missing
from orders
group by guarantee(month(created_at)) as month (
  sum(amount) ?? 0 as revenue
)
```

The current `fill month with {revenue: 0}` becomes unnecessary - you just use `guarantee()` in the GROUP BY and `?? 0` for defaults.

---

**Summary: Two "fill" operations, better names:**

| Current Name | What It Does | Proposed Name |
|--------------|--------------|---------------|
| `fill month` | Add missing date ROWS (spining) | `guarantee(month(...))` in GROUP BY |
| (new) | Propagate VALUES forward | `carry forward` or `prior_nonnull()` |

#### Proposed Enhancement Options for Forward Fill

**Option A: `carry forward` / `carry backward` commands**
```asql
from events
carry forward value by user_id order by timestamp

-- Or backward
from events
carry backward value by user_id order by timestamp
```

**Option B: Add `ignore nulls` option to `prior()`**
```asql
-- With full window syntax
from events
select *, value ?? prior(value ignore nulls) over (partition by user_id order by timestamp) as value

-- Could we simplify with shorthand? Maybe:
from events  
select *, value ?? prior(value ignore nulls by user_id order by timestamp) as value
```

**Option C: New `prior_nonnull()` function**
```asql
-- Dedicated function that keeps looking back until it finds a non-null
from events
select *, value ?? prior_nonnull(value by user_id order by timestamp) as value
```

**Why SQL window functions don't "carry forward":**

SQL evaluates all rows in parallel against the **original data**. When computing row 3:
- It doesn't see "row 2 was filled with 100" 
- It sees "row 2's original value was NULL"

This is fundamental to how window functions work - they're not iterative/procedural. The `IGNORE NULLS` clause explicitly tells the window function to skip NULLs when looking backward, which is the only way to achieve forward fill in SQL.

**Value:** Extremely common time series pattern. The verbose SQL is 6+ lines; any of these options reduces it to 1 line.

---

### 3. Drop Rows with Nulls

#### Pandas
```python
df.dropna()                     # Any null in any column
df.dropna(subset=['amount'])    # Specific columns
```

#### Current ASQL ✅ Already Fine
```asql
-- Drop if amount is null
from orders
where amount is not null

-- Multiple columns
from orders
where amount is not null 
  and category is not null
```

#### Proposed Enhancement
**Low priority.** The current `where ... is not null` is readable and explicit. A shorthand like `drop_null amount, category` saves little and hides intent.

---

### 4. Value Mapping / Replace

#### Pandas
```python
df['status'].replace({'A': 'Active', 'I': 'Inactive'})
df['status'].map({'A': 'Active', 'I': 'Inactive'})
```

#### Current ASQL ✅ Already Has `when`
```asql
from orders
select 
  when status
    is 'A' then 'Active'
    is 'I' then 'Inactive'
    otherwise 'Unknown'
  as status_label
```

The `when` syntax is already much cleaner than SQL's verbose CASE.

#### Proposed Enhancement
**None needed.** The `when` statement already handles this elegantly. A dictionary-style shorthand (`status => {'A': 'Active'}`) would be redundant.

---

### 5. Adding Computed Columns

#### Pandas
```python
df['total'] = df['price'] * df['quantity']
df['year'] = df['date'].dt.year
df['is_large'] = df['amount'] > 1000
```

#### Current ASQL ✅ Works Today
```asql
from orders
select *,
  price * quantity as total,
  year(date) as year,
  amount > 1000 as is_large
```

#### Proposed Enhancement
**None needed.** The `select *, <new columns>` pattern works well. 

**Note:** Some code references a `derive` keyword but this does NOT exist in the ASQL spec. Use `select *, ...` instead.

---

### 6. Conditional Column (np.where / np.select)

#### Pandas
```python
# Simple condition
df['tier'] = np.where(df['amount'] > 1000, 'high', 'low')

# Multiple conditions
df['tier'] = np.select(
    [df['amount'] > 1000, df['amount'] > 100],
    ['high', 'medium'],
    default='low'
)
```

#### Current ASQL ✅ Already Has `when`
```asql
-- Simple condition
from orders
select *,
  when amount > 1000 then 'high' else 'low' as tier

-- Multiple conditions
from orders
select *,
  when amount
    > 1000 then 'high'
    > 100 then 'medium'
    otherwise 'low'
  as tier
```

#### Proposed Enhancement (Ternary Syntax)
For simple one-liners, a ternary could be shorter:

```asql
-- Potential ternary syntax (not yet decided)
select amount > 1000 ? 'high' : 'low' as tier       -- JS-style
select 'high' if amount > 1000 else 'low' as tier   -- Python-style
```

**Value:** Medium. The `when` works fine but ternary would be nicer for simple cases. This applies anywhere expressions are allowed, not just in select.

---

### 7. Binning / Bucketing (pd.cut)

#### Pandas
```python
# Custom bin edges with labels
pd.cut(df['score'], 
       bins=[0, 60, 70, 80, 90, 100], 
       labels=['F', 'D', 'C', 'B', 'A'])

# Equal-width bins
pd.cut(df['age'], bins=10)
```

#### Current ASQL (Uses `when`)
```asql
from students
select *,
  when score
    >= 90 then 'A'
    >= 80 then 'B'
    >= 70 then 'C'
    >= 60 then 'D'
    otherwise 'F'
  as grade
```

This is readable but verbose for many bins.

#### Proposed Enhancement
```asql
-- bucket() function for common binning
from students
select *,
  bucket(score, [0, 60, 70, 80, 90, 100], ['F', 'D', 'C', 'B', 'A']) as grade

-- Fixed-width bins
from customers
select *,
  bucket(age, width=10) as age_bucket  -- 0-10, 10-20, etc.
```

**Value:** Medium. `when` already works; `bucket()` saves lines for many bins but isn't critical.

---

### 8. Rolling / Window Aggregations

#### Pandas
```python
df['rolling_avg'] = df['value'].rolling(7).mean()
df['cumsum'] = df['value'].cumsum()
df['prev_value'] = df['value'].shift(1)
```

#### Current ASQL ✅ Already Exists
The spec already defines these functions:

```asql
from daily_sales
order by date
select *,
  rolling_avg(revenue, 7) as seven_day_avg,
  rolling_sum(revenue, 30) as monthly_total,
  running_sum(amount) as cumulative_amount,
  prior(revenue) as prev_revenue
```

#### Proposed Enhancement
**None needed.** ASQL already has:
- `rolling_avg(col, n)`, `rolling_sum(col, n)`
- `running_sum(col)`, `running_avg(col)`, `running_count(*)`
- `prior(col)` (LAG), `next(col)` (LEAD)

These already match the pandas mental model.

---

### 9. Rank and Top-N per Group

#### Pandas
```python
# Rank within groups
df['rank'] = df.groupby('category')['sales'].rank(ascending=False)

# Top N per group
df.groupby('category').apply(lambda x: x.nlargest(5, 'sales'))
```

#### Current ASQL ✅ Already Has `per`
```asql
-- Top 1 per group (deduplication)
from orders
per customer_id first by -order_date

-- Add row numbers per group
from products
per category number by -sales as rank
where rank <= 5
```

#### Proposed Enhancement
A `top N` shorthand could be slightly cleaner:

```asql
-- Potential shorthand
from products
top 5 by sales per category
```

**Value:** Low. The `per ... number` + `where` pattern already works and is explicit.

---

### 10. Sampling

#### Pandas
```python
df.sample(n=100)        # Random n rows
df.sample(frac=0.1)     # Random 10%
df.head(10)             # First n rows
```

#### Current ASQL (Partial)
```asql
-- First n rows (already works)
from orders
limit 10

-- Random sampling varies by dialect, no ASQL abstraction yet
```

There's no portable `sample` in ASQL currently. You'd write dialect-specific SQL.

#### Proposed Enhancement
```asql
from orders
sample 100              -- random n rows

from orders
sample 10%              -- random percentage

from orders
sample 100 per category -- stratified sampling
```

**Compilation:**
```sql
-- BigQuery
SELECT * FROM orders TABLESAMPLE SYSTEM (10 PERCENT)

-- Snowflake
SELECT * FROM orders SAMPLE (10)

-- Fallback
SELECT * FROM orders ORDER BY RANDOM() LIMIT n
```

**Value:** High. Sampling syntax varies wildly across warehouses. A portable abstraction is valuable.

---

### 11. Explode / Unnest Arrays ✅ IMPLEMENTED

#### Pandas
```python
df.explode('tags')                    # One row per array element
df['col'].str.split(',').explode()    # Split string, then explode
```

#### ASQL ✅
```asql
from posts
explode tags as tag

-- Split and explode
from posts
explode split(tags_csv, ',') as tag
```

**Compiles to dialect-specific SQL:**
- **Postgres/DuckDB:** `FROM posts, UNNEST(tags) AS tag`
- **BigQuery:** `FROM posts CROSS JOIN UNNEST(tags) AS tag`
- **Snowflake:** `FROM posts CROSS JOIN (SELECT value AS tag FROM TABLE(FLATTEN(...)))`

**Status:** Implemented! Single keyword handles cross-dialect complexity.

---

### 12. Gap Filling in Time Series

#### Pandas
```python
# Resample fills gaps automatically
df.set_index('date').resample('D').sum().fillna(0)
```

#### Current ASQL ✅ Already Has `fill`
```asql
-- fill adds missing date rows after group by
from orders
group by month(created_at) as month (
  sum(amount) as revenue
)
fill month with {revenue: 0}
```

#### Proposed Enhancement
**None needed.** The `fill` command already handles this use case.

**Important distinction:**
- `fill month` = add missing DATE ROWS (gap filling)
- `fill_forward value` = propagate VALUES within existing rows (Section 2)

These are different operations!

---

### 13. Lag/Lead for Period Comparisons

#### Pandas
```python
df['prev_value'] = df.groupby('id')['value'].shift(1)
df['yoy'] = df['value'] - df.groupby('id')['value'].shift(12)
```

#### Current ASQL ✅ Already Has `prior`
```asql
from monthly_revenue
order by month
select *,
  prior(revenue) as prev_revenue,
  revenue - prior(revenue) as mom_change,
  revenue - prior(revenue, 12) as yoy_change
```

With partition:
```asql
from monthly_revenue
select *,
  prior(revenue) over (partition by product_id order by month) as prev_revenue
```

#### Proposed Enhancement
**None needed.** ASQL's `prior()` and `next()` already map to LAG/LEAD cleanly.

---

### 14. Data Profiling / Describe

#### Pandas
```python
df.describe()           # Summary stats
df.info()               # Column types, null counts
df['col'].value_counts() # Frequency distribution
```

#### Current ASQL (Verbose)
```asql
-- Value counts is easy
from orders
group by status (count(*) as count)
order by -count

-- But describe() would be very verbose:
from orders
select
  'amount' as column,
  count(*) as count,
  count(*) - count(amount) as null_count,
  min(amount) as min,
  max(amount) as max,
  avg(amount) as mean
-- Would need UNION ALL for each column...
```

#### Proposed Enhancement
```asql
from orders
describe

-- Or specific columns
from orders
describe amount, quantity
```

Generates a profiling table with count, nulls, min, max, mean, distinct, etc.

**Value:** Medium. Useful for exploration but not core analytics. Could be a CLI feature rather than language feature.

---

### 15. One-Hot Encoding

#### Pandas
```python
pd.get_dummies(df['category'])
```

#### Current ASQL (Verbose)
```asql
-- Requires knowing all values upfront
from orders
select *,
  when category is 'electronics' then 1 else 0 as category_electronics,
  when category is 'clothing' then 1 else 0 as category_clothing,
  when category is 'food' then 1 else 0 as category_food
```

#### Proposed Enhancement
```asql
from orders
one_hot category

-- Produces: category_electronics, category_clothing, etc.
```

**Value:** Medium. Common for ML feature prep in warehouse. Requires schema lookup for distinct values.

---

## Summary: What's Already in ASQL vs. Proposed

### ✅ Already Works Well (No Changes Needed)

| Pattern | ASQL Syntax |
|---------|-------------|
| Null coalescing | `col ?? default` |
| Conditional columns | `when ... then ... otherwise` |
| Adding computed columns | `select *, expr as name` |
| Rolling aggregations | `rolling_avg(col, n)`, `rolling_sum(col, n)` |
| Cumulative | `running_sum(col)`, `running_avg(col)` |
| Lag/Lead | `prior(col)`, `next(col)` |
| Deduplication | `per group first by -date` |
| Top N per group | `per group number by -col` + `where rank <= N` |
| Gap filling dates | `fill month with {col: 0}` |
| Value counts | `group by col (count(*))` |

### 🔶 Proposed Enhancements (High Value)

| Pattern | Proposed Syntax | Value |
|---------|-----------------|-------|
| Forward/back fill | `fill_forward col by group order by date` | **Very High** - verbose window function |
| Sampling | `sample 100` or `sample 10%` | **High** - dialect varies wildly |
| Explode arrays | `explode col as alias` | **High** - dialect varies wildly |
| Ternary expression | `cond ? a : b` or `a if cond else b` | **Medium** - shorter than `when` for simple cases |

### 🔷 Proposed Enhancements (Medium Value)

| Pattern | Proposed Syntax | Value |
|---------|-----------------|-------|
| Binning | `bucket(col, edges, labels)` | Medium - `when` already works |
| Describe/profile | `describe` | Medium - exploration tool |
| One-hot encoding | `one_hot col` | Medium - ML prep |

### ❌ Not Needed (Already Solved)

| Pattern | Why Not Needed |
|---------|----------------|
| `fill_null` command | Already have `??` operator |
| `drop_null` command | Already have `where col is not null` |
| `derive` keyword | Use `select *, ...` instead |
| Dictionary mapping `=>` | Already have `when` statement |

---

## Key Insight

The common thread: **pandas succeeds because it has good defaults and concise syntax for common patterns.** 

ASQL already covers most patterns well! The genuine gaps are:
1. **Forward/backward fill** - Very verbose window function pattern
2. **Sampling** - Dialect-specific, no portable syntax
3. **Explode/unnest** - Dialect-specific, no portable syntax

Everything else is either already good (`??`, `when`, `prior`, `rolling_avg`, `fill`, `per`) or low priority (`bucket`, `describe`).
