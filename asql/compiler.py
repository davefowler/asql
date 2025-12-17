"""ASQL compiler - transforms ASQL to SQL.

This module implements the ASQL compilation pipeline:
1. Pre-parse: Transform ASQL structural syntax to SQL-like syntax
2. Parse: Use SQLGlot with ASQL dialect to parse the SQL-like syntax
3. Generate: Output SQL in the target dialect

The pre-parser handles ASQL-specific structural transformations that fundamentally
differ from SQL (FROM-first, pipeline operators, aggregate blocks, etc.).

The ASQL dialect handles expression-level ASQL syntax that fits within SQLGlot's
extension model (custom tokens, function parsers, etc.).
"""

from typing import Optional
import sqlglot
from sqlglot import exp
from sqlglot.dialects import Dialect
import re

from asql.errors import ASQLCompilationError, ASQLSyntaxError
from asql.preparser import preparse_asql, ASQLPreParser
from asql.dialect import register_asql_dialect

# Ensure ASQL dialect is registered
register_asql_dialect()


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
) -> str:
    """
    Compile ASQL query to SQL.
    
    This is the main compilation function that implements the three-stage pipeline:
    1. Pre-parse: Transform ASQL to SQL-like syntax
    2. Parse: Use SQLGlot to parse the SQL-like syntax
    3. Generate: Output SQL in the target dialect
    
    Args:
        asql_query: ASQL query string (can contain multiple queries separated by semicolons)
        dialect: Target SQL dialect (e.g., 'postgres', 'mysql', 'bigquery', 'snowflake')
                 If None, will try to extract from -- dialect: comment in query
        pretty: Whether to format SQL output
    
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
    """
    try:
        if not asql_query.strip():
            raise ASQLSyntaxError("Empty ASQL query")
        
        # Extract dialect from comment if not provided
        if not dialect:
            dialect = _extract_dialect_from_comment(asql_query)
        
        # Split by semicolons to handle multiple queries
        query_parts = [q.strip() for q in asql_query.split(';') if q.strip()]
        
        if not query_parts:
            raise ASQLSyntaxError("No valid queries found")
        
        # If only one query, handle it normally
        if len(query_parts) == 1:
            return _compile_single_query(query_parts[0], dialect, pretty)
        
        # Multiple queries: compile each and combine
        sql_parts = []
        for query_part in query_parts:
            sql_parts.append(_compile_single_query(query_part, dialect, pretty))
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
) -> str:
    """
    Compile a single ASQL query to SQL.
    
    This implements the three-stage pipeline for a single query:
    1. Pre-parse ASQL to SQL-like syntax
    2. Parse with SQLGlot
    3. Generate target SQL
    
    Args:
        asql_query: Single ASQL query string
        dialect: Target SQL dialect
        pretty: Whether to format SQL output
        
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
