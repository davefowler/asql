# ASQL Documentation

This directory contains the MkDocs documentation source files for ASQL.

## Structure

- `index.md` - Homepage
- `getting-started.md` - Installation and setup guide
- `quick-start.md` - Quick start tutorial
- `examples.md` - Comprehensive examples with SQL dialect tabs
- `index.md` - Complete language specification (landing page)
- `architecture.md` - System architecture and design
- `status.md` - Implementation status
- `interactive-playground.md` - Playground documentation

## Code Tabs Format

Examples use MkDocs Material's tabbed code blocks to show ASQL compiled to multiple SQL dialects:

````markdown
=== "ASQL"
    ```asql
    from users
    ```

=== "PostgreSQL"
    ```sql
    SELECT * FROM users
    ```

=== "MySQL"
    ```sql
    SELECT * FROM users
    ```

=== "BigQuery"
    ```sql
    SELECT * FROM users
    ```

=== "Snowflake"
    ```sql
    SELECT * FROM users
    ```
````

## Local Development

```bash
# Install dependencies
pip install -r requirements-docs.txt

# Serve locally
mkdocs serve

# Build site
mkdocs build
```

## Adding Examples

When adding new examples:

1. Use the tabbed format shown above
2. Include ASQL tab first, then SQL dialect tabs
3. Supported dialects: PostgreSQL, MySQL, BigQuery, Snowflake, Redshift
4. Generate SQL using: `python scripts/generate_example_sql.py '<asql_query>'`

