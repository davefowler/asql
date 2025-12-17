# GitHub Issues To Create

**✅ All issues have been created!** This document is kept for reference.

**Created Issues**:
- [#36](https://github.com/davefowler/asql/issues/36) - String Matching Operators
- [#37](https://github.com/davefowler/asql/issues/37) - Dynamic Pivot
- [#38](https://github.com/davefowler/asql/issues/38) - Cohort Analysis Features
- [#39](https://github.com/davefowler/asql/issues/39) - Automatic Column Namespace Resolution
- [#40](https://github.com/davefowler/asql/issues/40) - Shorthand Natural Language (50/50)
- [#28](https://github.com/davefowler/asql/issues/28) - Ternary Conditionals (already existed)

---

**Original content below (for reference)**:

---

## 1. String Matching Operators

**Title**: Implement string matching operators (`contains`, `icontains`, `starts with`, `ends with`, `matches`)

**Labels**: `enhancement`, `medium-priority`

**Description**:

Implement intuitive string matching operators that are more readable than SQL's `LIKE` syntax.

**Proposed Syntax**:

```asql
# Case-sensitive
from users where email contains "@gmail.com"
from users where name starts with "John"
from users where filename ends with ".pdf"

# Case-insensitive (preferred for analysts)
from users where email icontains "gmail"
from users where name istarts with "john"
from users where filename iends with ".pdf"

# Pattern matching (LIKE syntax, not regex)
from users where email matches "%@gmail.com"
from users where phone matches "555-___-____"
```

**Design Decisions**:
- Use `icontains` / `istarts with` / `iends with` instead of `contains ... ignore case` - analysts will prefer this syntax
- `matches` by default supports LIKE syntax (with `%` and `_` wildcards), not regex
- Regex support may be added later but is not a priority (most dialects don't support it well anyway)

**SQL Equivalents**:
- `contains` → `LIKE '%pattern%'`
- `icontains` → `ILIKE '%pattern%'` (PostgreSQL) or `LOWER(column) LIKE LOWER('%pattern%')`
- `starts with` → `LIKE 'pattern%'`
- `ends with` → `LIKE '%pattern'`
- `matches` → `LIKE` (with pattern)

**Implementation Notes**:
- ✅ **IMPLEMENTED** - See `docs/spec.md` section 4.13 for full documentation
- See `spec_future.md` for original design notes
- Priority: Medium - can be worked around with `LIKE` in the interim

**Related**:
- `docs/spec_future.md` - String Matching Operators section
- `docs/unimplemented_features.md` - Tracking document

---

## 2. Dynamic Pivot

**Title**: Support dynamic pivot values from subquery

**Labels**: `enhancement`, `medium-priority`

**Description**:

Currently, pivot requires explicit values at compile time:

```asql
from sales
  pivot sum(amount) by category values ('Electronics', 'Clothing', 'Food')
```

Support getting values dynamically from a subquery:

```asql
from sales
  pivot sum(amount) by category values (
    from sales select distinct category
  )
```

**What it is**: Dynamic pivot allows the pivot column values to come from a subquery instead of being hardcoded. This is useful when you don't know all possible values at compile time.

**Implementation Difficulty**: Medium - requires either:
- Two-pass compilation (first pass to get values, second to generate CASE expressions)
- Dynamic SQL generation (warehouse-specific)
- Runtime evaluation (not possible in pure SQL)

**Current Status**: Static pivot is implemented. Dynamic pivot is not.

**Workaround**: Use raw SQL or warehouse-specific PIVOT syntax (e.g., Snowflake's `PIVOT` operator).

**Related**:
- `docs/spec_future.md` - Dynamic Pivot section
- `docs/unimplemented_features.md` - Tracking document
- `asql/preparser.py` - Current pivot implementation

---

## 3. Cohort Analysis Features

**Title**: Implement high-level cohort analysis operators

**Labels**: `enhancement`, `medium-priority`, `feature`

**Description**:

Cohort analysis is notoriously complex in SQL, typically requiring 3-5 CTEs for even basic queries. Implement high-level cohort operators that simplify this to 5-10 lines of ASQL.

**Vision**: A cohort analysis that takes 50+ lines of SQL should be expressible in 5-10 lines of ASQL.

**Key Features Needed**:
- Cohort assignment operators
- Retention calculation helpers
- Period-over-period comparisons
- Cohort rollup syntax

**Example** (proposed):
```asql
from events
  cohort by user_id using first(event_date)
  group by cohort_month, activity_month (
    count(distinct user_id) as active_users
  )
```

**Note**: Many building blocks are already implemented (`first()`, `prior()`, `running_sum()`, `month()`, etc.), but high-level cohort operators are not yet implemented.

**Current Status**: Not implemented. See `ai_notes/COHORT_ANALYSIS.md` for full design.

**Related**:
- `ai_notes/COHORT_ANALYSIS.md` - Full design document
- `docs/spec_future.md` - Cohort Analysis Features section
- `docs/unimplemented_features.md` - Tracking document

---

## 4. Automatic Column Namespace Resolution

**Title**: Auto-qualify conflicting column names with table context

**Labels**: `enhancement`, `low-priority`, `maybe`

**Description**:

When column names conflict across joined tables, automatically rename them with table context (e.g., `users.id` and `orders.id` both become `id` but get auto-qualified as `users_id` and `orders_id`).

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

**Related**:
- `docs/spec.md` section 15.3 - Current documentation
- `docs/spec_future.md` - Automatic Column Namespace Resolution section

---

## 5. Shorthand Natural Language (50/50)

**Title**: Support shorthand natural language queries without `from` clause

**Labels**: `enhancement`, `low-priority`, `maybe`, `50/50`

**Description**:

For very simple exploratory queries, allow omitting the `from` clause and inferring it from the aggregation:

```asql
# of Users by country
Sum of revenue by region
Avg Users.age by country
```

**Pros**:
- Very concise for exploratory queries
- Natural language feel

**Cons**:
- Different syntax from other queries
- Potentially confusing
- Requires inference logic

**Status**: Marked as 50/50 on implementation - may or may not make it into v1.0.

**Related**:
- `docs/spec_future.md` - Shorthand Natural Language section
- `docs/spec.md` Example 11 (removed) - Original example

---

## Notes

- Check existing issues before creating new ones
- User mentioned ternary conditionals already has an issue - verify this
- Update `docs/unimplemented_features.md` with issue links once created
