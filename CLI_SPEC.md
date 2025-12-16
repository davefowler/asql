# ASQL CLI Specification (psql-like)

**Version:** 0.1  
**Status:** Draft  
**Last Updated:** 2025-12-16

---

## 1. Overview

This document specifies a command-line interface (CLI) for ASQL that is **very similar to PostgreSQL’s `psql`**—especially for **connection invocation and shell ergonomics**.

The CLI is intended to:

- Start an interactive shell (REPL) connected to a database.
- Execute ad-hoc queries (SQL and ASQL) and display results.
- Initialize per-project configuration and schema metadata.
- Detect and link to existing project metadata (dbt, SQLMesh, or local “data” sources) when present.

The CLI name is **`asql`** (preferred). If `asql` conflicts in a target environment, `asqlsh` is an acceptable alias.

---

## 2. Goals / Non-goals

### 2.1 Goals

- **psql-like connection calls**: users should be able to replace `psql <conn>` with `asql <conn>` in most workflows.
- **Interactive shell** with:
  - Multi-line statements terminated by `;` (and optionally `\g`).
  - Readline editing, history, and tab completion hooks.
  - Familiar “backslash commands” (`\q`, `\?`, `\d`, `\dt`, `\i`, etc.).
- **Execute SQL** directly.
- **Execute ASQL** as first-class input (compile to SQL, then execute).
- **Project initialization**: create config + schema files, or link to existing metadata providers.

### 2.2 Non-goals (v0.1)

