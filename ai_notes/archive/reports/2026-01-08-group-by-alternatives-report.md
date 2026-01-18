# GROUP BY Naming & Syntax Alternatives

**Date**: 2026-01-08

## The Problem with "GROUP BY"

"GROUP BY" is a confusing term because:
1. It sounds like you're organizing data into groups (like folders)
2. The actual operation is **aggregation** - computing summary values
3. The mental model should be "for each X, compute Y"

Your suggestion is spot-on:
```sql
-- Instead of this:
group by customer_id (sum(amount))

-- This is clearer:
for each customer_id get (sum(amount))
```

---

## Survey of Alternative Syntax

### 1. **PRQL** - Uses `group` + `aggregate`

```prql
from orders
group customer_id (
  aggregate {
    total = sum amount,
    count = count *
  }
)
```

**Key insight**: PRQL separates the concepts:
- `group` = the grouping columns
- `aggregate` = the calculations

### 2. **Malloy** (Google) - Uses `group_by` with `aggregate`

```malloy
query: orders -> {
  group_by: customer_id
  aggregate: 
    total is sum(amount),
    order_count is count()
}
```

**Key insight**: Malloy makes it explicit that you're computing aggregates, not just "grouping"

### 3. **dplyr (R/tidyverse)** - Uses `group_by` + `summarize`

```r
orders %>%
  group_by(customer_id) %>%
  summarize(
    total = sum(amount),
    count = n()
  )
```

**Key insight**: `summarize` is much clearer than SELECT - you're creating a summary!

### 4. **Pandas (Python)** - Uses `groupby` + `agg`

```python
orders.groupby('customer_id').agg({
    'amount': ['sum', 'mean', 'count']
})
```

### 5. **Polars (Python/Rust)** - Uses `group_by` + `agg`

```python
orders.group_by('customer_id').agg([
    pl.sum('amount').alias('total'),
    pl.count().alias('order_count')
])
```

### 6. **Kusto (Azure Data Explorer)** - Uses `summarize`

```kusto
orders
| summarize total=sum(amount), count=count() by customer_id
```

**Key insight**: Kusto puts `summarize` FIRST, then `by` - reads as "summarize these values by these columns"

### 7. **InfluxQL** - Uses `GROUP BY` with explicit time

```influxql
SELECT SUM(amount) FROM orders GROUP BY customer_id, time(1h)
```

### 8. **Splunk SPL** - Uses `stats by`

```spl
... | stats sum(amount) as total by customer_id
```

**Key insight**: "stats by" reads naturally - "compute stats by customer"

---

## Alternative Naming Ideas

| Current | Alternative | Reads as... |
|---------|-------------|-------------|
| `group by X (agg)` | `for each X (agg)` | "For each X, compute..." |
| `group by X (agg)` | `per X (agg)` | "Per X, compute..." |
| `group by X (agg)` | `by X summarize (agg)` | "By X, summarize..." |
| `group by X (agg)` | `aggregate by X (agg)` | "Aggregate by X..." |
| `group by X (agg)` | `X: (agg)` | "X: compute these..." |

---

## Recommendation for ASQL

### Option A: Add alias `per` or `for each`

```sql
-- Current (keep working)
from orders
  group by customer_id (sum(amount))

-- New alias option
from orders
  per customer_id (sum(amount))

-- Or even more natural
from orders
  for each customer_id (sum(amount))
```

### Option B: Kusto-style `summarize ... by`

```sql
from orders
  summarize sum(amount) as total by customer_id
```

This reads very naturally: "from orders, summarize sum of amount by customer"

### Option C: Natural language style

```sql
from orders
  customer_id: sum(amount) as total
```

The colon could indicate "grouped by this, compute that"

---

## Prior Art Summary

| Language | Keyword | Notes |
|----------|---------|-------|
| SQL | `GROUP BY` | Original, confusing |
| PRQL | `group` + `aggregate` | Separates concepts |
| Malloy | `group_by` + `aggregate` | Explicit aggregation |
| dplyr | `group_by` + `summarize` | Clear naming |
| Kusto | `summarize ... by` | Reads naturally |
| Splunk | `stats by` | Concise |
| Pandas/Polars | `groupby` + `agg` | Pythonic |

---

## Verdict

**Kusto's `summarize ... by`** is probably the clearest because:
1. The action (`summarize`) comes first
2. `by` is a natural English preposition
3. Reads as a sentence: "summarize X by Y"

**dplyr's `summarize`** is also great - it makes clear you're creating a summary, not just "grouping"

For ASQL, consider:
1. Adding `summarize` as an alias for `group by`
2. Or `per` as a shorter alternative
3. Keep `group by` for SQL compatibility

```sql
-- All equivalent:
from orders group by customer_id (sum(amount) as total)
from orders summarize sum(amount) as total by customer_id
from orders per customer_id (sum(amount) as total)
```

