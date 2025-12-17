# Sampling

ASQL provides intuitive syntax for random sampling, essential for exploratory data analysis and working with large datasets.

## Fixed Sample Size

Get a random sample of N rows:

```asql
from orders
  sample 100
```

This returns 100 random rows from the table.

**Generated SQL:**

```sql
SELECT * FROM orders ORDER BY RANDOM() LIMIT 100
```

## Percentage Sampling

Get a random percentage of rows:

```asql
from orders
  sample 10%
```

This returns approximately 10% of the rows, randomly selected.

**Generated SQL (using SQL standard TABLESAMPLE):**

```sql
SELECT * FROM orders TABLESAMPLE BERNOULLI(10)
```

### Dialect Variations

| Dialect | SQL Output |
|---------|------------|
| PostgreSQL/Redshift | `TABLESAMPLE BERNOULLI(10)` or `TABLESAMPLE SYSTEM(10)` |
| BigQuery | `TABLESAMPLE SYSTEM(10 PERCENT)` |
| Snowflake | `SAMPLE (10)` |
| DuckDB | `USING SAMPLE 10%` |

## Stratified Sampling

Get N random rows per group value (stratified sampling):

```asql
from orders
  sample 100 per category
```

This returns 100 random rows for each distinct value of `category`.

**Generated SQL:**

```sql
SELECT *
FROM orders
QUALIFY ROW_NUMBER() OVER (PARTITION BY category ORDER BY RANDOM()) <= 100
```

### Use Cases

- **Balanced training datasets** — Ensure ML models see equal examples from each class
- **Representative samples** — Get proportional data across categories
- **Quality checks** — Sample from each segment for review

## Combining with Other Operations

Sampling can be combined with filters and other operations:

```asql
from orders
  where status = "completed"
  sample 1000
  order by created_at
```

**Note**: The `order by` applies to the final sampled result, not to the sampling process itself.

## Real-World Examples

### Quick Data Exploration

```asql
-- Get a quick look at recent orders
from orders
  sample 50
  order by -created_at
```

### Stratified Sample for Analysis

```asql
-- Sample orders from each region
from orders
  sample 100 per region
  select region, customer_id, amount, created_at
```

### Sample for Model Training

```asql
-- Balanced sample across categories
from products
  sample 500 per category
  select *
```

### Sample with Filters

```asql
-- Sample active users with purchases
from users
  where is_active
  where total_purchases > 0
  sample 1000
```

## Performance Considerations

| Method | Performance | Best For |
|--------|-------------|----------|
| `sample N` | Requires full scan | Small tables, any dialect |
| `sample N%` | Fast (block sampling) | Large tables with TABLESAMPLE support |
| `sample N per col` | Window function overhead | Stratified sampling |

### Tips

1. **For very large tables**, prefer `sample N%` which uses block-level sampling
2. **For reproducibility**, consider adding a seed (dialect-specific)
3. **For exact counts**, `sample N` is guaranteed; `sample N%` is approximate

## Quick Reference

| Syntax | Description | Example |
|--------|-------------|---------|
| `sample N` | Random N rows | `sample 100` |
| `sample N%` | Random N percent | `sample 10%` |
| `sample N per col` | N rows per group | `sample 100 per category` |

## Next Steps

- **[Pipeline Basics](pipeline.md)** — Combining sample with other operations
- **[Window Functions](window-functions.md)** — How stratified sampling works
- **[Examples](../examples.md)** — More sampling patterns
