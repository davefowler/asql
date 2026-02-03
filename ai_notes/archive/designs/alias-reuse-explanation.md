# Alias Reuse Implementation Explanation

## How the Current CTE Approach Works

### What It Does

The current implementation **groups expressions by dependency level**, not one CTE per column.

**Example:**
```asql
from order_items
  select
    unit_price * (1 - discount) as discount_price,    # Group 1: no dependencies
    discount_price * quantity as total_price,          # Group 2: depends on discount_price
    total_price * (1 + tax_rate) as taxed_price        # Group 3: depends on total_price
```

**Generated SQL (PostgreSQL):**
```sql
WITH _step0 AS (
  SELECT unit_price * (1 - discount) AS discount_price
  FROM order_items
),
_step1 AS (
  SELECT *, discount_price * quantity AS total_price
  FROM _step0
),
_step2 AS (
  SELECT *, total_price * (1 + tax_rate) AS taxed_price
  FROM _step1
)
SELECT * FROM _step2
```

So it creates **3 CTEs total** (base + 2 dependency levels), not one per column.

### Why CTEs Are Needed

**Question 1: Is this needed for pipelined SQL?**

Yes! Even though ASQL is pipelined, when you write:
```asql
from order_items
  select
    unit_price * (1 - discount) as discount_price,
    discount_price * quantity as total_price
```

This needs to compile to valid SQL. **Standard SQL doesn't allow referencing aliases in the same SELECT clause**. So we need to transform it somehow.

The pipeline nature of ASQL helps with chaining operations (WHERE, GROUP BY, etc.), but within a single SELECT clause, we still hit SQL's limitation.

### Alternative Approach: Expression Substitution

**Question 2: What if we just replace reused names with the original expression?**

Your suggestion:
```asql
select max(amount) as m, avg(amount/m) as avg_ratio
```

Instead of CTEs, detect that `m` isn't a real column, find it's defined as `max(amount)`, and replace:
```sql
SELECT max(amount) AS m, avg(amount/max(amount)) AS avg_ratio
```

**Pros:**
- ✅ Simpler - no CTEs needed
- ✅ Potentially faster - no intermediate tables
- ✅ Works for simple cases
- ✅ Less SQL generated

**Cons:**
- ❌ **Expression duplication** - violates DRY principle
- ❌ **Maintenance nightmare** - if you change `max(amount)` to `max(amount) * 1.1`, you have to update it in multiple places
- ❌ **Complex expressions get repeated** - imagine `(unit_price * (1 - discount) * quantity * (1 + tax_rate))` repeated 3 times
- ❌ **Readability** - the generated SQL becomes harder to read
- ❌ **Potential for errors** - if the expression is complex, repeating it increases chance of mistakes

**Example of the problem:**
```asql
select 
  (price * (1 - discount) * quantity * (1 + tax_rate)) as total,
  total * 0.1 as fee,
  total + fee as final_total
```

With substitution:
```sql
SELECT 
  (price * (1 - discount) * quantity * (1 + tax_rate)) AS total,
  (price * (1 - discount) * quantity * (1 + tax_rate)) * 0.1 AS fee,
  (price * (1 - discount) * quantity * (1 + tax_rate)) + ((price * (1 - discount) * quantity * (1 + tax_rate)) * 0.1) AS final_total
```

Yikes! That's unreadable and error-prone.

### Comparison

| Aspect | CTE Approach (Current) | Expression Substitution |
|--------|------------------------|------------------------|
| **Simplicity** | More complex | Simpler |
| **Performance** | Slightly slower (intermediate CTEs) | Faster (no CTEs) |
| **DRY Principle** | ✅ Single source of truth | ❌ Expression duplication |
| **Maintainability** | ✅ Change once, works everywhere | ❌ Must update multiple places |
| **Readability** | ✅ Clear dependency chain | ❌ Can become unreadable |
| **SQL Size** | Larger (CTE overhead) | Smaller (but repeated expressions) |
| **Complex Expressions** | ✅ Handles well | ❌ Becomes unwieldy |

### Recommendation

**For DuckDB**: Use native support (no transformation needed) ✅

**For other dialects**: 
- **Current CTE approach** is better for:
  - Complex expressions
  - Multiple levels of dependencies
  - Maintainability and readability
  
- **Expression substitution** could work for:
  - Simple, single-level dependencies
  - Performance-critical queries
  - When expression duplication is acceptable

### Hybrid Approach?

We could potentially do **smart substitution**:
- If expression is simple (single function call, single column reference), substitute
- If expression is complex or used multiple times, use CTE

But this adds complexity and might be confusing (unpredictable behavior).

### Current Implementation Details

The code groups expressions by dependency level:

1. **First pass**: Build dependency graph
   - Track which aliases are defined
   - Track which earlier aliases each expression references

2. **Second pass**: Group expressions
   - Group 1: Expressions with no dependencies (can compute immediately)
   - Group 2: Expressions that only depend on Group 1
   - Group 3: Expressions that only depend on Groups 1-2
   - etc.

3. **Third pass**: Generate CTEs
   - CTE 0: Base query with Group 1 expressions
   - CTE 1: SELECT * FROM CTE 0 + Group 2 expressions
   - CTE 2: SELECT * FROM CTE 1 + Group 3 expressions
   - Final: SELECT * FROM last CTE + WHERE/ORDER BY/etc.

This ensures expressions are computed in the right order while maintaining DRY.
