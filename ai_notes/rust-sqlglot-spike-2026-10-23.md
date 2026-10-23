# Rust sqlglot: estimate, strategy, spike (2026-10-23)

Question asked: what would it take to have sqlglot in Rust, and how should we
do it? Answer in one line: **don't port it, someone already did; the real work
is porting asql's own dialect onto that port, and that is the estimate below.**

## What exists already

A function-by-function Rust port of sqlglot is published and maintained:

| | polyglot-sql | sqlglot-rust (Protegrity) |
|---|---|---|
| Crate / version | `polyglot-sql` 0.13.3, 2026-10-09 | `sqlglot-rust` 0.10.33 |
| Size | 325k lines of Rust | 54k lines |
| Dialects | 38 (feature-gated) | 30 "mapping" dialects in one file |
| Fidelity method | sqlglot's own fixtures extracted from the Python repo (11,333 cases: identity 977, dialect identity 4,086, transpile 6,061), `make test-compare` against Python sqlglot | own 311k-statement acceptance corpus; 2.35% rejects |
| Port style | literal: `parse_pipe_syntax_aggregate` is documented as "Implemented from Python `_parse_pipe_syntax_aggregate`" | "inspired by"; ~40 expression types |
| Optimizer | qualify_columns, qualify_tables, annotate_types, simplify, pushdowns, scope, lineage | scope, annotate_types, lineage |
| Bindings | WASM (`@polyglot-sql/sdk`, 25 MB unpacked), Python wheel (PyO3, ~12 MB), C FFI, Go | C FFI, CLI |
| Governance | MIT, 972 stars, 209 commits, effectively one author (tobilg); ClickHouse forked it in mid-2026 | MIT, 39 stars |

polyglot-sql is the one that matters. It is what "port sqlglot line by line" produces
when someone does it: a typed AST (`Expression` enum, 932 variants, derive-macro
generated visitors), a 70k-line parser and a 46k-line generator that mirror
sqlglot's methods one to one, and sqlglot's test fixtures as the oracle.

## Measured on asql's output

`spike/rust-sqlglot/` runs every playground example through `asql.transpile`
for six targets (240 SQL strings), then transpiles each string with both
Python sqlglot and polyglot-sql: identity (read d → write d) and every
cross-dialect pair (30 pairs). Outputs are compared as strings, then as ASTs
(both parsed by Python sqlglot in the write dialect).

_Measurement pending: the polyglot-sql release build was still running when this note was first committed; numbers land in the next commit._

## Does asql need all of sqlglot?

No. asql touches a small slice:

