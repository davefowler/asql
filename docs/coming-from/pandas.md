# ASQL for pandas Users

If you’re coming from pandas, ASQL should feel immediately familiar: you build a result by chaining small, readable steps.

The big difference is execution model: **ASQL compiles to SQL and runs in your warehouse**, so you get the scalability of SQL with a workflow that feels a lot like a well-written pandas pipeline.

## What will feel familiar

- **Chaining**: each line is a “next transform”, like `df[...]`, `.assign(...)`, `.groupby(...)`, `.merge(...)`.
- **Column expressions**: write derived columns as expressions (no extra boilerplate).
- **Groupby mental model**: `group by ... (aggregations...)` mirrors `groupby().agg(...)`.
- **Common helpers baked in**: `fillna`-style defaults (`??`), dedupe patterns (`per ... first by`), pivot/melt (`pivot`/`unpivot`).

## A quick way to translate pandas → ASQL

- **Start** with `from <table>`
- **Filters** become `where ...`
- **assign / mutate** becomes `select *, <expr> as new_col`
- **groupby/agg** becomes `group by ... ( ... )`
- **merge** becomes `&` / `&?` joins
- **sort/head** becomes `order by ...` then `limit ...`

## Quick Reference

| Pandas | ASQL | Notes |
|--------|------|-------|
| `df[df['status'] == 'active']` | `where status = 'active'` | Filter rows |
| `df.groupby('region').sum()` | `group by region (sum(amount))` | Aggregate |
| `df.sort_values('date', ascending=False)` | `order by -date` | Sort (- for desc) |
| `df.head(10)` | `limit 10` | First N rows |
| `df['col'].fillna(0)` | `col ?? 0` | Replace nulls |
| `df.drop_duplicates(['id'])` | `per id first by -date` | Deduplicate |
| `df.merge(other, on='id')` | `& other on id` | Join |
| `pd.concat([df1, df2])` | `from union(df1, df2)` | Union tables |

---

## Filtering

=== "Pandas"
    ```python
    df = df[df['status'] == 'active']
    df = df[df['amount'] > 100]
    df = df[(df['region'] == 'US') | (df['region'] == 'EU')]
    ```

=== "ASQL"
    ```asql
    from orders
    where status = 'active'
    where amount > 100
    where region in ('US', 'EU')
    ```

---

## Grouping & Aggregation

=== "Pandas"
    ```python
    df.groupby('region').agg({
        'amount': 'sum',
        'order_id': 'count',
        'customer_id': 'nunique'
    }).reset_index()
    ```

=== "ASQL"
    ```asql
    from orders
    group by region (
        sum(amount) as total_amount,
        count(*) as order_count,
        count(distinct customer_id) as unique_customers
    )
    ```

---

## Adding Computed Columns

=== "Pandas"
    ```python
    df['total'] = df['price'] * df['quantity']
    df['year'] = df['date'].dt.year
    df['is_large'] = df['amount'] > 1000
    ```

=== "ASQL"
    ```asql
    from orders
    select *,
        price * quantity as total,
        year(date) as year,
        amount > 1000 as is_large
    ```

---

## Sorting

=== "Pandas"
    ```python
    df.sort_values('date', ascending=False)
    df.sort_values(['region', 'date'], ascending=[True, False])
    ```

=== "ASQL"
    ```asql
    from orders
    order by -date

    from orders
    order by region, -date
    ```

!!! tip "Descending with `-`"
    ASQL uses `-column` for descending order, like `-date` means "newest first".

---

## Null Handling

=== "Pandas"
    ```python
    df['col'].fillna(0)
    df['name'].fillna('Unknown')
    df.dropna(subset=['amount'])
    ```

=== "ASQL"
    ```asql
    -- Fill nulls with default
    select amount ?? 0 as amount

    -- Fill with string default
    select name ?? 'Unknown' as name

    -- Drop rows with null
    where amount is not null
    ```

---

## Deduplication

=== "Pandas"
    ```python
    # Keep first occurrence
    df.drop_duplicates(subset=['user_id', 'event_type'])
    
    # Keep last (most recent)
    df.sort_values('date').drop_duplicates(
        subset=['user_id'], 
        keep='last'
    )
    ```

=== "ASQL"
    ```asql
    -- Keep first by date (oldest)
    from events
    per user_id, event_type first by date

    -- Keep last by date (most recent)
    from events
    per user_id first by -date
    ```

---

## Rolling & Window Operations

=== "Pandas"
    ```python
    df['rolling_avg'] = df['value'].rolling(7).mean()
    df['cumsum'] = df['value'].cumsum()
    df['prev_value'] = df.groupby('user_id')['value'].shift(1)
    df['pct_change'] = df['value'].pct_change()
    ```

=== "ASQL"
    ```asql
    from daily_metrics
    order by date
    select *,
        rolling_avg(value, 7) as rolling_avg,
        running_sum(value) as cumsum,
        prior(value) as prev_value
    
    -- With partition
    from daily_metrics
    select *,
        prior(value) over (partition by user_id order by date) as prev_value
    ```

---

## Value Counts

=== "Pandas"
    ```python
    df['status'].value_counts()
    ```

=== "ASQL"
    ```asql
    from orders
    group by status (count(*) as count)
    order by -count
    ```

---

## Merge / Join

=== "Pandas"
    ```python
    # Inner join
    pd.merge(orders, customers, on='customer_id')
    
    # Left join
    pd.merge(orders, customers, on='customer_id', how='left')
    
    # Multiple keys
    pd.merge(df1, df2, on=['key1', 'key2'])
    ```

=== "ASQL"
    ```asql
    -- Inner join
    from orders
    & customers on orders.customer_id = customers.id

    -- Left join (? marks optional side)
    from orders
    &? customers on orders.customer_id = customers.id

    -- Or use dot notation (auto-joins via FK)
    from orders
    select orders.*, orders.customer.name
    ```

---

## Pivot

=== "Pandas"
    ```python
    df.pivot_table(
        values='amount',
        index='customer_id',
        columns='category',
        aggfunc='sum'
    )
    ```

=== "ASQL"
    ```asql
    from orders
    pivot sum(amount) by category values ('Electronics', 'Clothing', 'Home')
    ```

---

## Melt / Unpivot

=== "Pandas"
    ```python
    df.melt(
        id_vars=['id'],
        value_vars=['jan', 'feb', 'mar'],
        var_name='month',
        value_name='value'
    )
    ```

=== "ASQL"
    ```asql
    from monthly_data
    unpivot jan, feb, mar into month, value
    ```

---

## Conditional Column (np.where)

=== "Pandas"
    ```python
    df['tier'] = np.where(df['amount'] > 1000, 'high', 'low')
    
    # Multiple conditions
    df['tier'] = np.select(
        [df['amount'] > 1000, df['amount'] > 100],
        ['high', 'medium'],
        default='low'
    )
    ```

=== "ASQL"
    ```asql
    from orders
    select *,
        when amount > 1000 then 'high' else 'low' as tier

    -- Multiple conditions
    select *,
        when amount
            > 1000 then 'high'
            > 100 then 'medium'
            otherwise 'low'
        as tier
    ```

---

## Date Operations

=== "Pandas"
    ```python
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.to_period('M')
    df['day_of_week'] = df['date'].dt.dayofweek
    df['days_ago'] = (pd.Timestamp.now() - df['date']).dt.days
    ```

=== "ASQL"
    ```asql
    from orders
    select *,
        year(date) as year,
        month(date) as month,
        day of week date as day_of_week,
        days_since_date as days_ago
    ```

