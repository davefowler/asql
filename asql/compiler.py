"""ASQL compiler - transforms ASQL to SQL.

This module implements the ASQL compilation pipeline:
1. Pre-parse: Transform ASQL structural syntax to SQL-like syntax
2. Parse: Use SQLGlot with ASQL dialect to parse the SQL-like syntax
3. Generate: Output SQL in the target dialect

The pre-parser handles ASQL-specific structural transformations that fundamentally
differ from SQL (FROM-first, pipeline operators, aggregate blocks, etc.).

The ASQL dialect handles expression-level ASQL syntax that fits within SQLGlot's
extension model (custom tokens, function parsers, etc.).

Settings can be configured via:
- asql.config.yaml file
- Inline SET statements in the query
"""

from typing import Optional, List, Tuple
import sqlglot
from sqlglot import exp
from sqlglot.dialects import Dialect
import re

from asql.errors import ASQLCompilationError, ASQLSyntaxError
from asql.preparser import preparse_asql, ASQLPreParser
from asql.dialect import register_asql_dialect
from asql.config import CompileSettings, KNOWN_COMPILE_SETTINGS

# Ensure ASQL dialect is registered
register_asql_dialect()


def extract_inline_settings(
    statements: List[exp.Expression]
) -> Tuple[CompileSettings, Optional[str], List[exp.Expression]]:
    """
    Extract SET statements from parsed statements and return settings.
    
    SET statements at the beginning of a query can configure compilation behavior.
    
    Example:
        SET auto_spine = false;
        SET dialect = 'postgres';
        SELECT * FROM orders
    
    Args:
        statements: List of parsed SQLGlot expressions
        
    Returns:
        Tuple of (settings, dialect_override, remaining_statements)
        - settings: CompileSettings with values from SET statements
        - dialect_override: dialect if SET dialect = 'xxx' was found
        - remaining_statements: statements with SET removed
    """
    settings = CompileSettings()
    dialect_override: Optional[str] = None
    queries: List[exp.Expression] = []
    
    for stmt in statements:
        if isinstance(stmt, exp.Set):
            # Extract key/value pairs from SET statement
            for item in stmt.expressions:
                if hasattr(item, 'this') and isinstance(item.this, exp.EQ):
                    eq = item.this
                    key = eq.this.sql().lower().strip('"\'`')
                    value_expr = eq.expression
                    
                    # Get the value as Python type
                    if isinstance(value_expr, exp.Boolean):
                        value = value_expr.this
                    elif isinstance(value_expr, exp.Literal):
                        value = value_expr.this.strip('"\'')
                        # Try to parse as boolean
                        if value.lower() == 'true':
                            value = True
                        elif value.lower() == 'false':
                            value = False
                    elif isinstance(value_expr, exp.Var):
                        value = value_expr.this
                    else:
                        value = value_expr.sql().strip('"\'')
                    
                    # Apply to settings or dialect
                    if key == 'dialect':
                        dialect_override = str(value).lower()
                    elif key == 'auto_spine':
                        settings.auto_spine = bool(value)
                    elif key == 'week_start':
                        if value in ('monday', 'sunday'):
                            settings.week_start = value
                    elif key == 'relative_date_type':
                        if value in ('timestamp', 'date'):
                            settings.relative_date_type = value
                    # Unknown settings are silently ignored for forward compatibility
        else:
            queries.append(stmt)
    
    return settings, dialect_override, queries


def _extract_dialect_from_comment(asql_query: str) -> Optional[str]:
    """
    Extract dialect from comment directive in ASQL query.
    
    Looks for patterns like:
    - -- dialect: snowflake
    - -- Dialect: snowflake
    - # dialect: snowflake
    
    Can appear at the beginning, middle, or end of the query.
    
    Args:
        asql_query: ASQL query string
        
    Returns:
        Dialect name if found, None otherwise
    """
    # Check for -- dialect: or # dialect: patterns
    patterns = [
        r'--\s*dialect\s*:\s*(\w+)',  # -- dialect: snowflake
        r'#\s*dialect\s*:\s*(\w+)',    # # dialect: snowflake
    ]
    
    for pattern in patterns:
        match = re.search(pattern, asql_query, re.IGNORECASE)
        if match:
            return match.group(1).lower()
    
    return None


