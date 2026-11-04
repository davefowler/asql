# Contributing to asql

Thanks for helping. The short version:

1. `just install` sets up the Python environment, the JS lint tooling and the
   git pre-commit hook (ruff on staged Python, ESLint on staged playground JS).
2. Read [AGENTS.md](AGENTS.md). It is the single source of conventions for
   humans and coding agents: the `just` recipes, where code lives, tests
   first, changelog entries, and how a PR is reviewed and merged.
3. `just check` before pushing. CI runs the same gates plus `just smoke` and a
   Docker build; all must be green to merge.
4. Open the PR with the template filled in (why, what changed, how verified,
   what is still unsupported).

## Repository settings (maintainers)

`main` should be protected in **Settings → Branches**: require a pull
request, require the `test`, `postgres`, `lint`, `docker`, `e2e` and `build`
status checks, and squash merging only. These settings are not in the repo,
so re-check them after any transfer or rename.

Dependabot (`.github/dependabot.yml`) opens one grouped PR a week per
ecosystem (uv, npm, GitHub Actions); merge them like any other PR once CI is
green.

Releases are git tags: bump `version` in `pyproject.toml`, move the
`## [Unreleased]` entries in `CHANGELOG.md` under the new version, and tag
the squash commit `vX.Y.Z` on `main`. Nothing publishes automatically.
