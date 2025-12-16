# SQL Function Coverage in ASQL

This document tracks SQL functions and constructs from real-world examples (60 Fivetran dbt models) and their ASQL equivalents.

**Last Updated**: December 2025  
**Status**: ✅ All major functions now have ASQL syntax defined

---

## Summary

All high-frequency SQL constructs now have clean ASQL syntax:

| SQL Construct | Frequency | ASQL Syntax | Documentation |
|---------------|-----------|-------------|---------------|
| `CASE WHEN` | 70 | `when ... is ... then ... otherwise` | [case.md](case.md) |
| `COALESCE` | 58 | `??` operator | [docs/spec.md](../docs/spec.md) §4.6 |
| `CAST` | 34 | `::` operator | [docs/spec.md](../docs/spec.md) §4.8 |
| Date functions | 20+ | `N days ago`, `days()`, etc. | [dates.md](dates.md) |
| Window functions | 15+ | `per ... first by`, `prior()`, etc. | [WINDOW_UTILS.md](WINDOW_UTILS.md) |
| `REPLACE` | 11 | `replace()` | [docs/spec.md](../docs/spec.md) §4.10 |
| `GREATEST` | 5 | `max(a, b, c)` or `greatest()` | [docs/spec.md](../docs/spec.md) §4.11 |
| `LEAST` | 5 | `min(a, b, c)` or `least()` | [docs/spec.md](../docs/spec.md) §4.11 |
| `SUBSTRING` | 4 | `string[1:5]` slice syntax | [docs/spec.md](../docs/spec.md) §4.10 |
| `NULLIF` | 4 | `when x == val then null else x` | [docs/spec.md](../docs/spec.md) §4.12 |
| `STRING_AGG` | 3 | `string_agg(col, ", ")` | [docs/spec.md](../docs/spec.md) §4.10 |
| `CONCAT` | 3 | `concat(a, b, c)` | [docs/spec.md](../docs/spec.md) §4.10 |

---

## Quick Reference

### Conditional Logic
```asql
-- SQL: CASE status WHEN 'active' THEN 1 ELSE 0 END
when status is "active" then 1 otherwise 0

-- SQL: CASE WHEN age < 18 THEN 'minor' ELSE 'adult' END
when age < 18 then "minor" otherwise "adult"
```

### NULL Handling
```asql
-- SQL: COALESCE(name, 'Unknown')
name ?? "Unknown"

-- SQL: NULLIF(amount, 0)
when amount == 0 then null else amount
```

### Type Casting
```asql
-- SQL: CAST(created_at AS DATE)
created_at::DATE
```

### Dates
```asql
-- SQL: CURRENT_DATE - INTERVAL '7 days'
7 days ago

-- SQL: DATEDIFF(day, start, end)
days(end - start)

-- SQL: DATEADD(day, 7, order_date)
order_date + 7 days
```

### Window Functions
```asql
-- SQL: ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY date DESC)
per customer_id number by -date

-- Deduplication (keep most recent)
per customer_id first by -date

-- SQL: LAG(amount)
prior(amount)

-- SQL: SUM(x) OVER (ORDER BY date)
running_sum(amount)
```

### Strings
```asql
-- SQL: CONCAT(a, ' ', b)
concat(first_name, " ", last_name)

-- SQL: STRING_AGG(name, ', ')
string_agg(product_name, ", ")

-- SQL: SUBSTRING(email, 1, 5)
email[1:5]

-- SQL: REPLACE(text, 'old', 'new')
replace(description, "old", "new")
```

### Comparisons
```asql
-- SQL: GREATEST(a, b, c)
max(price1, price2, price3)

-- SQL: LEAST(a, b, c)
min(start_date, end_date)
```

---

## Detailed Documentation

For full syntax and examples, see:

- **[case.md](case.md)** - Conditional expressions with `when`
- **[dates.md](dates.md)** - Date handling, arithmetic, relative dates
- **[WINDOW_UTILS.md](WINDOW_UTILS.md)** - Window function patterns
- **[docs/spec.md](../docs/spec.md)** - Complete language specification

---

## Implementation Notes

### Dialect Mapping

ASQL compiles to dialect-specific SQL:

| ASQL | PostgreSQL | MySQL | Snowflake |
|------|------------|-------|-----------|
| `string_agg(x, ", ")` | `STRING_AGG(x, ', ')` | `GROUP_CONCAT(x)` | `LISTAGG(x, ', ')` |
| `7 days ago` | `CURRENT_DATE - INTERVAL '7 days'` | `DATE_SUB(NOW(), INTERVAL 7 DAY)` | `DATEADD(day, -7, CURRENT_DATE)` |
| `days(end - start)` | `EXTRACT(DAY FROM end - start)` | `DATEDIFF(end, start)` | `DATEDIFF(day, start, end)` |

### Configurable Preferences

Some syntax choices are configurable:

- **`max()`/`min()` vs `greatest()`/`least()`**: Default to `max()`/`min()` but `greatest()`/`least()` are supported for SQL familiarity
- **Week start**: Default ISO Monday, configurable to Sunday

---

*This document was originally "UNHANDLED_SQL_FUNCTIONS.md" - all items are now handled!*
