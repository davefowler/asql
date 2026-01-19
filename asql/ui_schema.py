"""
UI Schema for Visual ASQL Editor

Reads from ui-metadata.json - a static JSON file with all UI metadata.
Validation that ui-metadata.json matches the parser is done in tests/test_schema_sync.py.
"""
# Force reload when ui-metadata.json changes

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
        options.append(
            {
                "value": name,
                "label": agg_data.get("label", name),
                "description": agg_data.get("description", ""),
            }
        )
    return options
