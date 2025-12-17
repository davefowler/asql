# Unimplemented Features Tracking

This document tracks features that are specified but not yet implemented, along with their GitHub issue status.

**Last Updated**: December 2025

---

## High Priority

### 1. String Matching Operators ✅
**Status**: ✅ Implemented (December 2025)  
**GitHub Issue**: [#36](https://github.com/davefowler/asql/issues/36)  
**Spec Section**: 4.5 (String Matching)

**Implemented Syntax**:
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

**Implementation**: Transforms to SQL `LIKE` / `ILIKE` operators. Case-insensitive operators use `ILIKE` for PostgreSQL and dialects that support it.

---

## Medium Priority

### 2. Dynamic Pivot
**Status**: ✅ Implemented  
**GitHub Issue**: [#37](https://github.com/davefowler/asql/issues/37)  
**Spec Section**: 13.3 (Pivot)

**What it is**: Pivot where the values come from a subquery instead of being hardcoded at compile time.

**Implementation**: Dynamic pivot is now supported using subqueries in the values clause:

```asql
from sales
  pivot sum(amount) by category values (
    from sales select distinct category
  )
```

The subquery is compiled to a CTE and used to generate pivot expressions. See `docs/spec.md` section 13.3 and `docs/syntax/pivot-unpivot.md` for full documentation and examples.

---

### 3. Cohort Analysis Features
**Status**: ✅ Implemented (December 2025)  
**GitHub Issue**: [#38](https://github.com/davefowler/asql/issues/38)  
**Spec Section**: 14 (Cohort Analysis)

**Implementation**: The `cohort by` operator is now available, simplifying cohort queries from 50+ lines of SQL to 3-5 lines of ASQL.

**Documentation**:
- [Spec: Cohort Analysis](spec.md#14-cohort-analysis)
- [Syntax Guide: Cohorts](syntax/cohorts.md)

**Example**:
```asql
from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)
```

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
**Status**: ✅ **Implemented** (December 2025)  
**GitHub Issue**: [#39](https://github.com/davefowler/asql/issues/39)  
**Spec Section**: 15.3

**What it is**: Automatically qualify conflicting column names in joined queries by expanding `SELECT *` to `table.*` for each joined table.

**Implementation**: When `SELECT *` is used with joins, ASQL automatically expands it to `SELECT table1.*, table2.*, ...` for each joined table. This prevents column name conflicts and allows columns to be referenced with table qualification (e.g., `users.id`, `orders.id`).

**Example**:
```asql
from users & orders on users.id = orders.user_id
-- Automatically becomes:
-- SELECT users.*, orders.* FROM users JOIN orders ON users.id = orders.user_id
```

**Note**: Full automatic renaming (e.g., `users_id`, `orders_id`) would require schema information and is a potential future enhancement. The current implementation provides table-qualified columns which prevent conflicts.

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
