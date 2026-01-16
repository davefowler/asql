"""
UI Schema for Visual ASQL Editor

Provides lightweight metadata layer on top of SQLGlot's arg_types to enable
automatic UI generation. Each operation has a schema defining its parameters
and which widgets to use for rendering.
"""

# Operation schemas - maps operation type to UI configuration
OPERATION_UI_SCHEMAS = {
    "where": {
        "label": "Filter",
        "icon": "🔍",
        "description": "Filter rows by condition",
        "category": "filter",
        "parameters": [
            {
                "name": "condition",
                "label": "Condition",
                "widget": "expression",
                "required": True,
                "operators": ["=", "!=", "<", ">", "<=", ">=", "contains", "starts with", "ends with", "in"]
            }
        ]
    },

    "join": {
        "label": "Join",
        "icon": "🔗",
        "description": "Join with another table",
        "category": "join",
        "parameters": [
            {
                "name": "join_type",
                "label": "Join Type",
                "widget": "dropdown",
                "required": True,
                "default": "inner",
                "options": [
                    {"value": "inner", "label": "Inner Join (&)"},
                    {"value": "left", "label": "Left Join (&?)"},
                    {"value": "right", "label": "Right Join (?&)"},
                    {"value": "full", "label": "Full Outer Join (?&?)"},
                    {"value": "cross", "label": "Cross Join (*)"}
                ]
            },
            {
                "name": "table",
                "label": "Table",
                "widget": "text",
                "required": True,
                "placeholder": "table_name"
            },
            {
                "name": "condition",
                "label": "Join Condition",
                "widget": "expression",
                "required": False,
                "help": "Leave empty to infer from schema",
                "operators": ["=", "!="]
            }
        ]
    },

    "select": {
        "label": "Select Columns",
        "icon": "📋",
        "description": "Choose which columns to return",
        "category": "select",
        "parameters": [
            {
                "name": "columns",
                "label": "Columns",
                "widget": "list",
                "required": True,
                "item_type": "text",
                "placeholder": "column_name",
                "help": "List of columns to select"
            }
        ]
    },

    "group_by": {
        "label": "Group & Aggregate",
        "icon": "📊",
        "description": "Group rows and compute aggregations",
        "category": "aggregate",
        "parameters": [
            {
                "name": "dimensions",
                "label": "Group By",
                "widget": "list",
                "required": True,
                "item_type": "text",
                "placeholder": "column_name",
                "help": "Columns to group by"
            },
            {
                "name": "aggregates",
                "label": "Aggregations",
                "widget": "aggregate_list",
                "required": False,
                "functions": ["count", "sum", "avg", "min", "max", "count_distinct"],
                "help": "Aggregate functions to compute"
            }
        ]
    },

    "order_by": {
        "label": "Sort",
        "icon": "⬆️",
        "description": "Sort results",
        "category": "sort",
        "parameters": [
            {
                "name": "expressions",
                "label": "Sort By",
                "widget": "order_list",
                "required": True,
                "help": "Columns to sort by"
            }
        ]
    },

    "limit": {
        "label": "Limit",
        "icon": "🔢",
        "description": "Limit number of rows",
        "category": "limit",
        "parameters": [
            {
                "name": "count",
                "label": "Row Limit",
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
