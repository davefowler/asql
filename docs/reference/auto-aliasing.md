# Auto-Aliasing Reference

ASQL automatically generates meaningful column names when functions are used without explicit `AS` aliases. This solves SQL's problem of unusable default names like `count`, `f0_`, or `COUNT(DISTINCT user_id)`.

## Quick Example

```asql
from orders
group by region (
    count(*),           -- → column: "num"
    sum(amount),        -- → column: "sum_amount"
    avg(price),         -- → column: "avg_price"
    month(created_at)   -- → column: "month_created_at"
)
order by -sum_amount    -- Reference auto-aliased column!
```

No explicit aliases needed—ASQL generates clean, predictable names automatically.

---

## Alias Mapping Table

### Aggregate Functions

| Function | Auto Alias | Example |
|----------|-----------|---------|
| `sum(col)` | `sum_{col}` | `sum(amount)` → `sum_amount` |
| `avg(col)` | `avg_{col}` | `avg(price)` → `avg_price` |
| `min(col)` | `min_{col}` | `min(date)` → `min_date` |
| `max(col)` | `max_{col}` | `max(amount)` → `max_amount` |
| `count(*)` or `#` | `num` | `count(*)` → `num` |
| `count(col)` | `num_{col}` | `count(email)` → `num_email` |
| `count(distinct col)` | `num_distinct_{col}` | `count(distinct user_id)` → `num_distinct_user_id` |
| `first(col order by ...)` | `first_{col}` | `first(order_id order by -date)` → `first_order_id` |
| `last(col order by ...)` | `last_{col}` | `last(order_id order by date)` → `last_order_id` |

### Date Functions

| Function | Auto Alias | Example |
|----------|-----------|---------|
| `year(col)` | `year_{col}` | `year(created_at)` → `year_created_at` |
| `month(col)` | `month_{col}` | `month(created_at)` → `month_created_at` |
| `week(col)` | `week_{col}` | `week(created_at)` → `week_created_at` |
| `day(col)` | `day_{col}` | `day(created_at)` → `day_created_at` |
| `quarter(col)` | `quarter_{col}` | `quarter(created_at)` → `quarter_created_at` |
| `hour(col)` | `hour_{col}` | `hour(created_at)` → `hour_created_at` |
| `day_of_week(col)` | `day_of_week_{col}` | `day_of_week(created_at)` → `day_of_week_created_at` |
| `day_of_month(col)` | `day_of_month_{col}` | `day_of_month(created_at)` → `day_of_month_created_at` |
| `day_of_year(col)` | `day_of_year_{col}` | `day_of_year(created_at)` → `day_of_year_created_at` |
| `week_of_year(col)` | `week_of_year_{col}` | `week_of_year(created_at)` → `week_of_year_created_at` |

### Window Functions

| Function | Auto Alias | Example |
|----------|-----------|---------|
| `prior(col)` | `prior_{col}` | `prior(revenue)` → `prior_revenue` |
| `next(col)` | `next_{col}` | `next(revenue)` → `next_revenue` |
| `running_sum(col)` | `running_sum_{col}` | `running_sum(amount)` → `running_sum_amount` |
| `running_avg(col)` | `running_avg_{col}` | `running_avg(amount)` → `running_avg_amount` |
| `running_count(*)` | `running_num` | `running_count(*)` → `running_num` |
| `rolling_avg(col, n)` | `rolling_avg_{col}` | `rolling_avg(revenue, 7)` → `rolling_avg_revenue` |
| `rolling_sum(col, n)` | `rolling_sum_{col}` | `rolling_sum(amount, 30)` → `rolling_sum_amount` |
| `row_number()` | `row_num` | `row_number()` → `row_num` |
| `rank()` | `rank` | `rank()` → `rank` |
| `dense_rank()` | `dense_rank` | `dense_rank()` → `dense_rank` |

### String Functions

| Function | Auto Alias | Example |
|----------|-----------|---------|
| `upper(col)` | `upper_{col}` | `upper(name)` → `upper_name` |
| `lower(col)` | `lower_{col}` | `lower(email)` → `lower_email` |
| `length(col)` | `length_{col}` | `length(name)` → `length_name` |
| `trim(col)` | `trim_{col}` | `trim(input)` → `trim_input` |
| `concat(col1, col2)` | `concat_{col1}_{col2}` | `concat(first, last)` → `concat_first_last` |

