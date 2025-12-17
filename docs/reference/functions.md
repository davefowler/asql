# Functions Reference

Complete reference of ASQL built-in functions.

## Aggregate Functions

### count

Count rows or non-null values.

```asql
count(*)                    -- Count all rows
count(column)               -- Count non-null values
count(distinct column)      -- Count distinct values
#                           -- Shorthand for count(*)
#(column)                   -- Shorthand for count(column)
```

### sum

Sum numeric values.

```asql
sum(amount)                 -- Sum of amount
sum_amount                  -- Shorthand (same as above)
total(amount)               -- Alias for sum
total amount                -- Natural language style
```

### avg / average

Calculate average.

```asql
avg(price)                  -- Average price
average(price)              -- Alias
avg_price                   -- Shorthand
average of price            -- Natural language
```

### min / minimum

Find minimum value.

```asql
min(date)                   -- Earliest date
minimum(amount)             -- Smallest amount
min_created_at              -- Shorthand
```

### max / maximum

Find maximum value.

```asql
max(amount)                 -- Largest amount
maximum(amount)             -- Alias
max_created_at              -- Shorthand
```

---

## Date Truncation Functions

Truncate dates to a specific precision.

### year

```asql
year(created_at)            -- Truncate to year start: 2025-01-01
year_created_at             -- Shorthand
year of created_at          -- Natural language
```

### month

```asql
month(created_at)           -- Truncate to month start: 2025-03-01
```

### week

```asql
week(created_at)            -- Truncate to week start (Monday)
week_monday(created_at)     -- Explicit Monday start
week_sunday(created_at)     -- Sunday start
```

### day

```asql
day(created_at)             -- Truncate to day: 2025-03-15
```

### hour

```asql
hour(created_at)            -- Truncate to hour: 2025-03-15 14:00:00
```

### quarter

```asql
quarter(created_at)         -- Truncate to quarter start
```

---

## Date Part Extraction

Extract specific parts from dates (returns integers).

### day of week

```asql
day of week created_at      -- 1-7 (Monday = 1)
day_of_week(created_at)     -- Function style
```

### day of month

```asql
day of month created_at     -- 1-31
day_of_month(created_at)
```

### day of year

```asql
day of year created_at      -- 1-366
day_of_year(created_at)
```

### week of year

```asql
week of year created_at     -- 1-52
week_of_year(created_at)
```

### month of year

```asql
month of year created_at    -- 1-12
month_of_year(created_at)
```

### quarter of year

```asql
quarter of year created_at  -- 1-4
quarter_of_year(created_at)
```

---

## Date Difference Functions

Calculate time between dates.

### days

```asql
days(end_date - start_date)     -- Integer days between
days_between(start, end)        -- Alternative syntax
```

### weeks

```asql
weeks(end_date - start_date)    -- Integer weeks between
weeks_between(start, end)
```

### months

```asql
months(end_date - start_date)   -- Integer months between
months_between(start, end)
```

### years

```asql
years(end_date - start_date)    -- Integer years between
years_between(start, end)
```

### hours

```asql
hours(end_date - start_date)    -- Integer hours between
```

---

## Window Functions

### prior

Access previous row value (LAG).

```asql
prior(revenue)              -- Previous row's revenue
prior(revenue, 3)           -- 3 rows back
```

### next

Access next row value (LEAD).

```asql
next(revenue)               -- Next row's revenue
next(revenue, 2)            -- 2 rows ahead
```

### running_sum

Cumulative sum from start.

```asql
running_sum(amount)         -- Cumulative total
running sum amount          -- Space style
```

### running_avg

Cumulative average from start.

```asql
running_avg(amount)         -- Average to date
```

### running_count

Cumulative count from start.

```asql
running_count(*)            -- Row number (effectively)
```

### rolling_avg

Moving average with window size.

```asql
rolling_avg(price, 7)       -- 7-day moving average
rolling_avg(price, 30)      -- 30-day moving average
```

### rolling_sum

Moving sum with window size.

```asql
rolling_sum(amount, 7)      -- 7-day rolling sum
```

### first

Get first value with ordering.

```asql
first(order_id order by -order_date)    -- Latest order
first(order_id order by order_date)     -- Earliest order
```

### last

Get last value with ordering.

```asql
last(order_id order by order_date)      -- Latest order
```

### arg_max

Value where another column is maximum.

```asql
arg_max(order_id, order_date)           -- order_id at max order_date
```

### arg_min

Value where another column is minimum.

```asql
arg_min(order_id, order_date)           -- order_id at min order_date
```

### row_number

Standard SQL window function.

```asql
row_number() over (partition by customer_id order by -order_date)
```

### rank

Standard SQL window function.

```asql
rank() over (partition by department order by -salary)
```

### dense_rank

Standard SQL window function (no gaps).

```asql
dense_rank() over (partition by category order by -revenue)
```

---

## String Functions

### concat

Concatenate strings.

```asql
concat(first_name, " ", last_name)
```

### string_agg

Aggregate strings with separator.

```asql
string_agg(product_name, ", ")
```

### upper / lower

Change case.

```asql
upper(name)
lower(email)
```

### trim / ltrim / rtrim

Remove whitespace.

```asql
trim(input)
ltrim(input)
rtrim(input)
```

### length

String length.

```asql
length(name)
```

### substring

Extract substring.

```asql
substring(email, 1, 5)
email[1:5]                  -- Slice syntax
```

### replace

Replace text.

```asql
replace(text, "old", "new")
```

---

## Null Handling Functions

### coalesce

Return first non-null value.

```asql
value ?? default            -- Operator form (preferred)
primary_email ?? secondary_email ?? "unknown"  -- Chained fallbacks

-- Function form (also accepted)
coalesce(primary_email, secondary_email, "unknown")
```

---

## Type Functions

### cast

Explicit type conversion.

```asql
value::INTEGER              -- Cast to integer
value::DATE                 -- Cast to date
value::TIMESTAMP            -- Cast to timestamp
value::INTEGER?             -- Safe cast (NULL on failure)
```

---

## Special Functions

### guarantee

Specify explicit values for group by spine.

```asql
guarantee(status, ['pending', 'active', 'completed'])
```

---

## Function Aliases

| Natural Language | SQL Function |
|------------------|--------------|
| `total` | `SUM` |
| `average` | `AVG` |
| `maximum` | `MAX` |
| `minimum` | `MIN` |

## See Also

- **[Operators Reference](operators.md)** — All operators
- **[Aggregations](../syntax/aggregations.md)** — Using aggregates
- **[Window Functions](../syntax/window-functions.md)** — Window function patterns
