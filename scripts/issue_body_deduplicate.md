## Summary
Add `deduplicate by ...` as syntax sugar for the existing window + QUALIFY dedupe pattern.

## Proposed syntax

```asql
from events
  deduplicate by user_id, event_type
  order by -created_at
```

## Expected behavior
- Rewrite to:
  - `per user_id, event_type first by -created_at`
  - (or an equivalent `ROW_NUMBER() ... QUALIFY ... = 1` form)

## Acceptance criteria
- Tests for:
  - multiple partition columns
  - required order-by (helpful error if missing)
  - dialects without QUALIFY (fallback subquery if needed)

## Notes for the PR
- This operator is described in `docs/spec.md` §13.2; PR should confirm/update the spec.

__ISSUE_NUMBER__
__PR_TITLE__
__BRANCH__
