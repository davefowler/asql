"""AST transform to convert PIVOT to CASE/WHEN for non-native dialects.

SQLGlot can parse PIVOT expressions but cannot transpile them to CASE/WHEN
for dialects that don't support native PIVOT (PostgreSQL, MySQL, SQLite).
This module provides an AST transformation that runs before SQL generation.

For native PIVOT dialects (DuckDB, Snowflake, BigQuery): pass through unchanged.
For non-native dialects: convert to CASE/WHEN expressions.
"""

from __future__ import annotations

import re
from typing import List, Optional, TYPE_CHECKING

from sqlglot import exp

if TYPE_CHECKING:
    from asql.config import CompileSettings


# Dialects that support native PIVOT syntax
NATIVE_PIVOT_DIALECTS = frozenset({"duckdb", "snowflake", "bigquery"})

# Dialects that support dynamic PIVOT (without explicit values)
# BigQuery does NOT support dynamic PIVOT - it requires explicit values
DYNAMIC_PIVOT_DIALECTS = frozenset({"duckdb", "snowflake"})

# Native PIVOT dialects that require explicit values
STATIC_ONLY_PIVOT_DIALECTS = frozenset({"bigquery"})


def _get_pivot_values_from_schema(
    pivot_col: str,
    table_name: Optional[str],
    settings: Optional["CompileSettings"],
) -> Optional[List[str]]:
    """Get distinct values for a pivot column from the schema.
    
    Args:
        pivot_col: Column name to pivot on
        table_name: Source table name
        settings: Compile settings with schema
        
    Returns:
        List of distinct values if found in schema, None otherwise
    """
    if not settings or not settings.schema or not table_name:
        return None
    
    schema = settings.schema
    table = schema.get_table(table_name.lower())
    if not table:
        return None
    
    return table.get_distinct_values(pivot_col)


def _transform_pivot_to_case_when(
    stmt: exp.Select,
    pivot: exp.Pivot,
    table: exp.Table,
) -> exp.Select:
    """Transform a PIVOT expression to CASE/WHEN expressions.
    
    Args:
        stmt: The SELECT statement containing the pivot
        pivot: The Pivot expression to transform
        table: The table expression containing the pivot
        
    Returns:
        Modified SELECT statement with CASE/WHEN expressions
    """
    # Get pivot components
    agg_exprs = pivot.expressions
    if not agg_exprs:
        return stmt  # No aggregates, can't transform
    
    fields = pivot.args.get('fields', [])
    if not fields:
        return stmt  # No FOR clause
    
    # The first field should be an IN expression
    in_expr = fields[0] if fields and isinstance(fields[0], exp.In) else None
    if not in_expr:
        return stmt  # No IN clause = dynamic pivot without values
    
    pivot_col = in_expr.this
    pivot_values = in_expr.expressions
    
    if not pivot_values:
        return stmt  # No values to pivot
    
    # Build CASE/WHEN expressions for each pivot value
    new_expressions: List[exp.Expression] = []
    
    for val in pivot_values:
        # Get the value as string for column alias
        if isinstance(val, exp.Literal):
            val_str = val.this
        else:
            val_str = str(val)
        
        # Sanitize the value to make it a valid column name
        col_name = re.sub(r'[^a-zA-Z0-9_]', '_', val_str)
        
        for agg_expr in agg_exprs:
            # Handle aliased aggregates (e.g., SUM(amount) AS sum_amount from auto_aliasing)
            if isinstance(agg_expr, exp.Alias):
                agg = agg_expr.this  # The actual aggregate function
            else:
                agg = agg_expr
            
            # Get the inner column from the aggregate function
            inner_col = agg.this if hasattr(agg, 'this') else agg
            
            # Build: AGG(CASE WHEN pivot_col = 'value' THEN inner_col END) AS col_name
            case = exp.Case(
                ifs=[exp.If(
                    this=exp.EQ(this=pivot_col.copy(), expression=val.copy()),
                    true=inner_col.copy()
                )]
            )
            
            # Wrap in the same aggregate function type (Sum, Avg, etc.)
            wrapped_agg = agg.__class__(this=case)
            
            # Add alias using the pivot value
            aliased = exp.Alias(this=wrapped_agg, alias=exp.to_identifier(col_name))
            new_expressions.append(aliased)
    
    # Remove pivot from table
    table.set('pivots', [])
    
    # Replace SELECT expressions with our CASE/WHEN expressions
    # If SELECT *, replace entirely; otherwise append
    current_exprs = stmt.expressions
    if len(current_exprs) == 1 and isinstance(current_exprs[0], exp.Star):
        stmt.set('expressions', new_expressions)
    else:
        # Filter out Star and append pivot columns
        non_star_exprs = [e for e in current_exprs if not isinstance(e, exp.Star)]
        stmt.set('expressions', non_star_exprs + new_expressions)
    
    return stmt


