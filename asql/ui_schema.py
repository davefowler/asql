"""
UI Schema for Visual ASQL Editor

Provides lightweight metadata layer on top of SQLGlot's arg_types to enable
automatic UI generation. Each operation has a schema defining its parameters
and which widgets to use for rendering.
"""

# Operation schemas - maps operation type to UI configuration
# Uses exact ASQL terminology (not "friendly" renamed labels)
OPERATION_UI_SCHEMAS = {
    "where": {
        "label": "where",
        "icon": "🔍",
        "description": "Filter rows by condition",
        "category": "filter",
        "parameters": [
            {
                "name": "condition",
                "label": "condition",
                "widget": "expression",
                "required": True,
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
        "label": "group by",
        "icon": "📊",
        "description": "Group rows and compute aggregations",
        "category": "aggregate",
        "parameters": [
            {
                "name": "dimensions",
                "label": "group by",
                "widget": "list",
                "required": True,
                "item_type": "text",
                "placeholder": "column_name",
                "help": "Columns to group by"
            },
            {
                "name": "aggregates",
                "label": "aggregations",
                "widget": "aggregate_list",
                "required": False,
                "functions": ["count", "sum", "avg", "min", "max", "count_distinct"],
                "help": "Aggregate functions to compute"
            }
        ]
    },

    "order_by": {
        "label": "order by",
        "icon": "⬆️",
        "description": "Sort results",
        "category": "sort",
        "parameters": [
            {
                "name": "expressions",
                "label": "order by",
                "widget": "order_list",
                "required": True,
                "help": "Columns to sort by"
            }
        ]
    },

    "limit": {
        "label": "limit",
        "icon": "🔢",
        "description": "Limit number of rows",
        "category": "limit",
        "parameters": [
            {
                "name": "count",
                "label": "count",
                "widget": "number",
                "required": True,
                "default": 10,
                "min": 1
            }
        ]
    }
}


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
