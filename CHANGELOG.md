# Changelog

All notable changes to ASQL will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-11-04

### Added
- CI runs the Playwright playground tests (`just e2e`) and reports line coverage (`just coverage`); Dependabot keeps `uv.lock`, `package-lock.json` and the pinned Actions current; CONTRIBUTING lists the branch-protection checks and how a release is tagged
- Playground tables `employees`, `departments`, `issue_custom_fields`, `user_settings` and `monthly_metrics`, used by the docs' recursion, FK-shorthand, pivot and unpivot examples
- `just test <path>` runs only that path (the recipe used to run the whole suite as well); CI runs the execution tests against PostgreSQL 16 (`PostgresExecutor`, enabled by `ASQL_TEST_POSTGRES_URL`), executes every docs ` ```asql-play ` block on DuckDB (`tests/test_docs_execute.py`), and checks a corpus of malformed queries all raise (`tests/test_parse_strictness.py`)
- `tests/test_visual_roundtrip.py` also runs every ` ```asql-play ` block in the docs (217 queries) through the round trip, with the docs build's schema and settings
- Contributor setup: `AGENTS.md` (conventions, pointed to by `CLAUDE.md`), `just check` and `just review` recipes, a `/review` project command and a pull request template
- Visual ASQL round trips are lossless: `tests/test_visual_roundtrip.py` checks `asql.transpile(q)` against `asql.transpile(json_to_asql(visual(q)))` for DuckDB, PostgreSQL and Snowflake over the playground examples and the operator corpus
- Visual ASQL JSON keeps schema-qualified tables and table aliases, `distinct`, `extend`, `except`/`rename`/`replace`, `qualify`, `explode`, `sample` (`size`, `per`), `pivot`/`unpivot`, `like`/`ilike` (with `negate`), `matches`, `contains`/`starts with`/`ends with` as their own node types, `not_in`, `is not null`, `paren`, arithmetic and `||` binaries, `count(distinct x)`, computed dimensions and aggregates as `{"expression", "alias"}`, order-by expressions and `nulls`; anything else is an explicit `raw` node (expression, FROM source or whole pipeline) holding ASQL text that `json_to_asql` reproduces verbatim
- `json_to_asql` backtick-quotes identifiers that are not plain (`` `Last Name` ``, `` `my schema`.`my table` ``) in every name slot, parenthesizes binary children by precedence, and emits `like` as LIKE instead of a regex `matches`
- `stash as x` followed by a fresh `from` (the form documented in the spec) now parses: the new pipeline reads the stashed CTEs (`from a where x stash as a1` / `from b & a1 on ...`)
- Count inference: `# <table>` counts distinct entities (`from orders ( # users )` → `COUNT(DISTINCT user_id)`), with a schema, resolved from relationships or the `<singular>_id` convention (no inference without a schema)
- Versioning infrastructure with single source of truth in `pyproject.toml`
- CHANGELOG.md for tracking changes
- `fill_forward()` and `fill_backward()` window functions for NULL propagation in time series data
- Semantic graph support: `asql.semantic.load_graph()` reads a dbt-metrics `graph.yaml`; `Schema.from_graph()` feeds its grains and relationships into join inference and fanout protection, and queries can use bare metric names and `relationship.attribute` references

### Changed
- Requires sqlglot 30.24.0 or newer (was 30.0.0), the version CI tests against
- A join with no `on` now raises `ASQLResolutionError` when the schema declares several distinct explicit relationships between the two tables (for example buyer and seller both pointing at users), instead of silently using the first one

