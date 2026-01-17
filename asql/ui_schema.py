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

from .ui_schema_generator import generate_base_schema_from_asql

# Manual UI overrides - only specify what can't be auto-generated
# (labels, help text, dropdown options, etc.)
_MANUAL_UI_OVERRIDES = {
    "where": {
        "parameters": [
            {
                "name": "condition",
                "label": "condition",
                "operators": ["=", "!=", "<", ">", "<=", ">=", "contains", "starts with", "ends with", "in"]
            }
        ]
    },

    "join": {
        "label": "join",
        "icon": "🔗",
        "description": "Join with another table",
        "category": "join",
        "parameters": [
            {
                "name": "join_type",
                "label": "join type",
                "widget": "dropdown",
                "required": True,
                "default": "inner",
                "options": [
                    {"value": "inner", "label": "inner (&)"},
                    {"value": "left", "label": "left (&?)"},
                    {"value": "right", "label": "right (?&)"},
                    {"value": "full", "label": "full (?&?)"},
                    {"value": "cross", "label": "cross (*)"}
                ]
            },
            {
                "name": "table",
                "label": "table",
                "widget": "text",
                "required": True,
                "placeholder": "table_name"
            },
            {
                "name": "condition",
                "label": "on",
                "widget": "expression",
                "required": False,
                "help": "Leave empty to infer from schema",
                "operators": ["=", "!="]
            }
        ]
    },

    "select": {
        "label": "select",
        "icon": "📋",
        "description": "Choose which columns to return",
        "category": "select",
        "parameters": [
            {
                "name": "columns",
                "label": "columns",
                "widget": "list",
                "required": True,
                "item_type": "text",
                "placeholder": "column_name",
                "help": "List of columns to select"
            }
        ]
    },

    "group_by": {
        "parameters": [
            {
                "name": "dimensions",
                "label": "group by",
                "placeholder": "column_name",
                "help": "Columns to group by"
            },
            {
                "name": "aggregates",
                "label": "aggregations",
                "functions": ["count", "sum", "avg", "min", "max", "count_distinct"],
                "help": "Aggregate functions to compute"
            }
        ]
    },

    "order_by": {
        "parameters": [
            {
                "name": "expressions",
                "label": "order by",
                "help": "Columns to sort by"
            }
        ]
    },

    "limit": {
        "parameters": [
            {
                "name": "count",
                "label": "count",
                "min": 1
            }
        ]
    }
}

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

        for base_param in base.get("parameters", []):
            param_name = base_param["name"]
            if param_name in override_params_by_name:
                # Merge base + override for this parameter
                merged_param = {**base_param, **override_params_by_name[param_name]}
                merged_params.append(merged_param)
            else:
                merged_params.append(base_param)

        base["parameters"] = merged_params

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
