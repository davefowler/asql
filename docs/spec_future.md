# ASQL: Future Features & Considerations

This document contains features that are planned for future implementation, under consideration, or marked as "maybe" for v1.0.

**Note**: Features in this document are NOT implemented. See `spec.md` for the current specification of implemented features.

---

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
