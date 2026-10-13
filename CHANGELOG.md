# Changelog

All notable changes to ASQL will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Count inference: `# <table>` counts distinct entities (`from orders ( # users )` → `COUNT(DISTINCT user_id)`), with a schema, resolved from relationships or the `<singular>_id` convention (no inference without a schema)
- Versioning infrastructure with single source of truth in `pyproject.toml`
- CHANGELOG.md for tracking changes
- `fill_forward()` and `fill_backward()` window functions for NULL propagation in time series data
- Semantic graph support: `asql.semantic.load_graph()` reads a dbt-metrics `graph.yaml`; `Schema.from_graph()` feeds its grains and relationships into join inference and fanout protection, and queries can use bare metric names and `relationship.attribute` references

### Changed
- A join with no `on` now raises `ASQLResolutionError` when the schema declares several distinct explicit relationships between the two tables (for example buyer and seller both pointing at users), instead of silently using the first one

### Fixed
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

[Unreleased]: https://github.com/davefowler/asql/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/davefowler/asql/releases/tag/v0.1.0
