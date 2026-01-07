"""
dbt plugin integration for ASQL.

This module provides the dbt plugin hooks to:
1. Detect .asql files
2. Compile them before dbt processes them
3. Resolve model references from the manifest

TODO: This is a placeholder. The actual dbt plugin API may differ.
      See: https://docs.getdbt.com/docs/build/about-plugins
"""

from typing import Any


class Plugin:
    """
    dbt plugin for ASQL support.
    
    This is registered via pyproject.toml entry point:
    [project.entry-points."dbt.plugins"]
    asql = "dbt_asql:Plugin"
    """
    
    def __init__(self) -> None:
        """Initialize the ASQL plugin."""
        self.name = "asql"
        self.version = "0.1.0"
    
    # TODO: Implement actual dbt plugin hooks
    # The dbt plugin API is still evolving. Key hooks we need:
    #
    # 1. File extension registration
    #    - Tell dbt that .asql files are valid models
    #
    # 2. Pre-compilation hook
    #    - Called before dbt parses a model
    #    - We compile ASQL → SQL here
    #
    # 3. Manifest access
    #    - Need to read manifest to know which tables are models
    #    - Used for automatic ref() resolution
    #
    # Alternative approach: Custom model parser
    # dbt allows custom parsers for different file types.
    # We could register an AsqlParser that handles .asql files.


def get_manifest_models(manifest_path: str = "target/manifest.json") -> set[str]:
    """
    Load model names from dbt manifest.
    
    Args:
        manifest_path: Path to dbt's manifest.json
        
    Returns:
        Set of model names (without the model. prefix)
    """
    import json
    from pathlib import Path
    
    manifest_file = Path(manifest_path)
    if not manifest_file.exists():
        return set()
    
    with open(manifest_file) as f:
        manifest = json.load(f)
    
    models = set()
    for node_id, node in manifest.get("nodes", {}).items():
        if node.get("resource_type") == "model":
            models.add(node["name"])
    
    return models


# Alternative implementation approach: File preprocessing
#
# If dbt doesn't support plugins for custom file types,
# we can use a preprocessing approach:
#
# 1. User runs: dbt-asql compile
# 2. We scan models/ for .asql files
# 3. Compile each to .sql in a build/ directory
# 4. User runs: dbt run --models-path build/
#
# Or we could use a dbt wrapper:
#
# 1. User runs: dbt-asql run (instead of dbt run)
# 2. We preprocess .asql → .sql in place
# 3. Run dbt
# 4. Optionally restore .asql files

def preprocess_project(models_dir: str = "models") -> None:
    """
    Preprocess all .asql files in a dbt project.
    
    This is a fallback approach if dbt plugins don't support
    custom file extensions.
    
    Args:
        models_dir: Path to dbt models directory
    """
    from pathlib import Path
    from dbt_asql.compiler import compile_asql_model
    
    models_path = Path(models_dir)
    manifest_models = get_manifest_models()
    
    for asql_file in models_path.rglob("*.asql"):
        print(f"Compiling: {asql_file}")
        
        # Read ASQL
        asql_code = asql_file.read_text()
        
        # Compile to SQL
        sql = compile_asql_model(
            asql_code,
            known_models=manifest_models,
            dialect="postgres",  # TODO: detect from dbt profile
        )
        
        # Write .sql file alongside .asql
        sql_file = asql_file.with_suffix(".sql")
        sql_file.write_text(sql)
        
        print(f"  → {sql_file}")