- Full `psql` parity (every `\` command, every formatting knob).
- Implementing a new database driver.
- Supporting every database under the sun (initially target Postgres-compatible URIs and optionally DuckDB).

---

## 3. Command Summary

The CLI provides:

- **Interactive shell** (default):
  - `asql [CONNECTION] [OPTIONS]`

- **Single-command execution** (like `psql -c`):
  - `asql [CONNECTION] -c "<query>"`

- **Execute file** (like `psql -f`):
  - `asql [CONNECTION] -f path/to/file.sql`

- **Initialization**:
  - `asql init [OPTIONS]`

- **Schema operations**:
  - `asql schema pull [OPTIONS]`
  - `asql schema show [OPTIONS]`

- **Compile only**:
  - `asql compile [OPTIONS] <asql-or-sql>`

---

## 4. Connection Handling (psql-like)

### 4.1 Accepted Connection Inputs

`asql` MUST accept:

- A **PostgreSQL/libpq-style URI**:
  - `postgres://user:pass@host:5432/dbname?sslmode=require`
  - `postgresql://...`

- A **keyword/value connection string** (libpq style), best-effort:
  - `host=localhost port=5432 user=me dbname=app sslmode=require`

- **No explicit connection string**:
  - Use environment variables / config defaults to resolve a connection.

### 4.2 psql-compatible Flags (Minimum Set)

To be “drop-in-ish”, `asql` MUST support the most common `psql` flags:

- `-h, --host <host>`
- `-p, --port <port>`
- `-U, --username <user>`
- `-d, --dbname <db>`
- `-c, --command <query>`
- `-f, --file <path>`
- `-v, --set name=value` (variables for shell/templating)
- `-X` (do not read startup file)
- `-q, --quiet`
- `-t, --tuples-only`
- `-A, --no-align`
- `-F, --field-separator <sep>`
- `-P, --pset <name=value>` (subset)

Notes:

- Flags may be implemented as a **compatibility layer** mapping to internal settings.
- The CLI MAY add ASQL-specific flags, but they MUST NOT break the psql-like default behaviors.

### 4.3 Environment Variables (Minimum Set)

`asql` SHOULD support these `psql`-style env vars where applicable:

- `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`
- `PGSSLMODE`, `PGSSLROOTCERT`, `PGSSLCERT`, `PGSSLKEY`
- `PGCONNECT_TIMEOUT`

`asql` MAY additionally support:

- `ASQL_CONFIG` (path override)
- `ASQL_PROJECT_DIR` (project root override)

### 4.4 Connection Resolution Precedence

When determining the final connection parameters, the precedence MUST be:

1. Explicit CLI flags (`-h`, `-U`, etc.)
2. Explicit connection string argument (`asql <conn>`)
3. Project config (`.asql/config.toml`)
4. User config (e.g., `~/.config/asql/config.toml`)
5. Environment variables (`PG*`)
6. Driver defaults

---

## 5. Interactive Shell

### 5.1 Shell Entry

Running `asql [CONNECTION]` with no `-c`/`-f` MUST start an interactive shell.

The shell MUST:

- Show a prompt that includes connection context (db/user/host), e.g.:
  - `asql (db=mydb user=me host=localhost)>`
- Support multi-line editing.
- Treat a statement as complete when terminated by `;`.

### 5.2 Query Language Modes

The shell supports two input modes:

- **SQL mode**: send input as-is to the connected database.
- **ASQL mode**: compile input via `asql.compile(...)` to SQL, then execute.

Default mode SHOULD be **ASQL** (aligned with the project), but the CLI MUST ensure that typical SQL works without surprises.

Recommended behavior:

- If in ASQL mode, allow `sql:` prefix to force SQL passthrough for a single statement.
- If in SQL mode, allow `asql:` prefix to compile-and-run for a single statement.

Examples:

- `asql> from users where status = "active";` (ASQL)
- `asql> sql: select * from users where status = 'active';` (forced SQL)

### 5.3 Backslash Meta-Commands (Minimum Set)

The following MUST be implemented:

- `\q` / `\quit`: exit
- `\?` / `\help`: help summary
- `\conninfo`: show current connection info
- `\c [CONN]` / `\connect [CONN]`: change connection
- `\i <file>`: execute commands from file
- `\ir <file>`: execute file relative to current script directory
- `\o [file]`: redirect query output to file (or reset)
- `\timing [on|off]`: toggle timing
- `\x [on|off|auto]`: expanded display

Schema introspection commands SHOULD be provided (best-effort across backends):

- `\dt [pattern]`: list tables
- `\dv [pattern]`: list views
- `\dn [pattern]`: list schemas
- `\d <name>`: describe object

If a backend cannot support a command, `asql` MUST print a clear “not supported” message and not crash.

### 5.4 Output Formatting

`asql` MUST provide:

- Aligned table output (default)
- CSV output (`--csv` or `\pset format csv` equivalent)
- JSON output (`--json`)

At minimum, implement:

- `-A` (unaligned)
- `-t` (tuples only)
- `-F` (field separator)

### 5.5 Error Handling

- SQL/ASQL compilation errors MUST:
  - Print the error with context.
  - Leave the shell running.
  - Set a non-zero status only for non-interactive modes (`-c`, `-f`).

### 5.6 History

- History file location:
  - `~/.asql_history` (default)
  - override via `ASQL_HISTORY` (optional)

---

## 6. Project Initialization (`asql init`)

### 6.1 Purpose

`asql init` prepares a directory for a consistent “query project” experience by creating:

- A project config file
- A schema/metadata file OR a link to an existing metadata provider

### 6.2 Project Root Detection

Default project root is the current working directory.

If inside a git repository, `asql init` SHOULD treat the git root as project root unless `--project-dir` is provided.

### 6.3 Files Created

`asql init` MUST create a `.asql/` directory in the project root containing:

- `.asql/config.toml`
- `.asql/schema.yml` (or `.asql/schema.json`) **unless** the project links to an existing metadata provider.

The CLI SHOULD NOT overwrite existing files unless `--force` is provided.

### 6.4 Config Format (`.asql/config.toml`)

Minimum keys:

- `version`: config schema version (e.g., `1`)
- `default_dialect`: SQL dialect for compilation (e.g., `postgres`)
- `connection`: optional default connection string (may be empty)
- `schema_provider`: one of:
  - `"inline"` (local schema file)
  - `"dbt"`
  - `"sqlmesh"`
  - `"database"` (introspection)
  - `"duckdb"` (local file)
- `schema_path`: path to `.asql/schema.yml` when `inline`

Optional but recommended:

- `query_paths`: list of directories for `.asql` / `.sql` files
- `variables`: map of default session variables

### 6.5 Schema File Format (`.asql/schema.yml`)

The schema file is intended for:

- Table and column discovery
- Relationship metadata (FKs)
- Default time fields

It SHOULD be **dbt-compatible** where possible (reusing `schema.yml` conventions), with ASQL-specific extensions allowed.

Minimum structure (illustrative):

- `models:` list with:
  - `name`
  - `columns:` list with `name` (and optional `description`)
  - optional `default_time`
  - optional relationships (dbt-style `tests: relationships:`)

---

## 7. Autodetection & Linking (dbt / SQLMesh / data)

When running `asql init`, the CLI MUST attempt provider autodetection.

### 7.1 dbt Detection

If any of the following exist in the project root (or near it), treat it as a dbt project:

- `dbt_project.yml`
- `profiles.yml` (optional; often in `~/.dbt/`)

Behavior:

- Set `schema_provider = "dbt"`.
- Record `dbt_project_dir` in config.
- Prefer reading existing `models/**/schema.yml` files for relationships and documentation.
- If no dbt schema files exist, `asql` MAY generate an initial `.asql/schema.yml` as a starting point.

### 7.2 SQLMesh Detection

If any of the following exist, treat it as a SQLMesh project:

- `sqlmesh.yaml` or `sqlmesh.yml`
- `models/` directory with SQLMesh-style model files

Behavior:

- Set `schema_provider = "sqlmesh"`.
- Record `sqlmesh_project_dir` in config.
- Prefer linking to SQLMesh’s model graph/metadata rather than duplicating schema.

### 7.3 Local “Data” Detection (DuckDB-first)

If any of the following exist, treat it as a “local data” project:

- `*.duckdb` file in project root
- `duckdb.db` in project root

Behavior:

- Set `schema_provider = "duckdb"`.
- Record `duckdb_path`.
- Allow connecting without a Postgres URI.

### 7.4 Fallback: Database Introspection

If no dbt/sqlmesh/local-data signals are found, `asql` SHOULD:

- Create `.asql/schema.yml`.
- Optionally support `asql schema pull` to populate it from the live database.

---

## 8. Schema Commands

### 8.1 `asql schema pull`

Populates or updates the project schema metadata.

- Inputs:
  - Connection (from flags/config/env)
  - Target schemas (optional)
- Output:
  - Updates `.asql/schema.yml` (or writes to a cache path)

### 8.2 `asql schema show`

Prints the effective schema source:

- If provider is `dbt`/`sqlmesh`: show linked paths and detected models.
- If provider is `inline`: show `.asql/schema.yml` summary.

---

## 9. Non-Interactive Modes

### 9.1 `-c/--command`

Executes a single statement and exits.

- Exit code `0` on success.
- Exit code `1` on failure.

### 9.2 `-f/--file`

Executes statements from a file and exits.

- Should support both `.sql` and `.asql`.
- File extension MAY influence default language mode.

---

## 10. Exit Codes

- `0`: success
- `1`: runtime error (connection, query execution, compilation)
- `2`: CLI usage error (bad flags)

---

## 11. Security Considerations

- The CLI MUST avoid printing passwords in `\conninfo` or error messages.
- Config files SHOULD support referencing environment variables rather than storing secrets.
- If a connection string contains credentials, `asql init` SHOULD NOT write it to disk unless `--write-connection` is explicitly provided.

---

## 12. Compatibility Targets (psql)

### 12.1 “Drop-in” Definition

For v0.1, “drop-in for connection calls” means:

- `asql <postgres_uri>` works.
- `asql -h/-p/-U/-d` works.
- `asql -c` and `asql -f` work.
- Interactive basics and a small set of `\` commands work.

### 12.2 Parity Roadmap (Future)

Potential additions:

- `\copy`-like import/export
- `\watch`
- `\set`/`\unset` parity
- `.pgpass` support
- `PGSERVICE` support

---

## 13. Examples

### 13.1 Connect and start a shell

```bash
asql postgresql://me@localhost:5432/mydb
```

### 13.2 Connect using psql-like flags

```bash
asql -h localhost -p 5432 -U me -d mydb
```

### 13.3 Run a single query

```bash
asql postgresql://me@localhost/mydb -c "from users where status = 'active';"
```

### 13.4 Initialize a project

```bash
asql init
```

### 13.5 Pull schema from database

```bash
asql postgresql://me@localhost/mydb schema pull
```

---

## 14. Implementation Notes (Non-normative)

- The shell can be implemented using `readline` or `prompt_toolkit`.
- The database layer can start with Postgres via a standard Python driver (e.g., `psycopg`/`psycopg2`) and expand later.
- SQL compilation uses the existing `asql.compile()` API.
- Schema providers (dbt/sqlmesh) should be adapters behind a common interface.
