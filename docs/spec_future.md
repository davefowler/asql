# ASQL: Future Features & Considerations

This document contains features that are planned for future implementation, under consideration, or marked as "maybe" for v1.0.

**Note**: Features in this document are NOT implemented. See `spec.md` for the current specification of implemented features.

---

## String Matching Operators (Planned)

ASQL will provide intuitive string matching operators that are more readable than SQL's `LIKE` syntax.

**Proposed ASQL Syntax:**

```asql
# Contains (substring match) - case-sensitive
from users where email contains "@gmail.com"
from users where name contains "John"

# Case-insensitive contains (preferred for analysts)
from users where email icontains "gmail"
from users where name icontains "john"

# Starts with
from users where email starts with "admin"
from users where domain istarts with "https://"

# Ends with
from users where email ends with ".com"
from users where filename iends with ".pdf"

# Pattern matching (LIKE syntax, not regex by default)
from users where email matches "%@gmail.com"
from users where phone matches "555-___-____"
```

**Design Decisions:**
1. Use `icontains` / `istarts with` / `iends with` instead of `contains ... ignore case` - analysts will prefer this syntax
2. `matches` by default supports LIKE syntax (with `%` and `_` wildcards), not regex
3. Regex support may be added later but is not a priority (most dialects don't support it well anyway)

**Comparison with SQL:**

| ASQL | SQL Equivalent | Notes |
|------|----------------|-------|
| `contains "pattern"` | `LIKE '%pattern%'` | More intuitive, no wildcards |
| `icontains "pattern"` | `ILIKE '%pattern%'` (PostgreSQL) | Case-insensitive |
| `starts with "pattern"` | `LIKE 'pattern%'` | Clearer intent |
| `ends with "pattern"` | `LIKE '%pattern'` | Clearer intent |
| `matches "%pattern%"` | `LIKE '%pattern%'` | LIKE syntax, not regex |

**Implementation Priority**: Medium - String matching is common but can be worked around with `LIKE` in the interim.

---

## Dynamic Pivot

**Status**: ✅ Implemented

Dynamic pivot allows the pivot column values to come from a subquery instead of being hardcoded. This is useful when you don't know all possible values at compile time.

**Syntax**:
```asql
from sales
  pivot sum(amount) by category values (
    from sales select distinct category
  )
```

**Implementation**: The subquery is compiled to SQL and used in a CTE to generate pivot expressions. Note that pure SQL compilation has limitations - individual columns per value require knowing values at compile time. For full dynamic pivoting with individual columns per value, consider using warehouse-specific PIVOT operators (e.g., Snowflake's `PIVOT` operator).

---

## Ternary-Style Conditionals (Future Consideration)

ASQL may add support for concise ternary expressions in the future:

```asql
-- Potential future syntax (not yet decided)
amount == 0 ? null : amount           -- JS-style
null if amount == 0 else amount       -- Python-style
```

**Current**: Use `when` syntax which is clear and readable:
```asql
when amount == 0 then null else amount
```

**Priority**: Low - `when` syntax is already clear and readable. Ternary expressions are syntactic sugar.

---

## Automatic Column Namespace Resolution

**What it is**: When column names conflict across joined tables, automatically rename them with table context (e.g., `users.id` and `orders.id` both become `id` but get auto-qualified as `users_id` and `orders_id`).

**Current behavior**: Requires explicit qualification:
```asql
from users
  & orders
-- If both have 'id', you must explicitly qualify:
select users.id as user_id, orders.id as order_id
```

**Proposed behavior**: Automatically namespace conflicting names:
```asql
from users
  & orders
-- Both tables have 'id', automatically becomes:
select users_id, orders_id  -- or users.id, orders.id (qualified)
```

**Status**: Might not be implemented in the initial version. Explicit qualification is safer and clearer.

**Recommendation**: In v1.0, require explicit qualification for ambiguous columns. Auto-qualification could be added later if there's clear demand.

---

## Shorthand Natural Language (50/50 on implementation)

For very simple exploratory queries, you can omit the `from` clause and infer it from the aggregation:

```asql
# of Users by country
Sum of revenue by region
Avg Users.age by country
```

**Note**: This shorthand is nice for a big percentage of exploratory queries, but it's different from other queries that start with `from`. In these examples, the `from` table is inferred from its use in `# of Users`. It's really nice shorthand, but also potentially confusing.

**Status**: Marked as 50/50 on implementation - may or may not make it into v1.0.

**Pros**:
- Very concise for exploratory queries
- Natural language feel

**Cons**:
- Different syntax from other queries
- Potentially confusing
- Requires inference logic

---

## Cohort Analysis Features

**Source**: `ai_notes/COHORT_ANALYSIS.md`

Cohort analysis is notoriously complex in SQL, typically requiring 3-5 CTEs for even basic queries. ASQL could dramatically simplify this.

**Vision**: A cohort analysis that takes 50+ lines of SQL should be expressible in 5-10 lines of ASQL.

**Key Features Needed**:
- Cohort assignment operators
- Retention calculation helpers
- Period-over-period comparisons
- Cohort rollup syntax

**Note**: Many building blocks are already implemented (`first()`, `prior()`, `running_sum()`, `month()`, etc.), but high-level cohort operators are not yet implemented.

**Example** (proposed):
```asql
from events
  cohort by user_id using first(event_date)
  group by cohort_month, activity_month (
    count(distinct user_id) as active_users
  )
```

**Status**: Not implemented - see `ai_notes/COHORT_ANALYSIS.md` for full design.

---

## Future Considerations

These are broader ideas that may or may not be implemented:

- **Visual SQL Editor**: ASQL's structure could enable a great visual query builder whose base could also be a text editor/IDE. Get the best of visual and text-based exploration.
- **dbt Integration**: Building ASQL into dbt out of the gate would make it immediately useful for the dbt community
- **Common Schema Format**: A shared schema/statistics library for cross-database compatibility
- **Query Optimization**: ASQL-specific optimizations before SQL generation
- **IDE Integration**: Full-featured editor with autocomplete, error checking, SQL preview
- **Testing Framework**: Query testing and validation tools

---

**See Also**:
- `spec.md` - Current specification of implemented features
- `unimplemented_features.md` - Tracking document with GitHub issues
- `ai_notes/COHORT_ANALYSIS.md` - Detailed cohort analysis design
