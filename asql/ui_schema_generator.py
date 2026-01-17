"""
Auto-generate UI schemas from ASQL/SQLGlot metadata

This module introspects the ASQL dialect and SQLGlot to automatically
generate UI schemas, reducing manual schema maintenance.
"""

from typing import Dict, Any, List


def generate_base_schema_from_asql() -> Dict[str, Any]:
    """
    Auto-generate operation schemas from ASQL's TRANSFORM_PARSERS.

    This creates a base schema that can be merged with manual UI overrides.
    """
    from asql.dialect import ASQLParser

    schemas = {}

    for operation_name in ASQLParser.TRANSFORM_PARSERS.keys():
        # Generate base schema
        schema = {
            "label": operation_name.lower(),
            "icon": _guess_icon(operation_name),
            "description": f"{operation_name} operation",
            "category": _guess_category(operation_name),
            "parameters": _generate_parameters(operation_name),
        }

        schemas[operation_name.lower().replace(" ", "_")] = schema

    return schemas


def _guess_icon(operation_name: str) -> str:
    """Guess an icon based on operation name"""
    icon_map = {
        "WHERE": "🔍",
        "FILTER": "🔍",
        "IF": "🔍",
        "JOIN": "🔗",
        "LEFT": "🔗",
        "RIGHT": "🔗",
        "FULL": "🔗",
        "CROSS": "🔗",
        "SELECT": "📋",
        "PROJECT": "📋",
        "GROUP BY": "📊",
        "ORDER BY": "⬆️",
        "LIMIT": "🔢",
        "STASH": "💾",
        "COHORT": "👥",
        "PIVOT": "🔄",
        "UNPIVOT": "🔄",
        "EXPLODE": "💥",
        "EXTEND": "➕",
        "EXCEPT": "➖",
        "RENAME": "✏️",
        "REPLACE": "🔄",
    }
    return icon_map.get(operation_name, "📦")


def _guess_category(operation_name: str) -> str:
    """Guess category based on operation name"""
    if operation_name in ("WHERE", "FILTER", "IF", "HAVING"):
        return "filter"
    elif "JOIN" in operation_name or operation_name in ("LEFT", "RIGHT", "FULL", "CROSS"):
        return "join"
    elif operation_name in ("SELECT", "PROJECT", "EXTEND", "EXCEPT", "RENAME", "REPLACE"):
        return "select"
    elif operation_name == "GROUP BY":
        return "aggregate"
    elif operation_name == "ORDER BY":
        return "sort"
    elif operation_name == "LIMIT":
        return "limit"
    else:
        return "advanced"


def _generate_parameters(operation_name: str) -> List[Dict[str, Any]]:
    """
    Generate parameter schemas by introspecting SQLGlot and using heuristics.

    This is a simplified version - real implementation would be more sophisticated.
    """
    # Map operations to their common parameters
    param_patterns = {
        "WHERE": [{"name": "condition", "widget": "expression", "required": True}],
        "FILTER": [{"name": "condition", "widget": "expression", "required": True}],
        "IF": [{"name": "condition", "widget": "expression", "required": True}],
        "JOIN": [
            {"name": "join_type", "widget": "dropdown", "required": True, "default": "inner"},
            {"name": "table", "widget": "text", "required": True},
            {"name": "condition", "widget": "expression", "required": False},
        ],
        "SELECT": [{"name": "columns", "widget": "list", "required": True}],
        "PROJECT": [{"name": "columns", "widget": "list", "required": True}],
        "GROUP BY": [
            {"name": "dimensions", "widget": "list", "required": True},
            {"name": "aggregates", "widget": "aggregate_list", "required": False},
        ],
        "ORDER BY": [{"name": "expressions", "widget": "order_list", "required": True}],
        "LIMIT": [{"name": "count", "widget": "number", "required": True, "default": 10}],
        "EXTEND": [{"name": "columns", "widget": "list", "required": True}],
        "STASH": [{"name": "name", "widget": "text", "required": True, "placeholder": "cte_name"}],
    }

    return param_patterns.get(operation_name, [])


def generate_function_schemas() -> Dict[str, Any]:
    """
    Auto-generate function schemas from ASQL_FUNCTION_REGISTRY.
    """
    from asql.functions import ASQL_FUNCTION_REGISTRY

    schemas = {}

    for func_name in ASQL_FUNCTION_REGISTRY.keys():
        schema = {
            "name": func_name.lower(),
            "category": _guess_function_category(func_name),
            "signature": f"{func_name.lower()}(...)",
            "description": f"{func_name} function",
        }
        schemas[func_name.lower()] = schema

    return schemas


def _guess_function_category(func_name: str) -> str:
    """Guess function category from name"""
    if any(x in func_name for x in ["DAY", "WEEK", "MONTH", "YEAR", "DATE", "TIME"]):
        return "date"
    elif any(x in func_name for x in ["RUNNING", "ROLLING", "LAG", "LEAD", "RANK", "ROW"]):
        return "window"
    elif any(x in func_name for x in ["SUM", "AVG", "COUNT", "MIN", "MAX"]):
        return "aggregate"
    elif any(x in func_name for x in ["UPPER", "LOWER", "TRIM", "CONCAT", "SUBSTRING"]):
        return "string"
    else:
        return "other"


def merge_with_overrides(base_schema: Dict, overrides: Dict) -> Dict:
    """
    Merge auto-generated base schema with manual UI overrides.

    This allows us to auto-generate 90% and manually specify UI details.
    """
    merged = base_schema.copy()

    for key, value in overrides.items():
        if key in merged and isinstance(value, dict) and isinstance(merged[key], dict):
            # Deep merge for nested dicts
            merged[key] = {**merged[key], **value}
        else:
            # Direct override
            merged[key] = value

    return merged


# Example: Generate all operations and show what can be auto-discovered
if __name__ == "__main__":
    print("Auto-generated operation schemas:")
    print("=" * 60)

    schemas = generate_base_schema_from_asql()

    for op_name, schema in sorted(schemas.items()):
        print(f"\n{op_name.upper()}")
        print(f"  Label: {schema['label']}")
        print(f"  Icon: {schema['icon']}")
        print(f"  Category: {schema['category']}")
        print(f"  Parameters: {len(schema['parameters'])}")
        for param in schema["parameters"]:
            required = "required" if param.get("required") else "optional"
            print(f"    - {param['name']} ({param['widget']}) [{required}]")

    print("\n" + "=" * 60)
    print(f"Total operations: {len(schemas)}")
    print("\nNote: This is auto-generated! Can be merged with manual UI overrides.")
