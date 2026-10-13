"""
Column Tracking for Visual Editor

This module provides functions to track available columns through
ASQL pipeline steps using SQLGlot's schema awareness.

This enables dynamic column suggestions in dropdowns based on:
1. Schema (table structures)
2. Previous pipeline steps (what columns exist at this point)
"""

from sqlglot import exp
from sqlglot.optimizer import qualify
from sqlglot.schema import MappingSchema

from asql.errors import ASQLError


def get_output_columns_for_step(
    asql_up_to_step: str, schema: MappingSchema | None = None
) -> list[dict[str, str]]:
    """
    Get available output columns after executing ASQL up to a given step.

    Args:
        asql_up_to_step: ASQL query up to (and including) current step
        schema: Optional schema for table/column resolution

    Returns:
        List of dicts with column info: [{"name": "col", "type": "VARCHAR", "table": "users"}, ...]
    """
    import sqlglot
    import sqlglot.errors

    # Parse ASQL to AST
    try:
        ast = sqlglot.parse_one(asql_up_to_step, dialect="asql")
    except (ASQLError, sqlglot.errors.ParseError):
        # If parsing fails (syntax error, etc.), return empty list
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
    expr: exp.Expr, schema: MappingSchema | None = None
) -> dict[str, str] | None:
    """Extract column information from a SELECT expression."""

    # Get output name (handles aliases)
    col_name = expr.output_name
    if not col_name:
        # Complex expressions without aliases may not have an output name
        return None

    # Try to determine type from schema
    col_type = "UNKNOWN"
    table_name = None
    column = expr.this if isinstance(expr, exp.Alias) else expr
    if isinstance(column, exp.Column):
        table_name = column.table
        if schema and table_name:
            # SQLGlot's MappingSchema format is {table: {col: type}}
            table_schema = schema.mapping.get(table_name)
            if isinstance(table_schema, dict):
                col_type = table_schema.get(column.name, "UNKNOWN")

    return {"name": col_name, "type": col_type, "table": table_name or ""}
