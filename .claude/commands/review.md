Review the current branch the way a PR reviewer would, then fix what you confirm.

1. Run `just review` (lint, mypy, ESLint, the test suite, then the diff summary
   against main). Fix anything red before going further.
2. Run `/code-review high` on the diff against main. For each finding: verify it
   with a failing test or a reproduction, fix it if it is a real defect in this
   branch, and skip pre-existing or style-only findings with a one-line reason.
3. Re-run `just check`.
4. Report: what was found, what was fixed, what was skipped and why, and
   anything that should be called out as still unsupported in the PR description.
