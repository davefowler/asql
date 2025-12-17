# AI Notes

This folder contains AI-generated analysis reports, implementation plans, investigations, and development notes created during the ASQL project.

**These are internal reference documents** - they are NOT part of the public-facing documentation in `docs/`.

## Purpose

Use `ai_notes/` for:
- ✅ Analysis reports and investigations
- ✅ Implementation plans and design explorations
- ✅ Status reports and completion summaries
- ✅ Research notes and learnings
- ✅ Code quality checklists and reviews
- ✅ Feature comparisons and ideation

**Do NOT** put these in `docs/` - that folder is only for user-facing documentation that appears on the website.

## Organization

Files are organized by topic/feature. Current categories include:

### Status & Implementation
- `FEATURE_STATUS.md` - Pointers to canonical spec/status docs
- `IMPLEMENTATION_STATUS.md` - What's implemented vs. missing
- `PHASE_COMPLETION.md` - Phase completion summaries
- `CODE_QUALITY.md` - Code quality standards and cleanup tasks

### Feature Design & Plans
- `case.md` - Design exploration for `when` conditional expressions
- `STRING_MATCHING_PLAN.md` - Implementation plan for string matching operators
- `PIPELINE_CTE_IMPLEMENTATION.md` - Guide on implementing pipelined CTEs
- `DIALECT_REWRITE_TASK.md` - Dialect system rewrite planning

### Analysis & Research
- `style_analysis.md` - Analysis of default style settings
- `CRITICAL_REVIEW.md` - Critical review of ASQL specification
- `SQLMESH_COMPARISON.md` - Comparison with SQLMesh
- `DBT_DEEP_INTEGRATION_IDEATION.md` - dbt integration ideas
- `pandas-python-notebooks-learnings.md` - Learnings from pandas/Python

### Technical Deep Dives
- `dialect.md` - Dialect system documentation
- `joins.md` - JOIN implementation details
- `dates.md` - Date handling implementation
- `macros.md` - Macro system documentation
- `spines.md` - Spine concept documentation
- `WINDOW_UTILS.md` - Window function utilities

### Other
- `CLI_SPEC.md` - CLI specification notes
- `language-config.md` - Language configuration notes
- `playground-settings.md` - Playground settings documentation
- `UNDERSCORE_SPACE_PRINCIPLE.md` - Design principle documentation
- `SET_THEORY_ANCESTORS.md` - Set theory concepts
- `UNHANDLED_SQL_FUNCTIONS.md` - Unhandled SQL functions list
- `universal_function_shorthand.md` - Function shorthand documentation
- `other_sql_support_in_asql.md` - Other SQL support notes
- `sql-dialect-early-signs.md` - Early dialect system notes
- `auto_spine_simplifications.md` - Auto-spine simplification notes
- `COHORT_ANALYSIS.md` - Cohort analysis notes
- `comments.md` - Comments implementation notes

## Maintenance

### When to Delete Notes

Consider deleting or archiving notes when:
- ❌ The feature is fully implemented and the note is no longer relevant
- ❌ The analysis is outdated and superseded by newer documentation
- ❌ The note was a one-off investigation that's no longer useful
- ❌ The information has been moved to proper documentation in `docs/`

### When to Keep Notes

Keep notes that:
- ✅ Document important design decisions or rationale
- ✅ Contain implementation details that aren't in public docs
- ✅ Serve as reference for future similar work
- ✅ Are still actively referenced or useful

### Best Practices

1. **Naming**: Use descriptive, kebab-case filenames (e.g., `string-matching-plan.md`)
2. **Dates**: Consider adding dates in filenames for time-sensitive notes (e.g., `2025-01-style-analysis.md`)
3. **Status**: For implementation plans, mark completion status at the top
4. **Links**: Link to related notes and official docs when relevant
5. **Cleanup**: Periodically review and remove outdated notes (quarterly or when they become stale)

## Related Documentation

- **Public docs**: See `docs/` folder for user-facing documentation
- **Language spec**: `docs/spec.md` - The canonical ASQL specification
- **Future features**: `docs/spec_future.md` - Future/maybe features
