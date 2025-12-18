# Auto-Alias Mapping Table

This table documents the proposed auto-aliasing behavior for all ASQL functions/aggregates. When a function is used without an explicit `as` alias, it automatically generates a column name following the pattern shown.

**Status**: Future feature - see `docs/spec_future.md` for details.

| Function | Auto Alias Pattern | Can Call With Auto Alias? | Example |
|----------|-------------------|---------------------------|---------|
| **Aggregates** |
| `sum(col)` | `sum_{col}` | ✅ | `sum(amount)` → `sum_amount` |
| `avg(col)` | `avg_{col}` | ✅ | `avg(price)` → `avg_price` |
| `min(col)` | `min_{col}` | ✅ | `min(date)` → `min_date` |
| `max(col)` | `max_{col}` | ✅ | `max(amount)` → `max_amount` |
| `count(*)` / `#` | `count` | ❌ | `#` → `count` (no shorthand) |
| `count(col)` | `count_{col}` | ❌ | `count(email)` → `count_email` |
| `count(distinct col)` | `count_distinct_{col}` | ❌ | `count(distinct user_id)` → `count_distinct_user_id` |
| `# orders` | `count_orders` | ❌ | `# orders` → `count_orders` |
| `first(col order by ...)` | `first_{col}` | ❌ | `first(order_id order by -date)` → `first_order_id` |
| `last(col order by ...)` | `last_{col}` | ❌ | `last(order_id order by date)` → `last_order_id` |
| `arg_max(col1, col2)` | `arg_max_{col1}_{col2}` | ❌ | `arg_max(order_id, date)` → `arg_max_order_id_date` |
| `arg_min(col1, col2)` | `arg_min_{col1}_{col2}` | ❌ | `arg_min(order_id, date)` → `arg_min_order_id_date` |
| **Date Functions** |
| `year(col)` | `year_{col}` | ✅ | `year(created_at)` → `year_created_at` |
| `month(col)` | `month_{col}` | ✅ | `month(created_at)` → `month_created_at` |
| `week(col)` | `week_{col}` | ✅ | `week(created_at)` → `week_created_at` |
| `day(col)` | `day_{col}` | ✅ | `day(created_at)` → `day_created_at` |
| `quarter(col)` | `quarter_{col}` | ✅ | `quarter(created_at)` → `quarter_created_at` |
| `hour(col)` | `hour_{col}` | ✅ | `hour(created_at)` → `hour_created_at` |
| `day_of_week(col)` | `day_of_week_{col}` | ✅ | `day_of_week(created_at)` → `day_of_week_created_at` |
| `day_of_month(col)` | `day_of_month_{col}` | ✅ | `day_of_month(created_at)` → `day_of_month_created_at` |
| `day_of_year(col)` | `day_of_year_{col}` | ✅ | `day_of_year(created_at)` → `day_of_year_created_at` |
| `week_of_year(col)` | `week_of_year_{col}` | ✅ | `week_of_year(created_at)` → `week_of_year_created_at` |
| `month_of_year(col)` | `month_of_year_{col}` | ✅ | `month_of_year(created_at)` → `month_of_year_created_at` |
| `quarter_of_year(col)` | `quarter_of_year_{col}` | ✅ | `quarter_of_year(created_at)` → `quarter_of_year_created_at` |
| `date_trunc(unit, col)` | `{unit}_{col}` | ✅ | `date_trunc("month", created_at)` → `month_created_at` |
| `days(col1 - col2)` | `days_{col1}_{col2}` | ❌ | Date difference - complex expression |
| `weeks(col1 - col2)` | `weeks_{col1}_{col2}` | ❌ | Date difference - complex expression |
| `months(col1 - col2)` | `months_{col1}_{col2}` | ❌ | Date difference - complex expression |
| `years(col1 - col2)` | `years_{col1}_{col2}` | ❌ | Date difference - complex expression |
| `hours(col1 - col2)` | `hours_{col1}_{col2}` | ❌ | Date difference - complex expression |
| **Window Functions** |
| `prior(col)` | `prior_{col}` | ✅ | `prior(revenue)` → `prior_revenue` |
| `next(col)` | `next_{col}` | ✅ | `next(revenue)` → `next_revenue` |
| `running_sum(col)` | `running_sum_{col}` | ✅ | `running_sum(amount)` → `running_sum_amount` |
| `running_avg(col)` | `running_avg_{col}` | ✅ | `running_avg(amount)` → `running_avg_amount` |
| `running_count(*)` | `running_count` | ❌ | `running_count(*)` → `running_count` |
| `rolling_avg(col, n)` | `rolling_avg_{col}_{n}` | ✅ | `rolling_avg(revenue, 7)` → `rolling_avg_revenue_7` |
| `rolling_sum(col, n)` | `rolling_sum_{col}_{n}` | ✅ | `rolling_sum(amount, 30)` → `rolling_sum_amount_30` |
| `row_number()` | `row_num` | ❌ | `row_number()` → `row_num` |
| `rank()` | `rank` | ❌ | `rank()` → `rank` |
| `dense_rank()` | `dense_rank` | ❌ | `dense_rank()` → `dense_rank` |
| **String Functions** |
| `upper(col)` | `upper_{col}` | ✅ | `upper(name)` → `upper_name` |
| `lower(col)` | `lower_{col}` | ✅ | `lower(email)` → `lower_email` |
| `length(col)` | `length_{col}` | ✅ | `length(name)` → `length_name` |
| `trim(col)` | `trim_{col}` | ✅ | `trim(input)` → `trim_input` |
| `ltrim(col)` | `ltrim_{col}` | ✅ | `ltrim(input)` → `ltrim_input` |
| `rtrim(col)` | `rtrim_{col}` | ✅ | `rtrim(input)` → `rtrim_input` |
| `substring(col, start, len)` | `substring_{col}` | ❌ | Complex - requires explicit alias |
| `replace(col, old, new)` | `replace_{col}` | ❌ | Complex - requires explicit alias |
| `concat(col1, col2)` | `concat_{col1}_{col2}` | ❌ | Multiple args - requires explicit alias |
| `string_agg(col, sep)` | `string_agg_{col}` | ❌ | Multiple args - requires explicit alias |
| **Type Functions** |
| `cast(col AS type)` / `col::type` | `{col}_{type}` | ❌ | `amount::INTEGER` → `amount_integer` (or explicit) |
| **Special Functions** |
| `coalesce(col1, col2)` / `col1 ?? col2` | `coalesce_{col1}_{col2}` | ❌ | Multiple args - requires explicit alias |
| `guarantee(col, values)` | `guarantee_{col}` | ❌ | Special function - requires explicit alias |

## Notes

- **✅ Can Call With Auto Alias**: These functions support the shorthand syntax where you can write the auto-alias directly (e.g., `sum_amount` instead of `sum(amount) as sum_amount`)
- **❌ Cannot Call With Auto Alias**: These functions don't support shorthand syntax, but would still generate the auto-alias if used without `as`

## Pattern Rules

1. **Single-arg functions**: `func(col)` → `func_col`
2. **Multi-arg functions**: `func(col1, col2)` → `func_col1_col2` (but typically require explicit alias)
3. **Functions with parameters**: `func(col, n)` → `func_col_n`
4. **Special cases**:
   - `count(*)` / `#` → `count`
   - `row_number()` → `row_num`
   - `rank()` → `rank`
   - `dense_rank()` → `dense_rank`

## Rationale

Auto-aliasing makes queries more concise and enables declarative continuity - you can write `sum_amount` and reference `sum_amount` later without needing explicit aliases. This works best for single-argument functions that follow the `func_col` pattern.
