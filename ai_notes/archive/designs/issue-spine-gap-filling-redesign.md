# Spine gap-filling produces incorrect results due to join direction

## Problem

The current spine implementation in `asql/compiler/spine.py` adds a `LEFT JOIN` to connect the spine CTE to the main query:

```sql
FROM base_table
LEFT JOIN date_spine ON date_spine.month = month(base_table.created_at)
```

This produces **no gap-filling** because the base table is on the left side. Missing dates in the base table are not filled in - the LEFT JOIN only ensures we keep all base rows, not all spine rows.

## Expected Behavior

For gap-filling to work, the spine should drive the query:

```sql
FROM date_spine
LEFT JOIN (
  -- aggregated data
  SELECT month(created_at) as month, SUM(amount) as total
  FROM base_table
  GROUP BY 1
) AS data ON date_spine.month = data.month
```

This ensures all dates from the spine appear in the output, with NULL values for missing data.

## Example

**ASQL Query:**
```sql
from orders 
where created_at >= @2024-01-01 and created_at < @2024-04-01
spine by month(created_at) (sum(amount))
```

**Expected Output** (if January has no data):
| month      | total |
|------------|-------|
| 2024-01-01 | NULL  |
| 2024-02-01 | 5000  |
| 2024-03-01 | 7500  |

**Current Output** (missing January):
| month      | total |
|------------|-------|
| 2024-02-01 | 5000  |
| 2024-03-01 | 7500  |

## Proposed Solution

Restructure the spine transformation to:

1. Wrap the aggregation in a CTE first
2. Make the spine CTE the primary table in FROM
3. LEFT JOIN from spine to aggregated data

```sql
WITH 
  _base AS (
    SELECT month(created_at) as order_month, SUM(amount) as total
    FROM orders
    WHERE created_at >= '2024-01-01' AND created_at < '2024-04-01'
    GROUP BY 1
  ),
  _spine AS (
    SELECT * FROM generate_series(...)
  )
SELECT _spine.order_month, _base.total
FROM _spine
LEFT JOIN _base ON _spine.order_month = _base.order_month
```

## Files Affected

- `asql/compiler/spine.py` - Main transform logic (~lines 330-355)
- `tests/test_spine.py` - Need tests that verify gap-filling works

## Complexity

This is a significant refactor because:
1. The current approach modifies the existing query; the new approach needs to extract and restructure it
2. Must handle existing CTEs, joins, and complex FROM clauses
3. Must preserve column references and aliases

## Related Issues

- None currently identified

## Acceptance Criteria

- [ ] Spine queries produce rows for all dates in the spine range, even if no data exists
- [ ] Works with all supported dialects (DuckDB, Postgres, Snowflake, BigQuery)
- [ ] Tests verify gap-filling behavior, not just CTE generation
- [ ] Documentation updated to clarify gap-filling semantics
