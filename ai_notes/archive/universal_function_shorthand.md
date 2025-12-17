# Universal Function Shorthand in ASQL

A convention-based approach where function calls automatically generate smart column names, and those column name patterns can be used as shorthand for the function calls themselves.

**Last Updated**: December 2025

---

## Core Principle: Spaces and Underscores are Interchangeable

**In function and keyword contexts**, spaces and underscores can be used interchangeably. This allows users to write in whatever style feels natural - from explicit function calls to natural language.

```asql
-- All of these are EQUIVALENT:

-- Explicit function call (most precise)
day_of_week(created_at)

-- Function shorthand with underscores (pattern interpretation)
day_of_week_created_at

-- Natural language with spaces (most readable)
day of week created_at
```

**Important**: This applies to **function names and keywords**, NOT to column names. Column names must match exactly:
- ✅ `created_at` - matches column `created_at`
- ❌ `created at` - does NOT match column `created_at` (spaces in column names require quotes)

**The principle**:
1. Underscores in function/keyword context can be replaced with spaces
2. Spaces in function/keyword context can be replaced with underscores  
3. Column names are literal (no substitution)

**Examples of the principle in action**:

| Explicit | Shorthand | Natural Language |
|----------|-----------|------------------|
| `avg(amount)` | `avg_amount` | `avg amount` |
| `sum(revenue)` | `sum_revenue` | `sum revenue` |
| `year(created_at)` | `year_created_at` | `year created_at` |
| `day_of_week(date)` | `day_of_week_date` | `day of week date` |
| `month_of_year(col)` | `month_of_year_col` | `month of year col` |

This creates a spectrum from "programmer style" to "analyst style" - use whatever feels right for your context.

---

## Summary

**The Problem with SQL**: Functions have no default column names:
```sql
-- SQL gives you ugly column names by default:
SELECT DATE_TRUNC('year', created_at), AVG(amount) FROM orders
-- Column names: "date_trunc('year', created_at)", "avg" 😱

-- So everyone writes tedious aliases:
SELECT 
    DATE_TRUNC('year', created_at) AS year_created_at,
    AVG(amount) AS avg_amount
FROM orders
```

**ASQL's Solution**: Functions automatically get smart column names based on the pattern `{function}_{column}`, AND you can use that pattern as shorthand:

```asql
from orders
  select year(created_at), avg(amount)
-- Automatically becomes columns: year_created_at, avg_amount ✨

-- OR write the column name directly - ASQL interprets the pattern:
from orders
  select year_created_at, avg_amount
-- Same result!
```

---

## 1. Core Concept

### 1.1 Three Equivalent Syntaxes

All of these are equivalent and produce column `avg_amount`:

```asql
-- Function style (familiar)
avg(amount)

-- Space style (natural language)
avg amount

-- Underscore style (column reference)
avg_amount
```

For date functions, add "of" style:
```asql
year of created_at    →  year_of_created_at
month of signup_date  →  month_of_signup_date
```

### 1.2 Supported Functions

| Function Type | Functions |
|---------------|-----------|
| **Date** | `year`, `month`, `week`, `day`, `hour`, `quarter`, `minute`, `second` |
| **Aggregation** | `avg`, `sum`, `max`, `min`, `count` |
| **Math** | `abs`, `round`, `floor`, `ceil` |
| **String** | `upper`, `lower`, `length`, `trim` |

### 1.3 Function Aliases

Natural language aliases that map to SQL functions:

| Alias | SQL Function | Example |
|-------|--------------|---------|
| `total` | `SUM` | `total_revenue` → `SUM(revenue)` |
| `average` | `AVG` | `average_price` → `AVG(price)` |
| `maximum` | `MAX` | `maximum_amount` → `MAX(amount)` |
| `minimum` | `MIN` | `minimum_amount` → `MIN(amount)` |

```asql
-- All equivalent:
sum(revenue)
sum_revenue
total(revenue)
total_revenue
total revenue
```

This makes ASQL more accessible to business users who think in terms of "total revenue" rather than "sum of revenue".

### 1.3 How It Works

1. **Smart Column Naming**: When you write `avg(amount)`, ASQL automatically aliases it as `avg_amount`
2. **Pattern Interpretation**: When you write `avg_amount` in a select/group by, ASQL recognizes the pattern and interprets it as `avg(amount)`
3. **Schema Fallback**: If `avg_amount` is an actual column in the table, that takes precedence

---

## 2. Examples

### 2.1 Basic Select

```asql
from users
  select 
    year signup_date,        -- becomes year_signup_date  
    upper name,              -- becomes upper_name
    length email             -- becomes length_email
```

**Compiles to** (PostgreSQL):
```sql
SELECT 
    DATE_TRUNC('year', signup_date) AS year_signup_date,
    UPPER(name) AS upper_name,
    LENGTH(email) AS length_email
FROM users
```

### 2.2 Group By with Aggregations

```asql
from sales
  group by region (
    sum revenue,
    avg revenue,
    max sale_date,
    count sales
  )
-- Produces columns: region, sum_revenue, avg_revenue, max_sale_date, count_sales
```

