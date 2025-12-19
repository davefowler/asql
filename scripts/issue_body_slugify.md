## Summary
Add `slugify(expr)` helper to convert strings into URL-friendly slugs.

## Inspiration
- Inspired by dbt macro patterns (dbt_utils-style helpers for repeatable transformations).

## Proposed syntax

```asql
from products
  select slugify(name) as slug
```

## Expected behavior
- Lowercase output
- Replace runs of non-alphanumeric characters with `-`
- Trim leading/trailing `-`
- Reasonable behavior for NULLs (documented)

## Cross-dialect notes
- Prefer a rewrite that SQLGlot can transpile reliably.
- If regex differs per dialect, document supported dialect behavior or fall back to best-effort implementation.

## Acceptance criteria
- Compiler support + tests
- Update docs:
  - `docs/spec.md` (add function and examples)
  - `docs/spec_future.md` (remove/mark implemented)
  - `docs/coming-from/dbt.md` (mention this helper as dbt-macro inspired)

## Notes for the PR
- This feature is currently described in `docs/spec_future.md` and should be promoted to `docs/spec.md` once implemented.

__ISSUE_NUMBER__
__PR_TITLE__
__BRANCH__



