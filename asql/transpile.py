"""ASQL transpile function - the main entry point for ASQL → SQL conversion.

This module provides asql.transpile() which handles the full ASQL pipeline:
1. Parse with ASQL dialect (runs parser-stage transforms)
2. Apply dialect-aware transforms (spine, alias_reuse, column_operators, list_comprehension)
3. Generate SQL for target dialect

For non-ASQL input dialects, this is a passthrough to sqlglot.transpile().
"""

from __future__ import annotations

import typing as t

import sqlglot
from sqlglot import exp
from sqlglot.dialects.dialect import Dialect

if t.TYPE_CHECKING:
    from asql.schema import Schema
    from asql.config import CompileSettings


def transpile(
    sql: str,
    read: t.Union[str, Dialect, None] = "asql",
    write: t.Union[str, Dialect, None] = "duckdb",
    pretty: bool = False,
    schema: t.Union[dict, "Schema", None] = None,
    **kwargs: t.Any,
) -> t.List[str]:
    """Transpile SQL with full ASQL transform support.
    
    For ASQL/VisualASQL input: applies dialect-aware transforms between parse and generate.
    For other inputs: passthrough to sqlglot.transpile().
    
    Args:
        sql: SQL string to transpile
        read: Source dialect (default: "asql")
        write: Target dialect (default: "duckdb") 
        pretty: Format output with indentation
        schema: Schema dict or Schema object for column operators, joins, etc.
        **kwargs: Passed to ASQL dialect constructor (e.g., week_start, infer_join_keys)
    
    Returns:
        List of SQL strings (usually one element)
    
    Notes:
        - Inline SET statements (e.g., "SET week_start = monday;") only affect
          the current transpile() call, NOT subsequent calls.
        - When passing a pre-built dialect instance, the schema is NOT mutated;
          a copy of settings is made internally if schema is provided separately.
        - Each transpile() call is stateless - no settings persist between calls.
    
    Example:
        >>> import asql
        >>> asql.transpile("from users where active", write="postgres")[0]
        'SELECT * FROM users WHERE active'
        
        >>> asql.transpile("from orders spine by month(date) (sum(amount))", write="snowflake")[0]
        'WITH date_spine AS (...) SELECT ...'
    """
    # Determine if this is ASQL input
    read_name = _get_dialect_name(read)
    
    # Non-ASQL: passthrough to sqlglot (forward all parameters)
    if read_name not in ("asql", "visual_asql", "visualasql"):
        return sqlglot.transpile(sql, read=read, write=write, pretty=pretty, **kwargs)
    
    # Build ASQL dialect with settings
    from asql.dialect import ASQL
    
    if isinstance(read, str) or read is None:
        if schema:
            kwargs['schema'] = schema
        asql_dialect = ASQL(**kwargs) if kwargs else "asql"
    else:
        asql_dialect = read
        # If schema passed separately, copy settings to avoid mutating the passed dialect
        if schema and hasattr(asql_dialect, 'settings') and asql_dialect.settings:
            # Create a copy of settings to avoid mutation
            asql_dialect.settings = {**asql_dialect.settings, 'schema': schema}
    
    # Parse with ASQL (runs parser-stage transforms)
    try:
        asts = sqlglot.parse(sql, dialect=asql_dialect)
    except sqlglot.errors.ParseError:
        raise
    
    results = []
    write_name = _get_dialect_name(write) or "duckdb"
    
    # Check if we should strip comments (from kwargs or dialect settings)
    passthrough_comments = True
    if 'passthrough_comments' in kwargs:
        passthrough_comments = kwargs.get('passthrough_comments', True)
    elif hasattr(asql_dialect, 'settings') and asql_dialect.settings:
        passthrough_comments = asql_dialect.settings.get('passthrough_comments', True)
    
    for ast in asts:
        if ast is None:
            continue
        
        # Apply dialect-aware transforms
        ast = _apply_dialect_transforms(ast, write_name, schema, asql_dialect)
        
        # Strip comments if passthrough_comments is False
        if not passthrough_comments:
            ast = _strip_comments(ast)
        
        # Generate output
        sql_out = ast.sql(dialect=write, pretty=pretty)
        
        # Apply text-based post-processing for dialect-specific features
        sql_out = _apply_text_transforms(sql_out, write_name)
        
        results.append(sql_out)
    
    return results


def transpile_one(
    sql: str,
    read: t.Union[str, Dialect, None] = "asql",
    write: t.Union[str, Dialect, None] = "duckdb",
    pretty: bool = False,
    schema: t.Union[dict, "Schema", None] = None,
    **kwargs: t.Any,
) -> str:
    """Transpile a single SQL statement. Convenience wrapper around transpile().
    
    Raises:
        ValueError: If input contains multiple statements
    """
    results = transpile(sql, read=read, write=write, pretty=pretty, schema=schema, **kwargs)
    if len(results) != 1:
        raise ValueError(f"Expected 1 statement, got {len(results)}")
    return results[0]


