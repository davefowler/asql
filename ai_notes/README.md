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

### 📁 Root (`ai_notes/`)
Active notes and time-sensitive documents that are still being referenced:

**Time-Sensitive Analysis** (may become outdated):
- [`2025-12-16-style-analysis.md`](2025-12-16-style-analysis.md) - Analysis of default style settings violations

**Active Research & Tracking**:
- `CLI_SPEC.md` - CLI specification (psql-like interface)
- `UNHANDLED_SQL_FUNCTIONS.md` - Tracking document for SQL function coverage
- `other_sql_support_in_asql.md` - Research on supporting standard SQL within ASQL
- `pandas-python-notebooks-learnings.md` - Learnings from pandas/Python patterns
- `sql-dialect-early-signs.md` - Early signs of transformational SQL in existing tools
- `SET_THEORY_ANCESTORS.md` - Set theory concepts and ancestry patterns

### 📦 Archive (`ai_notes/archive/`)
Important design decisions, architectural explorations, and implementation guides that document the evolution of ASQL. These are kept for historical reference and design rationale.

#### 📐 Designs (`archive/designs/`)
Design decisions, architectural explorations, and feature designs:

**Core Design Principles**:
- `case.md` - Design exploration for `when` conditional expressions
- `CRITICAL_REVIEW.md` - Critical review of ASQL specification with design concerns
- `UNDERSCORE_SPACE_PRINCIPLE.md` - Core principle: underscore/space interchangeability
- `spines.md` - Spine concept and gap-filling design
- `auto_spine_simplifications.md` - Design exploration: patterns that become obsolete with auto-spine

**Architecture & Implementation**:
- `dialect.md` - Deep dive on implementing ASQL as SQLGlot dialect
- `PIPELINE_CTE_IMPLEMENTATION.md` - Detailed guide on implementing pipelined CTEs
- `STRING_MATCHING_PLAN.md` - Implementation plan for string matching operators
- `comments.md` - Comment extraction and metadata API design
- `language-config.md` - Language configuration system design
- `playground-settings.md` - Playground settings and style configuration

**Feature Design**:
- `joins.md` - JOIN design and simplification ideas
- `dates.md` - Date handling design and patterns
- `macros.md` - dbt macro replacement design (80% of macro value)
- `DBT_DEEP_INTEGRATION_IDEATION.md` - dbt integration ideas (last 20%)
- `COHORT_ANALYSIS.md` - Cohort analysis feature design
- `WINDOW_UTILS.md` - Window function utilities design
- `universal_function_shorthand.md` - Function shorthand pattern design

#### 🔬 Research (`archive/research/`)
Research notes, comparisons, and learnings from other tools:

- `SQLMESH_COMPARISON.md` - Comparison with SQLMesh architecture and features

## Maintenance

### When to Delete Notes

Delete notes when:
- ❌ The note was a one-off response for a single issue (e.g., status reports)
- ❌ The feature is fully implemented and the note is no longer relevant
- ❌ The analysis is outdated and superseded by newer documentation
- ❌ The information has been moved to proper documentation in `docs/`

**Examples of deleted notes**:
- `PHASE_COMPLETION.md` - Was just a response for a single issue
- `IMPLEMENTATION_STATUS.md` - Was just a response for a single issue
- `FEATURE_STATUS.md` - Superseded by canonical docs

### When to Archive Notes

Move to `archive/` when:
- ✅ The note documents important design decisions or rationale → `archive/designs/`
- ✅ The note contains architectural explorations that influenced the design → `archive/designs/`
- ✅ The note serves as reference for understanding "why" decisions were made → `archive/designs/`
- ✅ The note is an implementation guide that's complete but still useful for reference → `archive/designs/`
- ✅ The note is research/comparison with other tools → `archive/research/`

**Note**: Not all archived notes need to go into subfolders. Some may stay directly in `archive/` if they don't fit the designs/research categories.

### When to Keep in Root

Keep in root when:
- ✅ The note is still actively being referenced or updated
- ✅ The note is time-sensitive and may become outdated (add dates!)
- ✅ The note is a tracking document that's still in use

### Best Practices

1. **Date-based naming**: Time-specific reports (status reports, analysis results, completion summaries) MUST use date-prefixed filenames: `YYYY-MM-DD-descriptive-name.md` (e.g., `2025-12-16-style-analysis.md`)
   - This makes it clear these are snapshots in time, not "source of truth" documents
   - Use when: status reports, analysis results, completion summaries, one-off investigations
   - Don't use for: design docs, implementation guides, research (these go in archive)
2. **Dates in content**: For notes that remain in root but may become outdated, add date headers at the top (e.g., `**Date**: 2025-01-XX`)
3. **Status**: For implementation plans, mark completion status at the top
4. **Naming**: Use descriptive, kebab-case filenames (e.g., `string-matching-plan.md`)
5. **Links**: Link to related notes and official docs when relevant
6. **Cleanup**: Periodically review and:
   - Delete one-off status reports and outdated analyses
   - Archive completed design docs that document important decisions
   - Add dates to time-sensitive notes that remain in root

## Related Documentation

- **Public docs**: See `docs/` folder for user-facing documentation
- **Language spec**: `docs/spec.md` - The canonical ASQL specification
- **Future features**: `docs/spec_future.md` - Future/maybe features