def compile(
    asql_query: str,
    dialect: Optional[str] = None,
    pretty: bool = False,
    settings: Optional[CompileSettings] = None,
) -> str:
    """
    Compile ASQL query to SQL.
    
    This is the main compilation function that implements the three-stage pipeline:
    1. Pre-parse: Transform ASQL to SQL-like syntax
    2. Parse: Use SQLGlot to parse the SQL-like syntax
    3. Extract inline SET statements for settings
    4. Generate: Output SQL in the target dialect
    
    Args:
        asql_query: ASQL query string (can contain multiple queries separated by semicolons)
        dialect: Target SQL dialect (e.g., 'postgres', 'mysql', 'bigquery', 'snowflake')
                 If None, will try to extract from SET dialect or -- dialect: comment
        pretty: Whether to format SQL output
        settings: Compilation settings. If None, uses defaults.
                  Inline SET statements override these settings.
    
    Returns:
        SQL query string
    
    Raises:
        ASQLSyntaxError: If ASQL syntax is invalid
        ASQLCompilationError: If compilation fails
    
    Example:
        >>> compile("from users where status = 'active' limit 10", dialect="postgres")
        "SELECT * FROM users WHERE status = 'active' LIMIT 10"
        
        >>> compile("from sales group by region (sum(amount) as revenue)")
        "SELECT region, SUM(amount) AS revenue FROM sales GROUP BY region"
        
        >>> compile("SET auto_spine = true; from orders group by month(created_at) (...)")
        # Will include gap-filling CTEs for the date column
    """
    try:
        if not asql_query.strip():
            raise ASQLSyntaxError("Empty ASQL query")
        
        # Start with provided settings or defaults
        base_settings = settings or CompileSettings()
        
        # Extract dialect from comment if not provided
        if not dialect:
            dialect = _extract_dialect_from_comment(asql_query)
        
        # Pre-parse the entire query first (handles CTEs, FROM-first, etc.)
        preparsed = preparse_asql(asql_query)
        
        # Parse with SQLGlot to get statement list
        try:
            statements = sqlglot.parse(preparsed, dialect=dialect)
        except sqlglot.errors.ParseError as e:
            raise ASQLSyntaxError(
                f"Failed to parse ASQL query.\n"
                f"Original: {asql_query}\n"
                f"Pre-parsed: {preparsed}\n"
                f"Error: {e}"
            ) from e
        
        # Extract inline SET statements
        inline_settings, dialect_override, query_statements = extract_inline_settings(statements)
        
        # Merge settings: inline overrides base
        final_settings = base_settings.merge_with(inline_settings)
        
        # Use dialect from SET statement if provided and no explicit dialect
        if dialect_override and not dialect:
            dialect = dialect_override
        
        if not query_statements:
            raise ASQLSyntaxError("No valid queries found (only SET statements)")
        
        # Generate SQL for each query statement
        sql_dialect = Dialect.get_or_raise(dialect) if dialect else None
        sql_parts = []
        
        for stmt in query_statements:
            # TODO: Apply settings-based transformations here (e.g., auto_spine)
            # For now, just generate SQL
            sql = stmt.sql(dialect=sql_dialect, pretty=pretty)
            sql_parts.append(sql)
        
        return ";\n\n".join(sql_parts)
        
    except ASQLSyntaxError:
        raise
    except sqlglot.errors.ParseError as e:
        raise ASQLSyntaxError(f"ASQL syntax error: {e}") from e
    except Exception as e:
        raise ASQLCompilationError(f"Compilation error: {e}") from e


