# Underscore Function Notation: Edge Cases & Potential Issues

**Status**: Research document exploring potential edge cases, conflicts, and downsides of ASQL's underscore function notation (`sum_amount`, `avg_price`, etc.)

**Related**: See `auto-alias-mapping-table.md` for the proposed auto-aliasing patterns.

---

## Overview

ASQL's underscore function notation allows writing `sum_amount` instead of `sum(amount)`, creating declarative consistency. However, this syntax introduces potential ambiguities and edge cases that need to be explored and addressed.

---

## 1. Ambiguity: Function Call vs. Column Reference

### The Core Problem

When you write `sum_amount`, is it:
- A **function call** (`sum(amount)`)?
- A **column reference** to an existing column named `sum_amount`?

### Current Behavior (From `docs/concepts/shorthand.md`)

> "If an actual column name matches a potential function pattern, the **column takes precedence**"

```asql
-- If table has actual column "sum_revenue":
select sum_revenue    -- Uses the column, not sum(revenue)

-- To force function interpretation:
select sum(revenue) as sum_revenue
```

### Edge Cases & Questions

#### Case 1.1: Column Created by Previous Aggregation

```asql
-- Step 1: Create a column via aggregation
from orders
  group by customer_id (
    sum_amount as total_spent  -- Creates column: total_spent
  )

-- Step 2: Later query - what happens?
from previous_query
  select sum_amount  -- Is this sum(amount) or the column from step 1?
```

**Questions**:
- Does the column from step 1 exist in the result set?
- If `sum_amount` was auto-aliased (not explicitly aliased), does it exist as a column?
- How do we distinguish between "I want to aggregate again" vs "I want the existing column"?

#### Case 1.2: Double Grouping / Re-aggregation

```asql
-- First aggregation
from orders
  group by customer_id, month(created_at) (
    sum_amount,           -- → column: sum_amount
    avg_price            -- → column: avg_price
  )

-- Second aggregation (grouping by month only)
from previous_result
  group by month_created_at (
    sum_amount,          -- Is this sum(sum_amount) or just sum_amount?
    avg_avg_price        -- Is this avg(avg_price) or a new column name?
  )
```

**Questions**:
- Should `sum_amount` in the second query mean "sum the sum_amount column" (double aggregation)?
- Or should it mean "just select the sum_amount column" (no re-aggregation)?
- How do we express "I want to sum an already-aggregated column"?

#### Case 1.3: CTE / Subquery Context

```asql
-- CTE with aggregation
stash monthly_totals as (
  from orders
    group by month(created_at) (
      sum_amount  -- → column: sum_amount
    )
)

-- Main query
from monthly_totals
  select sum_amount  -- Column reference or function call?
  
-- What if we want to aggregate again?
from monthly_totals
  group by year(month_created_at) (
    sum_amount  -- Sum the sum_amount column? Or new sum(amount)?
  )
```

**Questions**:
- In a CTE/subquery context, how do we know what columns exist?
- Can we distinguish "aggregate the existing column" from "create new aggregation"?

---

## 2. Nested / Compound Functions

### Case 2.1: Average of an Average

```asql
-- First level: average by customer
from orders
  group by customer_id (
    avg_price  -- → column: avg_price
  )

-- Second level: average of averages by region
from previous_result
  group by region (
    avg_avg_price  -- Is this avg(avg_price) or a new column name?
  )
```