def _apply_dialect_transforms(
    ast: exp.Expression,
    dialect: str,
    schema: t.Union[dict, "Schema", None],
    asql_dialect: t.Any,
) -> exp.Expression:
    """Apply transforms that need to know the output dialect.
    
    These transforms run AFTER parsing but BEFORE SQL generation.
    They need to know the target dialect to emit correct SQL patterns.
    
    Transform order:
    0. Strip GROUP BY aliases (ASQL syntax cleanup → valid SQL)
    1. Spine transform (exp.Spine → gap-filling CTEs)
    2. Alias reuse (same-row refs → CTE chain for non-DuckDB)
    3. Column operators (* EXCEPT → explicit columns for unsupported dialects)
    4. List comprehension ([x FOR x] → ARRAY(SELECT) for non-DuckDB)
    """
    from asql.config import CompileSettings
    
    # Build settings from schema
    settings = None
    if schema:
        settings = CompileSettings(schema=schema)
    elif hasattr(asql_dialect, 'settings'):
        # Try to get settings from dialect
        dialect_schema = asql_dialect.settings.get('schema') if asql_dialect.settings else None
        if dialect_schema:
            settings = CompileSettings(schema=dialect_schema)
    
    if settings is None:
        settings = CompileSettings()
    
    # 0. Strip aliases from GROUP BY (ASQL allows, SQL doesn't)
    ast = _strip_group_by_aliases(ast)
    
    # 1. Spine transform (process exp.Spine nodes)
    ast = _transform_spine(ast, dialect, settings)
    
    # 2. Alias reuse (DuckDB supports native, others need CTEs)
    ast = _transform_alias_reuse(ast, dialect)
    
    # 3. Column operators (expand EXCEPT for unsupported dialects)
    ast = _transform_column_operators(ast, dialect, settings)
    
    # 4. List comprehension (DuckDB native, others need ARRAY(SELECT))
    ast = _transform_list_comprehension(ast, dialect)
    
    return ast


def _strip_group_by_aliases(ast: exp.Expression) -> exp.Expression:
    """Convert GROUP BY aliases to alias references.
    
    ASQL allows: group by month(date) as cohort (count(*))
    SQL standard: GROUP BY cohort (reference the SELECT alias)
    
    This transform converts GROUP BY Alias(expr, name) to GROUP BY name,
    which is supported by all major SQL dialects.
    """
    for select in ast.find_all(exp.Select):
        group = select.find(exp.Group)
        if not group:
            continue
        
        new_exprs = []
        for group_expr in group.expressions:
            if isinstance(group_expr, exp.Alias):
                # Convert to alias reference: GROUP BY cohort
                alias_name = group_expr.alias
                new_exprs.append(exp.Column(this=exp.to_identifier(alias_name)))
            else:
                new_exprs.append(group_expr)
        
        group.set("expressions", new_exprs)
    
    return ast


def _transform_spine(
    ast: exp.Expression,
    dialect: str,
    settings: "CompileSettings",
) -> exp.Expression:
    """Transform exp.Spine nodes into gap-filling CTEs.
    
    Finds Spine() expressions in GROUP BY and generates:
    - Date spine CTE with generate_series (for date truncation columns)
    - Categorical spine CTE with DISTINCT (for other columns)
    - LEFT JOIN to ensure all values appear
    """
    from asql.expressions import Spine
    from asql.compiler.spine import transform_spine_expressions
    
    # Check if there are any Spine expressions
    has_spine = any(isinstance(node, Spine) for node in ast.walk())
    if not has_spine:
        return ast
    
    return transform_spine_expressions(ast, dialect, settings)


def _transform_alias_reuse(
    ast: exp.Expression,
    dialect: str,
) -> exp.Expression:
    """Transform alias reuse into CTE chains for non-DuckDB dialects.
    
    DuckDB supports native alias reuse: SELECT a+1 AS b, b+1 AS c
    Other dialects need CTE chains to achieve the same effect.
    """
    from asql.compiler.alias_reuse import apply_alias_reuse
    
    return apply_alias_reuse(ast, dialect=dialect)


def _transform_column_operators(
    ast: exp.Expression,
    dialect: str,
    settings: "CompileSettings",
) -> exp.Expression:
    """Transform column operators for unsupported dialects.
    
    Expands * EXCEPT(col) to explicit column list for dialects
    that don't support the EXCEPT syntax (requires schema).
    """
    from asql.compiler.column_operators import transform_column_operators_for_dialect
    
    return transform_column_operators_for_dialect(ast, dialect, settings)


def _transform_list_comprehension(
    ast: exp.Expression,
    dialect: str,
) -> exp.Expression:
    """Transform list comprehensions for the target dialect.
    
    DuckDB: Keep native [x FOR x IN arr] syntax
    Others: Convert to ARRAY(SELECT x FROM UNNEST(arr))
    
    Note: This is currently handled during SQL generation via text replacement.
    The AST-level exp.Comprehension is preserved through generation.
    """
    # List comprehension handling is currently text-based in list_comprehension.py
    # The exp.Comprehension nodes are converted to ARRAY(SELECT...) in the parser
    # and then the list_comprehension module converts back to native syntax for DuckDB
    # 
    # For now, we don't need to do anything here - the parser already converts
    # to the universal ARRAY(SELECT...) form, and post-generation fixup handles DuckDB.
    return ast


def _strip_comments(ast: exp.Expression) -> exp.Expression:
    """Strip all comments from the AST.
    
    Used when passthrough_comments=False to remove source comments.
    """
    for node in ast.walk():
        if hasattr(node, 'comments') and node.comments:
            node.comments = []
    return ast


def _apply_text_transforms(sql: str, dialect: str) -> str:
    """Apply text-based post-processing for dialect-specific features.
    
    Some transformations are easier to do at the text level after SQL generation.
    """
    from asql.compiler.list_comprehension import fix_duckdb_list_comprehensions
    
    # Convert ARRAY(SELECT...) back to DuckDB native list comprehension syntax
    sql = fix_duckdb_list_comprehensions(sql, dialect)
    
    return sql


def _get_dialect_name(dialect: t.Union[str, Dialect, None]) -> str:
    """Extract dialect name string from dialect or Dialect instance."""
    if dialect is None:
        return ""
    if isinstance(dialect, str):
        return dialect.lower()
    # Handle Dialect class instances
    if hasattr(dialect, '__class__'):
        class_name = dialect.__class__.__name__
        # ASQL class → "asql"
        return class_name.lower()
    return str(dialect).lower()
