# Working on asql

Conventions for anyone (human or agent) changing this repo. `CLAUDE.md`
points here; keep this file the single source of truth.

## Commands (all through `just`)

| Command | What it does |
|---|---|
| `just install` | `uv sync --all-extras --locked` + `npm ci` |
| `just test [args]` | pytest, excluding `slow` and `e2e` (`just test tests/test_x.py -k name`) |
| `just lint` | ruff check, ruff format check, mypy (strict), ESLint |
| `just fix` | ruff autofix + format |
| `just check` | `lint` then `test`: everything CI's `test` and `lint` jobs run, minus `smoke` |
| `just review [base]` | `check`, then the diff summary against `base` (default `main`) for a reviewer |
| `just smoke` | build the wheel, install it in a clean venv, transpile a query |
| `just serve` | playground on :8011 and docs on :8012 with reload |

CI (`.github/workflows/ci.yml`) runs `just test`, `just smoke`, `just lint`
and a Docker build on every PR. A PR is mergeable when all four are green.

Don't call `pytest`, `ruff` or `mypy` directly in instructions or docs; the
recipes pin the locked environment (`uv run --all-extras --locked`).

## Where things live

- `asql/dialect/` is the sqlglot dialect: `tokenizer.py`, `parser.py`
  (FROM-first pipelines, `TRANSFORM_PARSERS`), `generator.py` (SQL → ASQL),
  `transforms/` (parser-stage rewrites such as auto aliases, week start).
- `asql/compiler/` holds dialect-aware rewrites that run in
  `asql.transpile()` after parsing (spine, alias reuse, fanout, ...).
- `asql/visual_dialect/generator.py` turns the AST into the Visual ASQL JSON;
  `asql/json_schema.py` turns that JSON back into ASQL text. The pair must be
  lossless: `tests/test_visual_roundtrip.py` is the contract.
- `asql/functions.py` registers ASQL functions and the `meta` keys the parser
  leaves on nodes so later stages can spell them back (`ALIAS_FUNC_META`,
  `STRING_OP_META`, `SAMPLE_META`).
- `asql/playground/` is the FastAPI playground; its examples
  (`examples/asql/*.json`) double as test corpora.
- `docs/` is the mkdocs site; `docs/spec.md` is the language reference.

## How to make a change

1. **Write the test first and watch it fail.** Parser and compiler changes get
   a case in the matching `tests/test_*.py`; anything that affects
   ASQL → JSON → ASQL gets a case in `tests/test_visual_roundtrip.py`
   (it checks all three dialects). Playground examples are also corpora, so a
   new syntax usually deserves an example.
2. Compare semantics, not strings, when a test checks generated SQL that may
   differ cosmetically: parse both sides with sqlglot and compare ASTs.
3. Prefer declarative tables (`dict` maps, `TRANSFORMS`) over `elif` chains
   when adding a node type or operator.
4. Never drop a clause or substitute an operator silently. If a stage cannot
   represent something, emit it verbatim (`raw` nodes in the visual JSON) or
   raise `ASQLCompilationError` with a message that says what to write instead.
5. `just check` before pushing; `just fix` for formatting. mypy is strict:
   type new functions fully.
6. Add a line under `## [Unreleased]` in `CHANGELOG.md` (Added / Changed / Fixed).
7. Docs: ` ```asql-play ` blocks must compile (the docs build runs them);
   use ` ```asql ` for snippets. Follow `docs/style_guide.md` in examples.

## Pull requests

- Keep one concern per PR; a parser bug found while doing something else is
  its own commit with its own test.
- The description says why, what changed, how it was verified, and what is
  still unsupported or deliberately out of scope. `.github/pull_request_template.md`
  has the headings.
- Review before merging: `just review`, then a `/code-review` pass (the
  `/review` project command runs both and fixes what it confirms).
- Merge with squash so `main` stays one commit per PR.
