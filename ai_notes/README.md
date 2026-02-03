# AI Notes

This folder contains AI-generated analysis reports, implementation plans, and development notes created during ASQL development.

**These are internal reference documents** - NOT part of the public-facing documentation in `docs/`.

## Structure

```
ai_notes/
├── README.md           # This file
├── CLI_SPEC.md         # CLI specification (psql-like interface)
└── archive/            # Historical documents
    ├── designs/        # 41 design docs and architectural decisions
    ├── reports/        # 62 dated analysis reports and investigations
    └── research/       # 16 research notes on other tools/approaches
```

## Archive Contents

### `archive/designs/` - Design Decisions
Feature designs, architectural explorations, and implementation guides that document the evolution of ASQL.

### `archive/reports/` - Dated Reports
Point-in-time analysis reports, audits, and investigations. Named with `YYYY-MM-DD-` prefix.

### `archive/research/` - Research Notes
Comparisons with other tools (PRQL, SQLMesh, Spark, etc.) and learnings from other query languages.

## Related Documentation

- **Public docs**: `docs/` - User-facing documentation (website)
- **Language spec**: `docs/spec.md` - Canonical ASQL specification
- **Future features**: `docs/spec_future.md` - Planned features
