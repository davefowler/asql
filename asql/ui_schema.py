"""
UI Schema for Visual ASQL Editor

Reads from ui-metadata.json - a static JSON file with all UI metadata.
Validation that ui-metadata.json matches the parser is done in tests/test_schema_sync.py.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

_SCHEMA_PATH = Path(__file__).parent / "ui-metadata.json"
_schema_cache: Optional[Dict] = None


def get_schema() -> Dict:
    """Get the full ASQL UI schema."""
    global _schema_cache
    if _schema_cache is None:
        with open(_SCHEMA_PATH) as f:
            _schema_cache = json.load(f)
    return _schema_cache


def get_operation_schema(operation_type: str) -> Dict:
    """
    Get UI schema for an operation type.

    Args:
        operation_type: Type of operation (e.g., 'where', 'join')

    Returns:
        Dict with schema metadata, or empty dict if not found
    """
    return get_schema().get("transforms", {}).get(operation_type, {})


def list_all_operations() -> List[Dict]:
    """
    List all available operations with their metadata.

    Returns:
        List of operation metadata dicts
    """
    operations = []
    transforms = get_schema().get("transforms", {})
    for op_type, schema in transforms.items():
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
    joins = get_schema().get("joins", {})
    for name, join_data in joins.items():
        options.append(
            {
                "value": name,
                "label": join_data.get("label", name),
                "description": join_data.get("description", ""),
            }
        )
    return options


def get_aggregate_options() -> List[Dict]:
    """Get aggregate function options for UI dropdown."""
    options = []
    aggregates = get_schema().get("aggregates", {})
    for name, agg_data in aggregates.items():
        option = {
            "value": name,
            "label": agg_data.get("label", name),
            "description": agg_data.get("description", ""),
        }
        # Include additional metadata
        if "aliases" in agg_data:
            option["aliases"] = agg_data["aliases"]
        if "types" in agg_data:
            option["types"] = agg_data["types"]
        if agg_data.get("natural_syntax"):
            option["natural_syntax"] = True
        options.append(option)
    return options


def get_function_options(category: Optional[str] = None) -> List[Dict]:
    """Get function options for UI dropdown.
    
    Args:
        category: Optional category filter (e.g., 'date', 'window', 'string')
    
    Returns:
        List of function metadata dicts
    """
    options = []
    functions = get_schema().get("functions", {})
    
    for cat_name, funcs in functions.items():
        # Skip if category filter doesn't match
        if category and cat_name != category:
            continue
            
        for name, func_data in funcs.items():
            option = {
                "value": name,
                "label": func_data.get("label", name),
                "description": func_data.get("description", ""),
                "category": cat_name,
                "args": func_data.get("args", []),
                "returns": func_data.get("returns", "any"),
            }
            # Include additional metadata
            if "aliases" in func_data:
                option["aliases"] = func_data["aliases"]
            if func_data.get("asql_only"):
                option["asql_only"] = True
            if func_data.get("natural_syntax"):
                option["natural_syntax"] = True
            options.append(option)
    
    return options


def get_function_categories() -> List[Dict]:
    """Get function categories with their functions.
    
    Returns:
        List of category dicts with functions
    """
    categories = []
    functions = get_schema().get("functions", {})
    
    for cat_name, funcs in functions.items():
        category = {
            "name": cat_name,
            "label": cat_name.replace("_", " ").title(),
            "functions": []
        }
        for name, func_data in funcs.items():
            category["functions"].append({
                "value": name,
                "label": func_data.get("label", name),
            })
        categories.append(category)
    
    return categories


def get_operators() -> Dict:
    """Get all operator definitions.
    
    Returns:
        Dict with operator categories (comparison, string, null, list, logical)
    """
    return get_schema().get("operators", {})