**Compiles to**:
```sql
SELECT 
    region,
    SUM(revenue) AS sum_revenue,
    AVG(revenue) AS avg_revenue,
    MAX(sale_date) AS max_sale_date,
    COUNT(*) AS count_sales
FROM sales
GROUP BY region
```

### 2.3 Using Underscore Pattern in Group By

```asql
from orders
  group by month_created_at (
    sum amount,
    avg amount,
    max amount,
    min amount,
    count order_id
  )
-- ASQL interprets month_created_at as month(created_at)
-- Columns: month_created_at, sum_amount, avg_amount, max_amount, min_amount, count_order_id
```

### 2.4 Mixed Styles

```asql
from products
  select
    upper(name),            -- function style → upper_name
    lower category,         -- space style → lower_category  
    abs_price,              -- underscore style → abs(price)
    round(discount, 2) as rounded_discount  -- explicit alias for multi-arg
```

---

## 3. Why This Matters

### 3.1 Benefits

1. **No aliasing needed** - ASQL picks smart names automatically
2. **Reference by convention** - Write `avg_amount` and ASQL interprets it as `avg(amount)`
3. **Natural language** - `sum revenue` reads like English
4. **Consistency** - Same pattern for ALL functions
5. **Less typing** - `sum revenue` vs `sum(revenue) as sum_revenue`

### 3.2 Philosophy

This is "convention over configuration" in action:
- Follow the naming pattern and everything just works
- Write `sum_revenue` anywhere and ASQL knows you mean `SUM(revenue) AS sum_revenue`
- No need to memorize complex syntax - just combine function + column names naturally

---

## 4. Implementation Notes

### 4.1 Parser Requirements

1. **Smart column naming**: `func(col)` generates alias `func_col` automatically
2. **Underscore pattern interpretation**: Parse `func_col` as `func(col)` in select/group by
3. **Space syntax**: Parse `func col` as `func(col)`
4. **Function registry**: Maintain list of recognized functions
5. **Schema-aware fallback**: If `avg_amount` is an actual column, use it directly

### 4.2 Function Registry

The parser maintains a set of recognized function prefixes:

```python
RECOGNIZED_FUNCTIONS = {
    # Date
    'year', 'month', 'week', 'day', 'hour', 'quarter', 'minute', 'second',
    # Aggregation
    'avg', 'sum', 'max', 'min', 'count',
    # Math
    'abs', 'round', 'floor', 'ceil',
    # String
    'upper', 'lower', 'length', 'trim',
}
```

When parsing `sum_revenue`:
1. Check if `sum` is in `RECOGNIZED_FUNCTIONS`
2. If yes, interpret as `sum(revenue)`
3. If no, treat as regular column name

---

## 5. Open Questions

### 5.1 Multi-word Column Names

How to handle `sum_total_amount`?
- Is it `sum(total_amount)` or `sum_total(amount)`?

**Proposal**: First underscore separates function from column:
- `sum_total_amount` = `sum(total_amount)`
- For ambiguous cases, use space or parens: `sum total_amount` or `sum(total_amount)`

### 5.2 Conflict with Existing Columns

What if table actually has a column named `avg_amount`?

**Proposal**: Actual columns limit precedence, pattern interpretation is fallback:
1. Parser checks schema first (if available)
2. If column exists, use it directly
3. If not, interpret as function pattern

### 5.3 Two-Argument Functions

How to handle `round(amount, 2)`?

**Proposal**: Underscore pattern only works for single-argument functions:
- `round_amount` → `round(amount)` (uses default precision)
- For specific precision: `round(amount, 2) as rounded_amount`

### 5.4 Which Functions to Support

Should we limit to a known set or be more flexible?

**Proposal**:
- Start with common functions (aggregations, date, math, string)
- Allow configuration to add custom functions
- Unknown patterns pass through as-is

### 5.5 Extending the Pattern

Could we support more complex patterns like `days_since_created_at` → `days(now() - created_at)`?

**Recommendation**: Start with basic single-function patterns, expand based on user feedback.

---

## 6. Syntax Summary Table

| Syntax Style | Example | Produces Column |
|--------------|---------|-----------------|
| Function style | `avg(amount)` | `avg_amount` |
| Space style | `avg amount` | `avg_amount` |
| Underscore style | `avg_amount` | `avg_amount` (interpreted as `avg(amount)`) |
| "of" style (dates) | `year of created_at` | `year_of_created_at` |

**Supported functions**:
- **Date**: `year`, `month`, `week`, `day`, `hour`, `quarter`, `minute`, `second`
- **Aggregation**: `avg`, `sum`, `max`, `min`, `count`
- **Math**: `abs`, `round`, `floor`, `ceil`
- **String**: `upper`, `lower`, `length`, `trim`

---

## 7. Related Documentation

- `dates.md`: Date-specific handling and syntax
- `docs/spec.md`: ASQL language specification
- `UNHANDLED_SQL_FUNCTIONS.md`: Functions not yet handled

---

**End of Document**