**Questions**:
- Does `avg_avg_price` mean "average the avg_price column"?
- Or does it mean "average of a column called avg_price" (which doesn't exist)?
- How do we express "average of an average" clearly?

**Potential Solutions**:
- Require explicit syntax: `avg(avg_price)` for re-aggregation
- Use different notation: `avg_of_avg_price`?
- Disallow nested aggregations via shorthand?

### Case 2.2: Sum of a Sum

```asql
-- Daily totals
from orders
  group by day(created_at) (
    sum_amount  -- → column: sum_amount
  )

-- Monthly totals (sum of daily sums)
from daily_totals
  group by month(created_at) (
    sum_amount  -- Sum the sum_amount column? Or new sum(amount)?
  )
```

**Questions**:
- Is `sum_amount` in the second query summing the `sum_amount` column?
- Or is it trying to sum a raw `amount` column that doesn't exist?
- How do we express "sum of sums" vs "new sum"?

### Case 2.3: Count of Counts

```asql
-- Count orders per customer
from orders
  group by customer_id (
    num  -- → column: num (count of orders)
  )

-- Count how many customers have orders
from customer_counts
  select num  -- Is this count(*) or the num column?
  
-- What if we want to count the num column?
from customer_counts
  select count(num)  -- Explicit - but what about shorthand?
```

**Questions**:
- Does `num` mean "count rows" or "select the num column"?
- How do we express "count the num column" in shorthand?

---

## 3. Column Name Conflicts

### Case 3.1: Table Has Column Matching Function Pattern

```asql
-- Table has actual column "sum_revenue"
from sales
  select sum_revenue  -- Uses column (current behavior)
  
-- But what if we want to aggregate?
from sales
  group by region (
    sum_revenue  -- Still uses column? Or creates sum(revenue)?
  )
```

**Questions**:
- Does grouping context change the precedence?
- Should grouping force function interpretation?
- How do we force column reference in grouping context?

### Case 3.2: Multiple Tables with Same Column Name

```asql
-- Join with ambiguous column names
from orders & users on orders.user_id = users.id
  group by region (
    sum_amount  -- Which amount? orders.amount or users.amount?
  )
```

**Questions**:
- Does `sum_amount` infer the table?
- Should we require explicit table qualification: `sum_orders_amount`?
- How does this interact with FK traversal conventions?

### Case 3.3: Function Result Becomes Column Name

```asql
-- Create column via function
from orders
  select 
    sum(amount) as sum_amount,  -- Explicit alias
    avg(price) as avg_price     -- Explicit alias

-- Later reference
from previous_result
  select sum_amount  -- Column reference (clear)
  
-- But what if we want to aggregate again?
from previous_result
  group by region (
    sum_amount  -- Column or function?
  )
```

**Questions**:
- Once a column exists, does shorthand always reference it?
- How do we express "aggregate this column again"?

---

## 4. Double Chaining / Cascading Aggregations

### Case 4.1: Multiple Levels of Aggregation

```asql
-- Level 1: Daily aggregation
from orders
  group by day(created_at) (
    sum_amount,      -- → sum_amount
    num              -- → num
  )

-- Level 2: Monthly aggregation (aggregate the daily aggregates)
from daily_agg
  group by month(created_at) (
    sum_amount,      -- Sum of daily sums? Or new sum?
    avg_num         -- Average of daily counts? Or new count?
  )

-- Level 3: Yearly aggregation
from monthly_agg
  group by year(created_at) (
    sum_amount,      -- Sum of monthly sums? Or new sum?
    avg_avg_num     -- Average of monthly averages? Or new count?
  )
```

**Questions**:
- How do we express cascading aggregations clearly?
- Does the notation scale to 3+ levels?
- Should we require explicit syntax for re-aggregation?

### Case 4.2: Mixed Aggregation Types

```asql
-- First: sum by customer
from orders
  group by customer_id (
    sum_amount  -- → sum_amount
  )

-- Second: average the sums by region
from customer_sums
  group by region (
    avg_sum_amount  -- Average of sum_amount column?
  )
```

**Questions**:
- Does `avg_sum_amount` mean `avg(sum_amount)`?
- Or does it mean "average of a column called sum_amount" (which exists)?
- How do we distinguish?

---

## 5. Context-Dependent Behavior

### Case 5.1: SELECT vs GROUP BY Context

```asql
-- In SELECT (non-aggregating context)
from orders
  select sum_amount  -- Column reference or function call?

-- In GROUP BY (aggregating context)
from orders
  group by region (
    sum_amount  -- Function call (creates aggregation)?
  )
```

**Questions**:
- Should context determine interpretation?
- SELECT = column reference, GROUP BY = function call?
- What about HAVING, ORDER BY, WHERE?

### Case 5.2: Window Functions Context

```asql
-- Window function with shorthand
from orders
  select 
    sum_amount,              -- Aggregate?
    running_sum_amount,      -- Window function?
    prior_sum_amount          -- Window function?
  group by region
```

**Questions**:
- Does `running_sum_amount` mean `running_sum(amount)` or `running_sum(sum_amount)`?
- How do we express "running sum of an aggregated column"?

---

## 6. Type System & Validation

### Case 6.1: Invalid Column References

```asql
-- Try to use column that doesn't exist
from orders
  select sum_revenue  -- Column doesn't exist, but sum(revenue) would work
```

**Questions**:
- Should this error immediately ("column sum_revenue doesn't exist")?
- Or should it fall back to function interpretation?
- How do we validate column existence vs function applicability?

### Case 6.2: Schema Awareness

```asql
-- If schema is known, we can validate
from orders  -- Schema: orders has columns [id, amount, price, ...]
  select sum_amount  -- Can validate: amount exists, sum(amount) is valid
```

**Questions**:
- Does schema awareness help resolve ambiguity?
- What if schema is unknown (dynamic queries)?
- Should we require explicit syntax when ambiguous?

---

## 7. User Confusion Scenarios

### Scenario 7.1: "Why isn't my aggregation working?"

```asql
-- User expects aggregation but gets column reference
from aggregated_data
  group by region (
    sum_amount  -- User thinks this aggregates, but it's selecting a column
  )
```

**Confusion**: User expects `sum_amount` to aggregate, but it references an existing column.

### Scenario 7.2: "Why is this so slow?"

```asql
-- User accidentally double-aggregates
from orders
  group by customer_id (
    sum_amount  -- Creates sum_amount column
  )
group by region (
  sum_amount   -- User thinks this selects column, but it re-aggregates?
)
```

**Confusion**: Unintended re-aggregation causes performance issues.

### Scenario 7.3: "Why can't I reference this column?"

```asql
-- User creates column via auto-alias
from orders
  group by region (
    sum_amount  -- Auto-aliased to sum_amount column
  )

-- Later tries to reference it
from previous_result
  select sum_amount  -- Works (column reference)

-- But in grouping context?
from previous_result
  group by month (
    sum_amount  -- Is this column or function? Unclear!
  )
```

**Confusion**: Context-dependent behavior is confusing.

---

## 8. Comparison with Other Systems

### How SQL Handles This

SQL avoids this problem by requiring explicit syntax:
- `SUM(amount)` is always a function call
- `sum_amount` is always a column reference
- No ambiguity, but verbose

### How dplyr (R) Handles This

```r
# dplyr: Explicit function calls
df %>%
  group_by(region) %>%
  summarize(sum_amount = sum(amount))  # Explicit

# Later: Column reference
df %>%
  select(sum_amount)  # Column reference (clear)
```

**Approach**: Explicit syntax eliminates ambiguity.

### How pandas Handles This

```python
# pandas: Explicit aggregation
df.groupby('region')['amount'].sum()  # Creates Series

# Later: Column access
df['sum_amount']  # Column reference (if it exists)
```

**Approach**: Explicit syntax, no shorthand.

---

## 9. Potential Solutions & Mitigations

### Solution 1: Context-Based Rules

**Rule**: In grouping context, always interpret as function call unless column is explicitly qualified.

```asql
-- Grouping context = function call
from orders
  group by region (
    sum_amount  -- Always sum(amount), not column reference
  )

-- To reference column, use explicit qualification
from aggregated_data
  group by region (
    aggregated_data.sum_amount  -- Explicit column reference
  )
```

**Pros**: Clear rules, predictable behavior
**Cons**: Requires table qualification syntax

### Solution 2: Explicit Re-aggregation Syntax

**Rule**: Require explicit syntax for re-aggregating existing columns.

```asql
-- First aggregation
from orders
  group by customer_id (
    sum_amount  -- → sum_amount column
  )

-- Re-aggregation requires explicit syntax
from customer_sums
  group by region (
    sum(sum_amount) as sum_sum_amount,  -- Explicit re-aggregation
    avg(sum_amount) as avg_sum_amount  -- Explicit re-aggregation
  )

-- Shorthand only for new aggregations
from orders
  group by region (
    sum_amount  -- New aggregation (amount column exists)
  )
```

**Pros**: Clear distinction, no ambiguity
**Cons**: More verbose for re-aggregations

### Solution 3: Column Existence Check

**Rule**: Check if column exists first, then fall back to function interpretation.

```asql
-- If sum_amount column exists, use it
-- Otherwise, interpret as sum(amount)
from aggregated_data
  select sum_amount  -- Column exists → column reference
  group by region (
    sum_amount  -- Column doesn't exist in grouping → function call
  )
```

**Pros**: Intuitive fallback behavior
**Cons**: Can be confusing, requires schema awareness

### Solution 4: Disallow Shorthand in Re-aggregation Context

**Rule**: Shorthand only works for "first-level" aggregations.

```asql
-- First level: shorthand works
from orders
  group by region (
    sum_amount  -- ✅ Shorthand allowed
  )

-- Second level: explicit syntax required
from aggregated_data
  group by month (
    sum(sum_amount)  -- ❌ Shorthand disallowed, explicit required
  )
```

**Pros**: Prevents confusion, clear rules
**Cons**: Inconsistent syntax

### Solution 5: Different Notation for Re-aggregation

**Rule**: Use different syntax for re-aggregating columns.

```asql
-- First aggregation
from orders
  group by region (
    sum_amount  -- → sum_amount column
  )

-- Re-aggregation uses different notation
from aggregated_data
  group by month (
    sum_of_sum_amount,    -- Re-aggregate sum_amount column
    avg_of_sum_amount     -- Average the sum_amount column
  )
```

**Pros**: Clear distinction, readable
**Cons**: New syntax to learn

---

## 10. Open Questions

1. **Should grouping context always force function interpretation?**
   - Or should column existence take precedence?

2. **How do we handle cascading aggregations?**
   - Require explicit syntax after first level?
   - Or allow shorthand at all levels?

3. **What about window functions?**
   - Does `running_sum_amount` mean `running_sum(amount)` or `running_sum(sum_amount)`?

4. **Should we validate column existence?**
   - Or always fall back to function interpretation?

5. **How do we document this clearly?**
   - What are the rules users should follow?
   - How do we prevent confusion?

6. **What about CTEs and subqueries?**
   - Does column existence in CTE affect interpretation?
   - How do we scope column names?

7. **Performance implications?**
   - Does ambiguity resolution require schema inspection?
   - Does this slow down query compilation?

---

## 11. Recommendations

### Short-term

1. **Document current behavior clearly**: Column precedence rules, context-dependent behavior
2. **Add examples**: Show common patterns and edge cases
3. **Consider explicit syntax**: For re-aggregations, require explicit `sum(column_name)`

### Medium-term

1. **Schema-aware resolution**: Use schema information to resolve ambiguity
2. **Better error messages**: When ambiguity exists, suggest explicit syntax
3. **Linting/validation**: Warn users about potential ambiguities

### Long-term

1. **Consider different notation**: For re-aggregations (e.g., `sum_of_sum_amount`)
2. **Type system**: Track column types and existence through query pipeline
3. **IDE support**: Autocomplete and validation based on schema

---

## 12. Testing Scenarios

### Test Cases to Implement

1. **Column precedence**: Table has `sum_amount` column, verify column is used
2. **Function fallback**: Table doesn't have column, verify function is called
3. **Re-aggregation**: Aggregate an aggregated column, verify behavior
4. **Cascading**: 3+ levels of aggregation, verify each level
5. **Mixed contexts**: SELECT, GROUP BY, HAVING, ORDER BY, WHERE
6. **CTEs**: Column existence in CTE affects interpretation
7. **Joins**: Multiple tables with same column names
8. **Window functions**: Window functions on aggregated columns

---

## Conclusion

The underscore function notation is powerful but introduces ambiguity that needs careful handling. The key challenges are:

1. **Distinguishing function calls from column references**
2. **Handling re-aggregations and cascading aggregations**
3. **Providing clear, predictable behavior**
4. **Preventing user confusion**

Potential solutions range from context-based rules to explicit syntax requirements. Further research and user testing will help determine the best approach.
