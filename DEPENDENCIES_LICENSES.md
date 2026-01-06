# ASQL Dependencies and Licenses

**Generated for acquisition diligence**

This document lists all third-party dependencies used by ASQL, their licenses, and their purpose in the codebase.

## Core Runtime Dependencies

| Dependency | License | Version | Purpose |
|------------|---------|---------|---------|
| **sqlglot** | MIT | ≥28.0.0 | **Core SQL parsing and transpilation engine**. Used to parse ASQL queries, convert them to SQL AST, and generate SQL for multiple dialects (PostgreSQL, BigQuery, Snowflake, MySQL, etc.). This is the primary dependency that enables ASQL's multi-dialect SQL generation. |
| **jinja2** | BSD License | ≥3.0.0 | **Template rendering for auto-aliasing**. Used to render column alias templates (e.g., `{func}_{col}` → `sum_amount`) with support for filters (lower, upper, camel, snake). Also used for stripping Jinja templates from SQL queries in the playground. |

## Development Dependencies

| Dependency | License | Version | Purpose |
|------------|---------|---------|---------|
| **pytest** | MIT | ≥7.0.0 | **Test framework**. Primary testing framework for all ASQL functionality. |
| **pytest-cov** | MIT | ≥4.0.0 | **Test coverage reporting**. Generates code coverage reports during test execution. |
| **black** | MIT | ≥23.0.0 | **Code formatter**. Formats Python code according to PEP 8 style guidelines. |
| **mypy** | MIT | ≥1.0.0 | **Static type checker**. Performs static type analysis on Python code. |
| **ruff** | MIT | ≥0.1.0 | **Linter**. Fast Python linter for catching code quality issues. |
| **pre-commit** | MIT | ≥3.0.0 | **Git hooks framework**. Runs code quality checks before commits. |

## Testing Infrastructure Dependencies

| Dependency | License | Version | Purpose |
|------------|---------|---------|---------|
| **duckdb** | MIT | ≥0.9.0 | **In-memory database for execution testing**. Used to execute generated SQL queries and validate that ASQL compiles to correct, executable SQL. Primary database engine for test suite. |
| **psycopg2-binary** | LGPL-2.1 | ≥2.9.0 | **PostgreSQL adapter for testing**. Used to execute SQL against PostgreSQL database for dialect-specific testing and validation. |

## Playground Dependencies

| Dependency | License | Version | Purpose |
|------------|---------|---------|---------|
| **fastapi** | MIT | ≥0.109.0 | **Web framework for playground**. Provides REST API endpoints for the interactive ASQL playground web application. |
| **uvicorn** | BSD License | ≥0.27.0 | **ASGI server**. Runs the FastAPI playground application. |

## Documentation Dependencies

| Dependency | License | Version | Purpose |
|------------|---------|---------|---------|
| **mkdocs** | BSD License | ≥1.5.0 | **Documentation generator**. Generates static documentation site from Markdown files. |
| **mkdocs-material** | MIT | ≥9.0.0 | **Material Design theme for MkDocs**. Provides the UI theme and styling for the documentation site. |
| **pymdown-extensions** | MIT | ≥10.0.0 | **Markdown extensions**. Adds additional Markdown features (tabs, code highlighting, etc.) to documentation. |
| **mkdocs-minify-plugin** | MIT | ≥0.7.0 | **Minification plugin**. Minifies HTML/CSS/JS in generated documentation. |
| **mkdocs-macros-plugin** | MIT | ≥1.0.0 | **Macro plugin**. Enables Python macros in Markdown documentation. |

## Additional Runtime Dependencies

| Dependency | License | Version | Purpose |
|------------|---------|---------|---------|
| **inflect** | MIT | ≥7.0.0 | **Pluralization/singularization**. Used in schema system for intelligent table name matching (e.g., "user" ↔ "users", "person" ↔ "people") when inferring foreign key relationships and join conditions. |

## Build System Dependencies

| Dependency | License | Version | Purpose |
|------------|---------|---------|---------|
| **setuptools** | MIT | ≥61.0 | **Python packaging**. Build system for creating Python packages. |
| **wheel** | MIT | - | **Python wheel format**. Creates wheel distributions for the package. |

## License Summary

- **MIT License**: sqlglot, fastapi, pytest, pytest-cov, duckdb, black, mypy, ruff, pre-commit, mkdocs-material, pymdown-extensions, mkdocs-minify-plugin, mkdocs-macros-plugin, inflect, setuptools, wheel
- **BSD License**: jinja2 (BSD License), uvicorn (BSD-3-Clause), mkdocs (BSD-2-Clause)
- **LGPL-2.1**: psycopg2-binary (PostgreSQL adapter - binary distribution acceptable for commercial use)

## Notes

1. **sqlglot** is the most critical dependency - it's the core engine that enables ASQL to parse queries and generate SQL for multiple database dialects.

2. **psycopg2-binary** uses LGPL-2.1 license. This is a copyleft license that requires any modifications to the library itself to be open-sourced, but does not affect the license of code that uses it. The binary distribution is typically acceptable for commercial use.

3. All other dependencies use permissive licenses (MIT, BSD) that are compatible with commercial/proprietary use.

4. Development and documentation dependencies are not required for runtime operation of ASQL - they are only needed for development, testing, and documentation generation.