| asql needs | sqlglot surface | in polyglot-sql? |
|---|---|---|
| Tokenizer with custom single-char tokens (`\|`→PIPE_GT, `#`→HASH) and keywords | `Tokenizer.SINGLE_TOKENS`, `KEYWORDS` | yes: `TokenizerConfig.single_tokens` / `keywords`, `Tokenizer::new(config)` |
| SQL expression grammar (asql reuses sqlglot's for `where`, `select`, function calls, subqueries) | `Parser._parse_expression` and ~80 private `_parse_*` methods asql overrides | parser exists, but `parse_expression`, `parse_unary`, `parse_comparison`, `match_token`, `advance`, `peek` are **private**; no hook/plugin API |
| 131 AST node classes | `exp.*` | 125 present (names differ: `EQ`→`Eq`, `CTE`→`Cte`, `If`→`IfFunc`); missing: `Spine` (asql's own), `WeekStart`, `IgnoreNulls`, `Semicolon`, `MD`; abstract bases (`Func`, `Binary`, `Query`) have no equivalent, matching is by enum variant |
| `node.meta` side-channel (`ALIAS_FUNC_META`, `STRING_OP_META`, `SAMPLE_META`, `_GROUP_STAGE`) | `Expression.meta` dict | **no**; nodes are plain structs. Would become real fields or a side table keyed by node id |
| Generators for postgres, duckdb, snowflake, bigquery, redshift, mysql (+8 minor) | `generator.py` + dialects | yes, all 14 |
| Generator overrides (`cast_sql`, `coalesce_sql`, `count_sql`, `eq_sql`, `from_sql`, `join_sql`, `ordered_sql`, `select_sql`, `with_sql`) for the ASQL *output* dialect (SQL → ASQL) | `Generator.TRANSFORMS` | partial: `CustomDialectBuilder` gives `generator_config_modifier`, `transform_fn`, `preprocess_fn`; no per-node generator override |
| `qualify_columns`, `annotate_types` | `sqlglot.optimizer` | yes |
| Visual JSON ↔ AST | our own code over `exp` | polyglot has `ast_json` (serde) which makes the JSON side easier |

So the "subset" is about 45–55k lines of Python if we ported ourselves (the
other note's number is right), but with polyglot-sql the subset question is
moot: all of it is there, and the gap is **extension points**, not coverage.

## On the other agent's write-up

Agree with: text in, text out; the answer key is Python sqlglot; most of it is
mechanical; it is a moving target with an unending upstream-tracking cost; asql
breaks because it subclasses private parser methods; name resolution and
lineage are the subtle parts; only worth doing when there is no Python in the
process (browser/WASM, embedded in a Rust engine); ask Toby.

Updates:

1. **The 3-month "port all of it" line item is already paid.** polyglot-sql is
   that port, done the way the note proposes (literal, fixture-driven), and the
   upstream-tracking cost is currently carried by its maintainer. The risk
   moves from "we must write it" to "one maintainer, 0.x, monthly breaking
   changes in exhaustive enum matches".
2. **The typed-tree problem is solved, not open.** 932 typed variants plus a
   derive macro for child traversal is what the loosely typed `args` dict
   became. It is verbose but mechanical; nobody needs `serde_json::Value`.
3. **"Why not line by line?"** That is the right method, and it is what
   polyglot did. The only reason to repeat it is if we need to own the code
   (governance), not because it is hard.
4. **The asql side is the real port**, and it is not mechanical, because asql's
   dialect is 4,062 lines of parser subclass that override sqlglot internals
   (`_parse_unary`, `_parse_factor`, `_parse_bracket`, `_parse_field`,
   `_parse_table`, `_parse_alias`, `_parse_comparison`...), plus `meta`
   side-channels and ~2,500 lines of compiler passes (spine, fanout, alias
   reuse, metrics) over the AST. Those have no hook in polyglot-sql today.

## Strategy options

### 0. Stay in Python, use `sqlglotc`
sqlglot's maintainers dropped their Rust tokenizer for a mypyc-compiled build.
If the need is speed, this is a `pip install` and zero porting. If the need is
"no Python in the process", it does not help.

### 1. asql front-end in Rust on top of polyglot-sql (recommended if Rust is needed)
asql's grammar is small: a pipeline of ~25 step keywords (`from`, `where`,
`group by`, `spine by`, `per`, `extend`, `stash`, `recurse`, `pivot`, joins
with `&`/`&?`/`?&`) and an expression grammar that is SQL's plus a dozen
sugar forms (`-col`, `#`, `x == y`, `@2024-01-01`, `7 days ago`, `contains`,
`[x for ...]`, `::tz`). Write that parser ourselves in Rust (a Pratt
expression parser plus the pipeline driver), emitting polyglot's `Expression`
directly, and use polyglot unchanged for SQL subqueries, generators,
qualify/annotate and the SQL → ASQL direction's parser.

- Pros: no fork; polyglot's private parser internals never matter; asql owns
  the grammar it already owns; upgrades are a `Cargo.toml` bump.
- Cons: we lose "sqlglot parses the SQL parts for free" inside ASQL
  expressions. Where ASQL embeds raw SQL (`(select ... )`, function calls with
  SQL syntax) we hand the token slice to polyglot's `Parser` (its
  `parse_column`, `parse_function`, `parse_table_parts`, `parse_term`,
  `parse_select_query` are public). The `meta` side channel becomes explicit
  fields on asql-owned wrapper nodes.

Phases, with the same agent setup that produced the render port:

| Phase | Deliverable | Estimate |
|---|---|---|
| A. Oracle harness | `spike/rust-sqlglot` grown into a parity test: every corpus query (playground + docs 217 + tests ≈ 1,500 ASQL queries) → Python asql SQL vs Rust asql SQL, AST-compared per dialect | 1 week |
| B. Tokenizer + pipeline driver + expression grammar | `from/where/select/group by (block)/order by/limit/joins/extend/stash` with asql's expression sugar; `Expression` out; postgres/duckdb/snowflake/bigquery via polyglot | 3–4 weeks |
| C. Parser-stage transforms | auto alias, auto qualify, count entity, join inference/fk shorthand, date units, underscore shorthands, pivot | 2–3 weeks |
| D. Compiler passes | spine, fanout, alias reuse, metrics, column operators, date parts | 3–4 weeks |
| E. Reverse direction + visual JSON | SQL → ASQL generator overrides (needs polyglot generator hooks or our own generator for the ASQL dialect), visual JSON round trip via `ast_json` | 2–3 weeks |
| F. Bindings | WASM for the playground, PyO3 wheel so Python asql can delegate | 1–2 weeks |

Total: **12–17 weeks** to parity with the Python package on the corpus, with
Python asql kept as the oracle throughout. Lineage/semantic graph not
included.

### 2. Fork polyglot-sql and add parser hooks
Make `parse_expression` and friends overridable through a trait object on
`ParserConfig`, then port asql's parser as an implementation of that trait,
method by method. Closest to the Python design, cheapest mental migration,
and the hooks could be upstreamed (tobilg accepts PRs; the ClickHouse fork
shows others extend it). Cost: 1–2 weeks for the hook layer plus the same B–F
above minus ~2 weeks, but every upstream release can break the hooks until
they land upstream. Pick this only if upstream agrees to the hook API first.

### 3. Port sqlglot ourselves
3 months plus ongoing, as the other note says, and then still options 1 or 2
for asql. Only justified if we need to own the SQL core (licensing is MIT so
that is a governance choice, not a legal one).

## Risks with polyglot-sql specifically

- **Bus factor one.** 209 commits, nearly all by one person; the ClickHouse
  fork lags at 0.5.x. Mitigation: vendor a pinned version; the code is
  readable because it mirrors sqlglot's method names.
- **0.x churn.** Breaking changes in 0.10, 0.11, 0.12, 0.13 (new enum
  variants, new struct fields). Our code must avoid exhaustive matches and
  struct literals, or we absorb a fix per release.
- **Unknown sqlglot version pin.** Fixtures are regenerated by hand
  (`make extract-fixtures`); the README does not say which sqlglot version.
  Our parity harness against Python sqlglot 30.24 is the real check.
- **Build cost.** One 325k-line crate: ~15 min release build on 4 cores.
  CI needs `sccache` or a prebuilt artifact; feature-gating to the six
  dialects we need only trims function catalogs, not the parser.
- **WASM size.** 25 MB unpacked npm package; needs measuring as a gzipped
  `.wasm` before promising a browser playground.

## Recommendation

- Do not port sqlglot. Adopt polyglot-sql if and when a Rust/WASM asql is
  needed, and spend the budget on option 1 (asql front-end in Rust).
- Before any of that, decide the trigger: a browser playground without a
  server, embedding in a Rust engine, or raw speed. For speed alone, option 0.
- Ask Toby whether sqlglot would bless or co-maintain a Rust core; a yes
  changes option 2 into the default.
- Keep `spike/rust-sqlglot` as the parity harness; extend it to the full
  query corpus as phase A if we proceed.
