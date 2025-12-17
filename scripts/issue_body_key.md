## Summary
Add `key(col1, col2, ...)` for stable surrogate key generation inspired by dbt_utils.

## Inspiration
- dbt_utils: `generate_surrogate_key([...])`

## Proposed syntax

```asql
from orders
  select key(user_id, order_id) as order_key
```

## Acceptance criteria
- Deterministic output for identical inputs
- Deterministic NULL handling
- Cross-dialect strategy (documented) for hashing/concat
- Tests for:
  - multiple columns
  - NULLs
  - mixed types

## Docs
- Mention this in `docs/coming-from/dbt.md` as inspired by dbt macros.
- Ensure `docs/spec.md` matches the implemented behavior (spec already mentions it).

__ISSUE_NUMBER__
__PR_TITLE__
__BRANCH__
