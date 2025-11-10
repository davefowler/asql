"""ASQL compiler - transforms ASQL to SQL."""

from typing import Optional
import sqlglot
from sqlglot import exp
from sqlglot.dialects import Dialect

from asql.errors import ASQLCompilationError, ASQLSyntaxError
from asql.parser import ASQLParser


def compile(
    asql_query: str,
    dialect: Optional[str] = None,
    pretty: bool = False,
) -> str:
    """
    Compile ASQL query to SQL.
    
    Args:
        asql_query: ASQL query string
        dialect: Target SQL dialect (e.g., 'postgres', 'mysql', 'bigquery')
        pretty: Whether to format SQL output
    
    Returns:
        SQL query string
    
    Raises:
        ASQLSyntaxError: If ASQL syntax is invalid
        ASQLCompilationError: If compilation fails
    """
    try:
        if not asql_query.strip():
            raise ASQLSyntaxError("Empty ASQL query")
        
        # Parse ASQL to SQLGlot AST
        parser = ASQLParser(asql_query)
        select_expr = parser.parse()
        
        # Generate SQL
        sql_dialect = Dialect.get_or_raise(dialect) if dialect else None
        sql = select_expr.sql(dialect=sql_dialect, pretty=pretty)
        
        return sql
        
    except ASQLSyntaxError:
        raise
    except sqlglot.errors.ParseError as e:
        raise ASQLSyntaxError(f"ASQL syntax error: {e}") from e
    except Exception as e:
        raise ASQLCompilationError(f"Compilation error: {e}") from e

