# Documentation Style Update Task

**Date**: 2025-12-17  
**Goal**: Update all ASQL documentation examples to match the style guide (`docs/style_guide.md`)

**Your Task**: Go through each documentation file systematically, updating ASQL code examples to use preferred style patterns. Work through the checklist task by task until all files are updated.

---

## Style Guide Reference

**Primary Reference**: `docs/style_guide.md` - Read this first to understand all preferred patterns.

**Quick Reference - Key Preferences**:

### Configurable Settings
- Equality: `=` (not `==`)
- Count: `#` (not `count(*)`)
- Coalesce: `??` (not `coalesce()`)
- Descending: `-col` (not `col DESC`)
- Cast: `::` (not `CAST()`)
- Quotes: `"` (not `'`)

### Preferred Syntax Patterns
- Conditionals: Ternary `? :` (simple binary) / `when` (multi-branch) (not `CASE WHEN`)
- Equality in when: `is` (not `=`)
- Default clause: `otherwise` (not `else`)
- CTEs: `stash as` (not `WITH ... AS`)
- Pipelines: Indentation (not `|`)
- String matching: `contains`, `starts with` (not `LIKE`)
- Window functions: `per` syntax (not `OVER()`)
- Joins: `&`, `&?` operators (not `JOIN`)
- FK traversal: `.owner.name` (not explicit joins)
- Date literals: `@2025-01-10` (not `"2025-01-10"`)
- Window helpers: `prior()`, `running_sum()` (not `LAG()`, `SUM() OVER()`)
- Max/Min: `max()`, `min()` (not `greatest()`, `least()`)
- Column ops: `except`, `rename` (not explicit SELECT)
- Date arithmetic: `+ 7 days` (not `DATEADD()`, `INTERVAL`)
- **Function shorthand**: `sum amount` (space) preferred for simple cases, `sum(amount)` (parens) preferred for complex expressions and documentation
  - Simple: `sum amount`, `avg price`, `year created_at` ✅
  - Complex: `sum(amount * quantity)`, `avg(price / 100)` ✅ (must use parens)
  - Underscore: `sum_amount` acceptable but not preferred

---

## Task List (Work Through Systematically)

### Phase 1: High Priority (Main Documentation)
1. [ ] `docs/quick_start.md` - Main getting started guide
2. [ ] `docs/tutorial.md` - Step-by-step tutorial
3. [ ] `docs/examples.md` - Example queries
4. [ ] `docs/spec.md` - Language specification (large file, many examples)

### Phase 2: Medium Priority (Reference Documentation)
5. [ ] `docs/syntax/expressions.md` - Expression syntax
6. [ ] `docs/syntax/aggregations.md` - Aggregation examples
7. [ ] `docs/syntax/joins.md` - Join examples
8. [ ] `docs/syntax/window-functions.md` - Window function examples
9. [ ] `docs/syntax/ctes.md` - CTE examples
10. [ ] `docs/syntax/dates.md` - Date function examples
11. [ ] `docs/syntax/pipeline.md` - Pipeline examples
12. [ ] `docs/reference/functions.md` - Function reference
13. [ ] `docs/reference/operators.md` - Operator reference
14. [ ] `docs/reference/keywords.md` - Keyword reference

### Phase 3: Lower Priority (Conceptual/Coming-From Guides)
15. [ ] `docs/concepts/shorthand.md` - Shorthand examples
16. [ ] `docs/concepts/pipelines.md` - Pipeline concepts
17. [ ] `docs/concepts/guaranteed-groups.md` - Grouping examples
18. [ ] `docs/coming-from/sql.md` - SQL comparison examples
19. [ ] `docs/coming-from/pandas.md` - Pandas comparison examples
20. [ ] `docs/coming-from/r.md` - R comparison examples
21. [ ] `docs/coming-from/dbt.md` - dbt comparison examples
22. [ ] `docs/integrating.md` - Integration examples

### Phase 4: Low Priority (Other)
23. [ ] `docs/group_by.md` - Grouping examples
24. [ ] `docs/window_functions.md` - Window function examples
25. [ ] `docs/status.md` - Status/feature list
26. [ ] `docs/playground.md` - Playground examples
27. [ ] `docs/architecture.md` - Architecture examples
28. [ ] `docs/design.md` - Design examples

---

## Process for Each File

For each file in the task list above:

1. **Read the file** completely to understand its context and purpose

2. **Identify all ASQL code blocks** (```asql ... ```)

3. **For each ASQL example**, check against style guide:
   - Equality: `=` vs `==`
   - Count: `#` vs `count(*)`
   - Coalesce: `??` vs `coalesce()`
   - Conditionals: Ternary `? :` vs `when` vs `CASE WHEN`
   - Quotes: `"` vs `'`
   - Descending: `-col` vs `col DESC`
   - Cast: `::` vs `CAST()`
   - String matching: `contains` vs `LIKE`
   - Joins: `&`, `&?` vs `JOIN`
   - Window functions: `per` vs `OVER()`
   - Date literals: `@2025-01-10` vs `"2025-01-10"`
   - **Function shorthand**: `sum amount` (preferred) vs `sum(amount)` (for complex/docs) vs `sum_amount` (acceptable)
   - And other patterns from style guide

4. **Update examples** to match preferred style, BUT:
   - ✅ **DO update** main examples to use preferred style
   - ❌ **DO NOT change** SQL output examples (they're showing SQL, not ASQL)
   - ❌ **DO NOT change** "coming-from" comparison examples that intentionally show both styles
   - ❌ **DO NOT change** examples that demonstrate alternatives (if showing "this also works")
   - ✅ **Preserve** the educational intent of examples

5. **After updating**, provide a summary:
   - List all changes made
   - Note any examples intentionally left unchanged (with reason)
   - Flag any ambiguous cases for review

6. **Mark the task complete** in the checklist above

---

## Important Rules

- **Work sequentially** - Complete one file before moving to the next
- **Read the style guide first** - Understand all preferences before starting
- **Preserve context** - Don't change examples that are intentionally showing alternatives
- **SQL vs ASQL** - Only update ASQL code blocks, never SQL output examples
- **Coming-from guides** - Update ASQL examples to preferred style, but keep comparison examples showing both
- **Be thorough** - Check every ASQL code block in each file

---

## When You're Done

After completing all tasks:
1. Review the checklist to ensure all files are marked complete
2. Provide a summary of:
   - Total files updated
   - Total examples changed
   - Any patterns that were consistently found and updated
   - Any edge cases or ambiguous examples that need review

---

## Start Here

Begin with **Task 1: `docs/quick_start.md`**

Read the file, identify all ASQL examples, update them to match the style guide, provide a summary, mark it complete, then move to the next task.

Continue until all tasks are complete.
