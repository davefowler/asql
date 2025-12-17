# Unimplemented Features Tracking

This document tracks features that are specified but not yet implemented, along with their GitHub issue status.

**Last Updated**: December 2025

---

## High Priority

### 1. String Matching Operators
**Status**: Not Implemented  
**GitHub Issue**: [#36](https://github.com/davefowler/asql/issues/36)  
**Spec Section**: 4.5 (String Matching)

**Proposed Syntax**:
- `contains` / `icontains` - substring match (case-sensitive / case-insensitive)
- `starts with` / `istarts with` - prefix match
- `ends with` / `iends with` - suffix match
- `matches` - LIKE pattern matching (not regex by default)

**Design Decision**: Use `icontains` instead of `contains ... ignore case` for better analyst UX.

**Example**:
```asql
from users where email icontains "gmail"
from users where name starts with "John"
from users where filename ends with ".pdf"
from users where email matches "%@gmail.com"  -- LIKE syntax, not regex
```

**Workaround**: Use SQL `LIKE` syntax directly.

---

## Medium Priority

### 2. Dynamic Pivot
**Status**: ✅ Implemented  
**GitHub Issue**: [#37](https://github.com/davefowler/asql/issues/37)  
**Spec Section**: 13.3 (Pivot)

**What it is**: Pivot where the values come from a subquery instead of being hardcoded at compile time.

**Implementation**: Dynamic pivot is now supported using subqueries in the values clause:
```asql
pivot sum(amount) by status values (from orders select distinct status)
```

The implementation compiles the subquery to SQL and uses it in a CTE to generate pivot expressions. Note that pure SQL compilation has limitations - individual columns per value require knowing values at compile time. For full dynamic pivoting with individual columns, consider using warehouse-specific PIVOT operators (e.g., Snowflake's `PIVOT` operator).

---

### 3. Cohort Analysis Features
**Status**: Not Implemented  
**GitHub Issue**: [#38](https://github.com/davefowler/asql/issues/38)  
**Spec Source**: `ai_notes/COHORT_ANALYSIS.md`

**Note**: Cohort examples have been temporarily removed from `playground/examples.py`. See issue #38 for details on adding them back when implemented.

**What it is**: High-level cohort analysis operators that simplify complex cohort queries from 50+ lines of SQL to 5-10 lines of ASQL.

**Key Features**:
- Cohort assignment operators
- Retention calculation helpers
- Period-over-period comparisons
- Cohort rollup syntax

**Note**: Many building blocks are already implemented (`first()`, `prior()`, `running_sum()`, etc.), but high-level cohort operators are not.

**Workaround**: Use existing window functions and manual cohort logic.

---

## Low Priority / Future Consideration

### 4. Ternary-Style Conditionals
**Status**: Future Consideration  
**GitHub Issue**: [#28](https://github.com/davefowler/asql/issues/28)  
**Spec Section**: 4.12

**Proposed Syntax**:
```asql
amount == 0 ? null : amount           -- JS-style
null if amount == 0 else amount       -- Python-style
```

**Current**: Use `when` syntax:
```asql
when amount == 0 then null else amount
```

**Priority**: Low - `when` syntax is already clear and readable.

---

### 5. Automatic Column Namespace Resolution
**Status**: Might Not Be Implemented  
**GitHub Issue**: [#39](https://github.com/davefowler/asql/issues/39)  
**Spec Section**: 15.3

**What it is**: Automatically rename conflicting column names with table context (e.g., `users.id` and `orders.id` both become `id` but get auto-qualified as `users_id` and `orders_id`).

**Current**: Requires explicit qualification:
```asql
from users & orders
select users.id as user_id, orders.id as order_id
```

**Recommendation**: Keep explicit qualification for v1.0 - it's safer and clearer.

---

### 6. Shorthand Natural Language (50/50)
**Status**: Maybe  
**GitHub Issue**: [#40](https://github.com/davefowler/asql/issues/40)  
**Spec Section**: Example 11

**What it is**: Omit `from` clause and infer table from aggregation:
```asql
# of Users by country
Sum of revenue by region
```

**Pros**: Nice shorthand for exploratory queries  
**Cons**: Different from other queries, potentially confusing

**Decision**: Marked as 50/50 - may or may not make it into v1.0.

---

## Implementation Notes

- Features marked as "Future Consideration" are lower priority and may not be implemented
- Features marked as "50/50" or "Maybe" are uncertain
- All features have workarounds using existing ASQL or raw SQL

---

## How to Update This Document

1. When a feature is implemented, mark it as "✅ Implemented" and add implementation date
2. When a GitHub issue is created, update the issue link
3. When priority changes, update the section
4. Add new unimplemented features as they're discovered or requested
