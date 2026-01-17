"""
UI Schema for Visual ASQL Editor

Provides lightweight metadata layer on top of SQLGlot's arg_types to enable
automatic UI generation. Each operation has a schema defining its parameters
and which widgets to use for rendering.

Architecture:
1. Base schemas are auto-generated from ASQL's TRANSFORM_PARSERS
2. Manual UI overrides add labels, help text, and widget specifics
3. Final schemas merge both (90% auto, 10% manual)
"""

import yaml
from pathlib import Path
from .ui_schema_generator import generate_base_schema_from_asql

# Load manual UI overrides from YAML file
# This centralizes all UI-specific metadata (labels, help text, dropdown options, etc.)
# in a single editable file without touching code
_OVERRIDES_PATH = Path(__file__).parent / "ui_overrides.yaml"

try:
    with open(_OVERRIDES_PATH, 'r') as f:
        _yaml_data = yaml.safe_load(f)
        _MANUAL_UI_OVERRIDES = _yaml_data.get("operations", {}) if _yaml_data else {}
except FileNotFoundError:
    # Fallback to empty dict if YAML file doesn't exist
    _MANUAL_UI_OVERRIDES = {}
except yaml.YAMLError as e:
    # Log error but don't crash - use empty overrides
    print(f"Warning: Failed to parse ui_overrides.yaml: {e}")
    _MANUAL_UI_OVERRIDES = {}

# Auto-generate base schemas and merge with manual overrides
_BASE_SCHEMAS = generate_base_schema_from_asql()

# Merge: Start with auto-generated, override with manual UI details
OPERATION_UI_SCHEMAS = {}
for op_name in _BASE_SCHEMAS.keys():
    base = _BASE_SCHEMAS[op_name]
    override = _MANUAL_UI_OVERRIDES.get(op_name, {})

    # Merge parameters
    if "parameters" in override:
        merged_params = []
        override_params_by_name = {p["name"]: p for p in override["parameters"]}
        base_param_names = {p["name"] for p in base.get("parameters", [])}

        for base_param in base.get("parameters", []):
            param_name = base_param["name"]
            if param_name in override_params_by_name:
                # Merge base + override for this parameter
                merged_param = {**base_param, **override_params_by_name[param_name]}
                merged_params.append(merged_param)
            else:
                merged_params.append(base_param)

        # Keep override-only params too (not in base)
        for override_param in override["parameters"]:
            if override_param["name"] not in base_param_names:
                merged_params.append(override_param)

        base["parameters"] = merged_params
        # Update override to use merged params so final merge doesn't overwrite
        override = {**override, "parameters": merged_params}

    # Merge top-level fields
    OPERATION_UI_SCHEMAS[op_name] = {**base, **override}



def get_operation_schema(operation_type: str) -> dict:
    """
    Get UI schema for an operation type.

    Args:
        operation_type: Type of operation (e.g., 'where', 'join')

    Returns:
        Dict with schema metadata, or empty dict if not found
    """
    return OPERATION_UI_SCHEMAS.get(operation_type, {})


def list_all_operations() -> list:
    """
    List all available operations with their metadata.

    Returns:
        List of operation metadata dicts
    """
    operations = []
    for op_type, schema in OPERATION_UI_SCHEMAS.items():
        operations.append({
            "type": op_type,
            "label": schema.get("label", op_type.title()),
            "icon": schema.get("icon", "📦"),
            "description": schema.get("description", ""),
            "category": schema.get("category", "other")
        })
    return operations
