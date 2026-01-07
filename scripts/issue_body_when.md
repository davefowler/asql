## Summary
Add ASQL `when` conditional expressions as a readable replacement for SQL `CASE`.

## Context
- This is already described in `docs/spec.md` §4.7 but not implemented.
- Reverse compilation can emit `when`-like output, but forward compilation does not support it.

## Acceptance criteria
- Tests (TDD) covering:
  - simple case (`when <expr> ...`)
  - searched case (`when <cond> ...`)
  - multiple branches
- Compiles to valid SQL `CASE WHEN ... THEN ... ELSE ... END` across dialects.

## Notes for the PR
- The feature is already in the spec; PR should confirm the spec matches the actual implementation.

__ISSUE_NUMBER__
__PR_TITLE__
__BRANCH__