def _compile_single_query(
    asql_query: str,
    dialect: Optional[str] = None,
    pretty: bool = False,
    settings: Optional[CompileSettings] = None,
) -> str:
    """
    Compile a single ASQL query to SQL.
    
    This implements the three-stage pipeline for a single query:
    1. Pre-parse ASQL to SQL-like syntax
    2. Parse with SQLGlot
    3. Generate target SQL
    
    Note: This is a legacy function. The main compile() function now handles
    settings extraction and multi-statement parsing more efficiently.
    
    Args:
        asql_query: Single ASQL query string
        dialect: Target SQL dialect
        pretty: Whether to format SQL output
        settings: Compilation settings (currently unused, for future features)
        
    Returns:
        SQL query string
    """
    # Stage 1: Pre-parse ASQL to SQL-like syntax
    sql_like = preparse_asql(asql_query)
    
    # Stage 2: Parse with SQLGlot
    # We use the default dialect for parsing since pre-parser has already
    # transformed ASQL-specific syntax to SQL-like syntax
    try:
        ast = sqlglot.parse_one(sql_like, dialect=dialect)
    except sqlglot.errors.ParseError as e:
        # Try to provide a more helpful error message
        raise ASQLSyntaxError(
            f"Failed to parse ASQL query.\n"
            f"Original: {asql_query}\n"
            f"Pre-parsed: {sql_like}\n"
            f"Error: {e}"
        ) from e
    
    # Stage 3: Generate target SQL
    sql_dialect = Dialect.get_or_raise(dialect) if dialect else None
    sql = ast.sql(dialect=sql_dialect, pretty=pretty)
    
    return sql


def compile_to_ast(asql_query: str) -> exp.Expression:
    """
    Compile ASQL query to SQLGlot AST (without generating SQL).
    
    This is useful for programmatic manipulation of the parsed query.
    
    Args:
        asql_query: ASQL query string
        
    Returns:
        SQLGlot expression tree
        
    Raises:
        ASQLSyntaxError: If ASQL syntax is invalid
        ASQLCompilationError: If compilation fails
    """
    try:
        if not asql_query.strip():
            raise ASQLSyntaxError("Empty ASQL query")
        
        # Pre-parse ASQL to SQL-like syntax
        sql_like = preparse_asql(asql_query)
        
        # Parse with SQLGlot
        ast = sqlglot.parse_one(sql_like)
        
        return ast
        
    except ASQLSyntaxError:
        raise
    except sqlglot.errors.ParseError as e:
        raise ASQLSyntaxError(f"ASQL syntax error: {e}") from e
    except Exception as e:
        raise ASQLCompilationError(f"Compilation error: {e}") from e


def get_preparsed(asql_query: str) -> str:
    """
    Get the pre-parsed SQL-like representation of an ASQL query.
    
    This is useful for debugging and understanding how ASQL syntax
    is transformed before SQLGlot parsing.
    
    Args:
        asql_query: ASQL query string
        
    Returns:
        SQL-like string (intermediate representation)
    """
    return preparse_asql(asql_query)


def get_settings_from_query(
    asql_query: str,
    base_settings: Optional[CompileSettings] = None,
) -> Tuple[CompileSettings, Optional[str]]:
    """
    Extract settings from a query's inline SET statements.
    
    Useful for tooling that needs to know what settings a query uses
    without fully compiling it.
    
    Args:
        asql_query: ASQL query string
        base_settings: Base settings to merge with (uses defaults if None)
        
    Returns:
        Tuple of (merged_settings, dialect_override)
        - merged_settings: CompileSettings with inline settings applied
        - dialect_override: dialect from SET statement, or None
    
    Example:
        >>> settings, dialect = get_settings_from_query('''
        ...     SET auto_spine = true;
        ...     SET dialect = 'postgres';
        ...     from orders ...
        ... ''')
        >>> settings.auto_spine
        True
        >>> dialect
        'postgres'
    """
    base = base_settings or CompileSettings()
    
    try:
        preparsed = preparse_asql(asql_query)
        statements = sqlglot.parse(preparsed)
        inline_settings, dialect_override, _ = extract_inline_settings(statements)
        merged = base.merge_with(inline_settings)
        return merged, dialect_override
    except Exception:
        # If parsing fails, return base settings unchanged
        return base, None
