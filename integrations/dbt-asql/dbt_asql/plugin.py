"""
dbt CLI preprocessor for ASQL.

Run `dbt-asql compile` to convert `.asql` model files to `.sql` before running
dbt. Works with any dbt version because dbt's plugin API does not support
custom file extensions (file extensions are hardcoded in
`dbt/parser/read_files.py` and the `dbtPlugin` API is for injecting nodes,
not file types).
"""

from __future__ import annotations

import json
from pathlib import Path

# =============================================================================
# Constants
# =============================================================================

# Valid SQL dialects supported by ASQL/SQLGlot
VALID_DIALECTS = frozenset(
    {
        "postgres",
        "postgresql",
        "mysql",
        "sqlite",
        "bigquery",
        "snowflake",
        "redshift",
        "duckdb",
        "spark",
        "databricks",
        "trino",
        "presto",
        "clickhouse",
        "oracle",
        "mssql",
        "tsql",
    }
)


class AsqlCompilationError(Exception):
    """Raised when ASQL compilation fails for a specific file."""

    def __init__(self, file_path: Path, original_error: Exception) -> None:
        self.file_path = file_path
        self.original_error = original_error
        super().__init__(f"Failed to compile {file_path}: {original_error}")


class InvalidDialectError(ValueError):
    """Raised when an invalid SQL dialect is specified."""

    def __init__(self, dialect: str) -> None:
        self.dialect = dialect
        valid_list = ", ".join(sorted(VALID_DIALECTS))
        super().__init__(f"Invalid dialect '{dialect}'. Valid dialects: {valid_list}")


# =============================================================================
# CLI Preprocessor Approach
# =============================================================================


def get_manifest_models(manifest_path: str = "target/manifest.json") -> set[str]:
    """
    Load model names from dbt manifest.

    Args:
        manifest_path: Path to dbt's manifest.json

    Returns:
        Set of model names (without the model. prefix).
        Returns empty set for missing or malformed manifest.
    """
    manifest_file = Path(manifest_path)
    if not manifest_file.exists():
        return set()

    try:
        with open(manifest_file, encoding="utf-8") as f:
            manifest = json.load(f)
    except json.JSONDecodeError:
        return set()

    # Validate manifest structure
    if not isinstance(manifest, dict):
        return set()

    nodes = manifest.get("nodes")
    if not isinstance(nodes, dict):
        return set()

    models = set()
    for _node_id, node in nodes.items():
        if isinstance(node, dict) and node.get("resource_type") == "model":
            name = node.get("name")
            if isinstance(name, str):
                models.add(name)

    return models


def discover_asql_files(models_dir: str = "models") -> list[Path]:
    """
    Find all .asql files in a dbt project.

    Args:
        models_dir: Path to dbt models directory

    Returns:
        List of paths to .asql files
    """
    models_path = Path(models_dir).resolve()
    if not models_path.exists():
        return []

    return list(models_path.rglob("*.asql"))


def validate_dialect(dialect: str) -> None:
    """
    Validate that the dialect is supported.

    Args:
        dialect: SQL dialect name

    Raises:
        InvalidDialectError: If dialect is not supported
    """
    if dialect.lower() not in VALID_DIALECTS:
        raise InvalidDialectError(dialect)


def compile_project(
    models_dir: str = "models",
    manifest_path: str = "target/manifest.json",
    dialect: str = "postgres",
    verbose: bool = True,
) -> list[tuple[Path, Path]]:
    """
    Compile all .asql files in a dbt project to .sql.

    This is the main entry point for the CLI preprocessor approach.

    Args:
        models_dir: Path to dbt models directory
        manifest_path: Path to dbt manifest (for ref detection)
        dialect: SQL dialect to compile to
        verbose: Print progress messages

    Returns:
        List of (asql_path, sql_path) tuples that were compiled

    Raises:
        InvalidDialectError: If dialect is not supported
        AsqlCompilationError: If compilation fails for a file
    """
    from dbt_asql.compiler import compile_asql_model

    # Validate dialect upfront
    validate_dialect(dialect)

    asql_files = discover_asql_files(models_dir)

    if not asql_files:
        if verbose:
            print(f"No .asql files found in {models_dir}")
        return []

    # Try to load manifest for model detection
    known_models = get_manifest_models(manifest_path)
    if verbose:
        if known_models:
            print(f"Found {len(known_models)} models in manifest")
        else:
            print(f"No manifest found at {manifest_path} (ref detection disabled)")

    compiled = []

    for asql_file in asql_files:
        if verbose:
            print(f"Compiling: {asql_file}")

        try:
            # Read ASQL with explicit encoding
            asql_code = asql_file.read_text(encoding="utf-8")

            # Compile to SQL
            sql = compile_asql_model(
                asql_code,
                known_models=known_models,
                dialect=dialect,
            )

            # Write .sql file alongside .asql with explicit encoding
            sql_file = asql_file.with_suffix(".sql")
            sql_file.write_text(sql, encoding="utf-8")

            if verbose:
                print(f"  → {sql_file}")
            compiled.append((asql_file, sql_file))

        except Exception as e:
            raise AsqlCompilationError(asql_file, e) from e

    return compiled


def clean_project(models_dir: str = "models", verbose: bool = True) -> list[Path]:
    """
    Remove generated .sql files for all .asql files.

    Args:
        models_dir: Path to dbt models directory
        verbose: Print progress messages

    Returns:
        List of paths that were removed
    """
    removed = []

    for asql_file in discover_asql_files(models_dir):
        sql_file = asql_file.with_suffix(".sql")
        if sql_file.exists():
            sql_file.unlink()
            if verbose:
                print(f"Removed: {sql_file}")
            removed.append(sql_file)

    return removed
