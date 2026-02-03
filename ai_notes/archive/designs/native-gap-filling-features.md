# Native Database Gap-Filling Features

**Date**: 2025-12-18  
**Status**: Future Enhancement Idea

## Overview

Several databases have native gap-filling features that could replace our CTE-based approach for certain dialects. This would generate cleaner, potentially more performant SQL.

## Database Support

### ClickHouse: `WITH FILL` ⭐ Best Candidate

```sql
SELECT
    toStartOfHour(time) AS h,
    sum(hits) AS total_hits
FROM wikistat
GROUP BY h
ORDER BY h ASC
WITH FILL STEP toIntervalHour(1)
```

- Dead simple - just append `WITH FILL` to ORDER BY
- Supports interpolation: `WITH FILL INTERPOLATE (column AS column)`
- No extra CTEs needed
- **Recommendation**: High priority to implement for ClickHouse dialect

### TimescaleDB: `time_bucket_gapfill()`

```sql
SELECT 
    time_bucket_gapfill('1 day', time) AS day,
    locf(avg(value)) AS value
FROM metrics
WHERE time > '2021-12-31' AND time < '2022-01-10'
GROUP BY day;
```

- PostgreSQL extension for time series
- `locf()` = last observation carried forward
- `interpolate()` = linear interpolation
- Requires explicit time bounds in WHERE clause
- **Recommendation**: Medium priority (requires detecting TimescaleDB)

### BigQuery: `GAP_FILL()` Function

```sql
SELECT *
FROM GAP_FILL(
  TABLE mydataset.device_data,
  ts_column => 'time',
  bucket_width => INTERVAL 1 MINUTE,
  value_columns => [('signal', 'linear')]
)
```

- Table-valued function that wraps the data
- Supports `linear`, `locf`, and `null` fill methods
- **Recommendation**: Lower priority (our CTE approach works fine, syntax is similar complexity)

### Snowflake: `RESAMPLE` Clause

```sql
SELECT observed,
       INTERPOLATE_FFILL(temperature) OVER (PARTITION BY city ORDER BY observed)
FROM original_data
RESAMPLE(USING observed INCREMENT BY INTERVAL '5 minutes')
```

- Primarily for upsampling/interpolation, not gap-filling with zeros
- **Recommendation**: Low priority (not a direct replacement)

### No Native Support

- PostgreSQL (vanilla)
- DuckDB  
- Databricks/Spark
- MySQL

These require our current CTE + generate_series approach.

## Implementation Considerations

### For ClickHouse

1. Detect `dialect = "clickhouse"`
2. Instead of generating spine CTE, just:
   - Add `ORDER BY <grouped_column> WITH FILL STEP <interval>` 
   - Use `COALESCE` for zero-filling
3. Much simpler generated SQL

### For TimescaleDB

1. Would need a way to detect TimescaleDB vs vanilla PostgreSQL
2. Could use `time_bucket_gapfill()` instead of `generate_series`
3. Requires explicit WHERE bounds (which we already encourage)

## Trade-offs

### Pros of Native Features
- Cleaner generated SQL
- Potentially better query plan optimization
- Database-native performance

### Cons
- More dialect-specific code paths
- Harder to test uniformly
- Some features (like BigQuery's GAP_FILL) aren't actually simpler

## Recommendation

**Start with ClickHouse** - it's the cleanest implementation and `WITH FILL` is a near-perfect match for our use case. Then evaluate if the added complexity is worth it for other dialects.

## Related Files

- `asql/compiler/auto_spine.py` - current implementation
- `ai_notes/spline-breaking.md` - edge cases documentation
- `docs/concepts/guaranteed-groups.md` - user documentation