def _transform_unpivot_to_union_all(
    stmt: exp.Select,
    pivot: exp.Pivot,
    table: exp.Table,
) -> exp.Select:
    """Transform an UNPIVOT expression to UNION ALL.
    
    UNPIVOT: SELECT * FROM table UNPIVOT(value FOR name IN (col1, col2, col3))
    becomes:
    SELECT *, 'col1' AS name, col1 AS value FROM table
    UNION ALL
    SELECT *, 'col2' AS name, col2 AS value FROM table
    UNION ALL
    SELECT *, 'col3' AS name, col3 AS value FROM table
    
    Args:
        stmt: The SELECT statement containing the unpivot
        pivot: The Pivot expression with unpivot=True
        table: The table expression containing the unpivot
        
    Returns:
        Modified SELECT statement with UNION ALL
    """
    # Get unpivot components
    # expressions = [value_col], fields = [In(name_col, [col1, col2, ...])]
    value_col = pivot.expressions[0] if pivot.expressions else None
    if not value_col:
        return stmt
    
    fields = pivot.args.get('fields', [])
    in_expr = fields[0] if fields and isinstance(fields[0], exp.In) else None
    if not in_expr:
        return stmt
    
    name_col = in_expr.this  # The name column identifier
    columns = in_expr.expressions  # The columns to unpivot
    
    if not columns:
        return stmt
    
    # Get the name column as string
    name_col_name = name_col.name if hasattr(name_col, 'name') else str(name_col)
    value_col_name = value_col.name if hasattr(value_col, 'name') else str(value_col)
    
    # Remove pivot from table
    table.set('pivots', [])
    
    # Build UNION ALL queries
    union_queries = []
    
    for col in columns:
        # Get column name for the literal value
        col_name = col.name if hasattr(col, 'name') else str(col)
        
        # Build: SELECT *, '<col_name>' AS name_col, <col> AS value_col FROM table
        name_literal = exp.Alias(
            this=exp.Literal.string(col_name),
            alias=exp.to_identifier(name_col_name)
        )
        value_alias = exp.Alias(
            this=col.copy() if hasattr(col, 'copy') else exp.Column(this=exp.to_identifier(col_name)),
            alias=exp.to_identifier(value_col_name)
        )
        
        # Clone the base SELECT
        select = exp.Select(
            expressions=[exp.Star(), name_literal, value_alias],
            from_=exp.From(this=table.copy()),
        )
        union_queries.append(select)
    
    # Combine with UNION ALL
    if len(union_queries) == 1:
        result = union_queries[0]
    else:
        result = union_queries[0]
        for query in union_queries[1:]:
            result = exp.Union(this=result, expression=query, distinct=False)
    
    # Wrap in a subquery with alias
    subquery = exp.Subquery(this=result, alias=exp.TableAlias(this=exp.to_identifier("__unpivot__")))
    
    # Return a SELECT * FROM (union) AS __unpivot__
    return exp.Select(
        expressions=[exp.Star()],
        from_=exp.From(this=subquery),
    )


