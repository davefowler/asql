# Changelog

All notable changes to ASQL will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Versioning infrastructure with single source of truth in `pyproject.toml`
- CHANGELOG.md for tracking changes
- `fill_forward()` and `fill_backward()` window functions for NULL propagation in time series data

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