### Type Functions

| Function | Auto Alias | Example |
|----------|-----------|---------|
| `col::type` | `{col}_{type}` | `amount::INTEGER` → `amount_integer` |
| `coalesce(a, b)` | `coalesce_{a}_{b}` | `primary ?? fallback` → `coalesce_primary_fallback` |

---

## Pattern Rules

1. **Single-arg functions**: `func(col)` → `func_col`
2. **Multi-arg functions**: `func(col1, col2)` → `func_col1_col2`
3. **Parameterized functions**: `func(col, n)` → `func_col`
4. **Special cases**:
   - `count(*)` / `#` → `num` (not `count` — analytics-friendly)
   - `row_number()` → `row_num`
   - `running_count(*)` → `running_num`

---

## Configuration

Auto-aliasing behavior can be customized via config file or `SET` statements.

### Config File

Create `asql.config.yaml` in your project root:

```yaml
compile:
  # Default template for all functions
  alias_template: "{prefix}_{col}"
  
  # Function-specific prefixes
  alias_prefixes:
    sum: "sum"
    avg: "avg"
    count: "num"
    
  # Function-specific templates
  alias_templates:
    count: "{prefix}"  # count(*) → "num" (no column suffix)
```

### SET Statements

Override settings per-query:

```asql
SET sum_alias_prefix = 'total';
SET alias_template = '{prefix}_{col}';

from orders
group by customer_id (sum(amount))
-- Generates: SUM(amount) AS total_amount
```

### Template Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `{func}` | Function name | `sum`, `avg`, `month` |
| `{prefix}` | Configured prefix (or function name) | `sum`, `num`, `year` |
| `{col}` | First column name | `amount`, `created_at` |
| `{arg1}`, `{arg2}` | Function arguments by position | `order_id`, `date` |
| `{distinct}` | "distinct" if DISTINCT used | `distinct` or empty |

### Template Filters

Apply transformations using `|` syntax:

| Filter | Description | Example |
|--------|-------------|---------|
| `lower` | Lowercase | `{func\|lower}` → `sum` |
| `upper` | Uppercase | `{func\|upper}` → `SUM` |
| `title` | Title case | `{func\|title}` → `Sum` |
| `camel` | camelCase | `{func\|camel}` → `runningCount` |
| `snake` | snake_case | `{func\|snake}` → `running_count` |

**Example with filters:**

```yaml
compile:
  alias_template: "{prefix|upper}_{col|upper}"
# sum(amount) → SUM_AMOUNT
```

---

## Precedence Rules

1. **Explicit alias** — `sum(amount) as total` uses `total`
2. **Function-specific template** — `count_alias_template: "{prefix}"`
3. **Function-specific prefix** — `count_alias_prefix: "num"`
4. **Default template** — `alias_template: "{prefix}_{col}"`
5. **Fallback** — Uses function name as prefix

---

## Why Not SQL's Default Names?

SQL dialects generate unusable column names without explicit aliases:

| Dialect | `count(*)` | `count(distinct id)` | `sum(amount)` |
|---------|-----------|---------------------|---------------|
| PostgreSQL | `count` | `count_1` | `sum` |
| MySQL | `COUNT(*)` | `COUNT(DISTINCT id)` | `SUM(amount)` |
| BigQuery | `f0_` | `f1_` | `f2_` |

**Problems:**
- Unpredictable (`count_1`, `count_2`)
- Require quotes (`COUNT(*)`)
- Meaningless (`f0_`)
- Hard to reference in code

**ASQL's solution:** Generate clean, predictable names like `num`, `num_distinct_id`, `sum_amount` that work everywhere without quotes.

---

## See Also

- **[Functions Reference](functions.md)** — All built-in functions
- **[Shorthand Syntax](../concepts/shorthand.md)** — Using shorthand notation
- **[Aggregations](../syntax/aggregations.md)** — Aggregate function patterns
