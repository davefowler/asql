# ASQL for R / dplyr Users

If you’re coming from the tidyverse, ASQL is aiming for the same feeling: readable, chainable transformations that emphasize intent.

ASQL compiles to SQL (so it runs in your warehouse), but its day-to-day ergonomics borrow from “verb-first” workflows like dplyr.

## What will feel familiar

- **Pipelines**: each line reads like the next `%>%` step.
- **Verbs**: `where` ≈ `filter`, `select` ≈ `select`, `group by (...)` ≈ `group_by() %>% summarize()`.
- **Mutate-style derivations**: add columns via `select *, ... as new_col`.
- **Common tidy patterns**: distinct/dedupe, case_when-style conditionals, pivot longer/wider.

## ASQL is a pipe you can read top-to-bottom

In dplyr you usually start with a data frame; in ASQL you start with a table:

- `orders %>% ...` becomes `from orders` then your transforms underneath.

## Quick Reference

| dplyr | ASQL | Notes |
|-------|------|-------|
| `filter(x > 10)` | `where x > 10` | Filter rows |
| `select(a, b, c)` | `select a, b, c` | Choose columns |
| `mutate(new = a + b)` | `select *, a + b as new` | Add columns |
| `group_by() %>% summarize()` | `group by ... (...)` | Aggregate |
| `arrange(desc(x))` | `order by -x` | Sort |
| `left_join()` | `&?` | Left join |
| `distinct()` | `per cols first by ...` | Unique rows |
| `%>%` (pipe) | Newline or `\|` | Chain operations |

---

## Filter

=== "R/dplyr"
    ```r
    orders %>%
      filter(status == "active") %>%
      filter(amount > 100)
    ```

=== "ASQL"
    ```asql
    from orders
    where status = 'active'
    where amount > 100
    ```

---

## Select & Mutate

=== "R/dplyr"
    ```r
    orders %>%
      select(id, customer_id, amount) %>%
      mutate(
        total = price * quantity,
        is_large = amount > 1000
      )
    ```

=== "ASQL"
    ```asql
    from orders
    select 
        id, 
        customer_id, 
        amount,
        price * quantity as total,
        amount > 1000 as is_large
    ```

---

## Group By & Summarize

=== "R/dplyr"
    ```r
    orders %>%
      group_by(region, month = floor_date(date, "month")) %>%
      summarize(
        revenue = sum(amount),
        orders = n(),
        customers = n_distinct(customer_id)
      )
    ```

=== "ASQL"
    ```asql
    from orders
    group by region, month(date) (
        sum(amount) as revenue,
        # as orders,
        count(distinct customer_id) as customers
    )
    ```

---

## Arrange

=== "R/dplyr"
    ```r
    orders %>%
      arrange(desc(date), customer_id)
    ```

=== "ASQL"
    ```asql
    from orders
    order by -date, customer_id
    ```

---

## Joins

=== "R/dplyr"
    ```r
    # Left join
    orders %>%
      left_join(customers, by = "customer_id")
    
    # Inner join
    orders %>%
      inner_join(customers, by = c("cust_id" = "id"))
    ```

=== "ASQL"
    ```asql
    -- Left join (? marks nullable side)
    from orders
    &? customers on orders.customer_id = customers.id

    -- Inner join
    from orders
    & customers on orders.cust_id = customers.id
    ```

---

## Case When

=== "R/dplyr"
    ```r
    orders %>%
      mutate(
        tier = case_when(
          amount > 1000 ~ "high",
          amount > 100 ~ "medium",
          TRUE ~ "low"
        )
      )
    ```

=== "ASQL"
    ```asql
    from orders
    select *,
        when amount
            > 1000 then 'high'
            > 100 then 'medium'
            otherwise 'low'
        as tier
    ```

---

## Window Functions

=== "R/dplyr"
    ```r
    orders %>%
      group_by(customer_id) %>%
      mutate(
        row_num = row_number(),
        running_total = cumsum(amount),
        prev_amount = lag(amount)
      ) %>%
      ungroup()
    ```

=== "ASQL"
    ```asql
    from orders
    select *,
        row_number() over (partition by customer_id order by date) as row_num,
        running_sum(amount) over (partition by customer_id order by date) as running_total,
        prior(amount) over (partition by customer_id order by date) as prev_amount
    ```

---

## Slice (Top N)

=== "R/dplyr"
    ```r
    # Top 5 overall
    orders %>%
      slice_max(amount, n = 5)
    
    # Top 3 per group
    orders %>%
      group_by(region) %>%
      slice_max(amount, n = 3)
    ```

=== "ASQL"
    ```asql
    -- Top 5 overall
    from orders
    order by -amount
    limit 5

    -- Top 3 per group
    from orders
    per region number by -amount as rank
    where rank <= 3
    ```

---

## Distinct

=== "R/dplyr"
    ```r
    orders %>%
      distinct(customer_id, .keep_all = TRUE)
    ```

=== "ASQL"
    ```asql
    from orders
    per customer_id first by -date
    ```

---

## Coalesce & Replace NA

=== "R/dplyr"
    ```r
    orders %>%
      mutate(
        amount = coalesce(amount, 0),
        name = replace_na(name, "Unknown")
      )
    ```

=== "ASQL"
    ```asql
    from orders
    select *,
        amount ?? 0 as amount,
        name ?? 'Unknown' as name
    ```

---

## Pivot Longer / Wider

=== "R/dplyr"
    ```r
    # Pivot longer (unpivot)
    df %>%
      pivot_longer(
        cols = c(jan, feb, mar),
        names_to = "month",
        values_to = "value"
      )
    
    # Pivot wider
    df %>%
      pivot_wider(
        names_from = category,
        values_from = amount
      )
    ```

=== "ASQL"
    ```asql
    -- Pivot longer (unpivot)
    from monthly_data
    unpivot jan, feb, mar into month, value

    -- Pivot wider
    from sales
    pivot amount by category
    ```