### Fixed
- The e2e harness starts the playground from the test interpreter (`asql.playground.app:app`) instead of a `venv/` that `just install` never creates, and its assertions match the current UI
- `prior()` / `next()` compile to `LAG` / `LEAD` with an `OVER` clause that takes the query's `order by` (they emitted a bare `LAG(x, 1)`, invalid everywhere); without an ordering they raise
- A non-aggregate pivot (`pivot value by setting_name …`) uses `MAX` as the spec says, so string values work (it used `SUM`)
- `spine by quarter(d) as quarter` keeps its alias outside the spine marker, so the aggregate block's projection is `quarter(d) AS quarter` and the Visual ASQL round trip holds
- Every docs ` ```asql-play ` example now runs against the playground schema: 42 examples named tables or columns it lacked (`date`, `month`, `product`, `monthly_data`, …) and are rewritten on existing columns, with explicit aliases where they sorted by a date part
- Fanout protection: a many-side join it skipped still gets the inflation warning (it was silenced along with the rewritten ones); a collapsed join no longer warns that it multiplies rows; stage-2 protection applies when a group key carries an alias (`group by orders.customer_id as cust`)
- `except email` followed by `select *, …` keeps the exclusion (the select replaced the projection and the `except` was silently dropped); like `rename`, it now closes the stage
- The alias-reuse CTE chain for non-DuckDB dialects no longer projects `SELECT *, *` nor re-selects every computed alias after `*` (duplicate output columns on PostgreSQL), and carries the star override (`select *, upper(name) as name`) on its base
- A strict `>` bound on a DATE-typed column starts the spine the next day; spine bounds read only the query's own `where`, never a subquery's
- `spine by year(d), month(d)` builds one spine at the finer grain and reads the year off it instead of cross-joining two spines (2 years × 5 months → 5 rows); units that do not nest (`week` with `month`) raise
- `spine by hour(ts)` is a timestamp series (it fell back to the distinct values, filling no gaps); a timestamp `<` bound ends the spine in the period before it
- A categorical spine counts the NULL group: `count(*)` counts a never-null row marker instead of the key column
- `@2024-01-03T06:00:00` is `CAST(… AS TIMESTAMP)` on PostgreSQL, which has no `TIMESTAMP()` function
- A `where` written before the first join qualifies its bare columns with the FROM table, so `from orders where status = "paid" & customers …` no longer fails as ambiguous when the joined table has the column too
- `select`, `group by` and `except` with nothing after them, `a ??` with no right side, `when … then` with no result and `… as` with no name raise instead of silently compiling to something else
- Docs examples that named columns the playground schema lacks (`ssn`, `salary`, `password`, `orders.date`, `orders.name`) and the cohort examples' ambiguous `count(distinct user_id)` after a join
- DuckDB list comprehensions are restored from the AST instead of a regex over the generated SQL, which corrupted `[x * 2 for x in numbers if abs(x) > 1]` (`IF ABS(x] > 1)`) and missed `[x for x in data.numbers]`
- A date spine without explicit WHERE bounds no longer degrades to the dates that already exist on BigQuery, Snowflake, MySQL, Spark, Trino and SQLite; the MIN/MAX bounds are scalar subqueries over the data and the series is built the same way as with explicit bounds
- Fanout protection no longer pre-aggregates a many-side table whose column a later join's ON clause needs (`orders → order_items → products` grouped by product failed with a binder error)
- Auto-aliasing no longer injects `AS` inside function arguments, IN lists or UNNEST (`concat(upper(first), " ", last)` compiled to `UPPER(first) AS upper_first || …`); only projections and pivot aggregates are named
- `first(x order by k)`, `last(...)` and `arg_max`/`arg_min` inside an aggregate block are aggregates (`ARG_MAX`/`ARG_MIN`, `MAX_BY` on Snowflake/BigQuery, an ordered `ARRAY_AGG` on Postgres/Redshift) instead of window functions in a GROUP BY query; dialects with none of these raise `ASQLDialectError`, which the docs render as a per-dialect note
- `except users.password_hash` / `rename users.id as user_id` after a join keep their qualifier on the matching `users.*` (the exclusions were silently dropped); an unqualified column with a join is an error naming the tables
- `when status is null then …` compiles to `IS NULL` (it was `= NULL`, always false), and the `when` base can be any expression (`when upper(status) is "A"`, `when a.b is "x"`)
- `spine by status (count(*))` compiled to an invalid alias-reuse chain on every dialect but DuckDB; the count now reads the source-qualified key
- `spine by month(x) as m` and `group by spine(month(x)) as m` lost the spine (the key alias was stripped before the spine transform ran); GROUP BY aliases are now stripped after it
- `running_sum(x) as rs … order by dbl` where `dbl` is a projection alias copied the alias into the window's ORDER BY (invalid); aliases are resolved to their expressions, and ordering by the running window itself is an error
- Inline `SET` statements (`SET include_transpilation_comments = false;`) were ignored by the compile stage when `transpile()` was called without keyword settings; `transpile()` now always runs with a dialect instance, and never mutates one a caller passes in (schema and `SET` no longer leak between calls)
- Underscore shorthand no longer re-aggregates a column an earlier stage produced (`group by country ( # as total_users ) select country, total_users` used to become `SUM(users)`); the spec's `stash as` example now compiles as written
- `select *, 1 as flag` over a table with unknown columns no longer emits `EXCLUDE (flag)` (an error on every engine, and unusable on Postgres without a schema); only an alias that overrides a column it reads (`upper(name) as name`) is excluded
- Steps after `limit`/`offset` read the limited rows (`limit 10 where x = 1` filtered the whole table before), and a step after a fixed projection reads that projection (`select a + 1 as c select c, 2 as d`, `select a, b extend a + b as c`, `select a + 1 as c where c > 1`)
- `spine by week(x)` with `week_start = sunday` joined the Sunday spine on Monday weeks, so every period came back empty; the join key now uses the same week start as the spine
- Same-row alias reuse on non-DuckDB dialects (`select row_number() over (...) as rn, rn * 2 as d`) applied the query's WHERE after the window instead of before it, and built a `SELECT * … GROUP BY` base for grouped queries; the base CTE now keeps WHERE, GROUP BY and HAVING
- A GROUP BY key alias that shadows a column it reads (`group by coalesce(region, 'unknown') as region`) grouped by the raw column; such keys now group by their expression
- The parser now raises on tokens it cannot place instead of dropping them (`from t where x = 1 foo bar` and `select a, , b` used to compile to a different query); `when … then y + 1, otherwise 0` keeps the full result expression and the `otherwise` branch; `when n < 10 then a, n < 100 then b` branches each carry their own condition; `rename`/`replace` directly after a `select` list parse
- `<window> over <col>` is read as `over (partition by <col>)` (`first(x order by y) over cohort`, `running_sum(v) over cohort`), as the cohort docs use it; a `WINDOW w AS (...)` clause still binds `over w`
- The playground image builds on Railway: the `Dockerfile` drops its custom `# syntax=` frontend and `RUN --mount` bind mounts, which Railway's builder rejects
- The playground compiles against its own tables and column types, so BigQuery month/year arithmetic on its timestamp columns and `except`/`rename`/`replace` on dialects without `EXCLUDE` compile instead of erroring
- On BigQuery, a relative date compared with a DATE or DATETIME column counts from `CURRENT_DATE` / `CURRENT_DATETIME()` (`d >= 7 days ago`, `d between 30 days ago and now()`), instead of failing with "DATE >= TIMESTAMP"
- BigQuery month/year arithmetic on a TIMESTAMP runs instead of failing at run time (`12 months ago`, `ts - 1 month`): it goes through DATETIME. DATE and DATETIME operands are unchanged, and a BigQuery operand of unknown type raises `ASQLDialectError` asking for its schema type or a cast
- A parenthesized pipeline whose `select` is not its first step now parses in every position (`a in (from u where b select a)`, `exists (...)`, scalar subqueries, derived tables, joined subqueries). SQL → ASQL output, which always writes nested queries in that order, round trips again
- Dates compile to working SQL on every dialect: `7 days ago`, `x + 1 month` and friends emit each warehouse's interval spelling (BigQuery, MySQL and Trino rejected the old `INTERVAL '7 days'`); `now()` is `CURRENT_TIMESTAMP` (BigQuery has no `NOW`); `x::"America/Los_Angeles"` and `x::PST` convert timezones per dialect instead of failing to parse or casting to a type named `PST`; `relative_date_type="date"` is honored instead of ignored
- The playground highlights ASQL again: the CodeMirror mode moved into the package (`asql/playground/static/asql-mode.js`) so the installed wheel and the Docker image serve it, and a missing static directory now fails at startup instead of silently 404ing
- Visual ASQL: ASQL-only functions (`days_since(x)`, `slugify(x)`, `running_sum(x)`, `bucket(...)`) keep their written call in the JSON and on the way back instead of their SQL expansion; SQL `date_trunc('month', x)` is no longer re-read as `month(x)` (which renamed its auto alias); reserved words used as names (`` `order` ``, `` `select` ``, `` `limit` ``) stay quoted; `select *, expr as alias` over a base table is kept verbatim instead of being re-read with an `EXCLUDE`
- A backticked name that spells a keyword (`` select `limit` ``) no longer ends the select list
- Join star expansion with a schema no longer emits `t.* AS "*"` on PostgreSQL
- The docs' reserved-word example used double quotes, which are string literals in ASQL; it now uses backticks
- Backticked names in `group by` keys and aggregate blocks (`` group by `my col` ( sum(`the amt`) as `Total Amt` ) ``) parse; quoted aliases keep their quotes (`AS "Total Amt"`), and the join star expansion quotes table names (`"other t".*`)
- `extend ... stash as foo` names the stage's own CTE instead of chaining `foo AS (SELECT * FROM __tmp1)`, and an auto CTE never reuses a name a `stash as __tmpN` already took
- `week(x)` as a group-by key no longer crashes PostgreSQL/Snowflake output (the key and its projection were one shared node, so the week start was resolved in only one of them)
- `from a where x = 1 union all from b` parses: `union`/`intersect` end a transform's payload
- `json_to_asql` string literals holding `"` are single-quoted (backslash escapes are not ASQL), `explode` keeps its alias, and `replace` uses `col with expr`
- `group by spine(month(x)), region (...)` now compiles like `spine by` (the `SPINE(...)` call no longer leaks into the SELECT list)
- Spine queries now actually fill gaps: the spine drives the query (`FROM spine LEFT JOIN source ON ... AND <where>`), spine keys are selected from the spine, `count(*)` counts source rows only, and a series starting mid-period no longer skips a period
- Underscore shorthands keep working with an explicit alias: `sum_amount as revenue` expands to `SUM(amount) AS revenue`
- A step after an aggregate block (`select *, ...`, `extend`, joins, window steps) now reads the block's output through a CTE instead of rewriting the grouped query and dropping its aggregates; `select *, new_col` over such a stage no longer excludes a column that does not exist
- `pivot ... group by key` groups the pivot by `key` (key columns are projected beside the pivot columns) instead of emitting an invalid outer `GROUP BY`; non-column keys raise a compile error
- Plain `group by k select ...` (no aggregate block) stays one grouped SELECT; only an aggregate block's output is closed into a CTE
- Spine fixes: `count(*)` rewrite is limited to the spined SELECT, bare key columns keep their output name, NULL categorical keys keep their rows, and `<`/`>` date bounds (including `@date` literals) are exclusive so half-open ranges add no phantom period
- After a bare `group by k`, only `select` may follow; `where`, joins, `extend` or another `group by` raise a compile error asking for an aggregate block or a select. A select before `group by` is closed into its own stage first
- Spine date bounds: strict `>` is no longer shifted (it dropped timestamp rows), and the exclusive upper bound is computed as a plain DATE literal so BigQuery's `GENERATE_DATE_ARRAY` accepts it; an unaliased key projection now reads from the spine
- `select *, col` after a block excludes only existing columns, and falls back to excluding every alias when the stage's columns are not all known
- `SELECT *` expansion for joins no longer picks up joins that live inside a CTE
- A join operator (`&`, `&?`, `?&`, `?&?`, `*`) after a `where` step is parsed as a join instead of bitwise AND / multiplication, which silently dropped the join. RIGHT/FULL joins filter the left table before joining.
- `join users` with no `on` and no schema relationship now raises an error instead of compiling to a cross join; `infer_join_keys` opts in to `{table}_id` convention inference (now also without a schema).
- `transpile(..., schema=<dict>)` and `ASQL(schema=<dict>)` convert the dict to a `Schema` once, instead of crashing in parse-stage transforms.
- Column-only join shorthand (`on user_id`) is no longer left as a bare `ON user_id`: without a schema it raises unless `infer_join_keys` is on, and the naming convention now picks the target by the column's prefix (`from users & orders on user_id` gives `orders.user_id = users.id`), raising when neither or both tables match.
- A RIGHT/FULL join after a `where` that follows earlier joins raises (name the filtered result with `stash as` first) instead of filtering the wrong rows; join inference and `on <col>` expansion also apply when the left side is the filtered subquery.
- **Output change:** `year()`, `quarter()`, `month()`, `week()`, `day()`, `hour()`, `minute()` and `second()` now truncate to the start of the unit (`DATE_TRUNC` / `TIMESTAMP_TRUNC`), as documented, instead of extracting an integer (`MONTH(x)` / `EXTRACT(MONTH FROM x)`), which merged the same month of different years. Use `month of year x` (and `day of month`, `day of year`, `week of year`, `quarter of year`) for integer extraction; these now parse.
- `week()` honors `week_start` (including `SET week_start`) on every dialect; `week_monday()` / `week_sunday()` pick a start explicitly. Sunday weeks compile at parse time to a portable shifted form (`DATE_TRUNC('WEEK', x + INTERVAL 1 DAY) - INTERVAL 1 DAY`), parenthesized so they stay one operand in arithmetic, so they are correct on every dialect and on plain `sqlglot.transpile` paths, not only `asql.transpile()`. `spine by week(...)` generates its spine with the same start day.
- SQL to ASQL (`write="asql"`) now prints sqlglot extraction nodes as extraction (`month of year x`, `day of month x`, `extract(year from x)`) and truncation nodes as `month(x)` / `week_monday(x)`, so converted queries keep their meaning.
- Settings with constrained values (`week_start`, `count`, ...) are lowercased on `SET` and validated when passed as `ASQL(...)` / `transpile()` keyword arguments; `week_start="tuesday"` raises.
- `day of year` extracts with `DAYOFYEAR` on BigQuery (it was `DOY`).
- **Breaking check:** comparing a truncating unit function with a number (`where year(created_at) = 2024`, `month(x) in (1, 2)`) now raises `ASQLCompilationError` instead of comparing a date with an integer. Use `extract(year from created_at) = 2024` or a date range. Docs examples were updated.

## [0.1.0] - 2025-01-XX

### Added
- Initial experimental release
- FROM-first pipe syntax
- Natural language aggregations (`sum amount`, `# users`)
- Date arithmetic (`7 days ago`, `30 days from now`)
- Date truncation functions (`year()`, `month()`, `week()`)
- Window function helpers (`per ... first by`, `prior()`, `next()`, `running_sum()`)
- Guaranteed groups (automatic gap-filling)
- Column operations (`except`, `rename`, `replace`)
- Sampling (`sample 100`, `sample 10%`, `sample 100 per category`)
- Pivot/Unpivot/Explode operations
- Multi-dialect output via SQLGlot
- VS Code extension with syntax highlighting
- MkDocs documentation site

### Supported Dialects
- PostgreSQL
- MySQL
- SQLite
- BigQuery
- Snowflake
- Redshift
- DuckDB
- Trino
- Spark SQL

[Unreleased]: https://github.com/davefowler/asql/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/davefowler/asql/releases/tag/v0.2.0
[0.1.0]: https://github.com/davefowler/asql/releases/tag/v0.1.0
