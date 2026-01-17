"""
Column Tracking for Visual Editor

This module provides functions to track available columns through
ASQL pipeline steps using SQLGlot's schema awareness.

This enables dynamic column suggestions in dropdowns based on:
1. Schema (table structures)
2. Previous pipeline steps (what columns exist at this point)
"""

from typing import List, Dict, Optional
from sqlglot import exp
from asql.errors import ASQLError
from sqlglot.optimizer import qualify
from sqlglot.schema import MappingSchema


def get_output_columns_for_step(
    asql_up_to_step: str,
    schema: Optional[MappingSchema] = None
) -> List[Dict[str, str]]:
    """
    Get available output columns after executing ASQL up to a given step.

    Args:
        asql_up_to_step: ASQL query up to (and including) current step
        schema: Optional schema for table/column resolution

    Returns:
        List of dicts with column info: [{"name": "col", "type": "VARCHAR", "table": "users"}, ...]
    """
    from asql.compiler.api import compile_to_ast

    # Compile ASQL to SQL AST
    try:
        ast = compile_to_ast(asql_up_to_step)
    except ASQLError:
        # If compilation fails (syntax error, compilation error, etc.), return empty list
        # This is expected when partial/incomplete ASQL is passed during editing
        return []

    # Use SQLGlot's qualify to expand * and resolve columns
    if schema:
        try:
            qualified = qualify.qualify(ast, schema=schema)
        except (KeyError, AttributeError, ValueError):
            # Schema resolution can fail for missing tables/columns - use unqualified AST
            qualified = ast
    else:
        qualified = ast

    # Extract output columns
    columns = []

    if isinstance(qualified, exp.Select):
        for select_expr in qualified.selects:
            col_info = _extract_column_info(select_expr, schema)
            if col_info:
                columns.append(col_info)

    return columns


def _extract_column_info(
    expr: exp.Expression,
    schema: Optional[MappingSchema] = None
) -> Optional[Dict[str, str]]:
    """Extract column information from a SELECT expression."""

    # Get output name (handles aliases)
    col_name = expr.output_name

    # Try to determine type from schema
    col_type = "UNKNOWN"
    table_name = None

    if isinstance(expr, exp.Column):
        table_name = expr.table
        if schema and table_name:
            # Look up type in schema
            # Note: SQLGlot's MappingSchema format is {table: {col: type}}
            table_schema = schema.mapping.get(table_name, {})
            col_type = table_schema.get(expr.name, "UNKNOWN")

    elif isinstance(expr, exp.Alias):
        # For aliased expressions, try to infer from the inner expression
        if isinstance(expr.this, exp.Column):
            inner = expr.this
            table_name = inner.table
            if schema and table_name:
                table_schema = schema.mapping.get(table_name, {})
                col_type = table_schema.get(inner.name, "UNKNOWN")

    return {
        "name": col_name,
        "type": col_type,
        "table": table_name or ""
    }


def get_available_tables(schema: Optional[MappingSchema] = None) -> List[str]:
    """Get list of available tables from schema."""
    if not schema:
        return []

    return list(schema.mapping.keys())


def get_columns_for_table(
    table_name: str,
    schema: Optional[MappingSchema] = None
) -> List[Dict[str, str]]:
    """
    Get all columns for a specific table.

    Args:
        table_name: Name of table
        schema: Schema containing table definitions

    Returns:
        List of column dicts: [{"name": "id", "type": "INT"}, ...]
    """
    if not schema or table_name not in schema.mapping:
        return []

    table_schema = schema.mapping[table_name]
    return [
        {"name": col_name, "type": col_type}
        for col_name, col_type in table_schema.items()
    ]


# Example usage for visual editor:

def populate_select_columns(
    current_step_index: int,
    all_steps: List[Dict],
    schema: Optional[MappingSchema] = None
) -> List[Dict[str, str]]:
    """
    Populate column options for SELECT step based on previous steps.

    Args:
        current_step_index: Index of current SELECT step
        all_steps: List of all pipeline steps up to current
        schema: Optional schema for resolution

    Returns:
        List of available columns with metadata
    """
    # Build ASQL up to this point
    asql_steps = []
    for i, step in enumerate(all_steps[:current_step_index + 1]):
        if step['type'] == 'from':
            asql_steps.append(f"from {step['table']}")
        # Add other step types...

    asql_query = "\n".join(asql_steps)
    return get_output_columns_for_step(asql_query, schema)


def populate_where_columns(
    current_step_index: int,
    all_steps: List[Dict],
    schema: Optional[MappingSchema] = None
) -> List[Dict[str, str]]:
    """
    Populate column options for WHERE expression.
    Same as SELECT - shows all available columns at this point.
    """
    return populate_select_columns(current_step_index, all_steps, schema)


def populate_join_tables(schema: Optional[MappingSchema] = None) -> List[str]:
    """Populate table options for JOIN step."""
    return get_available_tables(schema)


def populate_join_columns(
    join_table: str,
    schema: Optional[MappingSchema] = None
) -> List[Dict[str, str]]:
    """
    Populate column options for JOIN ON condition.
    Shows columns from the table being joined.
    """
    return get_columns_for_table(join_table, schema)
