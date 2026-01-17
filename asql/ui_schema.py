"""
UI Schema for Visual ASQL Editor

Reads directly from dialect_schema.py for single source of truth.
No more code generation or YAML overrides needed.

All metadata (operations, parameters, widgets, etc.) comes from the
unified dialect schema defined in dialect_schema.py.
"""

from typing import Dict, List
from .dialect_schema import TRANSFORMS, JOIN_TYPES, AGGREGATES


def _transform_to_ui_schema(transform) -> Dict:
    """Convert a Transform dataclass to UI schema dict format."""
    # Convert transform to dict
    schema = {
        "label": transform.label,
        "category": transform.category,
        "description": transform.description,
        "parameters": [],
    }

    # Convert parameters
    for param_name, param in transform.parameters.items():
        param_dict = {
            "name": param.name,
            "type": param.type,
            "required": param.required,
            "label": param.label,
            "widget": param.widget,
            "description": param.description,
        }

        # Add optional fields if present
        if param.placeholder:
            param_dict["placeholder"] = param.placeholder
        if param.help:
            param_dict["help"] = param.help
        if param.operators:
            param_dict["operators"] = param.operators
        if param.options:
            param_dict["options"] = param.options
        if param.min_value is not None:
            param_dict["min"] = param.min_value
        if param.max_value is not None:
            param_dict["max"] = param.max_value
        if param.populate_query:
            param_dict["populate_query"] = param.populate_query
        if param.populate_depends_on:
            param_dict["populate_depends_on"] = param.populate_depends_on

        schema["parameters"].append(param_dict)

    return schema


# Build UI schemas from dialect_schema.TRANSFORMS
OPERATION_UI_SCHEMAS = {}
for attr_name in dir(TRANSFORMS):
    if not attr_name.startswith("_"):
        transform = getattr(TRANSFORMS, attr_name)
        if hasattr(transform, "label"):
            # Use the transform label as the key (e.g., "where", "join")
            op_key = transform.label.replace(" ", "_")
            OPERATION_UI_SCHEMAS[op_key] = _transform_to_ui_schema(transform)


def get_operation_schema(operation_type: str) -> Dict:
    """
    Get UI schema for an operation type.

    Args:
        operation_type: Type of operation (e.g., 'where', 'join')

    Returns:
        Dict with schema metadata, or empty dict if not found
    """
    return OPERATION_UI_SCHEMAS.get(operation_type, {})


def list_all_operations() -> List[Dict]:
    """
    List all available operations with their metadata.

    Returns:
        List of operation metadata dicts
    """
    operations = []
    for op_type, schema in OPERATION_UI_SCHEMAS.items():
        operations.append(
            {
                "type": op_type,
                "label": schema.get("label", op_type.title()),
                "description": schema.get("description", ""),
                "category": schema.get("category", "other"),
            }
        )
    return operations


def get_join_type_options() -> List[Dict]:
    """Get join type options for UI dropdown."""
    options = []
    for attr_name in dir(JOIN_TYPES):
        if not attr_name.startswith("_"):
            join_type = getattr(JOIN_TYPES, attr_name)
            if hasattr(join_type, "label"):
                options.append(
                    {
                        "value": attr_name.lower(),
                        "label": join_type.label,
                        "description": join_type.description,
                    }
                )
    return options


def get_aggregate_options() -> List[Dict]:
    """Get aggregate function options for UI dropdown."""
    options = []
    for attr_name in dir(AGGREGATES):
        if not attr_name.startswith("_"):
            agg = getattr(AGGREGATES, attr_name)
            if hasattr(agg, "label"):
                options.append(
                    {"value": attr_name.lower(), "label": agg.label, "description": agg.description}
                )
    return options
