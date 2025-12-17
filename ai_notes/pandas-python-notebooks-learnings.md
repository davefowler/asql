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

#### Naming Confusion: Two Different "Fill" Operations

ASQL currently has a `fill` command, but it does something completely different from forward fill:

| Operation | What it does | Example |
|-----------|--------------|---------|
| **Gap Fill (current `fill`)** | Adds missing ROWS to time series | Jan, Mar, Apr → Jan, **Feb**, Mar, Apr |
| **Forward Fill** | Fills NULL VALUES with previous value | [100, NULL, NULL] → [100, 100, 100] |

These are fundamentally different operations.

📄 **For detailed analysis of gap filling, spines, the `guarantee()` proposal, continuous vs. discrete columns, and when to spine vs. not, see [spines.md](spines.md).**

**Summary of recommendations:**

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

### 11. Explode / Unnest Arrays

#### Pandas
```python
df.explode('tags')                    # One row per array element
df['col'].str.split(',').explode()    # Split string, then explode
```

#### Current ASQL (No Abstraction Yet)
You'd write dialect-specific SQL:

```sql
-- BigQuery
SELECT *, tag FROM posts, UNNEST(tags) as tag

-- Postgres
SELECT *, tag FROM posts, LATERAL unnest(tags) as tag

-- Snowflake
SELECT *, t.value as tag FROM posts, LATERAL FLATTEN(tags) t
```

#### Proposed Enhancement
```asql
from posts
explode tags as tag

-- Split and explode
from posts
explode split(tags_csv, ',') as tag
```

**Value:** High. Array handling syntax varies wildly between warehouses. A single keyword would handle cross-dialect complexity.

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