def transform_pivot_for_dialect(
    stmt: exp.Expression,
    dialect: Optional[str] = None,
    settings: Optional["CompileSettings"] = None,
) -> exp.Expression:
    """Transform PIVOT/UNPIVOT expressions for the target dialect.
    
    For native PIVOT dialects (DuckDB, Snowflake, BigQuery): returns unchanged.
    For non-native dialects: converts PIVOT to CASE/WHEN, UNPIVOT to UNION ALL.
    
    Args:
        stmt: SQLGlot expression (typically a SELECT statement)
        dialect: Target SQL dialect name
        settings: Compile settings (for schema-based dynamic pivot)
        
    Returns:
        Modified statement with PIVOT/UNPIVOT transformed if necessary
    """
    if not isinstance(stmt, exp.Select):
        return stmt
    
    dialect_lower = (dialect or "").lower()
    
    # For native PIVOT dialects: pass through unchanged.
    #
    # Special case: some dialects require explicit values for PIVOT (e.g., BigQuery),
    # so we may need to populate IN(...) from schema or raise a helpful error.
    if dialect_lower in NATIVE_PIVOT_DIALECTS:
        native = True
    else:
        native = False
    
    # Find FROM clause
    from_clause = stmt.args.get('from_')
    if not from_clause:
        return stmt
    
    # Find table with pivot
    table = from_clause.find(exp.Table)
    if not table:
        return stmt
    
    pivots = table.args.get('pivots', [])
    if not pivots:
        return stmt
    
    pivot = pivots[0]  # Take first pivot
    
    # Check if this is UNPIVOT
    if pivot.args.get('unpivot'):
        # For native UNPIVOT dialects (DuckDB, Snowflake), pass through
        if dialect_lower in DYNAMIC_PIVOT_DIALECTS:
            return stmt
        # For other dialects, convert to UNION ALL
        return _transform_unpivot_to_union_all(stmt, pivot, table)
    
    # It's a PIVOT - check if we have explicit values (IN clause)
    fields = pivot.args.get('fields', [])
    in_expr = fields[0] if fields and isinstance(fields[0], exp.In) else None
    
    # Get the pivot column - either from IN expression or direct field
    if in_expr:
        pivot_col_node = in_expr.this
        has_explicit_values = bool(in_expr.expressions)
    else:
        # Dynamic pivot: fields = [Column] (no IN expression)
        pivot_col_node = fields[0] if fields else None
        has_explicit_values = False
    
    if not has_explicit_values:
        # Dynamic pivot without values
        # For dialects with native dynamic pivot support (DuckDB, Snowflake), pass through
        if dialect_lower in DYNAMIC_PIVOT_DIALECTS:
            return stmt
        
        # For other dialects, try to get values from schema
        pivot_col_name = pivot_col_node.name if hasattr(pivot_col_node, 'name') else None
        table_name = table.name
        
        schema_values = _get_pivot_values_from_schema(pivot_col_name, table_name, settings)
        
        if schema_values:
            # Build IN expression with schema values
            value_literals = [exp.Literal.string(v) for v in schema_values]
            new_in_expr = exp.In(
                this=pivot_col_node.copy() if pivot_col_node else exp.Column(this=exp.to_identifier("unknown")),
                expressions=value_literals
            )
            pivot.set('fields', [new_in_expr])
            has_explicit_values = True  # We now have values from schema
        else:
            # Can't do dynamic pivot without schema
            dialect_name = dialect_lower if dialect_lower else "this dialect"
            raise ValueError(
                f"Dynamic pivot (without explicit values) is not supported for {dialect_name}.\n\n"
                f"Options:\n"
                f"  1. Add 'values' clause: pivot ... values ('val1', 'val2', ...)\n"
                f"  2. Provide schema with distinct_values for the pivot column\n"
                f"  3. Use a dialect with native dynamic pivot: DuckDB, Snowflake"
            )

    # If the target dialect supports native PIVOT, keep it as PIVOT.
    # (At this point, any "static-only" dialect has explicit values.)
    if native:
        return stmt
    
    # Transform PIVOT to CASE/WHEN for non-native dialects
    return _transform_pivot_to_case_when(stmt, pivot, table)

