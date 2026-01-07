"""
dbt plugin integration for ASQL.

This module provides two approaches for dbt integration:

1. **CLI Preprocessor** (Recommended)
   - Run `dbt-asql compile` to convert .asql → .sql files
   - Works with any dbt version
   - Native .asql files, no wrappers needed

2. **Jinja Extension** (Alternative)  
   - Use {% asql %}...{% endasql %} tags in .sql files
   - Patches dbt's Jinja environment automatically
   - Works like dbt-prql

## Research Findings (2026-01-07)

dbt does NOT support custom file extensions via plugins:
- File extensions are hardcoded in `dbt/parser/read_files.py`
- The `dbtPlugin` API is for injecting nodes, not file types
- dbt-prql uses Jinja tags, not native .prql files

See: https://github.com/dbt-labs/dbt-core/discussions/... (feature request)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2.ext import Extension

if TYPE_CHECKING:
    from jinja2 import nodes


# =============================================================================
# Constants
# =============================================================================

# Valid SQL dialects supported by ASQL/SQLGlot
VALID_DIALECTS = frozenset({
    "postgres", "postgresql",
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
    "mssql", "tsql",
})


class AsqlCompilationError(Exception):
    """Raised when ASQL compilation fails for a specific file."""
    
    def __init__(self, file_path: Path, original_error: Exception) -> None:
        self.file_path = file_path
        self.original_error = original_error
        super().__init__(
            f"Failed to compile {file_path}: {original_error}"
        )


class InvalidDialectError(ValueError):
    """Raised when an invalid SQL dialect is specified."""
    
    def __init__(self, dialect: str) -> None:
        self.dialect = dialect
        valid_list = ", ".join(sorted(VALID_DIALECTS))
        super().__init__(
            f"Invalid dialect '{dialect}'. Valid dialects: {valid_list}"
        )


# =============================================================================
# CLI Preprocessor Approach
# =============================================================================


def get_manifest_models(manifest_path: str = "target/manifest.json") -> set[str]:
    """
    Load model names from dbt manifest.
    
    Args:
        manifest_path: Path to dbt's manifest.json
        
    Returns:
        Set of model names (without the model. prefix)
    """
    manifest_file = Path(manifest_path)
    if not manifest_file.exists():
        return set()
    
    with open(manifest_file, encoding="utf-8") as f:
        manifest = json.load(f)
    
    # Validate manifest structure
    if not isinstance(manifest, dict):
        return set()
    
    nodes = manifest.get("nodes")
    if not isinstance(nodes, dict):
        return set()
    
    models = set()
    for node_id, node in nodes.items():
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


# =============================================================================
# Jinja Extension Approach (Alternative)
# =============================================================================


def _get_jinja_dialect() -> str:
    """
    Get the SQL dialect for Jinja extension.
    
    Reads from DBT_ASQL_DIALECT environment variable, defaults to postgres.
    """
    dialect = os.environ.get("DBT_ASQL_DIALECT", "postgres")
    # Validate but don't raise - just fall back to postgres
    if dialect.lower() not in VALID_DIALECTS:
        return "postgres"
    return dialect


class AsqlExtension(Extension):
    """
    Jinja extension for ASQL in dbt.
    
    Usage in .sql files:
        {% asql %}
        from orders
          where status = 'completed'
          group by region ( sum(amount) as revenue )
        {% endasql %}
    
    This is automatically registered when dbt-asql is installed,
    via the pth file mechanism (like dbt-prql).
    
    Environment variables:
        DBT_ASQL_DIALECT: SQL dialect to compile to (default: postgres)
    """
    
    tags = {"asql"}
    
    def parse(self, parser: "nodes.Parser") -> "nodes.Node":
        """Parse the {% asql %}...{% endasql %} block."""
        from jinja2 import nodes
        from jinja2.nodes import Const
        
        line_number = next(parser.stream).lineno
        asql_body = parser.parse_statements(["name:endasql"], drop_needle=True)
        
        return nodes.CallBlock(
            self.call_method("_compile_asql", [Const("")]),
            [], [], asql_body
        ).set_lineno(line_number)
    
    def _compile_asql(self, args: list, caller: callable) -> str:
        """Compile ASQL to SQL."""
        try:
            from dbt_asql.compiler import compile_asql_model
        except ImportError as e:
            raise ImportError(
                "Failed to import dbt_asql.compiler. "
                "Ensure the asql package is installed: pip install asql"
            ) from e
        
        asql_code = caller()
        dialect = _get_jinja_dialect()
        
        # Compile ASQL to SQL
        # Note: We don't have access to manifest here, so no auto ref detection
        sql = compile_asql_model(asql_code, dialect=dialect)
        
        # Return with comment showing original ASQL
        asql_lines = "\n".join(f"-- {line}" for line in asql_code.strip().splitlines())
        
        return f"""
-- SQL compiled from ASQL. Original:
{asql_lines}

{sql}
"""


def patch_dbt_environment() -> None:
    """
    Patch dbt's Jinja environment to include ASQL extension.
    
    This is called automatically via the pth file when dbt-asql is installed.
    
    Environment variables:
        DBT_ASQL_DISABLE: Set to disable the patch
        DBT_ASQL_LOG_LEVEL: Set to enable debug logging
        DBT_ASQL_DIALECT: SQL dialect for Jinja extension (default: postgres)
    """
    if os.environ.get("DBT_ASQL_DISABLE"):
        return
    
    import functools
    import logging
    
    logger = logging.getLogger(__name__)
    
    log_level = os.environ.get("DBT_ASQL_LOG_LEVEL")
    if log_level:
        logging.basicConfig()
        logger.setLevel(int(log_level))
        logger.info(f"dbt-asql: Log level set to {log_level}")
    
    try:
        from dbt.clients import jinja
    except ImportError:
        logger.debug("dbt not found, skipping Jinja patch")
        return
    
    # Store original function
    if not hasattr(jinja, "_get_environment"):
        jinja._get_environment = jinja.get_environment
    
    def add_asql_extension(func: callable) -> callable:
        """Wrap get_environment to add ASQL extension."""
        if getattr(func, "_asql_patched", False):
            return func
        
        @functools.wraps(func)
        def with_asql_extension(*args, **kwargs):
            env = func(*args, **kwargs)
            env.add_extension(AsqlExtension)
            return env
        
        with_asql_extension._asql_patched = True
        logger.debug(f"Patched {func.__qualname__} with ASQL extension")
        
        return with_asql_extension
    
    jinja.get_environment = add_asql_extension(jinja._get_environment)


# =============================================================================
# Plugin Class (for future dbt plugin API)
# =============================================================================


class Plugin:
    """
    dbt plugin for ASQL support.
    
    Currently dbt's plugin API does not support custom file extensions.
    This class is a placeholder for when that feature is added.
    
    Registration via pyproject.toml:
        [project.entry-points."dbt.plugins"]
        asql = "dbt_asql:Plugin"
    """
    
    def __init__(self) -> None:
        """Initialize the ASQL plugin."""
        self.name = "asql"
        self.version = "0.1.0"
    
    def initialize(self) -> None:
        """Initialize plugin - currently no-op."""
        pass
